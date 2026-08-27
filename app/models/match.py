import uuid

from sqlalchemy import Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPkMixin, TenantMixin, TimestampMixin

MATCH_TYPES = ("exact", "reference", "amount_tolerance", "date_window", "one_to_many", "ai_suggested")
MATCHED_BY = ("rule", "ai", "human")


class Match(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "matches"

    ledger_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("normalized_records.id"), nullable=True
    )
    bank_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("normalized_records.id"), nullable=True
    )
    gateway_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("normalized_records.id"), nullable=True
    )

    match_type: Mapped[str] = mapped_column(Enum(*MATCH_TYPES, name="match_type_enum"))
    confidence_score: Mapped[float] = mapped_column(Numeric(4, 3), default=1.0)
    matched_by: Mapped[str] = mapped_column(Enum(*MATCHED_BY, name="matched_by_enum"))
