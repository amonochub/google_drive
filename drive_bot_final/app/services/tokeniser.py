import re, unicodedata, transliterate

RE_NUM     = re.compile(r"\b\d{10,}\b")
RE_IBAN    = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,}\b")
RE_DATE    = re.compile(r"\d{2}\.\d{2}\.\d{4}")
RE_CURRENCY= re.compile(r"\d[\d\s.,]+\s?(EUR|USD|RUB|₽|€|\$)")

def normal(txt: str) -> str:
    txt = txt.lower()
    txt = unicodedata.normalize("NFKD", txt)
    return re.sub(r"\s+", "", txt)

def extract_tokens(s: str) -> set[str]:
    res = set()
    for r in (RE_NUM, RE_IBAN, RE_DATE, RE_CURRENCY):
        res |= set(r.findall(s))
    return {normal(t) for t in res}
