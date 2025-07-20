import pytest
from app.utils.file_validation import validate_file, FileValidationError

def test_valid_file():
    validate_file("test.pdf", 1024)
    validate_file("test.docx", 1024)

def test_invalid_extension():
    with pytest.raises(FileValidationError):
        validate_file("test.exe", 1024)

def test_too_large():
    with pytest.raises(FileValidationError):
        validate_file("test.pdf", 100 * 1024 * 1024)  # 100 МБ

def test_dangerous_chars():
    with pytest.raises(FileValidationError):
        validate_file("bad<file>.pdf", 1024)
    with pytest.raises(FileValidationError):
        validate_file("bad|file.pdf", 1024) 