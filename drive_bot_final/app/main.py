
import asyncio, logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from app.config import get_settings
from app.routers import main_router
from app.keyboards.menu import main_menu
from app.services.celery_app import celery_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

def build_bot() -> Bot:
    settings = get_settings()
    return Bot(token=settings.bot_token, parse_mode=ParseMode.HTML)

async def main():
    bot = build_bot()
    dp = Dispatcher()
    dp.include_router(main_router)
    await bot.set_my_commands([
        ("start", "Начать 🤗"),
        ("menu",  "Показать меню 🥰")
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
