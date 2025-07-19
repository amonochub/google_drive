from aiogram import Router, F
from aiogram.types import Message
from app.services.drive import list_folders

router = Router()

@router.message(F.text.startswith("📂"))
async def list_drive_folders(msg: Message):
    folders = await list_folders()
    if not folders:
        return await msg.answer("Папочек пока нет 🥲")
    txt = "\n".join(f"📁 <b>{name}</b> — <i>{cnt} файлов</i>" for name, cnt in folders)
    await msg.answer(txt)
