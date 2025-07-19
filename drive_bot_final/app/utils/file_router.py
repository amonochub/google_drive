
from pathlib import Path

def get_drive_path(filename: str) -> list[str]:
    """Return path segments based on prefix before first underscore."""
    stem = Path(filename).stem
    if "_" in stem:
        prefix, *_ = stem.split("_")
    else:
        prefix = "unsorted"
    return [prefix]

def determine_path(filename: str) -> str:
    """Возвращает строку-путь для файла по его имени (пример: по префиксу до первого _)."""
    stem = Path(filename).stem
    if "_" in stem:
        prefix, *_ = stem.split("_")
    else:
        prefix = stem
    return prefix
