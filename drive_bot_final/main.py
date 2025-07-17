import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from config import settings
from handlers.smart_document_handler import SmartDocumentHandler
from handlers.gdrive_handler import GDriveHandler
from utils.menu import main_menu, back_to_main_menu, document_type_menu
from aiogram.utils.chat_action import ChatActionSender
import mimetypes
from services.smart_document_processor import SmartDocumentProcessor
from services.ai_analyzer import analyze_document_info, check_bilingual_document_consistency, check_bilingual_document_consistency_llm
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import datetime
from utils.validators import validate_file_upload, validate_filename
from utils.rate_limiter import RateLimiter
from logging_config import setup_logging
from middleware.monitoring import MonitoringMiddleware
import io
import re
from typing import Dict, List, Any

setup_logging()

gdrive = GDriveHandler()
smart_handler = SmartDocumentHandler(gdrive)
smart_doc_processor = SmartDocumentProcessor()

# История последних 5 операций пользователя (в памяти)
user_history: Dict[int, List[str]] = {}

# Временное хранилище загруженных файлов (user_id -> {'file_name', 'file_bytes', 'mime_type'})
pending_files: Dict[int, Dict[str, Any]] = {}

user_folder_stack: Dict[int, List[str]] = {}  # user_id -> [folder_id, ...]

FOLDER_PAGE_SIZE = 5

GEMINI_DAILY_LIMIT = 20
# user_id -> {date: str, count: int}
gemini_usage_counter: Dict[int, Dict[str, int]] = {}

rate_limiter = RateLimiter(requests_per_minute=30)

def add_history(user_id, action, details):
    if not isinstance(user_id, int):
        return
    history = user_history.setdefault(user_id, [])
    history.append(f"{action}: {details}")
    if len(history) > 5:
        history.pop(0)

def get_history(user_id):
    if not isinstance(user_id, int):
        return []
    return user_history.get(user_id, [])

async def on_startup(bot: Bot):
    logging.info("Bot started!")

async def main():
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.message.middleware(MonitoringMiddleware())
    dp.callback_query.middleware(MonitoringMiddleware())

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        welcome_text = (
            "🥰 Привет-привет!\n\n"
            "Я твой помощник по документам!\n"
            "Чтобы я мог всё разложить по полочкам, пожалуйста, называй файлы вот так:\n"
            "<b>Принципал_Агент_тип_номер_дата.pdf</b>\n"
            "\n"
            "<b>Примеры:</b>\n"
            "Альфатрекс_Валиент_Договор_1234_01012023.pdf\n"
            "Альфатрекс_Агрико_Поручение_5678_02022023.pdf\n"
            "\n"
            "Если что-то не получается — не переживай, я всегда помогу! 💌\n"
            "Выбери, что будем делать дальше ⬇️"
        )
        await message.answer(welcome_text, reply_markup=main_menu(), parse_mode="HTML")

    @dp.callback_query(F.data == "menu_main")
    async def menu_main(call: types.CallbackQuery):
        if call.message:
            await call.message.answer("Главное меню:", reply_markup=main_menu())
        await call.answer()

    @dp.callback_query(F.data == "menu_browse")
    async def menu_browse(call: types.CallbackQuery):
        user_id = getattr(getattr(call, 'from_user', None), 'id', None)
        if not isinstance(user_id, int):
            return
        if user_id is not None:
            user_folder_stack[user_id] = [settings.root_folder_id]
        await browse_folder(call, settings.root_folder_id, 0, is_upload_mode=False)

    async def browse_folder(call, parent_id, page, is_upload_mode=False):
        user_id = getattr(getattr(call, 'from_user', None), 'id', None)
        if not isinstance(user_id, int):
            return
        # --- Исправление: защита от невалидных parent_id ---
        if not parent_id or parent_id in ('', '.', None):
            logging.warning(f"[user={user_id}] Некорректный parent_id '{parent_id}', fallback к root_folder_id")
            parent_id = settings.root_folder_id
        stack = user_folder_stack.setdefault(user_id, [settings.root_folder_id])
        if not stack or stack[-1] != parent_id:
            if parent_id == settings.root_folder_id:
                stack.clear()
                stack.append(settings.root_folder_id)
            elif parent_id not in stack:
                stack.append(parent_id)
            else:
                idx = stack.index(parent_id)
                stack[:] = stack[:idx+1]
        folders = await gdrive.list_folders(parent_id=parent_id, limit=1000)
        files = await gdrive.list_files(parent_id=parent_id, limit=1000)
        # --- Исправление: если только один файл и нет папок ---
        if not folders and len(files) == 1:
            file = files[0]
            file_name = file.get('name')
            file_id = file.get('id')
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=f"📄 {file_name}", callback_data=f"download_file_{file_id}")],
                [types.InlineKeyboardButton(text="⬆️ Назад", callback_data=f"up_folder_{0 if not is_upload_mode else 1}")],
                [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")]
            ])
            text = f"В этой папке только один файл:\n<b>{file_name}</b>"
            if call.message:
                await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            await call.answer()
            return
        # --- Если файлов и папок нет ---
        if not folders and not files:
            await call.message.answer("В этой папке ничего нет.", reply_markup=back_to_main_menu())
            await call.answer()
            return
        total = len(folders)
        start = page * FOLDER_PAGE_SIZE
        end = start + FOLDER_PAGE_SIZE
        page_folders = folders[start:end]
        kb: list[list[InlineKeyboardButton]] = []
        for f in page_folders:
            kb.append([types.InlineKeyboardButton(text=f["name"], callback_data=f"browse_folder_{f['id']}_{0 if not is_upload_mode else 1}_{page}")])
        # Добавляем файлы (только на первой странице)
        if page == 0 and files:
            for file in files:
                file_name = file.get('name')
                file_id = file.get('id')
                kb.append([
                    types.InlineKeyboardButton(text=f"📄 {file_name}", callback_data=f"download_file_{file_id}")
                ])
        if is_upload_mode:
            kb.append([types.InlineKeyboardButton(text="📥 Выбрать сюда", callback_data=f"choose_folder_{parent_id}")])
            kb.append([types.InlineKeyboardButton(text="➕ Создать папку", callback_data=f"create_folder_{parent_id}")])
        nav_row = []
        if page > 0:
            nav_row.append(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"browse_folder_{parent_id}_{0 if not is_upload_mode else 1}_{page-1}"))
        if end < total:
            nav_row.append(types.InlineKeyboardButton(text="➡️ Далее", callback_data=f"browse_folder_{parent_id}_{0 if not is_upload_mode else 1}_{page+1}"))
        if nav_row:
            kb.append(nav_row)
        if parent_id != settings.root_folder_id and len(stack) > 1:
            kb.append([types.InlineKeyboardButton(text="⬆️ Назад", callback_data=f"up_folder_{0 if not is_upload_mode else 1}")])
        kb.append([types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_main")])
        text = "Выберите папку (страница {}):".format(page+1)
        if call.message:
            await call.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        await call.answer()

    @dp.callback_query(lambda c: c.data and c.data.startswith("browse_folder_"))
    async def handle_browse_folder(call: types.CallbackQuery):
        # Пример callback: browse_folder_{id}_{is_upload_mode}_{page}
        if call is None or not hasattr(call, 'data') or call.data is None:
            await call.answer("Некорректные данные для навигации.", show_alert=True)
            return
        parts = call.data.split("_")
        if len(parts) < 4:
            await call.answer("Некорректные данные для навигации.", show_alert=True)
            return
        folder_id = parts[2]  # всегда строка
        try:
            is_upload_mode = bool(int(parts[3]))
        except Exception:
            is_upload_mode = False
        try:
            page = int(parts[4]) if len(parts) > 4 else 0
        except Exception:
            page = 0
        await browse_folder(call, folder_id, page, is_upload_mode=is_upload_mode)

    @dp.callback_query(lambda c: c.data and c.data.startswith("up_folder_"))
    async def handle_up_folder(call: types.CallbackQuery):
        # Пример callback: up_folder_{is_upload_mode}
        if call is None or not hasattr(call, 'data') or call.data is None:
            await call.answer("Некорректные данные для навигации.", show_alert=True)
            return
        parts = call.data.split("_")
        try:
            is_upload_mode = bool(int(parts[2])) if len(parts) > 2 else False
        except Exception:
            is_upload_mode = False
        user_id = getattr(getattr(call, 'from_user', None), 'id', None)
        if not isinstance(user_id, int):
            return
        stack = user_folder_stack.get(user_id, [settings.root_folder_id])
        if len(stack) > 1:
            stack.pop()
        if not stack:
            logging.warning(f"[user={user_id}] Стек папок пуст после pop, добавляю root_folder_id")
            stack.append(settings.root_folder_id)
        parent_id = stack[-1] if stack else settings.root_folder_id
        # --- Исправление: защита от невалидных parent_id ---
        if not parent_id or parent_id in ('', '.', None):
            logging.warning(f"[user={user_id}] Некорректный parent_id '{parent_id}' при возврате назад, fallback к root_folder_id")
            parent_id = settings.root_folder_id
        await browse_folder(call, parent_id, 0, is_upload_mode=is_upload_mode)

    @dp.callback_query(F.data == "menu_upload")
    async def menu_upload(call: types.CallbackQuery):
        if call.message:
            await call.message.answer(
                "⬆️ Пришлите один файл для загрузки\n\nВы сможете выбрать тип документа и папку вручную.",
                reply_markup=back_to_main_menu()
            )
        await call.answer()

    @dp.callback_query(F.data == "menu_search")
    async def menu_search(call: types.CallbackQuery):
        if call.message:
            await call.message.answer("🔍 Введите название файла для поиска:", reply_markup=back_to_main_menu())
        await call.answer()

    @dp.callback_query(F.data == "menu_history")
    async def menu_history(call: types.CallbackQuery):
        user_id = getattr(getattr(call, 'from_user', None), 'id', None)
        if not isinstance(user_id, int):
            await call.answer("Ошибка: не удалось определить пользователя.", show_alert=True)
            return
        history = get_history(user_id)
        text = "\n".join(history) if history else "История пуста."
        if call.message:
            await call.message.answer(f"🕑 История последних операций:\n{text}", reply_markup=back_to_main_menu())
        await call.answer()

    @dp.callback_query(F.data == "menu_check")
    async def menu_check(call: types.CallbackQuery, state=None):
        if call.message:
            await call.message.answer(
                "🧐 Пришлите документ для проверки (PDF, DOCX, JPG и др.).\n\nБот проверит имя файла и соответствие ключевых параметров (сумма, реквизиты и др.) между языками.",
                reply_markup=back_to_main_menu()
            )
        await call.answer()
        user_id = getattr(getattr(call, 'from_user', None), 'id', None)
        if not isinstance(user_id, int):
            return
        pending_files[user_id] = {"check_mode": True}

    @dp.message(F.media_group_id)
    async def handle_media_group(message: types.Message):
        # Для каждого файла в альбоме повторяем тот же пайплайн
        if message is not None and (hasattr(message, 'document') and message.document is not None or hasattr(message, 'photo') and message.photo is not None):
            if hasattr(message, 'document') and message.document is not None and hasattr(message.document, 'file_id') and message.document.file_id is not None:
                await handle_document(message)
            elif hasattr(message, 'photo') and message.photo is not None and isinstance(message.photo, list) and message.photo and hasattr(message.photo[-1], 'file_id') and message.photo[-1].file_id is not None:
                await handle_photo(message)

    # Универсальная функция для извлечения информации о файле из сообщения
    async def extract_file_info(message: types.Message):
        """
        Универсально извлекает file_name, file_bytes, mime_type из сообщения с документом или фото.
        Возвращает dict или None, если не удалось.
        """
        user_id = getattr(getattr(message, 'from_user', None), 'id', None)
        if not isinstance(user_id, int):
            return None
        bot = getattr(message, 'bot', None)
        if not bot:
            return None
        if message is not None and hasattr(message, 'document') and message.document is not None and hasattr(message.document, 'file_id') and message.document.file_id is not None:
            file_id = message.document.file_id
            file_name = getattr(message.document, 'file_name', None) or f"document_{file_id}"
            file_size = getattr(message.document, 'file_size', None)
            if file_size is None or file_size > settings.max_file_size_mb * 1024 * 1024:
                return None
            mime_type, _ = mimetypes.guess_type(str(file_name))
        elif message is not None and hasattr(message, 'photo') and message.photo is not None and isinstance(message.photo, list) and message.photo and hasattr(message.photo[-1], 'file_id') and message.photo[-1].file_id is not None:
            # Берём максимальное по размеру фото
            photo = message.photo[-1]
            file_id = photo.file_id
            file_name = f"photo_{file_id}.jpg"
            mime_type = "image/jpeg"
        else:
            return None
        if not bot or not file_id:
            return None
        file = await bot.get_file(file_id)
        file_path = getattr(file, 'file_path', None)
        if not file_path:
            return None
        file_bytes_obj = await bot.download_file(file_path) if bot and file_path else None
        if file_bytes_obj is None:
            return None
        if hasattr(file_bytes_obj, 'read'):
            if asyncio.iscoroutinefunction(file_bytes_obj.read):
                file_bytes = await file_bytes_obj.read()
            else:
                file_bytes = file_bytes_obj
        else:
            file_bytes = file_bytes_obj
        return {
            'user_id': user_id,
            'file_name': file_name,
            'file_bytes': file_bytes,
            'mime_type': mime_type
        }

    @dp.message(F.document)
    async def handle_document(message: types.Message):
        import time
        user_id = getattr(getattr(message, 'from_user', None), 'id', None)
        if not isinstance(user_id, int):
            await message.answer("Ошибка: не удалось определить пользователя.", reply_markup=back_to_main_menu())
            return
        if not rate_limiter.is_allowed(user_id):
            reset = rate_limiter.get_reset_time(user_id)
            await message.answer(f"⏳ Ой, ты очень активен! Давай чуть-чуть подождём {reset} сек, чтобы я не устал 😊", reply_markup=back_to_main_menu())
            return
        start_time = time.time()
        file_info = await extract_file_info(message)
        user_id = file_info['user_id'] if file_info else None
        if not file_info or not isinstance(user_id, int):
            logging.error(f"[user={getattr(message.from_user, 'id', None)}] Не удалось получить файл или файл слишком большой.")
            await message.answer("Ой-ой! 😳 Не получилось получить файл, возможно он слишком большой...\nПопробуй, пожалуйста, другой документ или уменьшить размер. Если нужна помощь — просто напиши мне! 💌", reply_markup=back_to_main_menu())
            return
        # --- Новый блок: только ИИ-анализ и предложение загрузки ---
        try:
            logging.info(f"[user={user_id}] Начало извлечения текста из файла {file_info['file_name']}")
            text = await smart_doc_processor.extract_text_from_bytes(
                file_info['file_bytes'], file_info['mime_type'], file_info['file_name']
            )
            elapsed = time.time() - start_time
            if elapsed > 10:
                await message.answer(f"⏳ Я всё ещё работаю над твоим файлом, чуть-чуть терпения... 🐢", reply_markup=back_to_main_menu())
            logging.info(f"[user={user_id}] Извлечение текста завершено за {elapsed:.2f} сек")
        except Exception as e:
            logging.error(f"[user={user_id}] Ошибка при извлечении текста: {e}")
            await message.answer("Ой! Что-то пошло не так при извлечении текста... 😔 Попробуй ещё раз или напиши мне, я помогу!", reply_markup=back_to_main_menu())
            return
        analysis = await analyze_document_info(text, file_info['file_name'])
        analysis_text = (
            f"\n<b>Вот что я нашёл в твоём документе! 🧐✨</b>"
            f"\n• Принципал: <b>{analysis.get('principal') or 'не найден'}</b>"
            f"\n• Агент: <b>{analysis.get('agent') or 'не найден'}</b>"
            f"\n• Тип документа: <b>{analysis.get('document_type') or 'не найден'}</b>"
            f"\n• Номер: <b>{analysis.get('number') or 'не найден'}</b>"
            f"\n• Дата: <b>{analysis.get('date') or 'не найдена'}</b>"
            "\n\nЕсли что-то не так — не стесняйся спросить, я всегда помогу разобраться! 💡"
        )
        await message.answer(analysis_text, parse_mode="HTML")
        try:
            check_result = await check_bilingual_document_consistency_llm(
                text,
                use_gemini=True,
                gemini_api_key=getattr(settings, 'gemini_api_key', None)
            )
        except Exception as e:
            logging.error(f"[user={user_id}] Ошибка при проверке двуязычной согласованности (ИИ): {e}")
            check_result = {"issues": ["Ошибка проверки двуязычности (ИИ)"], "recommendations": []}
        if check_result['issues']:
            issues_text = '\n'.join(f"❗️ {issue}" for issue in check_result['issues'])
        else:
            issues_text = "✅ Ключевые параметры совпадают в обеих частях документа. Молодец! 🦄"
        recs_text = '\n'.join(f"💡 {rec}" for rec in check_result['recommendations'])
        # Сохраняем файл для возможной загрузки по кнопке
        pending_files[user_id] = {**file_info, "ready_for_upload": True}
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Загрузить в Google Drive ✨", callback_data=f"upload_now_{user_id}")],
            [types.InlineKeyboardButton(text="Главное меню 🏠", callback_data="menu_main")]
        ])
        await message.answer(f"<b>Проверка двуязычной согласованности (ИИ):</b>\n{issues_text}\n{recs_text}\n\nВсё отлично! 🥳 Хочешь, я загружу этот файл в Google Drive? Просто нажми на кнопочку ниже! ⬇️", parse_mode="HTML", reply_markup=kb)
        return

    @dp.callback_query(lambda c: c.data and c.data.startswith("auto_save_"))
    async def auto_save_to_found_folder(call: types.CallbackQuery):
        user_id = getattr(getattr(call, 'from_user', None), 'id', None)
        if not isinstance(user_id, int) or user_id not in pending_files:
            logging.error(f"[user={user_id}] Нет загруженного файла для auto_save.")
            if call is not None and hasattr(call, 'answer'):
                await call.answer("Нет загруженного файла.", show_alert=True)
            return
        folder_id = call.data.replace("auto_save_", "") if call.data else None
        if not isinstance(folder_id, str):
            folder_id = None
        file_info = pending_files.pop(user_id)
        try:
            result = await gdrive.upload_file(
                file_info['file_name'],
                file_info['file_bytes'],
                parent_id=folder_id,
                mime_type=file_info['mime_type']
            )
        except Exception as e:
            logging.error(f"[user={user_id}] Ошибка загрузки файла в папку {folder_id}: {e}")
            if call.message and hasattr(call.message, 'edit_text'):
                await call.message.edit_text(f"❌ Ошибка загрузки: {e}", reply_markup=back_to_main_menu())
            if call is not None and hasattr(call, 'answer'):
                await call.answer()
            return
        if result['success']:
            add_history(user_id, "Загрузка файла", file_info['file_name'])
            logging.info(f"[user={user_id}] Файл {file_info['file_name']} успешно загружен в папку {folder_id}")
            if call.message and hasattr(call.message, 'edit_text'):
                await call.message.edit_text(f"✅ Файл успешно загружен в папку!\nИмя: {result['file']['name']}\nСсылка: {result['file'].get('webViewLink', 'нет')}", reply_markup=back_to_main_menu())
        else:
            logging.error(f"[user={user_id}] Ошибка загрузки файла: {result['error']}")
            if call.message and hasattr(call.message, 'edit_text'):
                await call.message.edit_text(f"❌ Ошибка загрузки: {result['error']}", reply_markup=back_to_main_menu())
        if call is not None and hasattr(call, 'answer'):
            await call.answer()

    @dp.callback_query(lambda c: c.data == "auto_create_folder")
    async def auto_create_folder(call: types.CallbackQuery):
        user_id = getattr(getattr(call, 'from_user', None), 'id', None)
        if not isinstance(user_id, int) or user_id not in pending_files:
            logging.error(f"[user={user_id}] Нет загруженного файла для auto_create_folder.")
            if call is not None and hasattr(call, 'answer'):
                await call.answer("Нет загруженного файла.", show_alert=True)
            return
        file_info = pending_files[user_id]
        text = await smart_doc_processor.extract_text_from_bytes(
            file_info['file_bytes'], file_info['mime_type'], file_info['file_name']
        )
        analysis = await analyze_document_info(text, file_info['file_name'])
        principal = analysis.get('principal') or 'Новая папка'
        try:
            result = await gdrive.create_folder(principal)
        except Exception as e:
            logging.error(f"[user={user_id}] Ошибка создания папки '{principal}': {e}")
            if call.message and hasattr(call.message, 'edit_text'):
                await call.message.edit_text(f"❌ Ошибка создания папки: {e}", reply_markup=back_to_main_menu())
            if call is not None and hasattr(call, 'answer'):
                await call.answer()
            return
        if result['success']:
            folder_id = result['folder']['id']
            file_info = pending_files.pop(user_id)
            try:
                upload_result = await gdrive.upload_file(
                    file_info['file_name'],
                    file_info['file_bytes'],
                    parent_id=folder_id,
                    mime_type=file_info['mime_type']
                )
            except Exception as e:
                logging.error(f"[user={user_id}] Ошибка загрузки файла в новую папку: {e}")
                if call.message and hasattr(call.message, 'edit_text'):
                    await call.message.edit_text(f"❌ Ошибка загрузки: {e}", reply_markup=back_to_main_menu())
                if call is not None and hasattr(call, 'answer'):
                    await call.answer()
                return
            if upload_result['success']:
                add_history(user_id, "Загрузка файла", file_info['file_name'])
                logging.info(f"[user={user_id}] Файл {file_info['file_name']} успешно загружен в новую папку '{principal}'")
                if call.message and hasattr(call.message, 'edit_text'):
                    await call.message.edit_text(f"✅ Папка '{principal}' создана и файл загружен!\nИмя: {upload_result['file']['name']}\nСсылка: {upload_result['file'].get('webViewLink', 'нет')}", reply_markup=back_to_main_menu())
            else:
                logging.error(f"[user={user_id}] Ошибка загрузки файла: {upload_result['error']}")
                if call.message and hasattr(call.message, 'edit_text'):
                    await call.message.edit_text(f"❌ Ошибка загрузки файла: {upload_result['error']}", reply_markup=back_to_main_menu())
        else:
            logging.error(f"[user={user_id}] Ошибка создания папки: {result['error']}")
            if call.message and hasattr(call.message, 'edit_text'):
                await call.message.edit_text(f"❌ Ошибка создания папки: {result['error']}", reply_markup=back_to_main_menu())
        if call is not None and hasattr(call, 'answer'):
            await call.answer()

    @dp.callback_query(lambda c: c.data == "choose_folder_manual")
    async def choose_folder_manual(call: types.CallbackQuery):
        await menu_upload(call)
        if call is not None and hasattr(call, 'answer'):
            await call.answer()

    @dp.message(F.photo)
    async def handle_photo(message: types.Message):
        user_id = getattr(getattr(message, 'from_user', None), 'id', None)
        if not isinstance(user_id, int):
            return
        if user_id is not None and not rate_limiter.is_allowed(user_id):
            reset = rate_limiter.get_reset_time(user_id)
            await message.answer(f"⏳ Ой, ты очень активен! Давай чуть-чуть подождём {reset} сек, чтобы я не устал 😊", reply_markup=back_to_main_menu())
            return
        file_info = await extract_file_info(message)
        user_id = file_info['user_id'] if file_info else None
        if not file_info:
            if message is not None and hasattr(message, 'answer'):
                await message.answer("Ой-ой! 😳 Не получилось получить фото, возможно оно слишком большое... Попробуй другое или напиши мне, я помогу! 🐾", reply_markup=back_to_main_menu())
            return
        # --- Новый блок: только ИИ-анализ и предложение загрузки ---
        text = await smart_doc_processor.extract_text_from_bytes(
            file_info['file_bytes'], file_info['mime_type'], file_info['file_name']
        )
        preview = (text[:1000] + '...') if text and len(text) > 1000 else text
        if preview:
            await message.answer(f"📝 Вот кусочек текста, который я нашёл:\n<code>{preview}</code>", parse_mode="HTML")
        analysis = await analyze_document_info(text, file_info['file_name'])
        analysis_text = (
            f"\n<b>Вот что я нашёл в твоём документе! 🧐✨</b>"
            f"\n• Принципал: <b>{analysis.get('principal') or 'не найден'}</b>"
            f"\n• Агент: <b>{analysis.get('agent') or 'не найден'}</b>"
            f"\n• Тип документа: <b>{analysis.get('document_type') or 'не найден'}</b>"
            f"\n• Номер: <b>{analysis.get('number') or 'не найден'}</b>"
            f"\n• Дата: <b>{analysis.get('date') or 'не найдена'}</b>"
            "\n\nЕсли что-то не так — не стесняйся спросить, я всегда помогу разобраться! 💡"
        )
        await message.answer(analysis_text, parse_mode="HTML")
        try:
            check_result = await check_bilingual_document_consistency_llm(
                text,
                use_gemini=True,
                gemini_api_key=getattr(settings, 'gemini_api_key', None)
            )
        except Exception as e:
            logging.error(f"[user={user_id}] Ошибка при проверке двуязычной согласованности (ИИ): {e}")
            check_result = {"issues": ["Ошибка проверки двуязычности (ИИ)"], "recommendations": []}
        if check_result['issues']:
            issues_text = '\n'.join(f"❗️ {issue}" for issue in check_result['issues'])
        else:
            issues_text = "✅ Ключевые параметры совпадают в обеих частях документа. Молодец! 🦄"
        recs_text = '\n'.join(f"💡 {rec}" for rec in check_result['recommendations'])
        # Сохраняем файл для возможной загрузки по кнопке
        pending_files[user_id] = {**file_info, "ready_for_upload": True}
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Загрузить в Google Drive ✨", callback_data=f"upload_now_{user_id}")],
            [types.InlineKeyboardButton(text="Главное меню 🏠", callback_data="menu_main")]
        ])
        await message.answer(f"<b>Проверка двуязычной согласованности (ИИ):</b>\n{issues_text}\n{recs_text}\n\nВсё отлично! 🥳 Хочешь, я загружу этот файл в Google Drive? Просто нажми на кнопочку ниже! ⬇️", parse_mode="HTML", reply_markup=kb)
        return

    @dp.callback_query(lambda c: c.data and c.data.startswith("analyze_ai_"))
    async def handle_analyze_ai(call: types.CallbackQuery):
        user_id = call.data.replace("analyze_ai_", "")
        # Получаем последний загруженный файл пользователя (или из pending_files)
        # Для простоты — ищем по user_id в pending_files, иначе не анализируем
        file_info = pending_files.get(int(user_id))
        if not file_info:
            await call.answer("Нет файла для анализа.", show_alert=True)
            return
        text = await smart_doc_processor.extract_text_from_bytes(
            file_info['file_bytes'], file_info['mime_type'], file_info['file_name']
        )
        analysis = await analyze_document_info(text, file_info['file_name'], force_llm=True)
        analysis_text = (
            f"\n<b>Результат анализа (ИИ):</b>"
            f"\nНомер договора: <b>{analysis.get('contract_number') or 'не найден'}</b>"
            f"\nДата договора: <b>{analysis.get('contract_date') or 'не найдена'}</b>"
            f"\nНомер поручения: <b>{analysis.get('assignment_number') or 'не найден'}</b>"
            f"\nДата поручения: <b>{analysis.get('assignment_date') or 'не найдена'}</b>"
            f"\nГород: <b>{analysis.get('city') or 'не найден'}</b>"
            f"\nРеквизиты: <b>{analysis.get('requisites') or 'не найдены'}</b>"
        )
        await call.message.answer(analysis_text, parse_mode="HTML")
        await call.answer()

    @dp.callback_query(F.data.startswith("doc_type_"))
    async def choose_doc_type(call: types.CallbackQuery):
        user_id = getattr(getattr(call, 'from_user', None), 'id', None)
        if not isinstance(user_id, int) or user_id not in pending_files:
            await call.answer("Нет загруженного файла.", show_alert=True)
            return
        doc_type_data = getattr(call, 'data', None)
        if not doc_type_data or not isinstance(doc_type_data, str) or not doc_type_data.startswith("doc_type_"):
            await call.answer("Некорректный тип документа.", show_alert=True)
            return
        doc_type = doc_type_data.replace("doc_type_", "")
        pending_files[user_id]['doc_type'] = doc_type
        # Инициализируем стек навигации по папкам
        pending_files[user_id]['folder_stack'] = [settings.root_folder_id]
        await browse_folder(call, settings.root_folder_id, 0, is_upload_mode=False)

    @dp.callback_query(lambda c: c.data and isinstance(c.data, str) and c.data.startswith("choose_folder_"))
    async def choose_folder(call: types.CallbackQuery):
        user_id = getattr(getattr(call, 'from_user', None), 'id', None)
        if not isinstance(user_id, int):
            return
        folder_id = None
        if call is not None and hasattr(call, 'data') and call.data is not None and isinstance(call.data, str):
            if call.data.startswith("choose_folder_"):
                folder_id = call.data.replace("choose_folder_", "")
        if not folder_id:
            if call is not None and hasattr(call, 'answer'):
                await call.answer("Некорректные данные для выбора папки.", show_alert=True)
            return
        file_info = pending_files.pop(user_id, None)
        if not file_info:
            if call is not None and hasattr(call, 'answer'):
                await call.answer("Нет файла для загрузки.", show_alert=True)
            return
        result = await gdrive.upload_file(
            file_info['file_name'],
            file_info['file_bytes'],
            parent_id=folder_id,
            mime_type=file_info['mime_type']
        )
        if result.get('success'):
            add_history(user_id, "Загрузка файла", file_info['file_name'])
            text = f"✅ Файл успешно загружен в Google Drive!\nИмя: {result['file']['name']}\nСсылка: {result['file'].get('webViewLink', 'нет')}"
            if call is not None and hasattr(call, 'message') and call.message and hasattr(call.message, 'edit_text'):
                await call.message.edit_text(text, reply_markup=back_to_main_menu())
        else:
            if call is not None and hasattr(call, 'message') and call.message and hasattr(call.message, 'edit_text'):
                await call.message.edit_text(f"❌ Ошибка загрузки: {result.get('error')}", reply_markup=back_to_main_menu())
        if call is not None and hasattr(call, 'answer'):
            await call.answer()

    @dp.callback_query(lambda c: c.data and isinstance(c.data, str) and c.data.startswith("download_file_"))
    async def handle_download_file(call: types.CallbackQuery):
        user_id = getattr(getattr(call, 'from_user', None), 'id', None)
        if not isinstance(user_id, int):
            await call.answer("Ошибка: не удалось определить пользователя.", show_alert=True)
            return
        file_id = call.data.replace("download_file_", "") if call.data else None
        if not file_id:
            if call is not None and hasattr(call, 'answer'):
                await call.answer("Некорректные данные для скачивания.", show_alert=True)
            return
        file = await gdrive.get_file_metadata(file_id) if file_id else None
        file_bytes = await gdrive.download_file(file_id) if file_id else None
        if not file or not file_bytes:
            if call is not None and hasattr(call, 'answer'):
                await call.answer("Не удалось получить файл.", show_alert=True)
            return
        from aiogram.types.input_file import BufferedInputFile
        if call is not None and hasattr(call, 'message') and call.message and hasattr(call.message, 'answer_document'):
            await call.message.answer_document(BufferedInputFile(file_bytes, filename=file['name']))
        if call is not None and hasattr(call, 'answer'):
            await call.answer()

    @dp.message()
    async def handle_search(message: types.Message):
        # Если это пересланный документ — сразу предлагаем загрузку
        if hasattr(message, 'document') and message.document is not None:
            await handle_document(message)
            return
        query = message.text.strip() if message and hasattr(message, 'text') and message.text else None
        if not query:
            await message.answer("Пожалуйста, напиши название файла, который ищешь! Я постараюсь найти его для тебя 🦊", reply_markup=back_to_main_menu())
            return
        user_id = getattr(getattr(message, 'from_user', None), 'id', None)
        if not isinstance(user_id, int):
            return
        results = await gdrive.search_files(query, limit=20)
        if not results:
            await message.answer("Ой, ничего не нашлось... 😔\nПопробуй изменить запрос или отправь мне новый файл — я всегда готов помочь! 🦊", reply_markup=back_to_main_menu())
            await message.answer("Возврат в главное меню", reply_markup=main_menu())
            return
        if len(results) > 5:
            await message.answer("Результатов слишком много, уточни, пожалуйста, запрос! 🧐", reply_markup=back_to_main_menu())
            await message.answer("Возврат в главное меню", reply_markup=main_menu())
            return
        buttons = [
            [types.InlineKeyboardButton(text=f"📄 {f['name']}", callback_data=f"download_file_{f['id']}")]
            for f in results
        ]
        kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(f"Найдено файлов: {len(results)}. Вот они! 🥰", reply_markup=kb)
        await message.answer("Возврат в главное меню", reply_markup=main_menu())

    async def get_file_path(file):
        # Рекурсивно строим путь к файлу по parents
        path: list[str] = []
        parents = file.get('parents', [])
        while parents:
            parent_id = parents[0]
            folder = await gdrive.get_folder_metadata(parent_id)
            if not folder:
                break
            path.insert(0, folder['name'])
            parents = folder.get('parents', [])
        return "/".join(path) if path else ""

    @dp.callback_query(lambda c: c.data and isinstance(c.data, str) and c.data.startswith("upload_now_"))
    async def handle_upload_now(call: types.CallbackQuery):
        user_id = getattr(getattr(call, 'from_user', None), 'id', None)
        if not isinstance(user_id, int) or user_id not in pending_files:
            await call.answer("Нет загруженного файла для загрузки.", show_alert=True)
            return
        file_info = pending_files.pop(user_id)
        if not file_info:
            if call is not None and hasattr(call, 'answer'):
                await call.answer("Нет файла для загрузки.", show_alert=True)
            return
        # Если файл после ИИ-проверки (ready_for_upload), загружаем без проверки дубликатов
        if file_info.get("ready_for_upload"):
            result = await gdrive.upload_file(
                file_info['file_name'],
                file_info['file_bytes'],
                parent_id=settings.root_folder_id,
                mime_type=file_info['mime_type']
            )
            if result.get('success'):
                add_history(user_id, "Загрузка файла", file_info['file_name'])
                if call is not None and hasattr(call, 'message') and call.message and hasattr(call.message, 'answer'):
                    await call.message.answer(f"Ура! 🎉 Твой файл уже уютно устроился в Google Drive!\nИмя: {result['file']['name']}\nСсылка: {result['file'].get('webViewLink', 'нет')}\nЕсли хочешь загрузить ещё что-то — я всегда рядом! 🐾", reply_markup=back_to_main_menu())
            else:
                if call is not None and hasattr(call, 'message') and call.message and hasattr(call.message, 'answer'):
                    await call.message.answer(f"Ой! Не получилось загрузить файл... 😢\nОшибка: {result.get('error')}\nПопробуй ещё раз или напиши мне, я помогу!", reply_markup=back_to_main_menu())
            if call is not None and hasattr(call, 'answer'):
                await call.answer()
            return
        # Обычный сценарий (с проверкой дубликатов)
        result = await gdrive.upload_file(
            file_info['file_name'],
            file_info['file_bytes'],
            parent_id=settings.root_folder_id,
            mime_type=file_info['mime_type']
        )
        if result.get('success'):
            add_history(user_id, "Загрузка файла", file_info['file_name'])
            if call is not None and hasattr(call, 'message') and call.message and hasattr(call.message, 'answer'):
                await call.message.answer(f"✅ Файл успешно загружен в Google Drive!\nИмя: {result['file']['name']}\nСсылка: {result['file'].get('webViewLink', 'нет')}", reply_markup=back_to_main_menu())
        else:
            if call is not None and hasattr(call, 'message') and call.message and hasattr(call.message, 'answer'):
                await call.message.answer(f"❌ Ошибка загрузки: {result.get('error')}", reply_markup=back_to_main_menu())
        if call is not None and hasattr(call, 'answer'):
            await call.answer()

    @dp.callback_query(lambda c: c.data and c.data.startswith("create_folder_"))
    async def handle_create_folder(call: types.CallbackQuery):
        # Пример callback: create_folder_{parent_id}
        if call is None or not hasattr(call, 'data') or call.data is None:
            if call is not None and hasattr(call, 'answer'):
                await call.answer("Некорректные данные для создания папки.", show_alert=True)
            return
        parts = call.data.split("_")
        if len(parts) < 3:
            if call is not None and hasattr(call, 'answer'):
                await call.answer("Некорректные данные для создания папки.", show_alert=True)
            return
        parent_id = parts[2]
        # Запросить у пользователя имя новой папки
        from aiogram.fsm.context import FSMContext
        from aiogram.fsm.state import State, StatesGroup
        class CreateFolderState(StatesGroup):
            waiting_for_name = State()
        state = getattr(call, 'fsm_context', None)
        if state is not None:
            await state.set_state(CreateFolderState.waiting_for_name)
            if call.message and hasattr(call.message, 'answer'):
                await call.message.answer("Введите имя новой папки:")
            await state.update_data(parent_id=parent_id)
        else:
            result = await gdrive.create_folder("Новая папка", parent_id=parent_id)
            if call.message and hasattr(call.message, 'answer'):
                if result.get('success'):
                    await call.message.answer(f"Папка создана: {result['folder']['name']}")
                else:
                    await call.message.answer(f"Ошибка создания папки: {result.get('error')}")
        if call is not None and hasattr(call, 'answer'):
            await call.answer()

    # Обработчик ввода имени новой папки (FSM)
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.state import State, StatesGroup
    class CreateFolderState(StatesGroup):
        waiting_for_name = State()
    @dp.message()
    async def process_new_folder_name(message: types.Message, state: FSMContext):
        if state is None:
            return
        current_state = await state.get_state()
        if current_state == CreateFolderState.waiting_for_name.state:
            data = await state.get_data()
            parent_id = data.get('parent_id')
            folder_name = message.text.strip() if message and hasattr(message, 'text') and message.text else None
            if not folder_name:
                if message is not None and hasattr(message, 'answer'):
                    await message.answer("Имя папки не может быть пустым. Введите ещё раз:")
                return
            result = await gdrive.create_folder(folder_name, parent_id=parent_id)
            if message is not None and hasattr(message, 'answer'):
                if result.get('success'):
                    await message.answer(f"Папка создана: {result['folder']['name']}")
                else:
                    await message.answer(f"Ошибка создания папки: {result.get('error')}")
            await state.clear()

    @dp.message(F.document)
    async def handle_document_check(message: types.Message):
        user_id = getattr(getattr(message, 'from_user', None), 'id', None)
        if not isinstance(user_id, int) or user_id in pending_files and pending_files[user_id].get("check_mode"):
            file_info = await extract_file_info(message)
            if not file_info or not file_info.get('file_name') or not file_info.get('file_bytes'):
                await message.answer("❌ Не удалось получить файл или файл слишком большой.", reply_markup=back_to_main_menu())
                pending_files.pop(user_id, None)
                return
            text = await smart_doc_processor.extract_text_from_bytes(file_info['file_bytes'], file_info['mime_type'], file_info['file_name'])
            suggested_name = extract_suggested_filename_from_content(file_info['file_bytes'])
            await message.answer(f"Рекомендуемое имя файла: {suggested_name}", reply_markup=back_to_main_menu())
            try:
                check_result = await check_bilingual_document_consistency_llm(text, file_name=file_info['file_name'])
            except Exception as e:
                logging.error(f"[user={user_id}] Ошибка при ИИ-проверке: {e}")
                check_result = {"issues": ["Ошибка ИИ-проверки"], "recommendations": []}
            if check_result['issues']:
                issues_text = '\n'.join(f"❗️ {issue}" for issue in check_result['issues'])
                recs_text = '\n'.join(f"💡 {rec}" for rec in check_result['recommendations'])
                await message.answer(f"<b>Проверка двуязычной согласованности (ИИ):</b>\n{issues_text}\n{recs_text}", parse_mode="HTML")
                pending_files.pop(user_id, None)
                return
        else:
            issues_text = "✅ Ключевые параметры совпадают в обеих частях документа."
            recs_text = '\n'.join(f"💡 {rec}" for rec in check_result['recommendations'])
            # Сохраняем файл для возможной загрузки по кнопке
            pending_files[user_id] = {**file_info, "check_mode": False, "ready_for_upload": True}
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="Загрузить в Google Drive", callback_data=f"upload_now_{user_id}")],
                [types.InlineKeyboardButton(text="Главное меню", callback_data="menu_main")]
            ])
            await message.answer(f"<b>Проверка двуязычной согласованности (ИИ):</b>\n{issues_text}\n{recs_text}\n\nФайл соответствует всем требованиям. Хотите загрузить его в Google Drive?", parse_mode="HTML", reply_markup=kb)
            return
        await handle_document(message)

    def extract_suggested_filename_from_content(file_bytes: bytes) -> str:
        # TODO: Реализовать реальный парсинг содержимого для генерации имени
        # Сейчас просто заглушка
        return 'Документ_тип_номер_дата.ext'

    await on_startup(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 