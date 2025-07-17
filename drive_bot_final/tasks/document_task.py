from .celery_app import celery
import logging
logger = logging.getLogger(__name__)
@celery.task
def dummy(x):
    logger.info(f"Dummy task called with x={x}")
    return x * 2
