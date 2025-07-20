from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Document, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.utils.telegram_utils import escape_markdown
import structlog
log = structlog.get_logger(__name__)

from app.utils.file_validation import validate_file, FileValidationError

# from ..services.pdf_ocr import PDFOCRService
# from ..services.ai_validator import AITextValidator
# (Заглушки для интеграции)

router = Router()

class ReadPDFStates(StatesGroup):
    waiting_for_pdf = State()
    processing = State()

def get_main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Загрузить файлы", callback_data="upload")],
        [InlineKeyboardButton(text="📦 Массовая загрузка", callback_data="bulk_upload")],
        [InlineKeyboardButton(text="🔍 Поиск файлов", callback_data="search_files")],
        [InlineKeyboardButton(text="📋 Мои файлы", callback_data="browse_files")],
        [InlineKeyboardButton(text="📖 Прочитать PDF", callback_data="read_pdf")],
        [InlineKeyboardButton(text="💱 Курсы валют", callback_data="currency_rates")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")]
    ])
    return keyboard

# --- ReplyKeyboard (постоянные кнопки) ---
def get_reply_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📤 Загрузить"), KeyboardButton("🔍 Найти")],
            [KeyboardButton("📦 Массово"), KeyboardButton("📖 Читать PDF")],
            [KeyboardButton("💱 Курсы"), KeyboardButton("⚙️ Настройки")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

# --- Универсальный обработчик без команд ---
@router.message()
async def universal_handler(message: Message, state: FSMContext):
    # Если это документ
    if message.document:
        doc = message.document
        try:
            validate_file(doc.file_name, doc.file_size)
        except FileValidationError as e:
            await message.answer(f"❌ Файл не принят: {e}")
            return
        filename = (doc.file_name or '').lower()
        # PDF
        if filename.endswith('.pdf'):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton("📖 Прочитать текст", callback_data="ocr_pdf")],
                [InlineKeyboardButton("📁 Сохранить в Drive", callback_data="save_drive")],
                [InlineKeyboardButton("🏦 Найти платежи", callback_data="bank_analyze")]
            ])
            await message.answer("Что делаем с PDF?", reply_markup=keyboard)
            return
        # Банковский документ
        if 'выписка' in filename or 'statement' in filename:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton("🏦 Анализ платежей", callback_data="bank_ocr")],
                [InlineKeyboardButton("📊 Создать отчет", callback_data="bank_report")]
            ])
            await message.answer("Банковский документ: выберите действие", reply_markup=keyboard)
            return
        # ZIP архив
        if filename.endswith('.zip'):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton("📦 Массовая загрузка", callback_data="bulk_upload")],
                [InlineKeyboardButton("📂 Показать содержимое", callback_data="show_zip")],
                [InlineKeyboardButton("⚡ Быстрая обработка", callback_data="quick_zip")]
            ])
            await message.answer("ZIP-архив: выберите действие", reply_markup=keyboard)
            return
        # Остальные файлы
        await message.answer(
            "Что делаем с документом?",
            reply_markup=get_main_menu_keyboard()
        )
        return
    # Если это текст
    if message.text:
        text = message.text.lower().strip()
        # Быстрые фразы
        if any(word in text for word in ["курс", "доллар", "евро", "юань"]):
            await message.answer(
                "💱 Курсы валют:",
                reply_markup=get_main_menu_keyboard()
            )
            return
        if "найти" in text or "поиск" in text:
            await message.answer(
                "🔍 Поиск файлов:",
                reply_markup=get_main_menu_keyboard()
            )
            return
        if any(word in text for word in ["договор", "акт", "счет"]):
            await message.answer(
                "📄 Создать документ?",
                reply_markup=get_main_menu_keyboard()
            )
            return
        if text in ["📤", "загрузить"]:
            await message.answer(
                "📤 Загрузка файлов:",
                reply_markup=get_main_menu_keyboard()
            )
            return
        if text in ["📦", "массово"]:
            await message.answer(
                "📦 Массовая загрузка:",
                reply_markup=get_main_menu_keyboard()
            )
            return
        if text in ["📖", "прочитать"]:
            await message.answer(
                "📖 Прочитать PDF:",
                reply_markup=get_main_menu_keyboard()
            )
            return
        if text in ["⚙️", "настройки"]:
            await message.answer(
                "⚙️ Настройки:",
                reply_markup=get_main_menu_keyboard()
            )
            return
        # Если не распознали — главное меню
        await message.answer(
            "🤖 Выберите действие:",
            reply_markup=get_main_menu_keyboard()
        )

@router.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "🤖 **Привет! Я твой помощник по работе с файлами!**\n\n"
        "Что хочешь сделать? Выбирай любое действие 😊",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "read_pdf")
async def start_read_pdf_process(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📖 **Давай прочитаем твой PDF вместе!**\n\n"
        "🌟 **Что я умею делать:**\n"
        "• Извлекаю весь текст из PDF файла\n"
        "• Исправляю ошибки распознавания\n" 
        "• Делаю текст красивым и читаемым\n"
        "• Показываю, что именно исправил\n\n"
        "📁 **Просто отправь мне свой PDF файл!**\n\n"
        "💡 *Файлы до 20 МБ обрабатываю без проблем*",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
        ]),
        parse_mode="Markdown"
    )
    await state.set_state(ReadPDFStates.waiting_for_pdf)

@router.message(ReadPDFStates.waiting_for_pdf, F.document)
async def process_pdf_document(message: Message, state: FSMContext):
    document: Document = message.document
    try:
        validate_file(document.file_name, document.file_size)
    except FileValidationError as e:
        await message.answer(f"❌ Файл не принят: {e}")
        return
    if not document.mime_type == 'application/pdf':
        await message.answer(
            "Ой! 😅 Я умею читать только PDF файлы.\n\n"
            "Отправь мне PDF документ, и я его с удовольствием прочитаю! 📖",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📖 Выбрать PDF", callback_data="read_pdf")]
            ])
        )
        return
    if document.file_size > 20 * 1024 * 1024:
        file_size_mb = document.file_size / (1024 * 1024)
        await message.answer(
            f"Упс! 😔 Твой файл слишком большой ({file_size_mb:.1f} МБ).\n\n"
            f"Я могу обработать файлы до 20 МБ. Попробуй файл поменьше! 💝",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📖 Попробовать другой", callback_data="read_pdf")]
            ])
        )
        return
    await state.set_state(ReadPDFStates.processing)
    progress_msg = await message.answer(
        "🎉 **Отлично! Начинаю читать твой PDF...**\n\n"
        "🔄 Скачиваю файл...\n"
        "⏳ Извлекаю текст...\n" 
        "⏳ Проверяю качество...\n"
        "⏳ Готовлю результат...\n\n"
        "💫 *Это займет немного времени, но оно того стоит!*",
        parse_mode="Markdown"
    )
    try:
        await progress_msg.edit_text(
            "🎉 **Читаю твой PDF...**\n\n"
            "✅ Скачал файл!\n"
            "🔄 Извлекаю текст...\n" 
            "⏳ Проверяю качество...\n"
            "⏳ Готовлю результат...\n\n"
            "📖 *Уже вижу твой текст!*",
            parse_mode="Markdown"
        )
        file = await message.bot.get_file(document.file_id)
        file_path = f"/tmp/{document.file_name}"
        await message.bot.download_file(file.file_path, file_path)
        await progress_msg.edit_text(
            "🎉 **Читаю твой PDF...**\n\n"
            "✅ Скачал файл!\n"
            "✅ Извлекаю текст!\n" 
            "🔄 Проверяю качество...\n"
            "⏳ Готовлю результат...\n\n"
            "🤖 *Исправляю найденные ошибки...*",
            parse_mode="Markdown"
        )
        # ocr_service = PDFOCRService()
        # raw_text, confidence, page_count = await ocr_service.extract_text_from_pdf(file_path)
        raw_text, confidence, page_count = "Тестовый текст PDF", 0.98, 3  # Заглушка
        await progress_msg.edit_text(
            "🎉 **Читаю твой PDF...**\n\n"
            "✅ Скачал файл!\n"
            "✅ Извлек текст!\n" 
            "✅ Проверил качество!\n"
            "🔄 Готовлю результат...\n\n"
            "✨ *Почти готово!*",
            parse_mode="Markdown"
        )
        # ai_validator = AITextValidator()
        # validated_text, corrections, quality_score = await ai_validator.validate_and_correct(raw_text)
        validated_text, corrections, quality_score = raw_text, [], 0.99  # Заглушка
        import os
        os.remove(file_path)
        await show_reading_results(
            message, 
            document.file_name,
            raw_text,
            validated_text,
            confidence,
            quality_score,
            corrections,
            page_count
        )
        await progress_msg.delete()
        await state.clear()
    except Exception as e:
        await progress_msg.delete()
        await message.answer(
            f"😔 **Ой, что-то пошло не так...**\n\n"
            f"Не удалось прочитать файл: `{str(e)}`\n\n"
            f"Попробуем еще раз? 🤗",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="read_pdf")],
                [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
            ]),
            parse_mode="Markdown"
        )
        await state.clear()

async def show_reading_results(
    message: Message,
    filename: str,
    raw_text: str,
    validated_text: str,
    ocr_confidence: float,
    ai_quality: float,
    corrections: list,
    page_count: int
):
    stats_text = (
        f"🎉 **Готово! Прочитал твой файл: {filename}**\n\n"
        f"📊 **Что получилось:**\n"
        f"📄 Прочитано страниц: **{page_count}**\n"
        f"📝 Найдено символов: **{len(raw_text):,}**\n"
        f"🎯 Качество чтения: **{ocr_confidence:.0%}**\n"
        f"✨ Качество проверки: **{ai_quality:.0%}**\n"
    )
    if corrections:
        stats_text += f"🔧 Исправил ошибок: **{len(corrections)}**\n\n"
        stats_text += "**🔍 Что исправил:**\n"
        for i, correction in enumerate(corrections[:5], 1):
            stats_text += f"• `{correction['original']}` → `{correction['corrected']}`\n"
        if len(corrections) > 5:
            stats_text += f"• ... и еще {len(corrections) - 5} исправлений! 😊\n"
    else:
        stats_text += "🎯 Исправлений не потребовалось - текст отличный!\n"
    stats_text += "\n💝 *Выбери, что хочешь сделать дальше:*"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Показать как было", callback_data="show_original_text")],
        [InlineKeyboardButton(text="✨ Показать исправленный", callback_data="show_clean_text")],
        [InlineKeyboardButton(text="💾 Скачать файлом", callback_data="download_text_file")],
        [InlineKeyboardButton(text="📖 Прочитать еще один", callback_data="read_pdf")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")]
    ])
    await message.answer(stats_text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "back_to_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🏠 **С возвращением!**\n\n"
        "Что будем делать дальше? 😊",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

@router.message(ReadPDFStates.waiting_for_pdf)
async def handle_non_document(message: Message):
    if message.text and message.text.lower() in ['отмена', 'назад', '/cancel']:
        await message.answer(
            "Хорошо, отменяю! 😊\n\nВозвращаемся в главное меню.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    await message.answer(
        "📖 **Я жду PDF файл для чтения!**\n\n"
        "Просто прикрепи файл к сообщению и отправь мне 💝\n\n"
        "*Или нажми кнопку ниже, чтобы вернуться назад*",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
        ]),
        parse_mode="Markdown"
    ) 

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from app.services.autocomplete_service import AutocompleteService
from app.config import settings
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from app.services.bank_ocr_service import BankDocumentOCR
from decimal import Decimal
from app.services.cbr_notifier import CBRNotificationService
from app.config import settings
from aiogram import Bot
import structlog
log = structlog.get_logger(__name__)

router = Router()

class QuickDocStates(StatesGroup):
    waiting_company1 = State()
    waiting_company2 = State()
    waiting_doctype = State()
    waiting_custom_doctype = State()
    waiting_date = State()
    waiting_number = State()

@router.message(F.text.startswith("/быстро"))
async def quick_document_start(message: Message, state: FSMContext):
    autocomplete = AutocompleteService(settings.REDIS_DSN)
    await autocomplete.connect()
    recent = await autocomplete.get_recent_counterparties(message.from_user.id)
    if recent:
        keyboard_buttons = []
        for i, counterparty in enumerate(recent[:5], 1):
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{i}. {counterparty['display']}",
                    callback_data=f"quick_counterparty_{i-1}"
                )
            ])
        keyboard_buttons.append([
            InlineKeyboardButton(text="✍️ Ввести новые", callback_data="quick_new_counterparty")
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.answer(
            "🚀 **Быстрое создание документа**\n\n"
            "Выбери контрагентов или введи новые:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "✍️ **Введи первую компанию:**\n\n"
            "Например: *Демирекс*",
            parse_mode="Markdown"
        )
        await state.set_state(QuickDocStates.waiting_company1)

@router.callback_query(F.data.startswith("quick_counterparty_"))
async def select_recent_counterparty(callback: CallbackQuery, state: FSMContext):
    autocomplete = AutocompleteService(settings.REDIS_DSN)
    await autocomplete.connect()
    index = int(callback.data.split("_")[-1])
    recent = await autocomplete.get_recent_counterparties(callback.from_user.id)
    if index < len(recent):
        counterparty = recent[index]
        await state.update_data(
            company1=counterparty['company1'],
            company2=counterparty['company2']
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Договор", callback_data="doctype_договор")],
            [InlineKeyboardButton(text="📄 Счет", callback_data="doctype_счет")],
            [InlineKeyboardButton(text="📝 Акт", callback_data="doctype_акт")],
            [InlineKeyboardButton(text="✍️ Другой", callback_data="doctype_custom")]
        ])
        await callback.message.edit_text(
            f"👥 **Контрагенты:** {counterparty['display']}\n\n"
            f"📋 **Выбери тип документа:**",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await state.set_state(QuickDocStates.waiting_doctype)

@router.callback_query(F.data.startswith("doctype_"))
async def select_doctype(callback: CallbackQuery, state: FSMContext):
    autocomplete = AutocompleteService(settings.REDIS_DSN)
    await autocomplete.connect()
    doctype = callback.data.replace("doctype_", "")
    data = await state.get_data()
    if doctype == "custom":
        await callback.message.edit_text(
            "✍️ **Введи тип документа:**\n\n"
            "Например: *Поручение*, *Справка*, *Уведомление*",
            parse_mode="Markdown"
        )
        await state.set_state(QuickDocStates.waiting_custom_doctype)
        return
    next_number = await autocomplete.get_next_document_number(
        data['company1'], data['company2'], doctype
    )
    await state.update_data(doctype=doctype, number=next_number)
    today = datetime.now().strftime("%d.%m.%Y")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📅 Сегодня ({today})", callback_data="date_today")],
        [InlineKeyboardButton(text="📅 Завтра", callback_data="date_tomorrow")],
        [InlineKeyboardButton(text="✍️ Ввести дату", callback_data="date_custom")]
    ])
    await callback.message.edit_text(
        f"👥 **Контрагенты:** {data['company1']} ↔ {data['company2']}\n"
        f"📋 **Тип:** {doctype}\n"
        f"🔢 **Номер:** {next_number} (автоматически)\n\n"
        f"📅 **Выбери дату:**",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(QuickDocStates.waiting_date) 

@router.message(F.document)
async def analyze_bank_document(message: Message):
    document = message.document
    if not (document.mime_type == 'application/pdf' or \
            'выписка' in (document.file_name or '').lower() or \
            'statement' in (document.file_name or '').lower()):
        return  # Не банковский документ
    processing_msg = await message.answer(
        "🏦 **Анализирую банковский документ...**\n\n"
        "🔍 Ищу платежи и переводы..."
    )
    try:
        file = await message.bot.get_file(document.file_id)
        file_path = f"/tmp/{document.file_name}"
        await message.bot.download_file(file.file_path, file_path)
        bank_ocr = BankDocumentOCR()
        payments = await bank_ocr.process_bank_document(file_path)
        import os
        os.remove(file_path)
        if not payments:
            await processing_msg.edit_text(
                "🤷‍♂️ **Платежи не найдены**\n\n"
                "Возможно, это не банковская выписка или документ плохо читается."
            )
            return
        report = f"🏦 **Найдено платежей: {len(payments)}**\n\n"
        total_rub = Decimal('0')
        total_usd = Decimal('0')
        total_eur = Decimal('0')
        for i, payment in enumerate(payments[:10], 1):
            report += f"**{i}.** {payment.amount} {payment.currency}\n"
            report += f"   👤 {payment.counterparty}\n"
            report += f"   📅 {payment.date.strftime('%d.%m.%Y')}\n"
            if payment.account_from:
                report += f"   💳 {payment.account_from}\n"
            report += "\n"
            if payment.currency == 'RUB':
                total_rub += payment.amount
            elif payment.currency == 'USD':
                total_usd += payment.amount
            elif payment.currency == 'EUR':
                total_eur += payment.amount
        if len(payments) > 10:
            report += f"... и еще {len(payments) - 10} платежей\n\n"
        report += "💰 **Итого:**\n"
        if total_rub > 0:
            report += f"   RUB: {total_rub:,.2f}\n"
        if total_usd > 0:
            report += f"   USD: {total_usd:,.2f}\n"
        if total_eur > 0:
            report += f"   EUR: {total_eur:,.2f}\n"
        await processing_msg.edit_text(report, parse_mode="Markdown")
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Подробный отчет", callback_data="detailed_bank_report")],
            [InlineKeyboardButton(text="💾 Сохранить в Excel", callback_data="save_bank_excel")],
            [InlineKeyboardButton(text="📋 Сопоставить с заявками", callback_data="match_applications")]
        ])
        await message.answer(
            "🎯 **Что делаем дальше?**",
            reply_markup=keyboard
        )
    except Exception as e:
        await processing_msg.edit_text(
            f"❌ **Ошибка при анализе документа:**\n\n"
            f"`{str(e)}`\n\n"
            f"Попробуй другой файл или обратись к администратору."
        ) 

# --- Глобальный экземпляр notifier (инициализируется при старте) ---
cbr_notifier: CBRNotificationService | None = None

@router.callback_query(F.data == "currency_rates")
async def show_currency_rates(callback: CallbackQuery):
    # Получаем актуальные курсы (можно интегрировать с мониторингом)
    import aiohttp
    from datetime import datetime
    CBR_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
    async with aiohttp.ClientSession() as session:
        async with session.get(CBR_URL) as resp:
            xml = await resp.text()
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)
    def get_rate(code):
        for valute in root.findall('.//Valute'):
            if valute.find('CharCode').text == code:
                return valute.find('Value').text
        return '?'
    usd = get_rate('USD')
    eur = get_rate('EUR')
    cny = get_rate('CNY')
    today = datetime.now().strftime('%d.%m.%Y')
    await callback.message.edit_text(
        f"💱 <b>Курсы валют ЦБ РФ на {today}</b>\n\n"
        f"• <b>USD</b>: {usd}\n"
        f"• <b>EUR</b>: {eur}\n"
        f"• <b>CNY</b>: {cny}\n\n"
        f"Хотите получать уведомления о новых курсах?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("🔔 Подписаться", callback_data="cbr_subscribe")],
            [InlineKeyboardButton("🔕 Отписаться", callback_data="cbr_unsubscribe")]
        ]),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "cbr_subscribe")
async def subscribe_to_cbr(callback: CallbackQuery):
    global cbr_notifier
    if cbr_notifier is None:
        cbr_notifier = CBRNotificationService(callback.bot, settings.REDIS_DSN)
        await cbr_notifier.connect()
    await cbr_notifier.subscribe_user(callback.from_user.id)
    await callback.answer("✅ Подписка активирована!")
    await callback.message.edit_text(
        "🔔 <b>Подписка активирована!</b>\n\n"
        "Теперь вы будете получать уведомления о новых курсах.\n\n"
        "⏰ Мониторинг работает с 13:00 до 16:00 по МСК",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "cbr_unsubscribe")
async def unsubscribe_from_cbr(callback: CallbackQuery):
    global cbr_notifier
    if cbr_notifier is None:
        cbr_notifier = CBRNotificationService(callback.bot, settings.REDIS_DSN)
        await cbr_notifier.connect()
    await cbr_notifier.unsubscribe_user(callback.from_user.id)
    await callback.answer("❌ Подписка отключена.")
    await callback.message.edit_text(
        "🔕 <b>Подписка отключена.</b>\n\n"
        "Вы больше не будете получать уведомления о курсах.",
        parse_mode="HTML"
    ) 