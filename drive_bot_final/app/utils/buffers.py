import redis.asyncio as redis
import pickle
from app.config import settings

redis_client = redis.from_url(settings.REDIS_DSN)

async def add_file(user_id: int, file_info):
    key = f"buffer:{user_id}"
    await redis_client.rpush(key, pickle.dumps(file_info))
    await redis_client.expire(key, settings.CACHE_TTL)

async def get_batch(user_id: int):
    key = f"buffer:{user_id}"
    data = await redis_client.lrange(key, 0, -1)
    return [pickle.loads(x) for x in data]

async def flush_batch(user_id: int):
    key = f"buffer:{user_id}"
    data = await get_batch(user_id)
    await redis_client.delete(key)
    return data

async def get_size(user_id: int):
    key = f"buffer:{user_id}"
    return await redis_client.llen(key)

async def set_ttl(user_id: int, ttl: int):
    key = f"buffer:{user_id}"
    await redis_client.expire(key, ttl) 