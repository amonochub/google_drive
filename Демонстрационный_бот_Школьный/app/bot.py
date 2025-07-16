import logging, asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from app.config import TELEGRAM_TOKEN, ADMIN_IDS
from app.roles import ROLES, DEMO_USERS
from app import db as dbm
from sqlalchemy import select, update
from sqlalchemy.exc import NoResultFound

logging.basicConfig(level=logging.WARNING)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- helpers ---
async def get_session():
    async with dbm.SessionLocal() as session:
        yield session

async def init_db():
    async with dbm.engine.begin() as conn:
        await conn.run_sync(dbm.Base.metadata.create_all)
        # preload demo users if not exist
        result = await conn.execute(select(dbm.User))
        if result.first() is None:
            for u in DEMO_USERS:
                await conn.execute(
                    dbm.User.__table__.insert().values(
                        login=u["login"], password=u["password"], role=u["role"]
                    )
                )
            await conn.commit()

async def send_notification(tg_id: int, text: str):
    try:
        await bot.send_message(chat_id=tg_id, text=text)
    except Exception as e:
        logging.warning(f"Не удалось отправить уведомление {tg_id}: {e}")

# Пример использования: отправить уведомление всем учителям (можно вызывать из любого места)
async def notify_teachers(text: str):
    async with dbm.SessionLocal() as session:
        result = await session.execute(select(dbm.User).where(dbm.User.role == "teacher", dbm.User.tg_id != None))
        for user in result.scalars():
            await send_notification(user.tg_id, text)

@dp.message(Command('start'))
async def cmd_start(message: Message):
    tg_id = message.from_user.id
    if tg_id in ADMIN_IDS:
        async for session in get_session():
            user_obj = await session.scalar(select(dbm.User).where(dbm.User.tg_id == tg_id))
            if not user_obj:
                # создать админа если нет
                from app.db import User
                admin_user = User(login=f"admin_{tg_id}", password="", role="admin", tg_id=tg_id, used=True)
                session.add(admin_user)
                await session.commit()
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="📝 Все заметки")],
                [KeyboardButton(text="📅 Календарь"), KeyboardButton(text="📊 Статистика")],
                [KeyboardButton(text="📚 Расписание"), KeyboardButton(text="📂 Файлы")],
                [KeyboardButton(text="🗳 Опросы"), KeyboardButton(text="🎤 Голосовые")],
                [KeyboardButton(text="💬 Родительское собрание"), KeyboardButton(text="🤖 AI-помощник")]
            ], resize_keyboard=True
        )
        await message.answer(
            "Добро пожаловать, дорогой администратор! 🌸\n\nВы — сердце нашей школы! Здесь вы можете управлять всеми деталями, помогать коллегам и делать мир чуть добрее.\n\nВыберите действие на клавиатуре ниже:",
            reply_markup=kb
        )
        return
    async for session in get_session():
        user_obj = await session.scalar(select(dbm.User).where(dbm.User.tg_id == tg_id))
        if user_obj:
            await message.answer(f"Вы уже авторизованы как {ROLES[user_obj.role]}. Напишите /help для списка команд.")
            return
    await message.answer("Введите логин:")

@dp.message(F.text & ~F.text.startswith('/'))
async def auth_or_commands(message: Message):
    tg_id = message.from_user.id
    if tg_id in ADMIN_IDS:
        text = message.text
        if text == "👥 Пользователи":
            await message.answer("Вот список всех пользователей школы! (реализация)")
        elif text == "📝 Все заметки":
            await message.answer("Вот все заметки! (реализация)")
        elif text == "📅 Календарь":
            await message.answer("Вот календарь событий! (реализация)")
        elif text == "📊 Статистика":
            await message.answer("Вот статистика! (реализация)")
        elif text == "📚 Расписание":
            await message.answer("Вот расписание уроков! (реализация)")
        elif text == "📂 Файлы":
            await message.answer("Вот все файлы! (реализация)")
        elif text == "🗳 Опросы":
            await message.answer("Вот все опросы! (реализация)")
        elif text == "🎤 Голосовые":
            await message.answer("Вот все голосовые сообщения! (реализация)")
        elif text == "💬 Родительское собрание":
            await message.answer("Вот чат родительского собрания! (реализация)")
        elif text == "🤖 AI-помощник":
            await message.answer("Я всегда готов помочь вам с любыми вопросами! (реализация)")
        else:
            await message.answer("Пожалуйста, выберите действие на клавиатуре ниже. Вы — лучший админ! 🌷")
        return
    async for session in get_session():
        user_obj = await session.scalar(select(dbm.User).where(dbm.User.tg_id == tg_id))
        if not user_obj:
            # assume waiting for login or password
            state = dp.current_state(chat=message.chat.id, user=message.from_user.id)
            data = await state.get_data()
            if "login" not in data:
                await state.update_data(login=message.text.strip())
                await message.answer("Введите пароль:")
            else:
                login = data["login"]
                password = message.text.strip()
                try:
                    user = await session.scalar(
                        select(dbm.User).where(dbm.User.login == login, dbm.User.password == password)
                    )
                    if not user or user.used:
                        await message.answer("❌ Неверные данные или аккаунт уже использован.")
                        await state.clear()
                        return
                    await session.execute(
                        update(dbm.User)
                        .where(dbm.User.id == user.id)
                        .values(tg_id=tg_id, used=True)
                    )
                    await session.commit()
                    await state.clear()
                    await message.answer(f"✅ Авторизация успешна. Ваша роль: {ROLES[user.role]}. Напишите /help.")
                except NoResultFound:
                    await message.answer("❌ Неверные данные.")
                    await state.clear()
            return
        # user is authenticated, process simple commands
        text = message.text.strip().lower()
        if text == "привет":
            await message.answer("Привет! Напишите /help для списка команд.")
        else:
            await message.answer("Не понимаю. Напишите /help.")

@dp.message(Command('help'))
async def cmd_help(message: Message):
    tg_id = message.from_user.id
    async for session in get_session():
        user_obj = await session.scalar(select(dbm.User).where(dbm.User.tg_id == tg_id))
    if not user_obj:
        await message.answer("Сначала авторизуйтесь. Напишите /start.")
        return
    role = user_obj.role
    if role == "teacher":
        await message.answer("/add_note <ученик> <текст> – добавить заметку\n/my_notes – мои заметки")
    elif role in ("admin","director"):
        await message.answer("/all_notes – все заметки\n/users – список пользователей")
    else:
        await message.answer("Доступные команды отсутствуют в демо.")

@dp.message(Command('add_note'))
async def cmd_add_note(message: Message):
    tg_id = message.from_user.id
    async for session in get_session():
        user_obj = await session.scalar(select(dbm.User).where(dbm.User.tg_id == tg_id))
        if not user_obj or user_obj.role != "teacher":
            await message.answer("Команда доступна только учителю.")
            return
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("Формат: /add_note <ученик> <текст>")
            return
        student, text = parts[1], parts[2]
        # for demo, just echo
        await message.answer(f"Заметка сохранена: {student} – {text}")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
