import logging
import time
from functools import wraps

def log_operation(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            logging.info(f"AUDIT: {func.__name__} duration={duration:.2f}s result={result}")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logging.error(f"AUDIT: {func.__name__} duration={duration:.2f}s error={e}")
            raise
    return wrapper 