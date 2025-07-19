
import io
import logging
import tempfile
import os
import fitz
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)
EXEC = ThreadPoolExecutor(max_workers=4)


def _img_ocr(img: Image.Image, lang: str = "rus+eng") -> str:
    return pytesseract.image_to_string(img, lang=lang)


def pdf_to_images(path: str) -> list[Image.Image]:
    """Сначала пробуем FitZ (быстрее), затем pdf2image."""
    try:
        doc = fitz.open(path)
        return [Image.frombytes("RGB", pix.size, pix.samples)
                for page in doc for pix in [page.get_pixmap(dpi=300)]]
    except Exception as e:
        log.warning("fitz_failed", exc_info=e)
        return convert_from_path(path, dpi=300)


def run_ocr(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in {".png", ".jpg", ".jpeg", ".tiff"}:
        text = _img_ocr(Image.open(path))
    elif ext == ".pdf":
        imgs = pdf_to_images(path)
        parts = list(EXEC.map(_img_ocr, imgs))
        text = "\n".join(parts)
    else:
        raise RuntimeError("Unsupported file for OCR")
    return text


# Add missing functions that are imported elsewhere
def extract_text(file_path: str) -> str:
    """Extract text from file using OCR."""
    return run_ocr(file_path)


def detect_language(text: str) -> str:
    """Simple language detection based on cyrillic characters."""
    cyrillic_chars = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
    total_chars = len([char for char in text if char.isalpha()])

    if total_chars == 0:
        return "unknown"

    cyrillic_ratio = cyrillic_chars / total_chars
    return "ru" if cyrillic_ratio > 0.5 else "en"
