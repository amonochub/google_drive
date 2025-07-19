
import io, logging, tempfile, os, fitz, pytesseract
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
