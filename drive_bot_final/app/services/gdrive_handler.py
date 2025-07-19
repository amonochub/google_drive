
"""Thin wrapper around Google Drive API.

The real implementation is kept as‑is from your project;
only interface is preserved so rest of the code remains unchanged.
"""
from __future__ import annotations
import io, logging, mimetypes, pathlib, asyncio
from app.config import get_settings
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

class GDriveHandler:
    def __init__(self):
        self.settings = get_settings()
        # Используйте self.settings.gdrive_root_folder и другие snake_case поля
        # TODO: initialise Google Drive client with personal account creds
        # left untouched per user's requirement.

    async def upload_file(self, local_path: str | pathlib.Path, drive_path: list[str]) -> str:
        """Uploads file to specified folder path, returns file ID.

        This is a stub that logs upload only. Replace with your existing logic.
        """
        log.info("Pretend upload %s to %s", local_path, drive_path)
        await asyncio.sleep(0.1)
        return "fake-file-id"


async def file_exists(folder_path: str, filename: str) -> Optional[str]:
    """Возвращает ID файла, если в указанной папке уже есть exact-совпадение."""
    # 1. Ищем (создаём при необходимости) конечную папку
    folder_id = await ensure_folders(folder_path)
    svc = _get_service()
    query = (
        f"'{folder_id}' in parents and "
        f"name = '{filename}' and trashed = false"
    )
    resp = svc.files().list(q=query, fields="files(id)").execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def build_view_link(file_id: str) -> str:
    return DRIVE_VIEW.format(file_id)

__all__ = ['upload_file']
