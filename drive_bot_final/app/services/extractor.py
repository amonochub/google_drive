import pdfplumber, docx
from pathlib import Path

def extract_pairs(path: str) -> list[tuple[str, str]]:
    if path.endswith(".pdf"):
        return _extract_pdf(path)
    return _extract_docx(path)

def _extract_docx(p: str):
    doc = docx.Document(p)
    pairs = []
    for tbl in doc.tables:
        for row in tbl.rows:
            if len(row.cells) >= 2:
                pairs.append((row.cells[0].text, row.cells[1].text))
    return pairs

def _extract_pdf(p: str):
    pairs = []
    with pdfplumber.open(p) as pdf:
        for page in pdf.pages:
            for tbl in (page.extract_tables() or []):
                for row in tbl:
                    if len(row) >= 2:
                        pairs.append((row[0] or "", row[1] or ""))
    return pairs
