import os
import re
from app.config import settings
from app.utils.filename_parser import SUPPORTED_EXTS

DANGEROUS_CHARS = r'[<>:"/\\|?*]'  # Windows/Unix запрещённые символы

class FileValidationError(Exception):
    pass

def validate_file(filename: str, file_size: int) -> None:
    ext = filename.lower().rsplit('.', 1)[-1]
    if ext not in SUPPORTED_EXTS:
        raise FileValidationError(f"Недопустимое расширение файла: .{ext}")
    if file_size > settings.max_file_size_mb * 1024 * 1024:
        raise FileValidationError(f"Файл слишком большой: {file_size/(1024*1024):.2f} МБ")
    if re.search(DANGEROUS_CHARS, filename):
        raise FileValidationError("Имя файла содержит опасные символы") 