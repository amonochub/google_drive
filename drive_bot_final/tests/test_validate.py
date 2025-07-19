from app.services.reporter import validate_doc, build_report
import tempfile

def test_validate_doc_and_report(monkeypatch):
    # Мокаем extract_pairs, чтобы не зависеть от реальных файлов
    monkeypatch.setattr("app.services.reporter.extract_pairs", lambda path: [("A", "B"), ("C", "C")])
    monkeypatch.setattr("app.services.reporter.compare_tokens", lambda l, r: ["diff"] if l != r else [])
    monkeypatch.setattr("app.services.reporter.highlight_diffs", lambda src, misses: src+"_patched")

    with tempfile.NamedTemporaryFile(suffix=".docx") as tmp:
        missings, patched = validate_doc(tmp.name)
        assert missings
        report = build_report(missings)
        assert "Левая" in report and "Правая" in report
        assert patched.endswith("_patched") 