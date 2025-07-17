import os
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from docx import Document
import re

def extract_text_from_docx(path: str) -> str:
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)

def extract_text_from_pdf(path: str) -> str:
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def ocr_pdf_image(path: str) -> str:
    images = convert_from_path(path)
    text = ""
    for image in images:
        text += pytesseract.image_to_string(image, lang="rus+eng")
    return text

def extract_text_from_image(path: str) -> str:
    image = Image.open(path)
    return pytesseract.image_to_string(image, lang="rus+eng")

def split_ru_en_blocks(text: str) -> tuple[str, str]:
    """
    Разделение текста на русский и английский блок.
    Простая эвристика: находим точку разделения по ключевым словам.
    """
    if "Moscow" in text:
        idx = text.find("Moscow")
        return text[:idx], text[idx:]
    # Если английский блок идёт первым
    if "Москва" in text:
        idx = text.find("Москва")
        return text[idx:], text[:idx]
    return text, text  # если не нашли — вернём полный дубликат

def extract_parameters(text: str) -> dict:
    patterns = {
        "iban": r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b",
        "swift": r"\b[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?\b",
        "account": r"\b(?:счет|account)[:\s\-]*([0-9]{8,})\b",
        "contract_number": r"(?:договор|contract)[^\d]{0,5}(\d+)",
        "contract_date": r"(?:от|dated)[^\d]{0,5}(\d{2}[./-]\d{2}[./-]\d{4})",
        "amount": r"(?:сумма|amount)[^\d]{0,5}([\d\s.,]+)",
        "principal": r"(?:принципал|principal)[^\n:]*[:\-\s]*([^\n]+)",
        "agent": r"(?:агент|agent)[^\n:]*[:\-\s]*([^\n]+)",
        "number": r"(?:номер поручения|assignment number)[^\d]{0,5}(\d+)",
        "date": r"(?:дата поручения|assignment date)[^\d]{0,5}(\d{2}[./-]\d{2}[./-]\d{4})",
    }
    extracted = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        extracted[key] = match.group(1).strip() if match else "не найден"
    return extracted

def compare_parameters(ru: dict, en: dict) -> str:
    differences = []
    for key in ru:
        if ru[key] != "не найден" and en[key] != "не найден":
            if ru[key].lower() != en[key].lower():
                differences.append(f"❗️ Несовпадение параметра '{key}': RU='{ru[key]}' EN='{en[key]}'")
    if not differences:
        return "✅ Все параметры совпадают!"
    else:
        return "\n".join(differences)

def analyze_document(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".docx":
            text = extract_text_from_docx(path)
        elif ext == ".pdf":
            text = extract_text_from_pdf(path)
            if not text.strip():
                text = ocr_pdf_image(path)
        elif ext in [".jpg", ".jpeg", ".png"]:
            text = extract_text_from_image(path)
        else:
            return "❌ Неподдерживаемый формат файла."
        ru_text, en_text = split_ru_en_blocks(text)
        ru_params = extract_parameters(ru_text)
        en_params = extract_parameters(en_text)
        result = "💡 Проверка двуязычной согласованности (ИИ):\n"
        result += compare_parameters(ru_params, en_params)
        result += "\n\n💡 DEBUG: Извлечённые параметры (RU):\n"
        for k, v in ru_params.items():
            result += f"{k}: {v}\n"
        result += "\n💡 DEBUG: Извлечённые параметры (EN):\n"
        for k, v in en_params.items():
            result += f"{k}: {v}\n"
        return result
    except Exception as e:
        return f"❌ Ошибка при анализе: {e}" 