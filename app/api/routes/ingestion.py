import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ingestion_batch import IngestionBatch, SOURCE_TYPES
from app.models.raw_record import RawRecord
from app.schemas.ingestion import IngestionBatchOut, UploadResponse
from app.services.storage import storage

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    source_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if source_type not in SOURCE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"source_type must be one of {SOURCE_TYPES}",
        )
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Only .csv uploads are supported")

    content = await file.read()

    batch = IngestionBatch(
        source_type=source_type,
        status="ingesting",
        original_filename=file.filename,
        started_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    db.flush()  # assigns batch.id

    file_key = storage.save(batch.id, file.filename, content)

    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        batch.status = "failed"
        db.commit()
        raise HTTPException(status_code=422, detail=f"Could not parse CSV: {exc}") from exc

    if not rows:
        batch.status = "failed"
        db.commit()
        raise HTTPException(status_code=422, detail="CSV file has no data rows")

    for row in rows:
        db.add(
            RawRecord(
                source_type=source_type,
                file_id=file_key,
                raw_payload=row,
                batch_id=batch.id,
            )
        )

    batch.total_records = len(rows)
    batch.status = "completed"
    batch.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(batch)

    return UploadResponse(batch=IngestionBatchOut.model_validate(batch), records_ingested=len(rows))


@router.get("/batches", response_model=list[IngestionBatchOut])
def list_batches(db: Session = Depends(get_db)):
    return db.query(IngestionBatch).order_by(IngestionBatch.created_at.desc()).all()


@router.get("/batches/{batch_id}", response_model=IngestionBatchOut)
def get_batch(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    batch = db.get(IngestionBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch
