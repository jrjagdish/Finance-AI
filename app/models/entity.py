import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPkMixin, TenantMixin

ENTITY_TYPES = ("customer", "vendor")


class Entity(UUIDPkMixin, TenantMixin, Base):
    __tablename__ = "entities"

    canonical_name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(Enum(*ENTITY_TYPES, name="entity_type_enum"))
    entity_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)


class EntityAlias(UUIDPkMixin, Base):
    __tablename__ = "entity_aliases"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id"), index=True
    )
    alias_text: Mapped[str] = mapped_column(String, index=True)
