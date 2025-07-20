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
from typing import Dict, List
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import tempfile
from collections import defaultdict
from dataclasses import dataclass
import time

CACHE_TTL = 45  # секунд
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

router = Router(name="upload")

# ────────────────────────────────────────── helpers


async def send_error(msg: Message, text: str) -> None:
    await msg.reply(f"❌ {text}\nПопробуем ещё раз? 🙂")


def _build_duplicate_kb(link: str, manual_cb: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔗 Открыть существующий", url=link))
    kb.row(InlineKeyboardButton(text="📂 Выбрать папку вручную", callback_data=manual_cb))
    return kb.as_markup()


def escape_markdown(text: str) -> str:
    for ch in r'_[]()~`>#+-=|{}.!':
        text = text.replace(ch, f'\\{ch}')
    return text


def build_batch_summary(batch: list[FileInfo]) -> tuple[str, InlineKeyboardMarkup]:
    lines = [f"<b>📋 Найдено {len(batch)} файлов:</b>", "<pre>№  Было ➜ Станет</pre>"]
    problem_idx = []
    for idx, fi in enumerate(batch, start=1):
        if fi.guessed:
            new_name = f"{fi.guessed.principal}_{fi.guessed.agent or ''}_{fi.guessed.doctype}_{fi.guessed.number}_{fi.guessed.date}.{fi.guessed.ext}"
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
    await call.message.edit_text("❌ Загрузка отменена.")
    await call.answer()

@router.callback_query(F.data == "bulk_upload")
async def cb_upload(call: CallbackQuery):
    uid = call.from_user.id
    batch = user_batches.pop(uid, [])
    total = len(batch)
    msg = call.message
    await msg.edit_text("🚀 Загружаю, секунду…")
    # TODO: upload to Drive
    for i, fi in enumerate(batch, 1):
        await asyncio.sleep(0.1)  # mock I/O
        await msg.edit_text(f"🚀 Загружаю: {i}/{total} файлов…")
    await msg.edit_text(f"✅ Готово! Загружено {total} файлов.")
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
    await call.message.edit_text(f"✏️ Давайте исправим имя для файла: <b>{batch[idx].orig_name}</b>\n\nВведите принципала:", parse_mode="HTML")
    await state.set_state(FilenameWizard.principal)
    await call.answer()

@router.message(FilenameWizard.principal)
async def wizard_principal(msg: Message, state: FSMContext):
    data = await state.get_data()
    batch = data["batch"]
    idx = data["fix_idx"]
    batch[idx].guessed = FilenameInfo(
        principal=msg.text.strip(),
        agent=None, doctype=None, number=None, date=None, ext=batch[idx].orig_name.split(".")[-1]
    )
    await state.update_data(batch=batch)
    await msg.answer("Введите агента:")
    await state.set_state(FilenameWizard.agent)

@router.message(FilenameWizard.agent)
async def wizard_agent(msg: Message, state: FSMContext):
    data = await state.get_data()
    batch = data["batch"]
    idx = data["fix_idx"]
    batch[idx].guessed.agent = msg.text.strip()
    await state.update_data(batch=batch)
    await msg.answer("Введите тип документа:")
    await state.set_state(FilenameWizard.doctype)

@router.message(FilenameWizard.doctype)
async def wizard_doctype(msg: Message, state: FSMContext):
    data = await state.get_data()
    batch = data["batch"]
    idx = data["fix_idx"]
    batch[idx].guessed.doctype = msg.text.strip()
    await state.update_data(batch=batch)
    await msg.answer("Введите номер:")
    await state.set_state(FilenameWizard.number)

@router.message(FilenameWizard.number)
async def wizard_number(msg: Message, state: FSMContext):
    data = await state.get_data()
    batch = data["batch"]
    idx = data["fix_idx"]
    batch[idx].guessed.number = msg.text.strip()
    await state.update_data(batch=batch)
    await msg.answer("Введите дату (ГГГГММДД):")
    await state.set_state(FilenameWizard.date)

@router.message(FilenameWizard.date)
async def wizard_date(msg: Message, state: FSMContext):
    data = await state.get_data()
    batch = data["batch"]
    idx = data["fix_idx"]
    batch[idx].guessed.date = msg.text.strip()
    await state.update_data(batch=batch)
    # Проверяем, есть ли ещё проблемные файлы
    next_idx = next((i for i, fi in enumerate(batch) if not fi.guessed), None)
    if next_idx is not None:
        await state.update_data(fix_idx=next_idx)
        await msg.answer(f"✏️ Следующий файл: <b>{batch[next_idx].orig_name}</b>\n\nВведите принципала:", parse_mode="HTML")
        await state.set_state(FilenameWizard.principal)
    else:
        # Все исправлены — показать сводку
        await state.clear()
        user_batches[msg.from_user.id] = batch
        text, markup = build_batch_summary(batch)
        await msg.answer("Все имена исправлены!\n\n" + text, reply_markup=markup, parse_mode="HTML")


# ────────────────────────────────────────── main handler


@router.message(F.document)
async def handle_upload(msg: Message):
    doc = msg.document
    if not doc or not doc.file_name:
        await send_error(msg, "Файл не найден или не содержит имени.")
        return
    user_id = msg.from_user.id
    # --- Redis batch buffer ---
    import tempfile, os
    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{doc.file_name}") as tmp:
        await msg.bot.download(doc.file_id, destination=tmp.name)
        guessed = await try_guess_filename(tmp.name, doc.file_name)
    os.unlink(tmp.name)
    status = 'ok' if guessed else 'need_wizard'
    fi = FileInfo(doc.file_id, doc.file_name, guessed, status)
    await add_file(user_id, fi)
    size = await get_size(user_id)
    if size == 1:
        import asyncio
        async def batch_timer():
            await asyncio.sleep(CACHE_TTL)
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
    await msg.reply(f"👌 Файл принят! Можно присылать ещё (до {VALID_BATCH_LIMIT} файлов за {CACHE_TTL} сек)")


# ────────────────────────────────────────── коллбек «ручная папка»


@router.callback_query(F.data.startswith("manual:"))
async def manual_folder(cb: CallbackQuery) -> None:
    file_id = cb.data.split(":", 1)[1]
    await cb.message.answer("Скоро появится выбор папки 😉")
    # TODO: реализовать инлайн-меню навигации по папкам
    await cb.answer()


class FilenameWizard(StatesGroup):
    principal = State()
    agent = State()
    doctype = State()
    number = State()
    date = State()
    confirm = State()

class BulkFixForm(StatesGroup):
    waiting_for_file_index = State()
    waiting_for_new_name = State()

@router.callback_query(F.data == "bulk_fix")
async def start_bulk_fix(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    batch = await get_batch(uid)
    if not batch:
        await cb.message.answer("Нет файлов для исправления.")
        return
    # Показываем список файлов с номерами
    text = "Выберите номер файла для исправления:\n"
    for i, fi in enumerate(batch, 1):
        text += f"{i}. {fi.orig_name}\n"
    await state.update_data(batch=batch)
    await cb.message.answer(text)
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
        text = await loop.run_in_executor(None, run_ocr, file_path)
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
