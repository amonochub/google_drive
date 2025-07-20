import asyncio, tempfile, os
from aiogram import Router, F
from aiogram.types import Message
from app.services.reporter import validate_doc, build_report

router = Router()

@router.message(F.text.startswith("🤖"))
async def ask_doc(msg: Message):
    await msg.answer("Пришли файл DOCX или PDF, я проверю!")

@router.message(F.document.file_name.endswith((".docx", ".pdf")))
async def run_validation(msg: Message):
    doc = msg.document
    with tempfile.NamedTemporaryFile(suffix=doc.file_name[-5:], delete=False) as tmp:
        await msg.bot.download(doc, destination=tmp.name)

    missings, patched_path = await asyncio.get_running_loop().run_in_executor(
        None, validate_doc, tmp.name
    )

    if not missings:
        await msg.answer("Ура! ❣️ Ошибок не найдено.")
    else:
        md_report = build_report(missings)
        await msg.answer(md_report, parse_mode="Markdown")

    # Безопасная отправка файла с проверкой существования
    if patched_path and os.path.exists(patched_path):
        try:
            with open(patched_path, "rb") as f:
                await msg.answer_document(f, caption="Подсветила различия 💡")
        except (OSError, IOError) as e:
            await msg.answer(f"Ошибка отправки файла: {e}")
        finally:
            # Безопасное удаление временного файла
            try:
                os.unlink(patched_path)
            except OSError:
                pass 