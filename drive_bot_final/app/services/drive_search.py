import asyncio
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from app.config import settings

class DriveSearchService:
    """Сервис для поиска файлов в Google Drive"""
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

    async def search_files(
        self,
        query: str,
        max_results: int = 50,
        file_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Поиск файлов по запросу (имя, содержимое, тип)
        """
        search_query = self._build_search_query(query, file_types)
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            self._execute_search,
            search_query,
            max_results
        )
        enriched_results = []
        for file_info in results:
            enriched_file = await self._enrich_file_info(file_info)
            enriched_results.append(enriched_file)
        return enriched_results

    def _build_search_query(self, query: str, file_types: Optional[List[str]] = None) -> str:
        search_parts = [f"name contains '{query}' or fullText contains '{query}'"]
        search_parts.append("mimeType != 'application/vnd.google-apps.folder'")
        search_parts.append("trashed = false")
        if file_types:
            type_conditions = []
            for file_type in file_types:
                if file_type.lower() == 'pdf':
                    type_conditions.append("mimeType = 'application/pdf'")
                elif file_type.lower() in ['doc', 'docx']:
                    type_conditions.append("mimeType contains 'document'")
                elif file_type.lower() in ['xls', 'xlsx']:
                    type_conditions.append("mimeType contains 'spreadsheet'")
                elif file_type.lower() in ['jpg', 'jpeg', 'png']:
                    type_conditions.append("mimeType contains 'image'")
            if type_conditions:
                search_parts.append(f"({' or '.join(type_conditions)})")
        return " and ".join(search_parts)

    def _execute_search(self, query: str, max_results: int) -> List[Dict]:
        results = self.service.files().list(
            q=query,
            pageSize=min(max_results, 100),
            fields="files(id,name,mimeType,size,modifiedTime,parents,webViewLink,iconLink)",
            orderBy="modifiedTime desc"
        ).execute()
        return results.get('files', [])

    async def _enrich_file_info(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        enriched = file_info.copy()
        try:
            path = await self._get_file_path(file_info.get('parents', []))
            enriched['path'] = path
        except:
            enriched['path'] = 'Root'
        try:
            enriched['size'] = int(file_info.get('size', 0))
        except (ValueError, TypeError):
            enriched['size'] = 0
        return enriched

    async def _get_file_path(self, parent_ids: List[str]) -> str:
        if not parent_ids:
            return 'Root'
        try:
            loop = asyncio.get_event_loop()
            parent_info = await loop.run_in_executor(
                None,
                lambda: self.service.files().get(
                    fileId=parent_ids[0],
                    fields="name,parents"
                ).execute()
            )
            parent_name = parent_info.get('name', 'Unknown')
            parent_parents = parent_info.get('parents', [])
            if parent_parents:
                parent_path = await self._get_file_path(parent_parents)
                return f"{parent_path}/{parent_name}"
            else:
                return parent_name
        except:
            return 'Unknown' 