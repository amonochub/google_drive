from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

router = Router()

# Заглушки для теста и примера
ROOT_ID = "root_id"
def list_children(folder_id):
    # Здесь должна быть интеграция с Google Drive API
    return []

def list_drive_files(folder_id):
    return list_children(folder_id)

@router.message(Command("browse"))
async def browse_root(message: types.Message):
    files = list_drive_files(ROOT_ID)
    kb = InlineKeyboardMarkup()
    for f in files:
        kb.add(InlineKeyboardButton(f, callback_data=f"open:{getattr(f, 'id', f)}"))
    await message.answer("📁 Выберите папку:", reply_markup=kb)

@router.callback_query(lambda c: c.data.startswith("open:"))
async def open_folder(call: types.CallbackQuery):
    folder_id = call.data.split(":", 1)[1]
    children = list_children(folder_id)
    if not children:
        await call.message.edit_text("📂 Папка пуста 😊")
        return
    kb = InlineKeyboardMarkup(row_width=1)
    for item in children:
        kb.add(InlineKeyboardButton(getattr(item, 'name', str(item)), callback_data=f"open:{getattr(item, 'id', item)}"))
    # Навигация
    kb.add(
        InlineKeyboardButton("🔙 Назад", callback_data="back"),
        InlineKeyboardButton("🏠 В корень", callback_data="root"),
    )
    await call.message.edit_text(f"📂 {call.message.text}", reply_markup=kb)

@router.callback_query(lambda c: c.data == "root")
async def go_root(call: types.CallbackQuery):
    await browse_root(call.message)
