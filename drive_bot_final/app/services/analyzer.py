
import re, logging, textwrap
from collections import defaultdict
import structlog

log = structlog.get_logger(__name__)

R_PATTERNS = {
    "iban": r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}",
    "swift": r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?",
    "account": r"\b\d{10,20}\b",
    "number": r"№\s?\d+",
    "date": r"(?:0?[1-9]|[12][0-9]|3[01])[./-](?:0?[1-9]|1[0-2])[./-](?:\d{4})",
    "currency_amount": r"\d{1,3}(?:[ \u00A0]\d{3})*(?:[.,]\d{2})?\s?(?:EUR|USD|RUB|₽|€|\$)",
}

def extract_parameters(text: str) -> dict[str, list[str]]:
    try:
        res = defaultdict(list)
        for key, pattern in R_PATTERNS.items():
            for m in re.findall(pattern, text, flags=re.IGNORECASE):
                res[key].append(m.strip())
        log.info("parameters_extracted", keys=list(res.keys()), count=sum(len(v) for v in res.values()))
        return dict(res)
    except Exception as e:
        log.error("extract_parameters_failed", error=str(e))
        return {}

def compare_ru_en(ru_text: str, en_text: str) -> list[str]:
    issues = []
    ru_params = extract_parameters(ru_text)
    en_params = extract_parameters(en_text)
    for key in {"iban","swift","account","number","date"}:
        ru_val = ru_params.get(key, ["не найден"])[0]
        en_val = en_params.get(key, ["не найден"])[0]
        if ru_val != en_val:
            issues.append(f"Несовпадение {key}: RU='{ru_val}' EN='{en_val}'")
    return issues
