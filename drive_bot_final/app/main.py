
import asyncio, logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand
from app.config import get_settings
from app.routers import main_router
from app.handlers.menu import router as menu_router
from app.services.celery_app import celery_app
import aiohttp
from datetime import datetime, time
import xml.etree.ElementTree as ET
from decimal import Decimal
from aiogram import types
from app.logging_setup import setup
import structlog
log = structlog.get_logger(__name__)
setup()


CBR_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
CURRENCIES = ["USD", "EUR", "CNY"]

class CBRMonitor:
    def __init__(self, bot):
        self.session = None
        self.last_rates = {}
        self.monitoring = False
        self.bot = bot
    async def fetch_cbr_rate(self, currency_code: str) -> Decimal:
        url = f"{CBR_URL}?date_req={datetime.now().strftime('%d/%m/%Y')}"
        async with self.session.get(url) as response:
            if response.status != 200:
                raise Exception(f"CBR API error: {response.status}")
            xml_content = await response.text()
            root = ET.fromstring(xml_content)
            for valute in root.findall('.//Valute'):
                char_code = valute.find('CharCode').text
                if char_code == currency_code:
                    value = valute.find('Value').text
                    value = value.replace(',', '.')
                    return Decimal(value)
            raise Exception(f"Currency {currency_code} not found")
    async def check_rates_update(self):
        try:
            new_rates = {}
            for currency in CURRENCIES:
                rate = await self.fetch_cbr_rate(currency)
                new_rates[currency] = rate
            changes = []
            for currency, new_rate in new_rates.items():
                old_rate = self.last_rates.get(currency)
                if old_rate and old_rate != new_rate:
                    change = new_rate - old_rate
                    changes.append({
                        'currency': currency,
                        'old_rate': old_rate,
                        'new_rate': new_rate,
                        'change': change
                    })
            if changes:
                await self.notify_rate_changes(changes)
                self.last_rates = new_rates
                log.info("cbr_rates_updated", changes=changes)
            return new_rates, changes
        except Exception as e:
            log.error("cbr_rates_error", error=str(e))
            return None, []
    async def notify_rate_changes(self, changes):
        timestamp = datetime.now().strftime("%H:%M:%S")
        for change in changes:
            message = (
                f"🚨 КУРС ОБНОВЛЕН! {timestamp}\n"
                f"💱 {change['currency']}: {change['old_rate']} → {change['new_rate']}\n"
                f"📈 Изменение: {change['change']:+.4f} руб"
            )
            # Здесь можно отправлять подписчикам, сейчас просто лог
            log.info("cbr_rate_change_message", message=message)
    def is_monitoring_time(self) -> bool:
        current_time = datetime.now().time()
        start_time = time(13, 0)
        end_time = time(16, 0)
        return start_time <= current_time <= end_time
    async def start_monitoring(self):
        self.session = aiohttp.ClientSession()
        self.monitoring = True
        initial_rates, _ = await self.check_rates_update()
        if initial_rates:
            self.last_rates = initial_rates
            log.info("cbr_monitoring_started", rates=self.last_rates)
        while self.monitoring:
            if self.is_monitoring_time():
                await self.check_rates_update()
                await asyncio.sleep(30)
            else:
                await asyncio.sleep(300)
    async def stop_monitoring(self):
        self.monitoring = False
        if self.session:
            await self.session.close()
        log.info("cbr_monitoring_stopped")


def build_bot() -> Bot:
    settings = get_settings()
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

async def main():
    bot = build_bot()
    dp = Dispatcher()
    dp.include_router(menu_router)
    dp.include_router(main_router)
    await bot.set_my_commands([
        BotCommand(command="start", description="Начать 🤗"),
        BotCommand(command="menu", description="Показать меню 🥰"),
        BotCommand(command="check_rates", description="Курсы валют ЦБ РФ")
    ])
    await bot.delete_webhook(drop_pending_updates=True)

    # Интеграция мониторинга ЦБ
    cbr_monitor = CBRMonitor(bot)
    asyncio.create_task(cbr_monitor.start_monitoring())

    @dp.message_handler(commands=["check_rates"])
    async def manual_check(message: types.Message):
        rates, _ = await cbr_monitor.check_rates_update()
        if rates:
            response = "💰 Текущие курсы ЦБ:\n"
            for currency, rate in rates.items():
                response += f"{currency}: {rate} руб\n"
            await message.reply(response)
        else:
            await message.reply("Не удалось получить курсы ЦБ РФ.")

    try:
        await dp.start_polling(bot)
    finally:
        await cbr_monitor.stop_monitoring()

if __name__ == "__main__":
    asyncio.run(main())
