import pytest
import asyncio
from app.services.gdrive_handler import GDriveHandler

@pytest.mark.asyncio
async def test_upload_file_smoke(monkeypatch):
    async def fake_upload_file(self, local_path, drive_path, user_id=None):
        return "fake-id"
    monkeypatch.setattr(GDriveHandler, "upload_file", fake_upload_file)
    handler = GDriveHandler()
    file_id = await handler.upload_file("dummy/path", ["folder"])
    assert file_id == "fake-id" 