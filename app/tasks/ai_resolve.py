from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.ai_resolver import resolve_exceptions_with_ai


@celery_app.task(name="tasks.resolve_exceptions_with_ai")
def resolve_exceptions_with_ai_task(batch_id: str) -> dict:
    db = SessionLocal()
    try:
        return resolve_exceptions_with_ai(db, batch_id)
    finally:
        db.close()
