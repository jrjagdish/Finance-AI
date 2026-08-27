from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.llm_call import LLMCall
from app.schemas.ai import LLMUsageSummary

router = APIRouter(tags=["llm"])


@router.get("/llm/usage", response_model=LLMUsageSummary)
def llm_usage(db: Session = Depends(get_db)):
    calls = db.query(LLMCall).all()
    total_calls = len(calls)
    total_prompt_tokens = sum(c.prompt_tokens or 0 for c in calls)
    total_completion_tokens = sum(c.completion_tokens or 0 for c in calls)
    latencies = [c.latency_ms for c in calls if c.latency_ms is not None]
    avg_latency_ms = sum(latencies) / len(latencies) if latencies else None
    by_model = dict(Counter(c.model_name for c in calls))

    return LLMUsageSummary(
        total_calls=total_calls,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        avg_latency_ms=avg_latency_ms,
        by_model=by_model,
    )
