from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

def main_menu() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="📂 Обзор папок"), KeyboardButton(text="⬆️ Загрузить файл")],
        [KeyboardButton(text="🤖 Проверка документа")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def with_back(*rows: list[str]) -> ReplyKeyboardMarkup:
    """
    Вернуть новую клавиатуру = переданные строки + «🏠 Главное меню».
    """
    buttons = [[KeyboardButton(text=txt) for txt in row] for row in rows]
    buttons.append([KeyboardButton(text="🏠 Главное меню")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True) 