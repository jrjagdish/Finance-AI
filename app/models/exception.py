import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPkMixin, TenantMixin, TimestampMixin

CONFIDENCE_TIERS = ("low", "medium", "high")
EXCEPTION_STATUSES = ("open", "approved", "rejected", "edited", "resolved")

REASON_CODES = (
    "AMT_MISMATCH",
    "FEE_DEDUCTED",
    "MISSING_REFERENCE",
    "SPLIT_PAYMENT",
    "DUPLICATE",
    "UNKNOWN_COUNTERPARTY",
)


class Exception_(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "exceptions"

    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("normalized_records.id"), index=True
    )
    ai_suggested_match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id"), nullable=True
    )

    confidence_tier: Mapped[str | None] = mapped_column(
        Enum(*CONFIDENCE_TIERS, name="confidence_tier_enum"), nullable=True
    )
    reason_code: Mapped[str] = mapped_column(Enum(*REASON_CODES, name="reason_code_enum"))
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    needs_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(
        Enum(*EXCEPTION_STATUSES, name="exception_status_enum"), default="open"
    )

    reviewer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
