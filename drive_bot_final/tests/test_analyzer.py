
from app.services.analyzer import extract_parameters

def test_extract():
    text = "Оплата 1000 EUR, IBAN DE89370400440532013000"
    p = extract_parameters(text)
    assert p["iban"][0] == "DE89370400440532013000"
