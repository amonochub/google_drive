from celery import Celery
from config import settings
celery = Celery('document_tasks', broker=settings.redis_url, backend=settings.redis_url)
