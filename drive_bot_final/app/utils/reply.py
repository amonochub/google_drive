from aiogram.types import Message, ReplyKeyboardMarkup
from app.keyboards.menu import MAIN_KB

async def send(
    message: Message,
    text: str,
    kb: ReplyKeyboardMarkup | None = None,
) -> None:
    """
    Отправляем текст + КЛАВИАТУРА.
    Если kb не передана – прикрепляем главное меню.
    """
    await message.answer(text, reply_markup=kb or MAIN_KB)
