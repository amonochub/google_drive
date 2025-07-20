import asyncio, tempfile
from aiogram import Router, F
from aiogram.types import Message
from app.services.reporter import validate_doc, build_report
from app.utils.telegram_utils import escape_markdown
from app.utils.file_validation import validate_file, FileValidationError

router = Router()

@router.message(F.text.startswith("🤖"))
async def ask_doc(msg: Message):
    await msg.answer("Пришли файл DOCX или PDF, я проверю!")

@router.message(F.document.file_name.endswith((".docx", ".pdf")))
async def run_validation(msg: Message):
    doc = msg.document
    try:
        validate_file(doc.file_name, doc.file_size)
    except FileValidationError as e:
        await msg.answer(f"❌ Файл не принят: {e}")
        return

    with tempfile.NamedTemporaryFile(suffix=doc.file_name[-5:], delete=False) as tmp:
        await msg.bot.download(doc, destination=tmp.name)

    missings, patched_path = await asyncio.get_running_loop().run_in_executor(
        None, validate_doc, tmp.name
    )

    if not missings:
        await msg.answer("Ура! ❣️ Ошибок не найдено.")
    else:
        md_report = build_report(missings)
        await msg.answer(escape_markdown(md_report), parse_mode="Markdown")

    await msg.answer_document(open(patched_path, "rb"), caption="Подсветила различия 💡") 