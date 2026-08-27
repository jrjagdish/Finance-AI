from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPkMixin, TenantMixin, TimestampMixin


class FeeRule(UUIDPkMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "fee_rules"

    name: Mapped[str] = mapped_column(String)
    rule_definition: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
