import structlog
import time
from functools import wraps

log = structlog.get_logger(__name__)

def log_operation(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            log.info("audit_success", func=func.__name__, duration=duration, result=str(result))
            return result
        except Exception as e:
            duration = time.time() - start_time
            log.error("audit_error", func=func.__name__, duration=duration, error=str(e))
            raise
    return wrapper 