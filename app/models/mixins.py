import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TenantMixin:
    # No auth/tenant enforcement in v1 — every row is written under a single
    # default tenant so the column doesn't need a backfill once auth lands.
    tenant_id: Mapped[str] = mapped_column(
        String, nullable=False, default=lambda: settings.default_tenant_id, index=True
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
