import re
from dataclasses import dataclass
from typing import Optional

__all__ = ["FilenameInfo", "parse_filename"]

SUPPORTED_EXTS = {"pdf", "docx", "doc", "xlsx", "xls", "txt", "png", "jpeg", "jpg", "tiff"}
DOC_TYPES = [
    "договор", "агентский_договор", "агентский-договор", "поручение", "акт"
]
DOC_TYPES_RGX = "|".join([dt.replace("_", "[_-]") for dt in DOC_TYPES])

# Обновлённая регулярка, разрешающая дату с точками и с дефисами
FILE_RE = re.compile(
    r'^(?P<principal>[А-Яа-яA-Za-z0-9]+)_'
    r'(?P<agent>[А-Яа-яA-Za-z0-9]+)_'
    r'(?P<doctype>[А-Яа-яA-Za-z0-9]+)_'
    r'(?P<number>\d+)_'
    r'(?P<date>\d{6}|\d{2}[.]\d{2}[.]\d{2}|\d{4}-\d{2}-\d{2})'
    r'\.[A-Za-z0-9]{2,4}$',  # расширение файла (.pdf, .docx и т. д.)
    re.IGNORECASE
)

@dataclass
class FilenameInfo:
    principal: str
    agent: str
    doctype: str
    number: str
    date: str
    gdrive_folder: str

def normalize_date(date_str: str) -> str:
    """Нормализация даты: 23.05.25 → 230525, 2025-05-30 → 20250530"""
    return date_str.replace('.', '').replace('-', '')

def parse_filename(filename: str) -> Optional[FilenameInfo]:
    """Основной парсер имени файла с расширенной поддержкой форматов дат"""
    match = FILE_RE.match(filename)
    if not match:
        return None
    gd = match.groupdict()
    normalized_date = normalize_date(gd["date"])
    # Защита от отсутствия года → fallback: 2025
    path_year = normalized_date[:4] if len(normalized_date) >= 6 else "2025"
    gdrive_folder = f"{gd['principal']}/{gd['doctype']}/{path_year}"
    return FilenameInfo(
        principal=gd["principal"],
        agent=gd["agent"],
        doctype=gd["doctype"].lower(),
        number=gd["number"],
        date=normalized_date,
        gdrive_folder=gdrive_folder
    ) 