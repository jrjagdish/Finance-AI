import uuid

from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPkMixin, TenantMixin, TimestampMixin


class MatchingRule(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "matching_rules"

    rule_definition: Mapped[dict] = mapped_column(JSONB)
    created_from_exception_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exceptions.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
