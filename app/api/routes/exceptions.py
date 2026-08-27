import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit_log import MatchAuditLog
from app.models.exception import Exception_
from app.models.match import Match
from app.models.matching_rule import MatchingRule
from app.models.normalized_record import NormalizedRecord
from app.schemas.exceptions import (
    ApproveIn,
    CommentIn,
    CreateRuleIn,
    EditIn,
    ExceptionOut,
    RejectIn,
)
from app.schemas.match import MatchingRuleOut

router = APIRouter(prefix="/exceptions", tags=["exceptions"])


def _other_record_ids(match: Match) -> list[uuid.UUID]:
    return [rid for rid in (match.ledger_record_id, match.bank_record_id, match.gateway_record_id) if rid]


def _audit(db: Session, subject_id: uuid.UUID, action: str, actor: str, actor_id: str | None, payload: dict):
    db.add(MatchAuditLog(subject_id=subject_id, action=action, actor=actor, actor_id=actor_id, payload=payload))


@router.get("", response_model=list[ExceptionOut])
def list_exceptions(
    reason_code: str | None = None,
    confidence_tier: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Exception_)
    if reason_code:
        q = q.filter(Exception_.reason_code == reason_code)
    if confidence_tier:
        q = q.filter(Exception_.confidence_tier == confidence_tier)
    if status:
        q = q.filter(Exception_.status == status)
    return q.order_by(Exception_.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{exception_id}", response_model=ExceptionOut)
def get_exception(exception_id: uuid.UUID, db: Session = Depends(get_db)):
    exception = db.get(Exception_, exception_id)
    if exception is None:
        raise HTTPException(status_code=404, detail="Exception not found")
    return exception


@router.post("/{exception_id}/approve", response_model=ExceptionOut)
def approve_exception(exception_id: uuid.UUID, payload: ApproveIn, db: Session = Depends(get_db)):
    exception = db.get(Exception_, exception_id)
    if exception is None:
        raise HTTPException(status_code=404, detail="Exception not found")
    if exception.ai_suggested_match_id is None:
        raise HTTPException(status_code=422, detail="Exception has no AI-suggested match to approve")

    match = db.get(Match, exception.ai_suggested_match_id)
    match.matched_by = "human"
    match.confidence_score = Decimal("1.0")

    record = db.get(NormalizedRecord, exception.record_id)
    record.status = "matched"
    for other_id in _other_record_ids(match):
        other = db.get(NormalizedRecord, other_id)
        if other:
            other.status = "matched"

    exception.status = "approved"
    exception.needs_human_review = False
    exception.reviewer_id = payload.reviewer_id
    exception.reviewer_comment = payload.reviewer_comment
    exception.resolved_at = datetime.now(timezone.utc)

    _audit(db, exception.id, "approve", "user", payload.reviewer_id, {"match_id": str(match.id)})
    db.commit()
    db.refresh(exception)
    return exception


@router.post("/{exception_id}/reject", response_model=ExceptionOut)
def reject_exception(exception_id: uuid.UUID, payload: RejectIn, db: Session = Depends(get_db)):
    exception = db.get(Exception_, exception_id)
    if exception is None:
        raise HTTPException(status_code=404, detail="Exception not found")

    record = db.get(NormalizedRecord, exception.record_id)
    record.status = "unmatched"

    if exception.ai_suggested_match_id is not None:
        match = db.get(Match, exception.ai_suggested_match_id)
        if match:
            for other_id in _other_record_ids(match):
                other = db.get(NormalizedRecord, other_id)
                if other:
                    other.status = "unmatched"
            db.delete(match)
        exception.ai_suggested_match_id = None

    exception.status = "rejected"
    exception.needs_human_review = False
    exception.reviewer_id = payload.reviewer_id
    exception.reviewer_comment = payload.reviewer_comment
    exception.resolved_at = datetime.now(timezone.utc)

    _audit(db, exception.id, "reject", "user", payload.reviewer_id, {})
    db.commit()
    db.refresh(exception)
    return exception


@router.post("/{exception_id}/edit", response_model=ExceptionOut)
def edit_exception(exception_id: uuid.UUID, payload: EditIn, db: Session = Depends(get_db)):
    exception = db.get(Exception_, exception_id)
    if exception is None:
        raise HTTPException(status_code=404, detail="Exception not found")

    record = db.get(NormalizedRecord, exception.record_id)
    matched_record = db.get(NormalizedRecord, payload.matched_record_id)
    if matched_record is None:
        raise HTTPException(status_code=404, detail="matched_record_id not found")

    match = Match(
        tenant_id=exception.tenant_id,
        ledger_record_id=record.id if record.source_type == "ledger" else matched_record.id if matched_record.source_type == "ledger" else None,
        bank_record_id=record.id if record.source_type == "bank" else matched_record.id if matched_record.source_type == "bank" else None,
        gateway_record_id=record.id if record.source_type == "gateway" else matched_record.id if matched_record.source_type == "gateway" else None,
        match_type="manual",
        confidence_score=Decimal("1.0"),
        matched_by="human",
    )
    db.add(match)
    db.flush()

    record.status = "matched"
    matched_record.status = "matched"

    exception.ai_suggested_match_id = match.id
    exception.status = "edited"
    exception.needs_human_review = False
    exception.reviewer_id = payload.reviewer_id
    exception.reviewer_comment = payload.reviewer_comment
    exception.resolved_at = datetime.now(timezone.utc)

    _audit(db, exception.id, "edit", "user", payload.reviewer_id, {"match_id": str(match.id)})
    db.commit()
    db.refresh(exception)
    return exception


@router.post("/{exception_id}/comment", response_model=ExceptionOut)
def comment_exception(exception_id: uuid.UUID, payload: CommentIn, db: Session = Depends(get_db)):
    exception = db.get(Exception_, exception_id)
    if exception is None:
        raise HTTPException(status_code=404, detail="Exception not found")

    exception.reviewer_comment = payload.comment
    exception.reviewer_id = payload.reviewer_id or exception.reviewer_id

    _audit(db, exception.id, "comment", "user", payload.reviewer_id, {"comment": payload.comment})
    db.commit()
    db.refresh(exception)
    return exception


@router.post("/{exception_id}/create-rule", response_model=MatchingRuleOut)
def create_rule_from_exception(exception_id: uuid.UUID, payload: CreateRuleIn, db: Session = Depends(get_db)):
    exception = db.get(Exception_, exception_id)
    if exception is None:
        raise HTTPException(status_code=404, detail="Exception not found")

    rule = MatchingRule(
        tenant_id=exception.tenant_id,
        rule_definition=payload.rule_definition,
        created_from_exception_id=exception.id,
        is_active=True,
    )
    db.add(rule)
    _audit(db, exception.id, "create_rule", "user", None, {"rule_definition": payload.rule_definition})
    db.commit()
    db.refresh(rule)
    return rule
