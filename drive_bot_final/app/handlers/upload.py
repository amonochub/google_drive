from __future__ import annotations

import asyncio
from aiogram import Router, F
from aiogram.types import (
    Message,
    FSInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from pathlib import Path
from typing import Dict, List, Optional
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import tempfile
from collections import defaultdict
from dataclasses import dataclass
import time
from datetime import datetime
import os
import structlog
log = structlog.get_logger(__name__)

router = Router(name="upload")

class FilenameWizard(StatesGroup):
    principal = State()
    agent = State()
    doctype = State()
    number = State()
    date = State()
    confirm = State()


# Удаляю локальную переменную CACHE_TTL, теперь используется settings.cache_ttl
VALID_BATCH_LIMIT = 15
user_batches = defaultdict(list)  # user_id -> [FileInfo]
user_batch_tasks = {}  # user_id -> asyncio.Task

@dataclass
class FileInfo:
    file_id: str
    orig_name: str
    guessed: FilenameInfo | None
    status: str  # 'ok' | 'need_wizard'


from app.utils.filename_parser import parse_filename, FilenameInfo
from app.services import gdrive_handler
from app.config import settings
from app.services.drive import upload_file
from app.services.ocr import run_ocr
from app.services.analyzer import extract_parameters
from app.utils.buffers import add_file, get_batch, flush_batch, get_size, set_ttl
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from app.services.drive import ensure_folders
from app.services.autocomplete_service import AutocompleteService
from app.utils.telegram_utils import escape_markdown
from app.utils.file_validation import validate_file, FileValidationError

@dataclass
class UploadResult:
    orig_name: str
    file_id: Optional[str]
    drive_link: Optional[str]
    status: str  # 'success' | 'failed' | 'manual'
    error: Optional[str] = None

# --- Получение подпапок Google Drive ---
async def list_drive_folders(parent_id: str):
    from app.services.drive import drive, run_sync, FOLDER_MIME
    q = f"'{parent_id}' in parents and mimeType = '{FOLDER_MIME}' and trashed = false"
    res = await run_sync(drive.files().list(q=q, spaces="drive", fields="files(id,name)").execute)
    return res.get("files", [])

# --- Генерация инлайн-меню для выбора папки ---
def build_folder_keyboard(folders, current_id, path):
    kb = InlineKeyboardBuilder()
    for f in folders:
        kb.button(text=f["name"], callback_data=f"choose_folder:{f['id']}:{'|'.join(path+[f['name']])}")
    if len(path) > 1:
        kb.button(text="⬅️ Назад", callback_data=f"choose_folder_back:{current_id}:{'|'.join(path[:-1])}")
    kb.button(text="➕ Создать новую папку", callback_data=f"create_folder:{current_id}:{'|'.join(path)}")
    kb.button(text="✅ Выбрать эту папку", callback_data=f"choose_folder_select:{current_id}:{'|'.join(path)}")
    return kb.as_markup()

# --- Callback-обработчик для дерева папок ---
@router.callback_query(F.data.startswith("choose_folder"))
async def choose_folder_callback(cb: CallbackQuery, state: FSMContext):
    data = cb.data.split(":", 2)
    action = data[0]
    folder_id = data[1]
    path = data[2].split("|") if len(data) > 2 else []
    if action == "choose_folder":
        folders = await list_drive_folders(folder_id)
        kb = build_folder_keyboard(folders, folder_id, path)
        breadcrumb = " / ".join(path)
        await cb.message.edit_text(f"📂 <b>Выберите папку</b>\nТекущий путь: <code>{breadcrumb}</code>", parse_mode="HTML", reply_markup=kb)
    elif action == "choose_folder_back":
        # Вернуться на уровень выше
        parent_path = path[:-1]
        parent_id = settings.gdrive_root_folder if not parent_path else await ensure_folders(parent_path)
        folders = await list_drive_folders(parent_id)
        kb = build_folder_keyboard(folders, parent_id, parent_path)
        breadcrumb = " / ".join(parent_path)
        await cb.message.edit_text(f"📂 <b>Выберите папку</b>\nТекущий путь: <code>{breadcrumb}</code>", parse_mode="HTML", reply_markup=kb)
    elif action == "choose_folder_select":
        # Сохраняем выбранную папку в state и ждём загрузки файла
        await state.update_data(selected_folder_id=folder_id, selected_folder_path=path)
        await cb.message.edit_text(f"✅ Папка выбрана: <code>{' / '.join(path)}</code>\nТеперь отправьте файл для загрузки.", parse_mode="HTML")
    await cb.answer()

@router.callback_query(F.data.startswith("create_folder"))
async def create_folder_callback(cb: CallbackQuery, state: FSMContext):
    data = cb.data.split(":", 2)
    parent_id = data[1]
    path = data[2].split("|") if len(data) > 2 else []
    await state.update_data(create_folder_parent_id=parent_id, create_folder_path=path)
    await cb.message.edit_text(f"Введите имя новой папки в <code>{' / '.join(path)}</code>:", parse_mode="HTML")
    await state.set_state("waiting_for_new_folder_name")
    await cb.answer()

@router.message()
async def handle_new_folder_name(msg: Message, state: FSMContext):
    data = await state.get_data()
    if state and data.get("create_folder_parent_id") and state.state == "waiting_for_new_folder_name":
        from app.services.drive import drive, run_sync
        parent_id = data["create_folder_parent_id"]
        folder_name = msg.text.strip()
        body = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
        res = await run_sync(drive.files().create(body=body, fields="id").execute)
        new_folder_id = res["id"]
        # После создания — сразу открываем новую папку в меню выбора
        path = data["create_folder_path"] + [folder_name]
        folders = await list_drive_folders(new_folder_id)
        kb = build_folder_keyboard(folders, new_folder_id, path)
        await msg.answer(f"Папка <b>{folder_name}</b> создана и выбрана!", parse_mode="HTML", reply_markup=kb)
        await state.clear()

# --- Загрузка файла в выбранную вручную папку ---
@router.message(F.document)
async def handle_manual_upload(msg: Message, state: FSMContext):
    data = await state.get_data()
    if data and data.get("selected_folder_id"):
        doc = msg.document
        import tempfile, os, pathlib
        file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{doc.file_name if doc.file_name else ''}") as tmp:
                file_path = tmp.name
                await msg.bot.download(doc.file_id, destination=tmp.name)
            from app.services.drive import drive, run_sync
            filename = pathlib.Path(file_path).name
            media_body = None
            with open(file_path, "rb") as f:
                import io
                from googleapiclient.http import MediaIoBaseUpload
                media_body = MediaIoBaseUpload(f, mimetype="application/octet-stream", resumable=True)
                body = {"name": filename, "parents": [data["selected_folder_id"]]}
                res = await run_sync(drive.files().create(body=body, media_body=media_body, fields="id").execute)
                file_id = res["id"]
            drive_link = f"https://drive.google.com/file/d/{file_id}/view"
            await msg.answer(f"✅ Файл <b>{filename}</b> загружен! <a href=\"{drive_link}\">Открыть</a>", parse_mode="HTML", disable_web_page_preview=True)
        finally:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
        await state.clear()
        # Возвращаем пользователя к стартовому меню
        await msg.answer("Главное меню:", reply_markup=None)

# ────────────────────────────────────────── helpers


async def send_error(msg: Message, text: str) -> None:
    await msg.reply(f"❌ {text}\nПопробуем ещё раз? 🙂")


def _build_duplicate_kb(link: str, manual_cb: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔗 Открыть существующий", url=link))
    kb.row(InlineKeyboardButton(text="📂 Выбрать папку вручную", callback_data=manual_cb))
    return kb.as_markup()


# --- Исправление форматирования для HTML/Markdown ---
def escape_html(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# Используйте escape_html/escape_markdown для всех сообщений, где есть пользовательский ввод или ссылки.


def build_batch_summary(batch: list[FileInfo]) -> tuple[str, InlineKeyboardMarkup]:
    lines = [f"<b>📋 Найдено {len(batch)} файлов:</b>", "<pre>№  Было ➜ Станет</pre>"]
    problem_idx = []
    for idx, fi in enumerate(batch, start=1):
        ext = fi.orig_name.split('.')[-1] if fi.orig_name and '.' in fi.orig_name else ''
        if fi.guessed:
            new_name = f"{fi.guessed.principal}_{fi.guessed.agent or ''}_{fi.guessed.doctype}_{fi.guessed.number}_{fi.guessed.date}.{ext}"
            lines.append(f"<pre>{idx:2} {fi.orig_name} ➜ {new_name}</pre>")
        else:
            lines.append(f"<pre>{idx:2} {fi.orig_name} ➜ ⚠️ не распознано</pre>")
            problem_idx.append(idx)
    kb = InlineKeyboardBuilder()
    kb.button(text=f"✅ Загрузить {len(batch) - len(problem_idx)} файлов", callback_data="bulk_upload")
    if problem_idx:
        kb.button(text="✏️ Исправить", callback_data="fix")
    kb.button(text="⏹ Отмена", callback_data="cancel")
    kb.adjust(1)
    return "\n".join(lines), kb.as_markup()

async def flush_and_ask(user_id: int, bot):
    batch = user_batches.pop(user_id, [])
    if not batch:
        return
    text, markup = build_batch_summary(batch)
    await bot.send_message(user_id, text, reply_markup=markup, parse_mode="HTML")

# --- CALLBACK HANDLERS ---
@router.callback_query(F.data == "cancel")
async def cb_cancel(call: CallbackQuery):
    user_batches.pop(call.from_user.id, None)
    # Проверка call и call.message перед edit_text
    if call is not None and hasattr(call, 'message') and hasattr(call.message, 'edit_text'):
        await call.message.edit_text("❌ Загрузка отменена.")
    await call.answer()

@router.callback_query(F.data == "bulk_upload")
async def cb_upload(call: CallbackQuery, state: FSMContext = None):
    from app.services.drive import upload_file, ensure_folders
    import tempfile, os, pathlib, asyncio
    uid = call.from_user.id
    batch: List[FileInfo] = user_batches.pop(uid, [])
    total = len(batch)
    msg = call.message
    if msg is not None:
        await msg.edit_text("🚀 Начинаю загрузку файлов в Google Drive...")
    results: List[UploadResult] = []
    manual_files = []
    semaphore = asyncio.Semaphore(3)
    progress_msgs = [None] * total

    async def upload_one(i: int, fi: FileInfo):
        file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{fi.orig_name}") as tmp:
                file_path = tmp.name
                await msg.bot.download(fi.file_id, destination=tmp.name)
            try:
                validate_file(fi.orig_name, os.path.getsize(file_path))
            except FileValidationError as e:
                results.append(UploadResult(orig_name=fi.orig_name, file_id=None, drive_link=None, status="failed", error=str(e)))
                if msg is not None:
                    await msg.answer(f"❌ Файл <b>{fi.orig_name}</b> не принят: {e}", parse_mode="HTML")
                return
            # Определяем путь для загрузки (например, по имени файла)
            path_parts = fi.orig_name.rsplit('.', 1)[0].split('_')[:-1]  # пример: все части кроме даты и расширения
            if not path_parts:
                manual_files.append((fi, file_path))
                results.append(UploadResult(orig_name=fi.orig_name, file_id=None, drive_link=None, status="manual"))
                if msg is not None:
                    await msg.edit_text(f"⚠️ Не удалось определить папку для <b>{fi.orig_name}</b>. Выберите вручную после загрузки остальных.", parse_mode="HTML")
                return
            async with semaphore:
                try:
                    progress_msgs[i] = await msg.answer(f"⏳ {i+1}/{total} — <b>{fi.orig_name}</b>: загружаю...", parse_mode="HTML")
                    folder_id = await ensure_folders(path_parts)
                    file_id = await upload_file(pathlib.Path(file_path), path_parts)
                    drive_link = f"https://drive.google.com/file/d/{file_id}/view"
                    results.append(UploadResult(orig_name=fi.orig_name, file_id=file_id, drive_link=drive_link, status="success"))
                    await progress_msgs[i].edit_text(f"✅ {i+1}/{total} — <b>{fi.orig_name}</b>: загружено!", parse_mode="HTML")
                except Exception as e:
                    results.append(UploadResult(orig_name=fi.orig_name, file_id=None, drive_link=None, status="failed", error=str(e)))
                    await progress_msgs[i].edit_text(f"❌ {i+1}/{total} — <b>{fi.orig_name}</b>: ошибка: {e}", parse_mode="HTML")
        finally:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)

    tasks = [upload_one(i, fi) for i, fi in enumerate(batch)]
    await asyncio.gather(*tasks)

    # Формируем итоговое сообщение
    links_text = ""
    for i, res in enumerate(results):
        if res.status == "success":
            links_text += f"<b>{i+1}.</b> <b>{res.orig_name}</b>: <a href=\"{res.drive_link}\">Открыть</a>\n"
    fail_text = ""
    failed = [r for r in results if r.status == "failed"]
    if failed:
        fail_text = "\n\n❌ Не удалось загрузить:\n" + "\n".join([f"<b>{r.orig_name}</b>: {r.error}" for r in failed])
    folder_link = f"https://drive.google.com/drive/folders/{settings.gdrive_root_folder}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📂 Открыть папку в Google Drive", url=folder_link)]])
    final_text = f"<b>Загрузка завершена!</b>\n\n{links_text}{fail_text}"
    if msg is not None:
        await msg.answer(final_text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    # Fallback: если есть файлы с нераспознанным путём — предлагаем выбрать папку вручную
    if manual_files and msg is not None:
        for fi, file_path in manual_files:
            await msg.answer(f"⚠️ Для файла <b>{fi.orig_name}</b> не удалось определить папку. Пожалуйста, выберите папку вручную:", parse_mode="HTML")
            folders = await list_drive_folders(settings.gdrive_root_folder)
            kb = build_folder_keyboard(folders, settings.gdrive_root_folder, ["Корень"])
            await msg.answer("📂 <b>Выберите папку для загрузки:</b>", parse_mode="HTML", reply_markup=kb)
    await call.answer()

# --- FSM wizard для исправления проблемных файлов ---
@router.callback_query(F.data == "fix")
async def cb_fix(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    batch = user_batches.get(uid, [])
    # Найти первый проблемный файл
    idx = next((i for i, fi in enumerate(batch) if not fi.guessed), None)
    if idx is None:
        await call.answer("Нет проблемных файлов!", show_alert=True)
        return
    await state.update_data(batch=batch, fix_idx=idx)
    # Проверка call и call.message перед edit_text
    if call is not None and hasattr(call, 'message') and hasattr(call.message, 'edit_text'):
        await call.message.edit_text(f"✏️ Давайте исправим имя для файла: <b>{batch[idx].orig_name}</b>\n\nВведите принципала:", parse_mode="HTML")
    await state.set_state(FilenameWizard.principal)
    await call.answer()

# --- Мультиязычная функция ---
def t(key: str, lang: str = 'ru') -> str:
    # Простейший словарь, можно расширять
    texts = {
        'ru': {
            'enter_principal': 'Введите принципала (организацию):',
            'enter_agent': 'Введите агента (контрагента):',
            'enter_doctype': 'Введите тип документа:',
            'enter_number': 'Введите номер документа:',
            'enter_date': 'Введите дату (ГГГГММДД):',
            'progress': '⏳ Заполняем {step}/{total} шагов...'
        },
        'en': {
            'enter_principal': 'Enter principal (organization):',
            'enter_agent': 'Enter agent (counterparty):',
            'enter_doctype': 'Enter document type:',
            'enter_number': 'Enter document number:',
            'enter_date': 'Enter date (YYYYMMDD):',
            'progress': '⏳ Step {step} of {total}...'
        }
    }
    return texts.get(lang, texts['ru']).get(key, key)

@router.message(FilenameWizard.principal)
async def wizard_principal(msg: Message, state: FSMContext):
    data = await state.get_data()
    batch = data["batch"]
    idx = data["fix_idx"]
    total = len(batch)
    step = 1
    lang = 'ru'  # TODO: определять язык пользователя
    if batch is None or idx is None or batch[idx] is None or not hasattr(batch[idx], 'orig_name') or batch[idx].orig_name is None:
        await send_error(msg, "Некорректные данные файла. Попробуйте ещё раз.")
        return
    principal = msg.text.strip() if msg is not None and msg.text and isinstance(msg.text, str) else ""
    orig_name = batch[idx].orig_name if batch[idx] and hasattr(batch[idx], 'orig_name') and batch[idx].orig_name else ""
    ext = orig_name.split(".")[-1] if orig_name else ""
    batch[idx].guessed = FilenameInfo(
        principal=principal,
        agent="",
        doctype="",
        number="",
        date="",
        gdrive_folder=""
    )
    await state.update_data(batch=batch)
    await msg.answer(f"{t('progress', lang).format(step=step, total=5)}\n{t('enter_agent', lang)}")
    await state.set_state(FilenameWizard.agent)

@router.message(FilenameWizard.agent)
async def wizard_agent(msg: Message, state: FSMContext):
    data = await state.get_data()
    batch = data["batch"]
    idx = data["fix_idx"]
    total = len(batch)
    step = 2
    lang = 'ru'
    if batch is None or idx is None or batch[idx] is None:
        await send_error(msg, "Ошибка при обработке файла. Попробуйте ещё раз.")
        return
    if batch[idx].guessed is None:
        await send_error(msg, "Ошибка при разборе имени файла. Попробуйте ещё раз.")
        return
    batch[idx].guessed.agent = msg.text.strip() if msg is not None and msg.text and isinstance(msg.text, str) else ""
    await state.update_data(batch=batch)
    await msg.answer(f"{t('progress', lang).format(step=step, total=5)}\n{t('enter_doctype', lang)}")
    await state.set_state(FilenameWizard.doctype)

@router.message(FilenameWizard.doctype)
async def wizard_doctype(msg: Message, state: FSMContext):
    data = await state.get_data()
    batch = data["batch"]
    idx = data["fix_idx"]
    total = len(batch)
    step = 3
    lang = 'ru'
    if batch is None or idx is None or batch[idx] is None:
        await send_error(msg, "Ошибка при обработке файла. Попробуйте ещё раз.")
        return
    batch[idx].guessed.doctype = msg.text.strip() if msg is not None and msg.text and isinstance(msg.text, str) else ""
    await state.update_data(batch=batch)
    await msg.answer(f"{t('progress', lang).format(step=step, total=5)}\n{t('enter_number', lang)}")
    await state.set_state(FilenameWizard.number)

@router.message(FilenameWizard.number)
async def wizard_number(msg: Message, state: FSMContext):
    data = await state.get_data()
    batch = data["batch"]
    idx = data["fix_idx"]
    total = len(batch)
    step = 4
    lang = 'ru'
    if batch is None or idx is None or batch[idx] is None:
        await send_error(msg, "Ошибка при обработке файла. Попробуйте ещё раз.")
        return
    batch[idx].guessed.number = msg.text.strip() if msg is not None and msg.text and isinstance(msg.text, str) else ""
    await state.update_data(batch=batch)
    await msg.answer(f"{t('progress', lang).format(step=step, total=5)}\n{t('enter_date', lang)}")
    await state.set_state(FilenameWizard.date)

@router.message(FilenameWizard.date)
async def wizard_date(msg: Message, state: FSMContext):
    data = await state.get_data()
    batch = data["batch"]
    idx = data["fix_idx"]
    total = len(batch)
    step = 5
    lang = 'ru'
    if batch is None or idx is None or batch[idx] is None:
        await send_error(msg, "Ошибка при обработке файла. Попробуйте ещё раз.")
        return
    batch[idx].guessed.date = msg.text.strip() if msg is not None and msg.text and isinstance(msg.text, str) else ""
    await state.update_data(batch=batch)
    # Предпросмотр результата
    preview = batch[idx].guessed
    ext = batch[idx].orig_name.split('.')[-1] if batch[idx].orig_name and '.' in batch[idx].orig_name else ''
    preview_text = f"<b>Предпросмотр имени файла:</b>\n<pre>{preview.principal}_{preview.agent}_{preview.doctype}_{preview.number}_{preview.date}.{ext}</pre>"
    await msg.answer(f"{t('progress', lang).format(step=step, total=5)}\n{preview_text}")
    # Проверяем, есть ли ещё проблемные файлы
    next_idx = next((i for i, fi in enumerate(batch) if not fi.guessed), None)
    if next_idx is not None:
        await state.update_data(fix_idx=next_idx)
        await msg.answer(f"✏️ Следующий файл: <b>{batch[next_idx].orig_name}</b>\n\n{t('enter_principal', lang)}", parse_mode="HTML")
        await state.set_state(FilenameWizard.principal)
    else:
        await state.clear()
        user_batches[msg.from_user.id] = batch
        text, markup = build_batch_summary(batch)
        if msg is not None and hasattr(msg, 'answer'):
            await msg.answer("Все имена исправлены!\n\n" + text, reply_markup=markup, parse_mode="HTML")


# ────────────────────────────────────────── main handler


@router.message(F.document)
async def handle_upload(msg: Message):
    doc = msg.document
    if not doc or not hasattr(doc, 'file_name') or doc.file_name is None:
        await send_error(msg, "Файл не найден или не содержит имени.")
        return
    try:
        validate_file(doc.file_name, doc.file_size)
    except FileValidationError as e:
        await send_error(msg, f"Файл не принят: {e}")
        return
    user_id = msg.from_user.id
    # --- Redis batch buffer ---
    import tempfile, os
    # Проверка doc перед id
    if doc is None or not hasattr(doc, 'file_id') or doc.file_id is None:
        await send_error(msg, "Ошибка: отсутствует file_id у документа.")
        return
    # Проверка doc перед download
    if doc is not None and hasattr(msg.bot, 'download') and hasattr(doc, 'file_id') and doc.file_id:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{doc.file_name if doc.file_name else ''}") as tmp:
            await msg.bot.download(doc.file_id, destination=tmp.name)
            guessed = await try_guess_filename(tmp.name, doc.file_name or '')
        os.unlink(tmp.name)
    else:
        await send_error(msg, "Ошибка загрузки файла.")
        return
    status = 'ok' if guessed else 'need_wizard'
    fi = FileInfo(doc.file_id, doc.file_name, guessed, status)
    await add_file(user_id, fi)
    size = await get_size(user_id)
    if size == 1:
        import asyncio
        async def batch_timer():
            await asyncio.sleep(settings.cache_ttl)
            batch = await flush_batch(user_id)
            if not batch:
                return
            await send_batch_summary(msg, batch)
        asyncio.create_task(batch_timer())
    if size > VALID_BATCH_LIMIT:
        await msg.reply(
            f"⚠️ Вы загрузили более {VALID_BATCH_LIMIT} файлов за раз.\n"
            "Для больших партий используйте ZIP-архив или CSV-режим.\n"
            "Подробнее: /help"
        )
        await flush_batch(user_id)
        return
    # Проверка msg перед answer
    if msg is not None and hasattr(msg, 'answer'):
        await msg.answer(f"�� Файл принят! Можно присылать ещё (до {VALID_BATCH_LIMIT} файлов за {settings.cache_ttl} сек)")


# ────────────────────────────────────────── коллбек «ручная папка»


@router.callback_query(F.data.startswith("manual:"))
async def manual_folder(cb: CallbackQuery) -> None:
    file_id = cb.data.split(":", 1)[1]
    await cb.message.answer("Скоро появится выбор папки 😉")
    # TODO: реализовать инлайн-меню навигации по папкам
    await cb.answer()

class BulkFixForm(StatesGroup):
    waiting_for_file_index = State()
    waiting_for_new_name = State()

@router.callback_query(F.data == "bulk_fix")
async def start_bulk_fix(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    batch = await get_batch(uid)
    if not batch:
        # Проверка call и call.message перед edit_text
        if cb is not None and hasattr(cb, 'message') and hasattr(cb.message, 'edit_text'):
            await cb.message.edit_text("Нет файлов для исправления.")
        return
    # Показываем список файлов с номерами
    text = "Выберите номер файла для исправления:\n"
    for i, fi in enumerate(batch, 1):
        text += f"{i}. {fi.orig_name}\n"
    # Проверка cb и cb.message перед answer
    if cb is not None and hasattr(cb, 'message') and hasattr(cb.message, 'answer'):
        await cb.message.answer(text)
    await state.update_data(batch=batch)
    await state.set_state(BulkFixForm.waiting_for_file_index)
    await cb.answer()

@router.message(BulkFixForm.waiting_for_file_index)
async def bulk_fix_index(msg: Message, state: FSMContext):
    data = await state.get_data()
    batch = data["batch"]
    try:
        idx = int(msg.text.strip()) - 1
        assert 0 <= idx < len(batch)
    except Exception:
        await msg.answer("Некорректный номер. Попробуйте ещё раз.")
        return
    await state.update_data(fix_idx=idx)
    await msg.answer(f"Введите новое имя для файла: {batch[idx].orig_name}")
    await state.set_state(BulkFixForm.waiting_for_new_name)

@router.message(BulkFixForm.waiting_for_new_name)
async def bulk_fix_new_name(msg: Message, state: FSMContext):
    data = await state.get_data()
    batch = data["batch"]
    idx = data["fix_idx"]
    new_name = msg.text.strip()
    batch[idx].orig_name = new_name
    # Можно также обновить guessed, если нужно
    await state.update_data(batch=batch)
    await msg.answer(f"Имя файла обновлено! Если нужно исправить ещё — выберите номер, иначе /menu.")
    await state.set_state(BulkFixForm.waiting_for_file_index)

async def try_guess_filename(file_path: str, orig_name: str) -> FilenameInfo | None:
    # 1. Попытка парсинга имени
    info = parse_filename(orig_name or "")
    if info:
        return info
    # 2. OCR/docx/pdf анализ
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        text = await run_ocr(file_path)
    except Exception:
        text = ""
    params = extract_parameters(text)
    # Пробуем собрать поля
    principal = params.get("org", [None])[0]
    doctype = next((dt for dt in ["договор", "акт", "поручение"] if dt in (text or "").lower()), None)
    number = params.get("number", [None])[0]
    date = params.get("date", [None])[0]
    ext = ""
    if orig_name:
        ext = orig_name.split(".")[-1].lower()
    if principal and doctype and number and date and ext:
        return FilenameInfo(principal=principal, agent=None, doctype=doctype, number=number, date=date, ext=ext)
    return None

async def send_batch_summary(msg: Message, batch: list[FileInfo]):
    # Вместо прямой отправки — используем flush_and_ask
    await flush_and_ask(msg.from_user.id, msg.bot)

# --- Блокирующий handler для неожиданных сообщений ---
@router.message()
async def block_unexpected_messages(msg: Message, state: FSMContext):
    user_state = await state.get_state()
    if not user_state:
        try:
            await msg.delete()
        except Exception:
            pass
        return
    # Если пользователь в сценарии — остальные хендлеры сработают раньше

class BulkUploadStates(StatesGroup):
    waiting_template = State()
    waiting_files = State()
    processing = State()

@router.message(F.text.startswith("/массовая"))
async def start_bulk_upload(message: Message, state: FSMContext):
    parts = message.text.split()[1:]
    if len(parts) >= 3:
        company1 = parts[0]
        company2 = parts[1]
        doctype = parts[2]
        date = parts[3] if len(parts) > 3 else None
        template = {
            'company1': company1,
            'company2': company2,
            'doctype': doctype,
            'date': date
        }
        await state.update_data(template=template, file_count=0)
        await message.answer(
            f"📦 **Массовая загрузка настроена**\n\n"
            f"👥 **Компании:** {company1} ↔ {company2}\n"
            f"📋 **Тип:** {doctype}\n"
            f"📅 **Дата:** {date or 'автоматически'}\n\n"
            f"📁 **Теперь отправляй файлы:**\n"
            f"• По одному или архивом ZIP\n"
            f"• Номера будут назначены автоматически: 1, 2, 3...\n"
            f"• Для остановки: `/стоп`",
            parse_mode="Markdown"
        )
        await state.set_state(BulkUploadStates.waiting_files)
    else:
        await message.answer(
            "📦 **Массовая загрузка**\n\n"
            "**Формат команды:**\n"
            "`/массовая Компания1 Компания2 ТипДокумента [Дата]`\n\n"
            "**Примеры:**\n"
            "• `/массовая Демирекс Валиент Договор`\n"
            "• `/массовая Рексен Альфа Акт 20250721`\n\n"
            "*После этого просто отправляй файлы!*",
            parse_mode="Markdown"
        )

@router.message(BulkUploadStates.waiting_files, F.document)
async def process_bulk_file(message: Message, state: FSMContext):
    document = message.document
    try:
        validate_file(document.file_name, document.file_size)
    except FileValidationError as e:
        await message.answer(f"❌ Файл не принят: {e}")
        return
    data = await state.get_data()
    template = data['template']
    file_count = data.get('file_count', 0)
    autocomplete = AutocompleteService(settings.REDIS_DSN)
    await autocomplete.connect()
    # Проверяем, это ZIP архив или обычный файл
    if document.mime_type == 'application/zip':
        await message.answer("📦 ZIP-архивы поддерживаются, но обработка реализуется отдельно.")
        return
    file_count += 1
    next_number = await autocomplete.get_next_document_number(
        template['company1'],
        template['company2'],
        template['doctype']
    )
    date = template.get('date') or datetime.now().strftime("%Y%m%d")
    extension = os.path.splitext(document.file_name)[1]
    new_filename = f"{template['company1']}_{template['company2']}_{template['doctype']}_{next_number}_{date}{extension}"
    gdrive_path = f"{template['company1']}/{template['doctype']}/{date[:4]}"
    file_info = {
        'file_id': document.file_id,
        'original_name': document.file_name,
        'new_name': new_filename,
        'gdrive_path': gdrive_path,
        'size': document.file_size
    }
    files_list = data.get('files_list', [])
    files_list.append(file_info)
    await state.update_data(
        file_count=file_count,
        files_list=files_list
    )
    await message.answer(
        f"✅ **Файл #{file_count} добавлен**\n\n"
        f"📄 `{document.file_name}`\n"
        f"➡️ `{new_filename}`\n"
        f"📁 `{gdrive_path}`\n\n"
        f"Продолжай отправлять файлы или `/загрузить` для начала загрузки",
        parse_mode="Markdown"
    )
