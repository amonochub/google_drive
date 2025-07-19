from app.services.gdrive_handler import upload_file

def test_upload_file_smoke(monkeypatch):
    # Подменяем network-часть заглушкой
    monkeypatch.setattr(upload_file, "__wrapped__", lambda *a, **kw: "fake_id")
    file_id = upload_file("dummy/path", b"123")
    assert file_id == "fake_id" 