import pytest
from app.utils.filename_parser import parse_filename

@pytest.mark.parametrize(
    "name,principal,agent,doctype,number,date",
    [
        (
            "Альфатрекс_Валиент_Поручение_54_280525",
            "Альфатрекс",
            "Валиент",
            "поручение",
            "54",
            "280525",
        ),
        (
            "Рексен_Велиент_Договор_1_23.05.25",
            "Рексен",
            "Велиент",
            "договор",
            "1",
            "230525",
        ),
        (
            "Демирекс_Валиент_Акт_1_2025-05-30",
            "Демирекс",
            "Валиент",
            "акт",
            "1",
            "20250530",
        ),
    ],
)
def test_parser(name, principal, agent, doctype, number, date):
    info = parse_filename(name)
    assert info
    assert info.principal == principal
    assert info.agent == agent
    assert info.doctype == doctype
    assert info.number == number
    assert info.date == date
    assert info.gdrive_path.startswith(principal) 