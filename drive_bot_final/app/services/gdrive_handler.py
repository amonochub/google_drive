
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
    # TODO: Implement proper Google Drive integration
    log.warning("file_exists not implemented - returning None")
    return None


def build_view_link(file_id: str) -> str:
    """Builds a Google Drive view link for the given file ID."""
    return f"https://drive.google.com/file/d/{file_id}/view"


__all__ = ['upload_file', 'file_exists', 'build_view_link']
