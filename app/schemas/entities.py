import uuid

from pydantic import BaseModel, ConfigDict


class EntityIn(BaseModel):
    canonical_name: str
    type: str
    entity_metadata: dict = {}


class EntityUpdate(BaseModel):
    canonical_name: str | None = None
    type: str | None = None
    entity_metadata: dict | None = None


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canonical_name: str
    type: str
    entity_metadata: dict


class AliasIn(BaseModel):
    alias_text: str


class AliasOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID
    alias_text: str


class FeeRuleIn(BaseModel):
    name: str
    rule_definition: dict
    is_active: bool = True


class FeeRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    rule_definition: dict
    is_active: bool
