import asyncio
import aiohttp
import feedparser
import yaml
import hashlib
import datetime as dt
from models import Article

async def parse_rss(text, source):
    feed = feedparser.parse(text)
    one_day_ago = dt.datetime.utcnow() - dt.timedelta(days=2)
    for e in feed.entries:
        if hasattr(e, 'published_parsed') and e.published_parsed:
            published = dt.datetime(*e.published_parsed[:6])
        else:
            published = dt.datetime.utcnow()
        if published < one_day_ago:
            continue
        yield Article(
            id=hashlib.md5(e.link.encode()).hexdigest(),
            title=e.title,
            summary=e.get("summary", ""),
            url=e.link,
            source=source,
            published=published,
        )

async def fetch_feed(session, src):
    try:
        if src.get("rss"):
            async with session.get(src["rss"], timeout=6) as r:
                text = await r.text()
            return [a async for a in parse_rss(text, src["name"])]
        else:
            # HTML-источник: реализуйте extract_links и fetch_article
            return []
    except Exception as e:
        import logging
        logging.error(f"Ошибка при загрузке {src.get('name')}: {e}")
        return []

async def crawl():
    with open("sources.yaml", encoding="utf-8") as f:
        sources = yaml.safe_load(f)
    async with aiohttp.ClientSession(headers={"User-Agent": "GOZBot/1.0 (+https://stranagoz.ru)"}) as sess:
        tasks = [fetch_feed(sess, s) for s in sources]
        nested = await asyncio.gather(*tasks)
    return [art for sub in nested for art in sub]
