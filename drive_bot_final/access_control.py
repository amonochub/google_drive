from aiogram import types
from config import settings

async def is_allowed(user: types.User | None) -> bool:
    if user is None:
        return False
    # if no allowed users specified, allow all
    return not settings.allowed_user_ids or user.id in settings.allowed_user_ids

def access_control(handler):
    async def wrapper(message: types.Message, *args, **kwargs):
        if not await is_allowed(message.from_user):
            await message.reply("❌ У вас нет прав для использования этого бота.")
            return
        return await handler(message, *args, **kwargs)
    return wrapper
