# drive_bot_final/smart_document_handler.py
from __future__ import annotations
import logging
from typing import Dict, Any, Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from prefix_router import PrefixRouter
from handlers.folder_manager import FolderManager
from handlers.gdrive_handler import GDriveHandler
import inspect
import re
from difflib import SequenceMatcher
from typing import Dict, Any, Optional
from docx import Document
import os

logger = logging.getLogger(__name__)


def extract_parameters(text: str) -> dict:
    patterns = {
        'contract_number': r'договор[а-я]* №\s*([\d\w\-]+)',
        'contract_date': r'от\s*«?(\d{1,2})[»"]?\s*\w+\s*202\d',
        'assignment_number': r'Поручени[ея]\s*№\s*([\d\w\-]+)',
        'principal': r'Принципал[а-я]*[:,]?\s*/?\s*(.+?)[\n\r]',
        'agent': r'Агент[а-я]*[:,]?\s*/?\s*(.+?)[\n\r]',
        'iban': r'IBAN[:\s]+([A-Z0-9]+)',
        'swift': r'SWIFT[:\s]+([A-Z0-9]+)',
        'amount': r'([\d\s]+[\.,]\d{2})\s*(RUB|EUR|USD)',
    }
    extracted = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            extracted[key] = match.group(1).strip()
        else:
            extracted[key] = 'не найден'
    return extracted

def compare_parameters(ru_params: dict, en_params: dict) -> str:
    messages = []
    for key in ru_params:
        ru_val = ru_params[key]
        en_val = en_params[key]
        if ru_val == 'не найден' and en_val == 'не найден':
            continue
        if ru_val != en_val:
            similarity = SequenceMatcher(None, ru_val, en_val).ratio()
            if similarity < 0.85:
                messages.append(f"❗️ Несовпадение параметра '{key}': RU='{ru_val}' EN='{en_val}'")
    if not messages:
        return "✅ Все ключевые параметры согласованы."
    return '\n'.join(messages)

def extract_text_from_pdf(path):
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def ocr_pdf_image(path):
    from pdf2image import convert_from_path
    import pytesseract
    images = convert_from_path(path)
    text = ""
    for image in images:
        text += pytesseract.image_to_string(image, lang='rus+eng')
    return text

def extract_text_from_image(img_path):
    from PIL import Image
    import pytesseract
    image = Image.open(img_path)
    return pytesseract.image_to_string(image, lang='rus+eng')

def analyze_any_document(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    text = ""
    if ext == ".docx":
        from docx import Document
        doc = Document(path)
        text = "\n".join(p.text for p in doc.paragraphs)
    elif ext == ".pdf":
        text = extract_text_from_pdf(path)
        if not text.strip():
            text = ocr_pdf_image(path)
    elif ext in [".jpg", ".jpeg", ".png"]:
        text = extract_text_from_image(path)
    else:
        return "❌ Неподдерживаемый формат файла."
    # Разделяем на RU/EN и сравниваем
    if "Moscow" in text:
        split_point = text.index("Moscow")
        ru_text = text[:split_point]
        en_text = text[split_point:]
    else:
        ru_text = text
        en_text = text
    ru_data = extract_parameters(ru_text)
    en_data = extract_parameters(en_text)
    result = compare_parameters(ru_data, en_data)
    return result, ru_data, en_data

class SmartDocumentHandler:
    def __init__(self, gdrive):
        self.gdrive = gdrive

    async def process(self, file_path: str, file_name: Optional[str] = None) -> Dict[str, Any]:
        try:
            result, ru_data, en_data = analyze_any_document(file_path)
            summary = (
                "🤖 <b>Анализ согласованности документа завершён</b>\n\n"
                f"{result}\n"
                f"<b>RU:</b> {ru_data}\n"
                f"<b>EN:</b> {en_data}\n"
                "\n👁 Проверьте соответствие реквизитов. Если документ OK — нажмите загрузить в Drive ⬇️"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Загрузить в Google Drive", callback_data="upload_now")],
                [InlineKeyboardButton(text="Главное меню", callback_data="menu_main")],
            ])
            return {
                "success": True,
                "message_text": summary,
                "keyboard": kb,
            }
        except Exception as e:
            logger.error(f"Ошибка при анализе документа: {e}")
            return {"success": False, "message_text": f"Ошибка анализа: {e}", "keyboard": None}