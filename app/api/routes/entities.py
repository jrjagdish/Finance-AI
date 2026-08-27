import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entity import Entity, EntityAlias
from app.models.fee_rule import FeeRule
from app.schemas.entities import (
    AliasIn,
    AliasOut,
    EntityIn,
    EntityOut,
    EntityUpdate,
    FeeRuleIn,
    FeeRuleOut,
)

router = APIRouter(tags=["entities"])


@router.get("/entities", response_model=list[EntityOut])
def list_entities(type: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Entity)
    if type:
        q = q.filter(Entity.type == type)
    return q.order_by(Entity.canonical_name).all()


@router.post("/entities", response_model=EntityOut)
def create_entity(payload: EntityIn, db: Session = Depends(get_db)):
    if payload.type not in ("customer", "vendor"):
        raise HTTPException(status_code=422, detail="type must be 'customer' or 'vendor'")
    entity = Entity(canonical_name=payload.canonical_name, type=payload.type, entity_metadata=payload.entity_metadata)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.put("/entities/{entity_id}", response_model=EntityOut)
def update_entity(entity_id: uuid.UUID, payload: EntityUpdate, db: Session = Depends(get_db)):
    entity = db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    db.commit()
    db.refresh(entity)
    return entity


@router.post("/entities/{entity_id}/aliases", response_model=AliasOut)
def add_alias(entity_id: uuid.UUID, payload: AliasIn, db: Session = Depends(get_db)):
    entity = db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    alias = EntityAlias(entity_id=entity_id, alias_text=payload.alias_text)
    db.add(alias)
    db.commit()
    db.refresh(alias)
    return alias


@router.get("/master-data/fee-rules", response_model=list[FeeRuleOut])
def list_fee_rules(db: Session = Depends(get_db)):
    return db.query(FeeRule).filter(FeeRule.is_active.is_(True)).order_by(FeeRule.created_at.desc()).all()


@router.post("/master-data/fee-rules", response_model=FeeRuleOut)
def create_fee_rule(payload: FeeRuleIn, db: Session = Depends(get_db)):
    rule = FeeRule(name=payload.name, rule_definition=payload.rule_definition, is_active=payload.is_active)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule
