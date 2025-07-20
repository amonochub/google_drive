import asyncio
import datetime as dt
import decimal
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from celery import Celery
import structlog
log = structlog.get_logger(__name__)

# --- Настройки ---
from app.config import settings

router = Router()

celery_app = Celery(
    "calc_tasks",
    broker=settings.REDIS_DSN,
    backend=settings.REDIS_DSN
)

CBR_URL = "https://www.cbr.ru/scripts/XML_daily.asp?date_req={for_date}"
ISO2CBR = {"USD": "R01235", "EUR": "R01239", "CNY": "R01375"}

async def fetch_cbr_rate(currency: str, for_date: dt.date) -> decimal.Decimal | None:
    url = CBR_URL.format(for_date=for_date)
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                return None
            xml_text = await resp.text()
    tree = ET.fromstring(xml_text)
    valute = tree.find(f".//Valute[@ID='{ISO2CBR[currency]}']")
    if valute is None:
        return None
    value = valute.find("Value").text.replace(",", ".")
    nominal = int(valute.find("Nominal").text)
    return decimal.Decimal(value) / nominal

async def safe_fetch_rate(currency: str, date: dt.date) -> decimal.Decimal | None:
    import logging, aiohttp
    try:
        rate = await fetch_cbr_rate(currency, date)
        if rate is None:
            log.warning("cbr_rate_not_found", currency=currency, date=str(date))
        return rate
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        log.error("cbr_fetch_failed", currency=currency, date=str(date), error=str(e))
        return None

def result_message(currency, rate, amount, commission_pct):
    rub_sum = (amount * rate).quantize(decimal.Decimal("0.01"))
    fee = (rub_sum * commission_pct / 100).quantize(decimal.Decimal("0.01"))
    total = (rub_sum + fee).quantize(decimal.Decimal("0.01"))
    return (
        f"📊 <b>Расчёт</b>\n"
        f"Курс ЦБ {currency} → ₽: <b>{rate}</b>\n"
        f"Сумма перевода: <b>{amount} {currency}</b>\n"
        f"Сумма в рублях: <b>{rub_sum} ₽</b>\n"
        f"Вознаграждение агента ({commission_pct}%): <b>{fee} ₽</b>\n"
        f"🧮 <b>Итого к оплате: {total} ₽</b>"
    )

class CalcStates(StatesGroup):
    choosing_day = State()
    choosing_currency = State()
    entering_amount = State()
    entering_commission = State()
    waiting_tomorrow_rate = State()

@dataclass
class CalcData:
    for_tomorrow: bool = False
    currency: str | None = None
    amount: decimal.Decimal | None = None
    commission: decimal.Decimal | None = None

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📂 Обзор папок")],
        [KeyboardButton(text="📤 Загрузка файлов")],
        [KeyboardButton(text="🤖 Проверка ИИ")],
        [KeyboardButton(text="💰 Расчёт для клиента")],
    ],
    resize_keyboard=True
)

day_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Сегодня", callback_data="calc_today")],
        [InlineKeyboardButton(text="Завтра", callback_data="calc_tomorrow")],
    ]
)

currency_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🇪🇺 EUR", callback_data="cur_EUR"),
            InlineKeyboardButton(text="🇺🇸 USD", callback_data="cur_USD"),
            InlineKeyboardButton(text="🇨🇳 CNY", callback_data="cur_CNY"),
        ]
    ]
)

@router.message(F.text == "💰 Расчёт для клиента")
async def calc_menu_start(msg: Message, state: FSMContext):
    await state.set_state(CalcStates.choosing_day)
    await state.update_data(data=CalcData().__dict__)
    await msg.answer(
        "За какой день рассчитать перевод?\n\n"
        "👈 Выберите одну из кнопок ниже.",
        reply_markup=day_kb
    )

@router.callback_query(F.data.startswith("calc_"))
async def process_day(cb: CallbackQuery, state: FSMContext):
    pick = cb.data.split("_")[1]  # today / tomorrow
    data = (await state.get_data()) or {}
    data.update(for_tomorrow=(pick == "tomorrow"))
    await state.update_data(**data)
    await state.set_state(CalcStates.choosing_currency)
    await cb.message.edit_text(
        "Выберите валюту расчёта 👇",
        reply_markup=currency_kb
    )
    await cb.answer()

@router.callback_query(F.data.startswith("cur_"))
async def process_currency(cb: CallbackQuery, state: FSMContext):
    currency = cb.data.split("_")[1]
    data = await state.get_data()
    data["currency"] = currency
    await state.update_data(**data)
    await state.set_state(CalcStates.entering_amount)
    await cb.message.edit_text(
        f"Введите сумму перевода в <b>{currency}</b> (только число)."
    )
    await cb.answer()

@router.message(CalcStates.entering_amount)
async def input_amount(msg: Message, state: FSMContext):
    try:
        amount = decimal.Decimal(msg.text.replace(",", "."))
        assert amount > 0
    except Exception:
        return await msg.reply("Введите положительное число. Попробуйте ещё раз 😊")
    data = await state.get_data()
    data["amount"] = amount
    await state.update_data(**data)
    await state.set_state(CalcStates.entering_commission)
    await msg.answer(
        "Укажите размер вознаграждения агента в процентах (например 3.5)",
    )

@router.message(CalcStates.entering_commission)
async def input_commission(msg: Message, state: FSMContext):
    try:
        pct = decimal.Decimal(msg.text.replace(",", "."))
        assert pct >= 0
    except Exception:
        return await msg.reply("Число должно быть ≥ 0. Попробуйте ещё раз.")
    data = await state.get_data()
    data["commission"] = pct
    await state.update_data(**data)

    if data["for_tomorrow"]:
        tomorrow = dt.date.today() + dt.timedelta(days=1)
        rate = await safe_fetch_rate(data["currency"], tomorrow)
        if rate:
            await msg.answer(
                result_message(data["currency"], rate, data["amount"], pct),
                reply_markup=main_kb
            )
            return await state.clear()
        await msg.answer(
            "Курс ЦБ на завтра пока не опубликован 🙈\n"
            "Я пришлю расчёт сразу, как только он появится!",
            reply_markup=main_kb
        )
        await state.set_state(CalcStates.waiting_tomorrow_rate)
        celery_app.send_task(
            "calc_tasks.wait_rate_and_notify",
            kwargs={
                "chat_id": msg.chat.id,
                "currency": data["currency"],
                "amount": str(data["amount"]),
                "commission": str(pct),
            },
        )
        return
    today = dt.date.today()
    rate = await safe_fetch_rate(data["currency"], today)
    if rate is None:
        await msg.answer("Сегодняшний курс пока не доступен. Попробуйте позже.")
        return await state.clear()
    await msg.answer(
        result_message(data["currency"], rate, data["amount"], pct),
        reply_markup=main_kb
    )
    await state.clear()

@celery_app.task(name="calc_tasks.wait_rate_and_notify", bind=True, max_retries=None)
def wait_rate_and_notify(self, chat_id: int, currency: str, amount: str, commission: str):
    import asyncio
    loop = asyncio.get_event_loop()
    async def _run():
        amt = decimal.Decimal(amount)
        pct = decimal.Decimal(commission)
        tomorrow = dt.date.today() + dt.timedelta(days=1)
        while True:
            rate = await fetch_cbr_rate(currency, tomorrow)
            if rate:
                await bot.send_message(
                    chat_id,
                    result_message(currency, rate, amt, pct),
                    reply_markup=main_kb
                )
                break
            await asyncio.sleep(300)
    return loop.run_until_complete(_run()) 