import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPkMixin, TenantMixin, TimestampMixin


class LLMCall(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "llm_calls"

    exception_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exceptions.id"), nullable=True
    )
    model_name: Mapped[str] = mapped_column(String)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
