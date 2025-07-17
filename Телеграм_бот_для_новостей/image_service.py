import os
import openai
import aiohttp
from models import Article

openai.api_key = os.getenv("OPENAI_API_KEY")

async def generate_cover(title: str, summary: str = "") -> bytes:
    # Формируем промпт для инфографики
    prompt = (
        f"Инфографика, современный стиль, иллюстрирующая: {title}. "
        f"Краткое описание: {summary}. "
        f"Без текста, чистая визуализация, оборонная промышленность, Россия."
    )
    response = await openai.images.async_generate(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024"
    )
    image_url = response['data'][0]['url']
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as resp:
            return await resp.read() 