import os, logging
from app.services.celery_app import celery_app
from app.services.reporter import validate_doc, build_report
from app.services.drive import upload_file

log = logging.getLogger(__name__)

@celery_app.task
def validate_task(file_path: str, user_id: int, chat_id: int, bot_token: str):
    from aiogram import Bot
    bot = Bot(bot_token, parse_mode="HTML")
    misses, patched = validate_doc(file_path)

    if not misses:
        txt = "✅ Проверка завершена, расхождений нет!"
        await bot.send_message(chat_id, txt)
    else:
        report = build_report(misses)
        await bot.send_message(chat_id, report, parse_mode="Markdown")

    await bot.send_document(chat_id, open(patched, "rb"), caption="Файл с подсветкой ⬆️")
    os.remove(file_path)
    os.remove(patched) 