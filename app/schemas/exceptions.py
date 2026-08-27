import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExceptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    record_id: uuid.UUID
    ai_suggested_match_id: uuid.UUID | None
    confidence_tier: str | None
    reason_code: str
    explanation: str | None
    needs_human_review: bool
    status: str
    reviewer_id: str | None
    reviewer_comment: str | None
    created_at: datetime
    resolved_at: datetime | None


class RejectIn(BaseModel):
    reviewer_id: str | None = None
    reviewer_comment: str | None = None


class ApproveIn(BaseModel):
    reviewer_id: str | None = None
    reviewer_comment: str | None = None


class EditIn(BaseModel):
    matched_record_id: uuid.UUID
    reviewer_id: str | None = None
    reviewer_comment: str | None = None


class CommentIn(BaseModel):
    reviewer_id: str | None = None
    comment: str


class CreateRuleIn(BaseModel):
    rule_definition: dict


class FeedbackIn(BaseModel):
    reviewer_id: str | None = None
    rating: str  # "helpful" | "not_helpful"
    comment: str | None = None
