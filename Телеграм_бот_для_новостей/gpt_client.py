import os
import asyncio
from openai import AsyncOpenAI
from models import Article
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

# Initialize the async OpenAI client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MAX_CONCURRENT = 3
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

SYSTEM_PROMPT = "Ты аналитик, привыкший писать глубоко, но кратко."
USER_TMPL = (
    "Сделай абзац в 3–4 предложения по новости STRICTLY BELOW. "
    "Первое предложение — факт, второе — почему важно, третье — прогноз. "
    "Никаких вводных вроде 'По сообщению...'. "
    "НОВОСТЬ:\n{title}\n{summary}"
)


async def summarize(article: Article) -> str:
    """Generate a summary for the given article using OpenAI API."""
    async with semaphore:
        last_error = None
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=2, max=10)
        ):
            try:
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": USER_TMPL.format(
                                title=article.title,
                                summary=article.summary
                            )
                        }
                    ],
                    timeout=20,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                last_error = e
        return f"[GPT ERROR]: {last_error}"
