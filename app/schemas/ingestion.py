import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IngestionBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: str
    status: str
    total_records: int
    original_filename: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class UploadResponse(BaseModel):
    batch: IngestionBatchOut
    records_ingested: int
