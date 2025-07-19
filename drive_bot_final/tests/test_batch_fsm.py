import pytest
import asyncio
from aiogram.fsm.context import FSMContext
from app.handlers.upload import FilenameWizard, FileInfo
from app.utils.filename_parser import FilenameInfo

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

@pytest.mark.asyncio
async def test_fsm_wizard_batch(monkeypatch):
    # Подготовка batch с одним проблемным файлом
    batch = [FileInfo(file_id="1", orig_name="badname.docx", guessed=None, status="need_wizard")]
    state = DummyState()
    await state.update_data(batch=batch, fix_idx=0)

    # Мокаем сообщения пользователя
    class DummyMsg:
        def __init__(self):
            self.texts = []
        async def answer(self, text, **kwargs):
            self.texts.append(text)
        @property
        def text(self):
            return self.texts[-1] if self.texts else ""
        @property
        def from_user(self):
            class U: id = 123
            return U()

    msg = DummyMsg()

    # Симулируем шаги FSM
    from app.handlers.upload import wizard_principal, wizard_agent, wizard_doctype, wizard_number, wizard_date
    msg.texts.append("PRINCIPAL")
    await wizard_principal(msg, state)
    msg.texts.append("AGENT")
    await wizard_agent(msg, state)
    msg.texts.append("TYPE")
    await wizard_doctype(msg, state)
    msg.texts.append("42")
    await wizard_number(msg, state)
    msg.texts.append("20240530")
    await wizard_date(msg, state)

    data = await state.get_data()
    assert batch[0].guessed.principal == "PRINCIPAL"
    assert batch[0].guessed.agent == "AGENT"
    assert batch[0].guessed.doctype == "TYPE"
    assert batch[0].guessed.number == "42"
    assert batch[0].guessed.date == "20240530" 