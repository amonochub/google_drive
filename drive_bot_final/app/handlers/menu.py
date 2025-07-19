from aiogram import Router, F
from aiogram.types import Message
from app.keyboards.menu import main_menu

router = Router()

@router.message(F.text == "/menu")
async def show_menu(msg: Message):
    await msg.answer("Выбирай действие, мой друг 🌼", reply_markup=main_menu())
