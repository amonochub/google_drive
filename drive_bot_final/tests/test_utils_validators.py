import pytest
from utils.validators import validate_file_upload, validate_filename

def test_validate_file_upload_valid():
    errors = validate_file_upload("test.pdf", 1024, 10)
    assert errors == []

def test_validate_file_upload_dangerous():
    errors = validate_file_upload("virus.exe", 1024, 10)
    assert any("опасное" in e.lower() for e in errors)

def test_validate_file_upload_unsupported():
    errors = validate_file_upload("file.xyz", 1024, 10)
    assert any("неподдерживаемое" in e.lower() for e in errors)

def test_validate_file_upload_too_large():
    errors = validate_file_upload("test.pdf", 20 * 1024 * 1024, 10)
    assert any("размер файла" in e.lower() for e in errors)

def test_validate_file_upload_long_name():
    errors = validate_file_upload("a"*300+".pdf", 1024, 10)
    assert any("имя" in e.lower() for e in errors)

def test_validate_filename_valid():
    valid, reason, suggested = validate_filename("Альфа_Бета_Договор_1234_01012023.pdf", b"")
    assert valid
    assert reason == ''
    assert suggested == "Альфа_Бета_Договор_1234_01012023.pdf"

def test_validate_filename_invalid():
    valid, reason, suggested = validate_filename("badname.pdf", b"")
    assert not valid
    assert "шаблон" in reason.lower()
    assert suggested.startswith("Документ_тип_номер_дата") 