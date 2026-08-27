from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.matching import run_matching_engine


@celery_app.task(name="tasks.run_matching_engine")
def run_matching_engine_task(tenant_id: str) -> dict:
    db = SessionLocal()
    try:
        return run_matching_engine(db, tenant_id)
    finally:
        db.close()
