import docx
import pytest
from app.services.ocr import extract_text


def test_extract_text_on_sample(tmp_path):
    sample = tmp_path / "sample.docx"
    doc = docx.Document()
    doc.add_paragraph("Hello OCR!")
    doc.save(sample)
    text = extract_text(sample.read_bytes(), sample.name)
    assert "Hello" in text

def test_extract_text_invalid_extension(tmp_path):
    file = tmp_path / "badfile.exe"
    file.write_bytes(b"not a real exe")
    text = extract_text(file.read_bytes(), file.name)
    assert text == ""

def test_extract_text_empty_file(tmp_path):
    file = tmp_path / "empty.pdf"
    file.write_bytes(b"")
    text = extract_text(file.read_bytes(), file.name)
    assert text == ""

def test_extract_text_dangerous_filename(tmp_path):
    file = tmp_path / "bad<file>.pdf"
    file.write_bytes(b"%PDF-1.4\n%EOF")
    text = extract_text(file.read_bytes(), file.name)
    assert text == ""

def test_extract_text_pdf_unreadable(tmp_path):
    file = tmp_path / "unreadable.pdf"
    file.write_bytes(b"%PDF-1.4\nnot really a pdf\n%%EOF")
    text = extract_text(file.read_bytes(), file.name)
    assert text == "" 

def test_extract_text_too_large(tmp_path):
    file = tmp_path / "big.pdf"
    file.write_bytes(b"%PDF-1.4\n" + b"0" * (25 * 1024 * 1024) + b"\n%%EOF")
    text = extract_text(file.read_bytes(), file.name)
    assert text == "" 