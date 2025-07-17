from config import settings
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
import logging
import io
from tenacity import retry, stop_after_attempt, wait_exponential
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os
import asyncio
from utils.cache import TTLCache

logger = logging.getLogger(__name__)

class GDriveException(Exception):
    pass
class QuotaExceededException(GDriveException):
    pass
class FolderNotFoundException(GDriveException):
    pass

class GDriveHandler:
    def __init__(self, settings_=None):
        self.settings = settings_ or settings
        SCOPES = ['https://www.googleapis.com/auth/drive']
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        else:
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        self.service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        # --- TTLCache ---
        self._folders_cache = TTLCache(3600)  # 1 час
        self._folder_content_cache = TTLCache(1800)  # 30 мин
        self._file_meta_cache = TTLCache(900)  # 15 мин

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def list_folders(self, parent_id=None, limit=10):
        parent_id = parent_id or self.settings.root_folder_id
        cache_key = f"folders:{parent_id}:{limit}"
        cached = self._folders_cache.get(cache_key)
        if cached is not None:
            return cached[:limit] if limit else cached
        try:
            folders = []
            page_token = None
            while True:
                results = await asyncio.to_thread(
                    lambda: self.service.files().list(
                        q=f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                        pageSize=1000,
                        fields="nextPageToken, files(id, name)",
                        pageToken=page_token
                    ).execute()
                )
                folders.extend(results.get('files', []))
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            self._folders_cache.set(cache_key, folders)
            return folders[:limit] if limit else folders
        except HttpError as e:
            logger.error(f"Google Drive API error (list_folders): {e}")
            if hasattr(e, 'resp') and getattr(e.resp, 'status', None) == 403:
                raise QuotaExceededException("Drive API quota exceeded")
            raise GDriveException(f"API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error (list_folders): {e}")
            raise GDriveException(f"Unexpected error: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def search_folders(self, query, limit=10):
        try:
            results = await asyncio.to_thread(
                lambda: self.service.files().list(
                    q=f"name contains '{query}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                    pageSize=limit,
                    fields="files(id, name)"
                ).execute()
            )
            return results.get('files', [])
        except HttpError as e:
            logger.error(f"Google Drive API error (search_folders): {e}")
            if hasattr(e, 'resp') and getattr(e.resp, 'status', None) == 403:
                raise QuotaExceededException("Drive API quota exceeded")
            raise GDriveException(f"API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error (search_folders): {e}")
            raise GDriveException(f"Unexpected error: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def upload_file(self, file_name, file_bytes, parent_id=None, mime_type=None):
        parent_id = parent_id or self.settings.root_folder_id
        file_metadata = {
            'name': file_name,
            'parents': [parent_id]
        }
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type or 'application/octet-stream')
        try:
            file = await asyncio.to_thread(
                lambda: self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, name, webViewLink'
                ).execute()
            )
            # Инвалидируем кэш папки и файлов
            self.invalidate_caches(parent_id=parent_id)
            return {'success': True, 'file': file}
        except HttpError as e:
            logger.error(f"Google Drive API error (upload_file): {e}")
            if hasattr(e, 'resp') and getattr(e.resp, 'status', None) == 403:
                raise QuotaExceededException("Drive API quota exceeded")
            elif hasattr(e, 'resp') and getattr(e.resp, 'status', None) == 404:
                raise FolderNotFoundException(f"Folder {parent_id} not found")
            raise GDriveException(f"API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error (upload_file): {e}")
            raise GDriveException(f"Unexpected error: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def create_folder(self, name, parent_id=None):
        parent_id = parent_id or self.settings.root_folder_id
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        try:
            folder = await asyncio.to_thread(
                lambda: self.service.files().create(
                    body=file_metadata,
                    fields='id, name'
                ).execute()
            )
            # Инвалидируем кэш папки
            self.invalidate_caches(parent_id=parent_id)
            return {'success': True, 'folder': folder}
        except HttpError as e:
            logger.error(f"Google Drive API error (create_folder): {e}")
            if hasattr(e, 'resp') and getattr(e.resp, 'status', None) == 403:
                raise QuotaExceededException("Drive API quota exceeded")
            raise GDriveException(f"API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error (create_folder): {e}")
            raise GDriveException(f"Unexpected error: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def list_files(self, parent_id=None, limit=20):
        parent_id = parent_id or self.settings.root_folder_id
        cache_key = f"files:{parent_id}:{limit}"
        cached = self._folder_content_cache.get(cache_key)
        if cached is not None:
            return cached[:limit] if limit else cached
        try:
            files = []
            page_token = None
            while True:
                results = await asyncio.to_thread(
                    lambda: self.service.files().list(
                        q=f"'{parent_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false",
                        pageSize=1000,
                        fields="nextPageToken, files(id, name, mimeType, webViewLink)",
                        pageToken=page_token
                    ).execute()
                )
                files.extend(results.get('files', []))
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            self._folder_content_cache.set(cache_key, files)
            return files[:limit] if limit else files
        except HttpError as e:
            logger.error(f"Google Drive API error (list_files): {e}")
            if hasattr(e, 'resp') and getattr(e.resp, 'status', None) == 403:
                raise QuotaExceededException("Drive API quota exceeded")
            raise GDriveException(f"API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error (list_files): {e}")
            raise GDriveException(f"Unexpected error: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_file_metadata(self, file_id):
        cache_key = f"filemeta:{file_id}"
        cached = self._file_meta_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            file = await asyncio.to_thread(
                lambda: self.service.files().get(fileId=file_id, fields="id, name, mimeType, webViewLink").execute()
            )
            self._file_meta_cache.set(cache_key, file)
            return file
        except HttpError as e:
            logger.error(f"Google Drive API error (get_file_metadata): {e}")
            raise GDriveException(f"API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error (get_file_metadata): {e}")
            raise GDriveException(f"Unexpected error: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def download_file(self, file_id):
        try:
            def download_task():
                request = self.service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                from googleapiclient.http import MediaIoBaseDownload
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                fh.seek(0)
                return fh.read()
            return await asyncio.to_thread(download_task)
        except HttpError as e:
            logger.error(f"Google Drive API error (download_file): {e}")
            raise GDriveException(f"API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error (download_file): {e}")
            raise GDriveException(f"Unexpected error: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def search_files(self, query, parent_id=None, limit=20):
        q = f"name contains '{query}' and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            q = f"'{parent_id}' in parents and " + q
        try:
            results = await asyncio.to_thread(
                lambda: self.service.files().list(
                    q=q,
                    pageSize=limit,
                    fields="files(id, name, mimeType, webViewLink, parents)"
                ).execute()
            )
            return results.get('files', [])
        except HttpError as e:
            logger.error(f"Google Drive API error (search_files): {e}")
            raise GDriveException(f"API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error (search_files): {e}")
            raise GDriveException(f"Unexpected error: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_folder_metadata(self, folder_id):
        cache_key = f"foldermeta:{folder_id}"
        cached = self._folders_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            folder = await asyncio.to_thread(
                lambda: self.service.files().get(fileId=folder_id, fields="id, name, parents").execute()
            )
            self._folders_cache.set(cache_key, folder)
            return folder
        except HttpError as e:
            logger.error(f"Google Drive API error (get_folder_metadata): {e}")
            raise GDriveException(f"API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error (get_folder_metadata): {e}")
            raise GDriveException(f"Unexpected error: {e}")

    # Инвалидация кэша при изменениях
    def invalidate_caches(self, parent_id=None, file_id=None):
        if parent_id:
            self._folders_cache.invalidate(f"folders:{parent_id}:10")
            self._folder_content_cache.invalidate(f"files:{parent_id}:20")
            self._folders_cache.invalidate(f"foldermeta:{parent_id}")
        if file_id:
            self._file_meta_cache.invalidate(f"filemeta:{file_id}")
        # Можно добавить полную очистку при необходимости
