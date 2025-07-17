import logging
import time
from aiogram.dispatcher.middlewares.base import BaseMiddleware
import json

logger = logging.getLogger(__name__)

class MonitoringMiddleware(BaseMiddleware):
    def __init__(self, slow_threshold=1.0):
        super().__init__()
        self.slow_threshold = slow_threshold  # seconds

    async def __call__(self, handler, event, data):
        start = time.monotonic()
        user_id = None
        update_type = None
        try:
            # Безопасно получаем user_id
            user_id = getattr(getattr(event, 'from_user', None), 'id', None)
            if user_id is None:
                message = getattr(event, 'message', None)
                user_id = getattr(getattr(message, 'from_user', None), 'id', None)
            # Определяем тип апдейта
            if hasattr(event, 'message'):
                update_type = 'message'
            elif hasattr(event, 'callback_query'):
                update_type = 'callback_query'
            else:
                update_type = type(event).__name__
            result = await handler(event, data)
            duration = time.monotonic() - start
            if duration > self.slow_threshold:
                logger.warning(json.dumps({
                    "event": "slow_update",
                    "user_id": user_id,
                    "update_type": update_type,
                    "duration": duration,
                }, ensure_ascii=False))
            else:
                logger.info(json.dumps({
                    "event": "update",
                    "user_id": user_id,
                    "update_type": update_type,
                    "duration": duration,
                }, ensure_ascii=False))
            return result
        except Exception as e:
            duration = time.monotonic() - start
            logger.error(json.dumps({
                "event": "error",
                "user_id": user_id,
                "update_type": update_type,
                "duration": duration,
                "error": str(e),
            }, ensure_ascii=False))
            raise 