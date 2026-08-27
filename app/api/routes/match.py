import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ingestion_batch import IngestionBatch
from app.models.match import Match
from app.models.matching_rule import MatchingRule
from app.schemas.match import MatchingRuleIn, MatchingRuleOut, MatchOut, MatchRunResponse
from app.services.matching import run_matching_engine

router = APIRouter(prefix="/match", tags=["matching"])


@router.post("/run/{batch_id}", response_model=MatchRunResponse)
def run_match(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    batch = db.get(IngestionBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    batch.status = "matching"
    db.flush()
    counts = run_matching_engine(db, batch.tenant_id)
    batch.status = "completed"
    db.commit()

    return MatchRunResponse(batch_id=batch_id, counts=counts)


@router.get("/results", response_model=list[MatchOut])
def list_matches(
    match_type: str | None = None,
    matched_by: str | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Match)
    if match_type:
        q = q.filter(Match.match_type == match_type)
    if matched_by:
        q = q.filter(Match.matched_by == matched_by)
    return q.order_by(Match.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/results/{match_id}", response_model=MatchOut)
def get_match(match_id: uuid.UUID, db: Session = Depends(get_db)):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


@router.post("/rules", response_model=MatchingRuleOut)
def create_rule(payload: MatchingRuleIn, db: Session = Depends(get_db)):
    rule = MatchingRule(rule_definition=payload.rule_definition, is_active=payload.is_active)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/rules", response_model=list[MatchingRuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.query(MatchingRule).filter(MatchingRule.is_active.is_(True)).order_by(MatchingRule.created_at.desc()).all()
