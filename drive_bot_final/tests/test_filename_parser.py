import pytest
from app.utils.filename_parser import (
    parse_filename, 
    validate_filename, 
    sanitize_filename, 
    FilenameValidationError
)

@pytest.mark.parametrize(
    "name,principal,agent,doctype,number,date",
    [
        (
            "Альфатрекс_Валиент_Поручение_54_280525.pdf",
            "Альфатрекс",
            "Валиент",
            "поручение",
            "54",
            "280525",
        ),
        (
            "Рексен_Велиент_Договор_1_230525.docx",
            "Рексен",
            "Велиент",
            "договор",
            "1",
            "230525",
        ),
        (
            "Демирекс_Валиент_Акт_1_20250530.pdf",
            "Демирекс",
            "Валиент",
            "акт",
            "1",
            "20250530",
        ),
        (
            "Компания_договор_123_240101.pdf",
            "Компания",
            None,
            "договор",
            "123",
            "240101",
        ),
    ],
)
def test_parser(name, principal, agent, doctype, number, date):
    info = parse_filename(name)
    assert info is not None
    assert info.principal == principal
    assert info.agent == agent
    assert info.doctype == doctype
    assert info.number == number
    assert info.date == date
    assert info.gdrive_path.startswith(principal)


@pytest.mark.parametrize(
    "filename,expected_errors",
    [
        ("valid_file.pdf", []),  # Валидный файл
        ("", ["Имя файла не может быть пустым"]),  # Пустое имя
        ("a" * 300 + ".pdf", ["Имя файла слишком длинное (максимум 255 символов)"]),  # Слишком длинный
        ("file<with>bad:chars.pdf", ["Имя файла содержит запрещенные символы: < > : \" / \\ | ? * или управляющие символы"]),  # Запрещенные символы
        (".hidden_file.pdf", ["Имя файла не должно начинаться или заканчиваться точкой"]),  # Начинается с точки
        ("file_name.", ["Имя файла не должно начинаться или заканчиваться точкой"]),  # Заканчивается точкой
        ("con.pdf", ["'con' является зарезервированным именем"]),  # Зарезервированное имя
        ("file.xyz", ["Неподдерживаемое расширение файла: xyz"]),  # Неподдерживаемое расширение
        ("   ", ["Имя файла не может состоять только из пробелов"]),  # Только пробелы
    ],
)
def test_validate_filename(filename, expected_errors):
    errors = validate_filename(filename)
    assert errors == expected_errors


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("normal_file.pdf", "normal_file.pdf"),  # Нормальный файл
        ("file<with>bad:chars.pdf", "file_with_bad_chars.pdf"),  # Замена запрещенных символов
        (".hidden_file.pdf", "hidden_file.pdf"),  # Удаление точки в начале
        ("file_name.", "file_name"),  # Удаление точки в конце
        ("con.pdf", "file_con.pdf"),  # Обработка зарезервированного имени
    ],
)
def test_sanitize_filename(filename, expected):
    result = sanitize_filename(filename)
    assert result == expected


def test_sanitize_filename_empty():
    with pytest.raises(FilenameValidationError, match="Имя файла не может быть пустым"):
        sanitize_filename("")


def test_sanitize_filename_becomes_empty():
    with pytest.raises(FilenameValidationError, match="Имя файла становится пустым после очистки"):
        sanitize_filename("...")


def test_filename_info_validation():
    """Тест валидации компонентов FilenameInfo"""
    # Валидные данные
    info = parse_filename("Компания_Агент_договор_123_240101.pdf")
    assert info is not None
    
    # Тест полного имени файла
    assert info.full_filename == "Компания_Агент_договор_123_240101.pdf"


def test_parse_filename_with_duplicate_suffix():
    """Тест парсинга файлов с суффиксами дублирования"""
    info = parse_filename("Компания_договор_123_240101 (1).pdf")
    assert info is not None
    assert info.principal == "Компания"
    assert info.number == "123"


def test_parse_filename_invalid():
    """Тест парсинга невалидных файлов"""
    # Неподдерживаемый формат
    assert parse_filename("random_file.pdf") is None
    
    # Неподдерживаемое расширение
    assert parse_filename("Компания_договор_123_240101.xyz") is None
    
    # Пустое имя
    assert parse_filename("") is None 