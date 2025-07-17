import os
import openai
import asyncio
from models import Article
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

openai.api_key = os.getenv("OPENAI_API_KEY")

MAX_CONCURRENT = 3
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

SYSTEM_PROMPT = "Ты аналитик, привыкший писать глубоко, но кратко."
USER_TMPL = (
    "Сделай абзац в 3–4 предложения по новости STRICTLY BELOW. "
    "Первое предложение — факт, второе — почему важно, третье — прогноз. "
    "Никаких вводных вроде ‘По сообщению...’. "
    "НОВОСТЬ:\n{title}\n{summary}"
)

async def summarize(article: Article) -> str:
    async with semaphore:
        async for attempt in AsyncRetrying(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10)):
            try:
                resp = await openai.ChatCompletion.acreate(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": USER_TMPL.format(title=article.title, summary=article.summary)}
                    ],
                    timeout=20,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                last_error = e
        return f"[GPT ERROR]: {last_error}" 