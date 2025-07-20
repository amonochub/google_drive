
import io, logging, tempfile, os, fitz, pytesseract
from PIL import Image
from pdf2image import convert_from_path
from concurrent.futures import ThreadPoolExecutor
import os
import aiofiles
import structlog
log = structlog.get_logger(__name__)

def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Универсальный извлекатель текста из PDF, DOCX и изображений.
    """
    import io
    import fitz  # pymupdf
    from pdf2image import convert_from_bytes
    import pytesseract
    from docx import Document

    try:
        ext = filename.lower().split('.')[-1]
        if ext == "pdf":
            # PDF: пробуем pymupdf, если не получилось — OCR
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                text = ""
                for page in doc:
                    text += page.get_text()
                if text.strip():
                    log.info("pdf_text_extracted", filename=filename, ext=ext)
                    return text
            except Exception:
                pass
            # OCR по страницам
            images = convert_from_bytes(file_bytes)
            log.info("pdf_text_extracted", filename=filename, ext=ext, pages=len(images))
            return "\n".join(pytesseract.image_to_string(img, lang="rus+eng") for img in images)
        elif ext in ("jpg", "jpeg", "png"):
            from PIL import Image
            img = Image.open(io.BytesIO(file_bytes))
            log.info("image_text_extracted", filename=filename, ext=ext)
            return pytesseract.image_to_string(img, lang="rus+eng")
        elif ext == "docx":
            doc = Document(io.BytesIO(file_bytes))
            log.info("docx_text_extracted", filename=filename, ext=ext)
            return "\n".join([p.text for p in doc.paragraphs])
        else:
            log.warning("unsupported_filetype", filename=filename, ext=ext)
            return ""
    except Exception as e:
        log.error("ocr_failed", filename=filename, error=str(e))
        return ""

async def run_ocr(file_path: str) -> str:
    """
    Асинхронно извлекает текст из файла по пути file_path (PDF, DOCX, изображения).
    """
    filename = os.path.basename(file_path)
    async with aiofiles.open(file_path, "rb") as f:
        file_bytes = await f.read()
    return extract_text(file_bytes, filename)

def detect_language(text: str) -> str:
    import re
    if re.search(r'[а-яА-Я]', text):
        return "ru"
    elif re.search(r'[a-zA-Z]', text):
        return "en"
        return "unknown"