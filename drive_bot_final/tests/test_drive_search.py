import pytest
from unittest.mock import patch, MagicMock
from app.services.drive_search import DriveSearchService
import asyncio

@pytest.mark.asyncio
async def test_search_files_by_name():
    service = DriveSearchService()
    with patch.object(service, '_execute_search', return_value=[
        {'id': '1', 'name': 'Test.pdf', 'size': '12345', 'parents': [], 'modifiedTime': '2024-07-21T12:00:00Z'}
    ]):
        with patch.object(service, '_enrich_file_info', side_effect=lambda x: x):
            results = await service.search_files('Test')
            assert len(results) == 1
            assert results[0]['name'] == 'Test.pdf'

@pytest.mark.asyncio
async def test_search_files_by_type():
    service = DriveSearchService()
    with patch.object(service, '_execute_search', return_value=[
        {'id': '2', 'name': 'Report.docx', 'size': '54321', 'parents': [], 'modifiedTime': '2024-07-21T12:00:00Z'}
    ]):
        with patch.object(service, '_enrich_file_info', side_effect=lambda x: x):
            results = await service.search_files('Report', file_types=['docx'])
            assert len(results) == 1
            assert results[0]['name'] == 'Report.docx'

@pytest.mark.asyncio
async def test_search_files_nothing_found():
    service = DriveSearchService()
    with patch.object(service, '_execute_search', return_value=[]):
        results = await service.search_files('Nothing')
        assert results == []

@pytest.mark.asyncio
async def test_search_files_api_error():
    service = DriveSearchService()
    with patch.object(service, '_execute_search', side_effect=Exception('API error')):
        with pytest.raises(Exception):
            await service.search_files('Error') 