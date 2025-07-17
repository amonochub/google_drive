
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    kb = [
        [InlineKeyboardButton(text='📂 Обзор папок', callback_data='menu_browse')],
        [InlineKeyboardButton(text='⬆️ Загрузить файл', callback_data='menu_upload')],
        [InlineKeyboardButton(text='🧐 Проверить документы', callback_data='menu_check')],
        [InlineKeyboardButton(text='🔍 Поиск по папкам', callback_data='menu_search')],
        [InlineKeyboardButton(text='🕑 История', callback_data='menu_history')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_to_main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='🏠 Главное меню', callback_data='menu_main')]
        ]
    )

def document_type_menu():
    kb = [
        [InlineKeyboardButton(text='Агентский договор', callback_data='doc_type_agent_contract')],
        [InlineKeyboardButton(text='Поручение', callback_data='doc_type_instruction')],
        [InlineKeyboardButton(text='Акт', callback_data='doc_type_act')],
        [InlineKeyboardButton(text='Другое', callback_data='doc_type_other')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
