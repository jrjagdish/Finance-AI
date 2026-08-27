from celery import Celery

from app.core.config import settings

celery_app = Celery("finance_ai", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])

from app import tasks  # noqa: E402,F401  (imported after celery_app exists — registers all @celery_app.task defs)
