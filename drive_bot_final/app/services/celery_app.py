from celery import Celery
from app.config import settings
 
celery_app = Celery(
    "docbot",
    broker=settings.REDIS_DSN,
    backend=settings.REDIS_DSN
) 