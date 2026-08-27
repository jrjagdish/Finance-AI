import uuid
from datetime import date

from sqlalchemy import Enum, ForeignKey, Numeric, String, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPkMixin, TenantMixin, TimestampMixin
from app.models.ingestion_batch import SOURCE_TYPES

RECORD_STATUSES = ("unmatched", "matched", "ai_suggested", "exception")


class NormalizedRecord(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "normalized_records"

    source_type: Mapped[str] = mapped_column(Enum(*SOURCE_TYPES, name="source_type_enum"))
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_records.id"), index=True
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion_batches.id"), index=True
    )

    txn_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    reference_no: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=True
    )

    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    txn_date: Mapped[date] = mapped_column(Date)

    narration_raw: Mapped[str | None] = mapped_column(String, nullable=True)
    narration_clean: Mapped[str | None] = mapped_column(String, nullable=True)

    fee_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    tax_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)

    status: Mapped[str] = mapped_column(
        Enum(*RECORD_STATUSES, name="record_status_enum"), default="unmatched"
    )
