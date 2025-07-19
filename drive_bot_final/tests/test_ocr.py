from app.services.ocr import extract_text

def test_extract_text_on_sample(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("Hello OCR!")

    text = extract_text(sample)
    assert "Hello" in text
