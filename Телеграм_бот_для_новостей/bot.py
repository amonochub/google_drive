import asyncio
import logging
import os
from dotenv import load_dotenv
load_dotenv()
from aiogram import Bot, Dispatcher, types, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton
from news_parser import crawl
from gpt_client import summarize as generate_summary
from sent_storage import mark_sent, init_db
from models import Article
from aiogram.filters import Command
# Если есть image_service:
try:
    from image_service import generate_cover
except ImportError:
    generate_cover = None

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")  # для публикации

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()

# --- In-memory state (user_id -> dict) ---
user_state = {}

# --- Команды ---
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Подобрать свежие новости")]],
        resize_keyboard=True
    )
    await message.answer("Добро пожаловать! Нажмите кнопку ниже, чтобы подобрать свежие новости.", reply_markup=kb)

@router.message(lambda m: m.text == "Подобрать свежие новости")
async def pick_news_menu(message: types.Message):
    await message.answer("Подбираю свежие новости...", reply_markup=None)
    articles = await crawl()
    # Оставляем только 5 свежих
    articles = sorted(articles, key=lambda a: a.published or 0, reverse=True)[:5]
    user_state[message.from_user.id] = {"articles": articles}
    # Формируем красивый список
    news_list = "\n".join([
        f"{idx+1}. 📰 {art.title.strip()}" for idx, art in enumerate(articles)
    ])
    await message.answer(f"Выберите новость:\n\n{news_list}")
    # Кнопки только с цифрами
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=str(idx+1), callback_data=f"pick_{idx}") for idx in range(len(articles))]
        ]
    )
    await message.answer("Нажмите номер новости:", reply_markup=kb)

@router.callback_query(lambda c: c.data.startswith("pick_"))
async def pick_news(callback: types.CallbackQuery):
    idx = int(callback.data.split("_")[1])
    state = user_state.get(callback.from_user.id, {})
    articles = state.get("articles", [])
    if idx >= len(articles):
        await callback.answer("Некорректный выбор.", show_alert=True)
        return
    article = articles[idx]
    state["selected_article"] = article
    await callback.message.answer("Генерирую статью...")
    summary = await generate_summary(article)
    state["summary"] = summary
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Согласовать", callback_data="approve_summary")],
            [InlineKeyboardButton(text="Замечания", callback_data="revise_summary")]
        ]
    )
    await callback.message.answer(f"Сгенерированная статья:\n{summary}", reply_markup=kb)

@router.callback_query(lambda c: c.data == "revise_summary")
async def revise_summary(callback: types.CallbackQuery):
    await callback.message.answer("Введите замечания к статье:")
    user_state[callback.from_user.id]["awaiting_summary_revision"] = True

@router.message(lambda m: user_state.get(m.from_user.id, {}).get("awaiting_summary_revision"))
async def handle_summary_revision(message: types.Message):
    state = user_state[message.from_user.id]
    article = state["selected_article"]
    remarks = message.text
    await message.answer("Дорабатываю статью...")
    # Можно доработать prompt для GPT с учётом замечаний
    summary = await generate_summary(article)
    state["summary"] = summary
    state["awaiting_summary_revision"] = False
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Согласовать", callback_data="approve_summary")],
            [InlineKeyboardButton(text="Замечания", callback_data="revise_summary")]
        ]
    )
    await message.answer(f"Обновлённая статья:\n{summary}", reply_markup=kb)

@router.callback_query(lambda c: c.data == "approve_summary")
async def approve_summary(callback: types.CallbackQuery):
    state = user_state[callback.from_user.id]
    article = state["selected_article"]
    summary = state["summary"]
    if generate_cover:
        await callback.message.answer("Генерирую изображение...")
        image_bytes = await generate_cover(article.title)
        state["image"] = image_bytes
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Согласовать", callback_data="approve_image")],
                [InlineKeyboardButton(text="Замечания", callback_data="revise_image")]
            ]
        )
        await callback.message.answer_photo(image_bytes, caption="Сгенерированное изображение", reply_markup=kb)
    else:
        # Если нет image_service, сразу к публикации
        await publish_news(callback, article, summary, None)

@router.callback_query(lambda c: c.data == "revise_image")
async def revise_image(callback: types.CallbackQuery):
    await callback.message.answer("Введите замечания к изображению:")
    user_state[callback.from_user.id]["awaiting_image_revision"] = True

@router.message(lambda m: user_state.get(m.from_user.id, {}).get("awaiting_image_revision"))
async def handle_image_revision(message: types.Message):
    state = user_state[message.from_user.id]
    article = state["selected_article"]
    remarks = message.text
    await message.answer("Дорабатываю изображение...")
    # Можно доработать prompt для image_service с учётом замечаний
    image_bytes = await generate_cover(article.title)
    state["image"] = image_bytes
    state["awaiting_image_revision"] = False
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Согласовать", callback_data="approve_image")],
            [InlineKeyboardButton(text="Замечания", callback_data="revise_image")]
        ]
    )
    await message.answer_photo(image_bytes, caption="Обновлённое изображение", reply_markup=kb)

@router.callback_query(lambda c: c.data == "approve_image")
async def approve_image(callback: types.CallbackQuery):
    state = user_state[callback.from_user.id]
    article = state["selected_article"]
    summary = state["summary"]
    image_bytes = state.get("image")
    await publish_news(callback, article, summary, image_bytes)

async def publish_news(callback, article, summary, image_bytes):
    # Публикация в канал (или отправка пользователю)
    if image_bytes:
        await bot.send_photo(CHANNEL_ID or callback.from_user.id, image_bytes, caption=summary)
    else:
        await bot.send_message(CHANNEL_ID or callback.from_user.id, summary)
    mark_sent(article.id, article.published)
    await callback.message.answer("Новость опубликована!")

async def main():
    init_db()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
