import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPkMixin, TenantMixin, _utcnow
from app.models.ingestion_batch import SOURCE_TYPES


class RawRecord(UUIDPkMixin, TenantMixin, Base):
    __tablename__ = "raw_records"

    source_type: Mapped[str] = mapped_column(Enum(*SOURCE_TYPES, name="source_type_enum"))
    file_id: Mapped[str | None] = mapped_column(nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion_batches.id"), index=True
    )
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
