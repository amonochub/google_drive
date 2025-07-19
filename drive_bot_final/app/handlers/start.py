from aiogram import Router, F
from aiogram.types import Message
from app.keyboards.menu import main_menu

router = Router()

@router.message(F.text == "/start")
async def cmd_start(msg: Message):
    await msg.answer(
        "Приветик! Я помогу загрузить документы, посмотреть папочки и проверить их ИИ-магией 🪄",
        reply_markup=main_menu()
    ) 