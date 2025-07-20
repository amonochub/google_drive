import pytest
from app.utils.filename_parser import parse_filename, FilenameInfo

def test_date_normalization():
    from app.utils.filename_parser import normalize_date
    assert normalize_date("280525") == "280525"
    assert normalize_date("23.05.25") == "230525"
    assert normalize_date("2025-05-30") == "20250530"

@pytest.mark.parametrize(
    "filename,principal,agent,doctype,number,date",
    [
        ("Альфатрекс_Валиент_Поручение_54_280525.pdf", "Альфатрекс", "Валиент", "поручение", "54", "280525"),
        ("Рексен_Велиент_Договор_1_23.05.25.pdf", "Рексен", "Велиент", "договор", "1", "230525"),
        ("Демирекс_Валиент_Акт_1_2025-05-30.docx", "Демирекс", "Валиент", "акт", "1", "20250530"),
        ("Компания1_Компания2_Договор_1_280525.xlsx", "Компания1", "Компания2", "договор", "1", "280525"),
        ("Компания1_Компания2_Договор_1_23.05.25.pdf", "Компания1", "Компания2", "договор", "1", "230525"),
        ("Компания1_Компания2_Договор_1_2025-05-30.pdf", "Компания1", "Компания2", "договор", "1", "20250530"),
    ]
)
def test_parser(filename, principal, agent, doctype, number, date):
    info = parse_filename(filename)
    assert info is not None, f"Не удалось распарсить: {filename}"
    assert info.principal == principal
    assert info.agent == agent
    assert info.doctype == doctype
    assert info.number == number
    assert info.date == date

# Удаляем/комментируем тесты, связанные с parse_filename_flexible
def test_parser_edge_cases():
    # Проверяем, что некорректные имена не парсятся
    bad_names = [
        "InvalidName.pdf",
        "TooShort.pdf",
        "@#$%^&*().pdf",
        "Company1__Agent__Type__42__20250101.pdf",
        "Company  Agent  Type  42  20250101.pdf",
        "компания_агент_тип_номер_20251301.pdf",
        "компания_агент_тип_номер_20250230.pdf",
        "компания_агент_тип_номер_2025-02-30.pdf",
        "компания_агент_тип_номер_2025/02/30.pdf",
        "компания_агент_тип_номер_2025.02.30.pdf",
        "компания_агент_тип_номер_2025-13-01.pdf",
        "компания_агент_тип_номер_2025-00-01.pdf",
        "компания_агент_тип_номер_2025-01-00.pdf",
        "компания_агент_тип_номер_2025-01-32.pdf",
        "компания_агент_тип_номер_2025-01-1a.pdf",
        "компания_агент_тип_номер_2025-01-01-EXTRA.pdf",
        "компания_агент_тип_номер_.pdf",
        "компания_агент_тип_номер-.pdf",
        "компания_агент_тип-.pdf",
        "компания-агент-.pdf",
        "компания-.pdf",
        "公司_代理人_类型_42_20250101.pdf",
        "company@agent#type$42%20250101.pdf",
        "company_agent_type_42_20250101_extra_long_name_with_lots_of_segments.pdf",
    ]
    for name in bad_names:
        info = parse_filename(name)
        assert info is None, f"Ожидалась ошибка для '{name}'"

# test_flexible_parser удалён, так как функция больше не используется 