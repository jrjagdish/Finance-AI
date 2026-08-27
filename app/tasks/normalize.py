from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.normalization import normalize_batch


@celery_app.task(name="tasks.normalize_batch")
def normalize_batch_task(batch_id: str) -> dict:
    db = SessionLocal()
    try:
        return normalize_batch(db, batch_id)
    finally:
        db.close()
