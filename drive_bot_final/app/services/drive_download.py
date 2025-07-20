import asyncio
from typing import Dict, Any, Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from app.config import settings

class DriveDownloadService:
    """Сервис для подготовки скачивания файлов из Google Drive"""
    def __init__(self):
        creds = Credentials(
            token=None,
            refresh_token=settings.gdrive_refresh_token,
            client_id=settings.gdrive_client_id,
            client_secret=settings.gdrive_client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=[settings.drive_scopes] if isinstance(settings.drive_scopes, str) else settings.drive_scopes,
        )
        self.service = build('drive', 'v3', credentials=creds)

    async def prepare_download(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Подготовка файла для скачивания: получение информации, создание публичной ссылки
        """
        loop = asyncio.get_event_loop()
        file_info = await loop.run_in_executor(
            None,
            lambda: self.service.files().get(
                fileId=file_id,
                fields="id,name,mimeType,size,webViewLink,webContentLink"
            ).execute()
        )
        if not file_info:
            return None
        share_info = await self._create_public_link(file_id)
        download_info = {
            'id': file_info['id'],
            'name': file_info['name'],
            'mimeType': file_info['mimeType'],
            'size': int(file_info.get('size', 0)),
            'web_view_url': file_info['webViewLink'],
            'download_url': self._get_direct_download_url(file_id),
            'share_url': share_info['webViewLink']
        }
        return download_info

    async def _create_public_link(self, file_id: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        permission = {'type': 'anyone', 'role': 'reader'}
        await loop.run_in_executor(
            None,
            lambda: self.service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()
        )
        file_info = await loop.run_in_executor(
            None,
            lambda: self.service.files().get(
                fileId=file_id,
                fields="webViewLink"
            ).execute()
        )
        return file_info

    def _get_direct_download_url(self, file_id: str) -> str:
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    async def get_file_thumbnail(self, file_id: str) -> str:
        loop = asyncio.get_event_loop()
        file_info = await loop.run_in_executor(
            None,
            lambda: self.service.files().get(
                fileId=file_id,
                fields="thumbnailLink"
            ).execute()
        )
        return file_info.get('thumbnailLink', '')

    async def revoke_public_access(self, file_id: str):
        loop = asyncio.get_event_loop()
        permissions = await loop.run_in_executor(
            None,
            lambda: self.service.permissions().list(fileId=file_id).execute()
        )
        for permission in permissions.get('permissions', []):
            if permission.get('type') == 'anyone':
                await loop.run_in_executor(
                    None,
                    lambda: self.service.permissions().delete(
                        fileId=file_id,
                        permissionId=permission['id']
                    ).execute()
                ) 