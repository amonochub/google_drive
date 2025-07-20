from app.services.reporter import validate_doc, build_report
import tempfile
import pytest
from app.utils.file_validation import FileValidationError, validate_file

def test_validate_doc_and_report(monkeypatch):
    # Мокаем extract_pairs, чтобы обе пары были неравны
    monkeypatch.setattr("app.services.reporter.extract_pairs", lambda path: [("A", "B"), ("X", "Y")])
    monkeypatch.setattr("app.services.reporter.compare_tokens", lambda l, r: ["diff"] if l != r else [])
    monkeypatch.setattr("app.services.reporter.highlight_diffs", lambda src, misses: src+"_patched")
    monkeypatch.setattr("app.services.reporter.extract_tokens", lambda s: [s])

    with tempfile.NamedTemporaryFile(suffix=".docx") as tmp:
        missings, patched = validate_doc(tmp.name)
        assert missings and len(missings) == 2
        report = build_report(missings)
        assert "A" in report and "B" in report and "X" in report and "Y" in report
        assert patched.endswith("_patched") 

def test_validate_doc_invalid_extension(tmp_path):
    file = tmp_path / "badfile.exe"
    file.write_bytes(b"not a real exe")
    with pytest.raises(FileValidationError):
        validate_file(file.name, file.stat().st_size)

def test_validate_doc_dangerous_chars(tmp_path):
    file = tmp_path / "bad<file>.pdf"
    file.write_bytes(b"%PDF-1.4\n%EOF")
    with pytest.raises(FileValidationError):
        validate_file(file.name, file.stat().st_size)

def test_validate_doc_too_large(tmp_path):
    file = tmp_path / "big.pdf"
    file.write_bytes(b"%PDF-1.4\n" + b"0" * (100 * 1024 * 1024) + b"\n%%EOF")
    with pytest.raises(FileValidationError):
        validate_file(file.name, file.stat().st_size) 