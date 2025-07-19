import pytest

from app.utils.file_router import determine_path

@pytest.mark.parametrize(
    "filename, expected_part",
    [
        ("Invoice_123.pdf", "Invoice"),
        ("PRINCIPAL_AGENT_doc.docx", "PRINCIPAL"),
        ("Фото.jpg", "Фото"),
    ],
)
def test_determine_path_smoke(filename, expected_part):
    """
    Smoke-тест: функция возвращает строку с ожидаемым префиксом.
    """
    path = determine_path(filename)
    assert isinstance(path, str)
    assert expected_part.lower() in path.lower()
