"""
Ежедневный воркфлоу «Страна ГОЗ»:
1. собрать свежие новости из sources.yaml
2. отфильтровать уже отправленные
3. сгенерировать краткие сводки через GPT
4. сохранить ID отправленных статей
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from news_parser import crawl          # async -> List[Article]
from sent_storage import filter_new, mark_sent, init_db
from gpt_client import summarize as generate_summary  # async -> str
from models import Article             # dataclass Article

# --- настройка логов ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# сколько одновременно запросов к GPT
MAX_CONCURRENT_GPT = 3
# брать новости не старше N дней
MAX_AGE_DAYS = 3

# --- Ключевые слова для фильтрации ГОЗ-новостей ---
KEYWORDS = [
    "государственный оборонный заказ", "гоз", "275-фз", "44-фз", "223-фз",
    "контракт гоз", "исполнение государственного контракта", "сопровождение контрактов",
    "отчетность по гоз", "раздельный учет гоз", "аудиторская проверка",
    "ценообразование гоз", "финансовое сопровождение", "банковское сопровождение гоз",
    "казначейское сопровождение гоз", "нмцк",
    "контроль исполнения гоз", "проверки фас", "прокуратура", "административная ответственность",
    "нарушение условий гоз", "судебная практика гоз",
    "тендеры гоз", "конкурсы гоз", "электронные торговые площадки гоз",
    "работа с военпредом", "мобилизационное планирование",
    "новости оборонной промышленности", "модернизация гоз", "цифровые решения гоз"
]

def contains_keywords(text: str) -> bool:
    text = text.lower()
    return any(k in text for k in KEYWORDS)

async def filter_fresh(articles: List[Article]) -> List[Article]:
    """Оставляем только свежие статьи (не старше MAX_AGE_DAYS)."""
    return [a for a in articles if a.published and a.published > datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)]

# --- Категории для квотирования ---
CATEGORIES = {
    "gos_it":  ["цифр", "гис", "госуслуг", "it", "информац"],
    "zakon":   ["закон", "поправк", "фз", "постановлен"],
    "export":  ["втс", "экспорт", "иапо", "рособоронэксп"],
    "nauka":   ["исследован", "опытно", "ниокр"],
    "contracts":["контракт", "гособоронзаказ", "гоз", "многомиллиард"],
}

def categorize(a: Article) -> str | None:
    text = (a.title + " " + a.summary).lower()
    for cat, kw in CATEGORIES.items():
        if any(k in text for k in kw):
            return cat
    return None

async def worker_gpt(sem: asyncio.Semaphore, article: Article) -> tuple[Article, str]:
    """Обернуть вызов GPT семафором, чтобы быть дружелюбным к Rate-Limit."""
    async with sem:
        summary = await generate_summary(article)
    return article, summary

async def main() -> None:
    logging.info("🚀 Старт ежедневного воркфлоу")
    init_db()
    # 1️⃣  собираем статьи
    articles: List[Article] = await crawl()
    logging.info("Новых статей от источников: %d", len(articles))

    # 2️⃣  фильтруем по дате и дублям
    fresh = await filter_fresh(articles)
    fresh = filter_new(fresh)
    # 2b: фильтрация по ключевым словам
    fresh = [a for a in fresh if contains_keywords(a.title) or contains_keywords(a.summary)]
    logging.info("После фильтра дублей, даты и ключевых слов осталось: %d", len(fresh))
    if not fresh:
        logging.info("Нечего отправлять — выходим.")
        return

    # --- Квотирование по категориям ---
    from collections import defaultdict
    import random
    cats = defaultdict(list)
    for art in fresh:
        c = categorize(art)
        if c:
            cats[c].append(art)
    picked = []
    for cat, lst in cats.items():
        lst = sorted(lst, key=lambda a: a.published, reverse=True)[:3]  # топ-3 свежих
        random.shuffle(lst)
        if lst:
            picked.append(lst[0])
    picked = picked[:5]  # максимум 5 новостей в выдаче
    logging.info("Выбрано по категориям: %s", {cat: (lst[0].title if lst else None) for cat, lst in cats.items()})
    if not picked:
        logging.info("Нет подходящих статей по категориям.")
        return

    # 3️⃣  генерируем сводки через GPT
    sem = asyncio.Semaphore(MAX_CONCURRENT_GPT)
    tasks = [worker_gpt(sem, art) for art in picked]
    done_pairs = await asyncio.gather(*tasks, return_exceptions=False)

    # 4️⃣  здесь вы можете отправить всё в Telegram / e-mail / куда нужно
    for art, summary in done_pairs:
        # пример: печатаем в консоль (замените на bot.publish(...))
        logging.info(
            "\n📌 %s\n%s\nИсточник: %s\n",
            art.title,
            summary.strip(),
            art.url,
        )
        # помечаем как отправленную
        mark_sent(art.id, art.published)

    logging.info("✅ Завершено: %d статей обработано", len(done_pairs))

if __name__ == "__main__":
    asyncio.run(main()) 