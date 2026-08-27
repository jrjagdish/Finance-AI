import uuid

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPkMixin, TimestampMixin

ACTORS = ("system", "ai", "user")


class MatchAuditLog(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "match_audit_log"

    # References either a match or an exception, depending on `action`.
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    action: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(Enum(*ACTORS, name="audit_actor_enum"))
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
