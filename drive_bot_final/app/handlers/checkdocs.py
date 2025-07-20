
from aiogram import Router
from aiogram.types import Message
from aiogram.filters.command import Command
from app.services.ocr import extract_text, detect_language
from app.services.analyzer import extract_parameters, compare_ru_en
import tempfile, logging, pathlib
import structlog

router = Router()
log = structlog.get_logger(__name__)

@router.message(Command("check"))
async def cmd_check(msg: Message):
    if not msg.reply_to_message or not msg.reply_to_message.document:
        await msg.answer("Пришлите команду /check в ответ на документ.")
        return
    doc = msg.reply_to_message.document
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=pathlib.Path(doc.file_name or "").suffix)
        await msg.bot.download(file=doc, destination=tmp.name)
        text = extract_text(tmp.name)
        lang = detect_language(text)
        params = extract_parameters(text)
        out = [f"Обнаружен язык: {lang}", "Извлечённые параметры:"]
        for k, v in params.items():
            out.append(f"- {k}: {', '.join(v)}")
        await msg.answer("\n".join(out))
        log.info("document_checked", file=doc.file_id, user=msg.from_user.id, filename=doc.file_name, lang=lang, params=params)
    except Exception as e:
        log.error("check_failed", file=doc.file_id if doc else None, user=msg.from_user.id, error=str(e))
