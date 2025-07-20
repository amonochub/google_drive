import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.drive_download import DriveDownloadService
import asyncio

@pytest.mark.asyncio
async def test_prepare_download_success():
    service = DriveDownloadService()
    file_id = 'abc123'
    # Мокаем service.service.files().get(...).execute
    files_mock = MagicMock()
    files_mock.get.return_value.execute.return_value = {
        'id': file_id, 'name': 'Test.pdf', 'mimeType': 'application/pdf', 'size': '12345', 'webViewLink': 'web', 'webContentLink': 'content'
    }
    service.service.files = MagicMock(return_value=files_mock)
    # Мокаем _create_public_link
    service._create_public_link = AsyncMock(return_value={'webViewLink': 'share'})
    result = await service.prepare_download(file_id)
    assert result['id'] == file_id
    assert 'web_view_url' in result
    assert result['share_url'] == 'share'

@pytest.mark.asyncio
async def test_prepare_download_api_error():
    service = DriveDownloadService()
    files_mock = MagicMock()
    files_mock.get.return_value.execute.side_effect = Exception('API error')
    service.service.files = MagicMock(return_value=files_mock)
    service._create_public_link = AsyncMock(return_value={'webViewLink': 'share'})
    with pytest.raises(Exception):
        await service.prepare_download('err404')

@pytest.mark.asyncio
async def test_prepare_download_no_access():
    service = DriveDownloadService()
    files_mock = MagicMock()
    files_mock.get.return_value.execute.return_value = None
    service.service.files = MagicMock(return_value=files_mock)
    service._create_public_link = AsyncMock(return_value={'webViewLink': 'share'})
    result = await service.prepare_download('noaccess')
    assert result is None or result.get('id') is None 