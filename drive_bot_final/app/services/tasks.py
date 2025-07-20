import os, logging
from app.services.celery_app import celery_app
from app.services.reporter import validate_doc, build_report
from app.services.drive import upload_file

log = logging.getLogger(__name__)

@celery_app.task
def validate_task(file_path: str, user_id: int, chat_id: int, bot_token: str):
    import asyncio
    
    async def _validate():
        from aiogram import Bot
        bot = Bot(bot_token, parse_mode="HTML")
        misses, patched = validate_doc(file_path)

        if not misses:
            txt = "✅ Проверка завершена, расхождений нет!"
            await bot.send_message(chat_id, txt)
        else:
            report = build_report(misses)
            await bot.send_message(chat_id, report, parse_mode="Markdown")

        # Безопасная отправка файла
        if os.path.exists(patched):
            try:
                with open(patched, "rb") as f:
                    await bot.send_document(chat_id, f, caption="Файл с подсветкой ⬆️")
            except (OSError, IOError) as e:
                import logging
                logging.getLogger(__name__).error(f"Ошибка отправки файла {patched}: {e}")
        
        await bot.session.close()
        
        # Безопасное удаление файлов
        for file_path_to_remove in [file_path, patched]:
            try:
                if os.path.exists(file_path_to_remove):
                    os.remove(file_path_to_remove)
            except OSError as e:
                import logging
                logging.getLogger(__name__).warning(f"Не удалось удалить файл {file_path_to_remove}: {e}")
    
    # Run the async function in an event loop
    asyncio.run(_validate()) 