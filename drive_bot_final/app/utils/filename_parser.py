import re
from dataclasses import dataclass
from typing import Optional, List
import pathlib
import logging
import unicodedata

__all__ = ["FilenameInfo", "parse_filename", "validate_filename", "sanitize_filename", "FilenameValidationError"]

# Максимальная длина имени файла (без пути)
MAX_FILENAME_LENGTH = 255
# Максимальная длина каждого компонента имени
MAX_COMPONENT_LENGTH = 100

SUPPORTED_EXTS = {"pdf", "docx", "doc", "xlsx", "xls", "txt", "png", "jpeg", "jpg", "tiff", "tif"}
DOC_TYPES = [
    "договор", "агентский_договор", "агентский-договор", "поручение", "акт"
]
DOC_TYPES_RGX = "|".join([dt.replace("_", "[_-]") for dt in DOC_TYPES])

# Символы, запрещенные в именах файлов (Windows + дополнительные)
FORBIDDEN_CHARS = r'[<>:"/\\|?*\x00-\x1f]'
# Зарезервированные имена файлов в Windows
RESERVED_NAMES = {
    "con", "prn", "aux", "nul", "com1", "com2", "com3", "com4", "com5", 
    "com6", "com7", "com8", "com9", "lpt1", "lpt2", "lpt3", "lpt4", 
    "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"
}

# Гибкая регулярка: principal[_agent]_doctype_number_date.ext
FILE_RE = re.compile(
    rf"^([\w\- ]+?)(?:_([\w\- ]+?))?_({DOC_TYPES_RGX})_(\d+)_((?:\d{{6}}|\d{{8}}))(?:\.(\w+))?$",
    re.IGNORECASE
)

class FilenameValidationError(Exception):
    """Исключение для ошибок валидации имени файла"""
    pass

@dataclass
class FilenameInfo:
    principal: str
    agent: Optional[str]
    doctype: str
    number: str
    date: str
    ext: str

    def __post_init__(self):
        """Валидация данных после создания экземпляра"""
        self._validate_components()

    def _validate_components(self):
        """Валидация компонентов имени файла"""
        if not self.principal or not self.principal.strip():
            raise FilenameValidationError("Принципал не может быть пустым")
        
        if len(self.principal) > MAX_COMPONENT_LENGTH:
            raise FilenameValidationError(f"Принципал слишком длинный (максимум {MAX_COMPONENT_LENGTH} символов)")
        
        if self.agent and len(self.agent) > MAX_COMPONENT_LENGTH:
            raise FilenameValidationError(f"Агент слишком длинный (максимум {MAX_COMPONENT_LENGTH} символов)")
        
        if not self.doctype or not self.doctype.strip():
            raise FilenameValidationError("Тип документа не может быть пустым")
        
        if not self.number or not self.number.strip():
            raise FilenameValidationError("Номер документа не может быть пустым")
        
        if not self.date or not self.date.strip():
            raise FilenameValidationError("Дата не может быть пустой")
        
        if not self.ext or self.ext.lower() not in SUPPORTED_EXTS:
            raise FilenameValidationError(f"Неподдерживаемое расширение файла: {self.ext}")
        
        # Проверка формата даты
        if not re.match(r'^\d{6}$|^\d{8}$', self.date):
            raise FilenameValidationError("Дата должна быть в формате ГГММДД или ГГГГММДД")

    @property
    def full_filename(self) -> str:
        """Полное имя файла"""
        parts = [self.principal]
        if self.agent:
            parts.append(self.agent)
        parts.extend([self.doctype, self.number, self.date])
        return "_".join(parts) + f".{self.ext}"

    @property
    def gdrive_path(self) -> str:
        parts = [self.principal]
        if self.agent:
            parts.append(self.agent)
        parts.append(self.doctype)
        return "/".join(parts) + f"/{self.number}_{self.date}"


def sanitize_filename(filename: str) -> str:
    """
    Санитизация имени файла для безопасности
    
    Args:
        filename: Исходное имя файла
        
    Returns:
        Очищенное имя файла
        
    Raises:
        FilenameValidationError: Если имя файла невозможно очистить
    """
    if not filename or not filename.strip():
        raise FilenameValidationError("Имя файла не может быть пустым")
    
    # Удаление управляющих символов
    filename = ''.join(char for char in filename if unicodedata.category(char)[0] != 'C' or char in '\t\n\r')
    
    # Удаление запрещенных символов
    filename = re.sub(FORBIDDEN_CHARS, '_', filename)
    
    # Удаление точек в начале и конце (скрытые файлы и проблемы Windows)
    filename = filename.strip('.')
    
    # Ограничение длины
    if len(filename) > MAX_FILENAME_LENGTH:
        name, ext = pathlib.Path(filename).stem, pathlib.Path(filename).suffix
        max_name_length = MAX_FILENAME_LENGTH - len(ext)
        name = name[:max_name_length]
        filename = name + ext
    
    # Проверка зарезервированных имен
    name_without_ext = pathlib.Path(filename).stem.lower()
    if name_without_ext in RESERVED_NAMES:
        filename = f"file_{filename}"
    
    if not filename or filename.isspace():
        raise FilenameValidationError("Имя файла становится пустым после очистки")
    
    return filename


def validate_filename(filename: str) -> List[str]:
    """
    Валидация имени файла
    
    Args:
        filename: Имя файла для проверки
        
    Returns:
        Список ошибок валидации (пустой список если ошибок нет)
    """
    errors = []
    
    if not filename or not filename.strip():
        errors.append("Имя файла не может быть пустым")
        return errors
    
    # Проверка длины
    if len(filename) > MAX_FILENAME_LENGTH:
        errors.append(f"Имя файла слишком длинное (максимум {MAX_FILENAME_LENGTH} символов)")
    
    # Проверка запрещенных символов
    if re.search(FORBIDDEN_CHARS, filename):
        errors.append("Имя файла содержит запрещенные символы: < > : \" / \\ | ? * или управляющие символы")
    
    # Проверка точек в начале и конце
    if filename.startswith('.') or filename.endswith('.'):
        errors.append("Имя файла не должно начинаться или заканчиваться точкой")
    
    # Проверка зарезервированных имен
    name_without_ext = pathlib.Path(filename).stem.lower()
    if name_without_ext in RESERVED_NAMES:
        errors.append(f"'{name_without_ext}' является зарезервированным именем")
    
    # Проверка расширения
    ext = pathlib.Path(filename).suffix.lstrip('.').lower()
    if ext and ext not in SUPPORTED_EXTS:
        errors.append(f"Неподдерживаемое расширение файла: {ext}")
    
    # Проверка на только пробелы
    if filename.isspace():
        errors.append("Имя файла не может состоять только из пробелов")
    
    return errors


def parse_filename(filename: str) -> Optional[FilenameInfo]:
    """
    Парсинг имени файла согласно шаблону
    
    Args:
        filename: Имя файла для парсинга
        
    Returns:
        FilenameInfo или None если парсинг не удался
        
    Raises:
        FilenameValidationError: Если данные не прошли валидацию
    """
    logger = logging.getLogger("filename_parser")
    
    if not filename:
        logger.warning("Пустое имя файла")
        return None
    
    # Санитизация имени файла
    try:
        filename = sanitize_filename(filename)
    except FilenameValidationError as e:
        logger.warning(f"Ошибка санитизации файла {filename}: {e}")
        return None
    
    # Валидация имени файла
    validation_errors = validate_filename(filename)
    if validation_errors:
        logger.warning(f"Ошибки валидации файла {filename}: {'; '.join(validation_errors)}")
        return None
    
    name = pathlib.Path(filename).stem
    # Удаление суффиксов типа " (1)", " (2)" которые добавляются при дублировании
    name = re.sub(r'\s*\(\d+\)$', '', name)
    ext = pathlib.Path(filename).suffix.lstrip('.').lower()
    
    logger.debug(f"Парсинг: filename={filename}, name={name}, ext={ext}")
    
    # Попытка сопоставления с регулярным выражением
    match = FILE_RE.match(name + '.' + ext)
    if not match:
        logger.debug(f"Регулярное выражение не совпало для {name}.{ext}")
        return None
    
    principal, agent, doctype, number, date, ext_found = match.groups()
    logger.debug(f"Извлечено: principal={principal}, agent={agent}, doctype={doctype}, "
                f"number={number}, date={date}, ext={ext_found or ext}")
    
    # Использование найденного расширения из regex или исходного
    ext = ext_found or ext
    
    if ext not in SUPPORTED_EXTS:
        logger.debug(f"Расширение {ext} не поддерживается")
        return None
    
    try:
        return FilenameInfo(
            principal=principal.strip(),
            agent=agent.strip() if agent else None,
            doctype=doctype.lower().replace("-", "_").replace(" ", "_"),
            number=number,
            date=date,
            ext=ext,
        )
    except FilenameValidationError as e:
        logger.warning(f"Ошибка валидации компонентов файла {filename}: {e}")
        return None 