from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.synthetic_data import generate_synthetic_dataset

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/synthetic-data")
def synthetic_data(
    total_records: int = Query(default=100, ge=50, le=500),
    seed: int | None = None,
    db: Session = Depends(get_db),
):
    return generate_synthetic_dataset(db, total_records=total_records, seed=seed)
