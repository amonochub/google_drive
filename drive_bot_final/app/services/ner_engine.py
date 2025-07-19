import spacy, unicodedata, re
from functools import lru_cache

_nlp = spacy.load("ru_core_news_lg")
DEF_LABELS = {"ORG", "PER", "DATE", "MONEY", "CARDINAL", "GPE"}

@lru_cache(1024)
def normalize(t: str) -> str:
    t = unicodedata.normalize("NFKC", t).lower()
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .,")

def get_entities(text: str, labels: set[str] = DEF_LABELS) -> set[str]:
    doc = _nlp(text)
    ents = {normalize(ent.text) for ent in doc.ents if ent.label_ in labels}
    return ents
