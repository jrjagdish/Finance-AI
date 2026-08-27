import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ingestion_batch import IngestionBatch
from app.models.normalized_record import NormalizedRecord
from app.schemas.records import NormalizedRecordOut, NormalizeRunResponse, NormalizeStatusResponse
from app.tasks.normalize import normalize_batch_task

router = APIRouter(tags=["normalization"])


@router.post("/normalize/run/{batch_id}", response_model=NormalizeRunResponse)
def run_normalization(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    batch = db.get(IngestionBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    async_result = normalize_batch_task.delay(str(batch_id))
    return NormalizeRunResponse(batch_id=batch_id, task_id=async_result.id, status="queued")


@router.get("/normalize/status/{batch_id}", response_model=NormalizeStatusResponse)
def normalization_status(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    batch = db.get(IngestionBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return NormalizeStatusResponse(batch_id=batch_id, status=batch.status, total_records=batch.total_records)


@router.get("/records", response_model=list[NormalizedRecordOut])
def list_records(
    source_type: str | None = None,
    status: str | None = None,
    entity_id: uuid.UUID | None = None,
    batch_id: uuid.UUID | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(NormalizedRecord)
    if source_type:
        q = q.filter(NormalizedRecord.source_type == source_type)
    if status:
        q = q.filter(NormalizedRecord.status == status)
    if entity_id:
        q = q.filter(NormalizedRecord.entity_id == entity_id)
    if batch_id:
        q = q.filter(NormalizedRecord.batch_id == batch_id)
    return q.order_by(NormalizedRecord.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/records/{record_id}", response_model=NormalizedRecordOut)
def get_record(record_id: uuid.UUID, db: Session = Depends(get_db)):
    record = db.get(NormalizedRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return record
