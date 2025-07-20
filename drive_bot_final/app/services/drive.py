from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from app.config import settings
from app.services.audit import log_operation
from app.config import settings
import functools
import asyncio
import logging
import random
import structlog
log = structlog.get_logger(__name__)
log.info("drive_scopes", scopes=settings.drive_scopes)

SCOPES = ["https://www.googleapis.com/auth/drive"]


# Создаём credentials для User OAuth2
creds = Credentials(
    token=None,  # access_token, если есть, иначе refresh_token будет использован
    refresh_token=settings.gdrive_refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=settings.gdrive_client_id,
    client_secret=settings.gdrive_client_secret,
    scopes=[settings.drive_scopes] if isinstance(settings.drive_scopes, str) else settings.drive_scopes
)
drive = build("drive", "v3", credentials=creds)

FOLDER_MIME = "application/vnd.google-apps.folder"

async def gdrive_request_with_backoff(func, *args, max_retries=5, **kwargs):
    for attempt in range(max_retries):
        try:
            result = await func(*args, **kwargs)
            log.info("gdrive_request_success", func=func.__name__, attempt=attempt)
            return result
        except Exception as e:
            log.warning("gdrive_request_retry", func=func.__name__, attempt=attempt, error=str(e))
            await asyncio.sleep(2 ** attempt + random.random())
    log.error("gdrive_request_failed", func=func.__name__, error=str(e))
    raise

# --- run_sync: safe for async context ---
def run_sync(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

__all__ = [
    "drive",
    "FOLDER_MIME",
    "run_sync",
    "ensure_folders",
    "upload_to_gdrive",
    "parse_filename_to_path",
    # ... другие экспортируемые функции ...
]

async def _find_child_folder(parent_id: str, title: str) -> str | None:
    q = (
        f"'{parent_id}' in parents and name = '{title}' and mimeType = '{FOLDER_MIME}' "
        "and trashed = false"
    )
    res = await gdrive_request_with_backoff(run_sync, drive.files().list(q=q, spaces="drive", fields="files(id)").execute)
    files = res.get("files", [])
    return files[0]["id"] if files else None

async def _create_child_folder(parent_id: str, title: str) -> str:
    body = {"name": title, "mimeType": FOLDER_MIME, "parents": [parent_id]}
    res = await gdrive_request_with_backoff(run_sync, drive.files().create(body=body, fields="id").execute)
    return res["id"]

async def ensure_folders(path_parts):
    """Ensure nested folders exist under root, return id of the deepest one."""
    parent = settings.gdrive_root_folder
    for part in path_parts:
        if not part:
            continue
        child = await _find_child_folder(parent, part)
        if child is None:
            child = await _create_child_folder(parent, part)
        parent = child
    return parent  # id of the last folder in chain

@log_operation
async def list_folders():
    res = drive.files().list(q=f"'{settings.gdrive_root_folder}' in parents and mimeType = 'application/vnd.google-apps.folder'", fields="files(name, id, size)").execute()
    return [(f["name"], f.get("size", "?")) for f in res.get("files", [])]

@log_operation
async def upload_file(bytestream, name):
    media = {"name": name, "parents": [settings.gdrive_root_folder]}
    file = await gdrive_request_with_backoff(run_sync, drive.files().create(body=media, media_body=bytestream, fields="id").execute)
    return file["id"] 