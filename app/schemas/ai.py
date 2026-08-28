import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AIResolveResponse(BaseModel):
    batch_id: uuid.UUID
    task_id: str


class LLMCallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exception_id: uuid.UUID | None
    model_name: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    created_at: datetime


class LLMUsageSummary(BaseModel):
    total_calls: int
    total_prompt_tokens: int
    total_completion_tokens: int
    avg_latency_ms: float | None
    by_model: dict[str, int]
