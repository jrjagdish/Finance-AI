import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class NormalizedRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: str
    batch_id: uuid.UUID
    txn_id: str | None
    reference_no: str | None
    entity_id: uuid.UUID | None
    amount: Decimal
    currency: str
    txn_date: date
    narration_raw: str | None
    narration_clean: str | None
    fee_amount: Decimal | None
    tax_amount: Decimal | None
    status: str
    created_at: datetime


class NormalizeRunResponse(BaseModel):
    batch_id: uuid.UUID
    task_id: str | None
    status: str


class NormalizeStatusResponse(BaseModel):
    batch_id: uuid.UUID
    status: str
    total_records: int
