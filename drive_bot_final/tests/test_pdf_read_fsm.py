import pytest
import asyncio
from aiogram.fsm.context import FSMContext
from app.handlers.menu import ReadPDFStates, process_pdf_document, handle_non_document

class DummyState:
    def __init__(self):
        self._data = {}
        self._state = None
    async def update_data(self, **kwargs):
        self._data.update(kwargs)
    async def get_data(self):
        return self._data
    async def set_state(self, state):
        self._state = state
    async def clear(self):
        self._data = {}
        self._state = None

class DummyBot:
    async def get_file(self, file_id):
        return type('File', (), {'file_path': f"/tmp/{file_id}.pdf"})()
    async def download_file(self, file_path, dest):
        with open(dest, 'w') as f:
            f.write('PDFDATA')

class DummyMsg:
    def __init__(self, document=None, text=None):
        self.document = document
        self.text = text
        self.answers = []
        self.bot = DummyBot()
    async def answer(self, text, **kwargs):
        self.answers.append(text)
        return self  # возвращаем self для поддержки progress_msg
    async def edit_text(self, text, **kwargs):
        self.answers.append(text)
        return self
    async def delete(self):
        self.answers.append('deleted')

class DummyDocument:
    def __init__(self, mime_type, file_size, file_id, file_name):
        self.mime_type = mime_type
        self.file_size = file_size
        self.file_id = file_id
        self.file_name = file_name

@pytest.mark.asyncio
async def test_pdf_read_valid():
    state = DummyState()
    doc = DummyDocument('application/pdf', 1024 * 1024, 'fileid', 'test.pdf')
    msg = DummyMsg(document=doc)
    await process_pdf_document(msg, state)
    assert any('Готово! Прочитал твой файл' in a for a in msg.answers)

@pytest.mark.asyncio
async def test_pdf_read_wrong_type():
    state = DummyState()
    doc = DummyDocument('application/msword', 1024 * 1024, 'fileid', 'test.docx')
    msg = DummyMsg(document=doc)
    await process_pdf_document(msg, state)
    assert any('Я умею читать только PDF' in a for a in msg.answers)

@pytest.mark.asyncio
async def test_pdf_read_too_large():
    state = DummyState()
    doc = DummyDocument('application/pdf', 25 * 1024 * 1024, 'fileid', 'big.pdf')
    msg = DummyMsg(document=doc)
    await process_pdf_document(msg, state)
    assert any('файл слишком большой' in a for a in msg.answers)

@pytest.mark.asyncio
async def test_pdf_read_cancel():
    state = DummyState()
    msg = DummyMsg(text='отмена')
    await handle_non_document(msg)
    assert any('отменяю' in a.lower() for a in msg.answers)

@pytest.mark.asyncio
async def test_pdf_read_waiting_for_pdf():
    state = DummyState()
    msg = DummyMsg(text='что-то не то')
    await handle_non_document(msg)
    assert any('жду PDF файл' in a for a in msg.answers) 