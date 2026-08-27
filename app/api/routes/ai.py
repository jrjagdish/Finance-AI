import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.session import get_db
from app.models.exception import Exception_
from app.models.ingestion_batch import IngestionBatch
from app.schemas.ai import AIJobStatus, AIResolveResponse
from app.schemas.exceptions import ExceptionOut, FeedbackIn
from app.tasks.ai_resolve import resolve_exceptions_with_ai_task
from app.models.audit_log import MatchAuditLog

router = APIRouter(prefix="/ai", tags=["ai-resolver"])


@router.post("/resolve/{batch_id}", response_model=AIResolveResponse)
def trigger_ai_resolve(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    batch = db.get(IngestionBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    async_result = resolve_exceptions_with_ai_task.delay(str(batch_id))
    return AIResolveResponse(batch_id=batch_id, task_id=async_result.id)


@router.get("/resolve/status/{job_id}", response_model=AIJobStatus)
def ai_resolve_status(job_id: str):
    result = celery_app.AsyncResult(job_id)
    return AIJobStatus(
        job_id=job_id,
        state=result.state,
        result=result.result if result.successful() else None,
    )


@router.get("/suggestions", response_model=list[ExceptionOut])
def list_suggestions(confidence_tier: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Exception_).filter(Exception_.ai_suggested_match_id.isnot(None))
    if confidence_tier:
        q = q.filter(Exception_.confidence_tier == confidence_tier)
    return q.order_by(Exception_.created_at.desc()).all()


@router.get("/suggestions/{exception_id}", response_model=ExceptionOut)
def get_suggestion(exception_id: uuid.UUID, db: Session = Depends(get_db)):
    exception = db.get(Exception_, exception_id)
    if exception is None or exception.ai_suggested_match_id is None:
        raise HTTPException(status_code=404, detail="AI suggestion not found")
    return exception


@router.post("/suggestions/{exception_id}/feedback")
def suggestion_feedback(exception_id: uuid.UUID, payload: FeedbackIn, db: Session = Depends(get_db)):
    exception = db.get(Exception_, exception_id)
    if exception is None:
        raise HTTPException(status_code=404, detail="Exception not found")

    db.add(
        MatchAuditLog(
            subject_id=exception.id,
            action="ai_feedback",
            actor="user",
            actor_id=payload.reviewer_id,
            payload={"rating": payload.rating, "comment": payload.comment},
        )
    )
    db.commit()
    return {"status": "recorded"}
