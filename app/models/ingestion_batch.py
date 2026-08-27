import uuid
from datetime import datetime

from sqlalchemy import Enum, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPkMixin, TenantMixin, TimestampMixin

SOURCE_TYPES = ("ledger", "bank", "gateway", "master")
BATCH_STATUSES = ("pending", "ingesting", "normalizing", "matching", "ai_resolving", "completed", "failed")


class IngestionBatch(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "ingestion_batches"

    source_type: Mapped[str] = mapped_column(Enum(*SOURCE_TYPES, name="source_type_enum"))
    status: Mapped[str] = mapped_column(
        Enum(*BATCH_STATUSES, name="batch_status_enum"), default="pending"
    )
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
