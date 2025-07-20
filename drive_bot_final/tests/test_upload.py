import pytest
from unittest.mock import AsyncMock, patch
from app.handlers.upload import UploadResult, FileInfo
import asyncio

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

@pytest.mark.asyncio
async def test_batch_upload_success():
    # Мокаем upload_file и ensure_folders
    with patch("app.services.drive.upload_file", new=AsyncMock(return_value="fileid123")), \
         patch("app.services.drive.ensure_folders", new=AsyncMock(return_value="folderid123")):
        class DummyMsg:
            def __init__(self):
                self.answered = []
                self.bot = AsyncMock()
            async def answer(self, text, **kwargs):
                self.answered.append(text)
                return self
            async def edit_text(self, text, **kwargs):
                self.answered.append(text)
                return self
        msg = DummyMsg()
        fi = FileInfo(file_id="f1", orig_name="Alpha_Beta_Type_42_20250101.pdf", guessed=None, status="ok")
        from app.handlers.upload import cb_upload
        call = AsyncMock()
        call.from_user.id = 123
        call.message = msg
        from app.handlers.upload import user_batches
        user_batches[123] = [fi]
        await cb_upload(call)
        assert any("загружено" in t or "Загрузка завершена" in t for t in msg.answered)

@pytest.mark.asyncio
async def test_batch_upload_error():
    # Мокаем upload_file с ошибкой и ensure_folders
    with patch("app.services.drive.upload_file", new=AsyncMock(side_effect=Exception("fail!"))), \
         patch("app.services.drive.ensure_folders", new=AsyncMock(return_value="folderid123")):
        class DummyMsg:
            def __init__(self):
                self.answered = []
                self.bot = AsyncMock()
            async def answer(self, text, **kwargs):
                self.answered.append(text)
                return self
            async def edit_text(self, text, **kwargs):
                self.answered.append(text)
                return self
        msg = DummyMsg()
        fi = FileInfo(file_id="f2", orig_name="Alpha_Beta_Type_42_20250101.pdf", guessed=None, status="ok")
        from app.handlers.upload import cb_upload, user_batches
        call = AsyncMock()
        call.from_user.id = 456
        call.message = msg
        user_batches[456] = [fi]
        await cb_upload(call)
        assert any("ошибка" in t or "Не удалось загрузить" in t for t in msg.answered)

@pytest.mark.asyncio
async def test_batch_upload_manual():
    # Мокаем upload_file и ensure_folders
    with patch("app.services.drive.upload_file", new=AsyncMock(return_value="fileid123")), \
         patch("app.services.drive.ensure_folders", new=AsyncMock(return_value="folderid123")):
        class DummyMsg:
            def __init__(self):
                self.answered = []
                self.bot = AsyncMock()
            async def answer(self, text, **kwargs):
                self.answered.append(text)
                return self
            async def edit_text(self, text, **kwargs):
                self.answered.append(text)
                return self
        msg = DummyMsg()
        fi = FileInfo(file_id="f3", orig_name="badname.pdf", guessed=None, status="ok")
        from app.handlers.upload import cb_upload, user_batches
        call = AsyncMock()
        call.from_user.id = 789
        call.message = msg
        user_batches[789] = [fi]
        await cb_upload(call)
        assert any("не удалось определить папку" in t.lower() for t in msg.answered) 

@pytest.mark.asyncio
async def test_batch_upload_invalid_extension():
    with patch("app.services.drive.upload_file", new=AsyncMock(return_value="fileid123")), \
         patch("app.services.drive.ensure_folders", new=AsyncMock(return_value="folderid123")):
        class DummyMsg:
            def __init__(self):
                self.answered = []
                self.bot = AsyncMock()
            async def answer(self, text, **kwargs):
                self.answered.append(text)
                return self
            async def edit_text(self, text, **kwargs):
                self.answered.append(text)
                return self
        msg = DummyMsg()
        fi = FileInfo(file_id="f4", orig_name="Alpha_Beta_Type_42_20250101.exe", guessed=None, status="ok")
        from app.handlers.upload import cb_upload, user_batches
        call = AsyncMock()
        call.from_user.id = 999
        call.message = msg
        user_batches[999] = [fi]
        await cb_upload(call)
        assert any("не принят" in t.lower() for t in msg.answered)

@pytest.mark.asyncio
async def test_batch_upload_dangerous_chars():
    with patch("app.services.drive.upload_file", new=AsyncMock(return_value="fileid123")), \
         patch("app.services.drive.ensure_folders", new=AsyncMock(return_value="folderid123")):
        class DummyMsg:
            def __init__(self):
                self.answered = []
                self.bot = AsyncMock()
            async def answer(self, text, **kwargs):
                self.answered.append(text)
                return self
            async def edit_text(self, text, **kwargs):
                self.answered.append(text)
                return self
        msg = DummyMsg()
        fi = FileInfo(file_id="f5", orig_name="bad<file>.pdf", guessed=None, status="ok")
        from app.handlers.upload import cb_upload, user_batches
        call = AsyncMock()
        call.from_user.id = 1001
        call.message = msg
        user_batches[1001] = [fi]
        await cb_upload(call)
        assert any("не принят" in t.lower() for t in msg.answered) 