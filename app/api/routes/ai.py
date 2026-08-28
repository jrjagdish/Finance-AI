import uuid

import inngest
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.inngest_client import inngest_client
from app.models.exception import Exception_
from app.models.ingestion_batch import IngestionBatch
from app.schemas.ai import AIResolveResponse
from app.schemas.exceptions import ExceptionOut, FeedbackIn
from app.models.audit_log import MatchAuditLog

router = APIRouter(prefix="/ai", tags=["ai-resolver"])


@router.post("/resolve/{batch_id}", response_model=AIResolveResponse)
def trigger_ai_resolve(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    batch = db.get(IngestionBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    event_ids = inngest_client.send_sync(
        inngest.Event(name="finance/exceptions.ai_resolve", data={"batch_id": str(batch_id)})
    )
    return AIResolveResponse(batch_id=batch_id, task_id=event_ids[0] if event_ids else None)


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
