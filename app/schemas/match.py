import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ledger_record_id: uuid.UUID | None
    bank_record_id: uuid.UUID | None
    gateway_record_id: uuid.UUID | None
    match_type: str
    confidence_score: Decimal
    matched_by: str
    created_at: datetime


class MatchRunResponse(BaseModel):
    batch_id: uuid.UUID
    counts: dict[str, int]


class MatchingRuleIn(BaseModel):
    rule_definition: dict
    is_active: bool = True


class MatchingRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_definition: dict
    is_active: bool
    created_at: datetime
