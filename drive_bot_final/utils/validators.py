from pathlib import Path
from typing import List
import re

ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.txt'}
DANGEROUS_EXTENSIONS = {'.exe', '.bat', '.cmd', '.scr', '.com', '.pif'}

def validate_file_upload(filename: str, file_size: int, max_size_mb: int) -> List[str]:
    errors = []
    file_ext = Path(filename).suffix.lower()
    if file_ext in DANGEROUS_EXTENSIONS:
        errors.append(f"Опасное расширение файла: {file_ext}")
    elif file_ext not in ALLOWED_EXTENSIONS:
        errors.append(f"Неподдерживаемое расширение: {file_ext}")
    max_size_bytes = max_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        errors.append(f"Размер файла превышает {max_size_mb}MB")
    if not filename or len(filename) > 255:
        errors.append("Недопустимое имя файла")
    return errors

def validate_filename(filename: str, file_bytes: bytes) -> tuple[bool, str, str]:
    """
    Проверяет имя файла по шаблону и возвращает (валидно, причина, рекомендуемое имя).
    Если имя невалидно, рекомендуемое имя формируется на основе анализа содержимого (заглушка).
    """
    # Явный шаблон: буквы латиницы, кириллицы (включая Ёё), цифры, дефис, подчёркивание
    part = r'[A-Za-zА-Яа-яЁё0-9_-]+'
    pattern = rf'^{part}_{part}_{part}_\d+_\d{{6}}\.[a-zA-Z0-9]+$'
    if re.fullmatch(pattern, filename):
        return True, '', filename
    ext = Path(filename).suffix
    suggested = f'Документ_тип_номер_дата{ext}'
    return False, 'Имя не соответствует шаблону Принципал_Агент_тип_номер_дата.расширение', suggested 