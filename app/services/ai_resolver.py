import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.exception import REASON_CODES, Exception_
from app.models.llm_call import LLMCall
from app.models.match import Match
from app.models.normalized_record import NormalizedRecord

CANDIDATE_DATE_WINDOW_DAYS = 30
CANDIDATE_AMOUNT_TOLERANCE_PCT = Decimal("0.25")
MAX_CANDIDATES = 10


class AIMatchSuggestion(BaseModel):
    match_candidate_id: str | None = Field(
        default=None, description="id of the best matching candidate record, or null if none is a good match"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reason_code: Literal[*REASON_CODES]  # type: ignore[valid-type]
    explanation: str = Field(description="Plain-language explanation for a finance analyst")


def _confidence_tier(confidence: float) -> str:
    if confidence >= settings.ai_high_confidence:
        return "high"
    if confidence >= settings.ai_medium_confidence:
        return "medium"
    return "low"


def _find_candidates(db: Session, record: NormalizedRecord) -> list[NormalizedRecord]:
    other_sources = [s for s in ("ledger", "bank", "gateway") if s != record.source_type]
    lo = record.txn_date - timedelta(days=CANDIDATE_DATE_WINDOW_DAYS)
    hi = record.txn_date + timedelta(days=CANDIDATE_DATE_WINDOW_DAYS)

    q = (
        db.query(NormalizedRecord)
        .filter(
            NormalizedRecord.tenant_id == record.tenant_id,
            NormalizedRecord.source_type.in_(other_sources),
            NormalizedRecord.status == "unmatched",
            NormalizedRecord.id != record.id,
            NormalizedRecord.txn_date >= lo,
            NormalizedRecord.txn_date <= hi,
        )
        .all()
    )

    def score(c: NormalizedRecord) -> tuple:
        amount_diff = abs(c.amount - record.amount)
        date_diff = abs((c.txn_date - record.txn_date).days)
        same_entity = 0 if (record.entity_id and c.entity_id == record.entity_id) else 1
        return (same_entity, amount_diff, date_diff)

    return sorted(q, key=score)[:MAX_CANDIDATES]


def _build_prompt_payload(record: NormalizedRecord, candidates: list[NormalizedRecord]) -> str:
    lines = [
        "You are a finance reconciliation assistant. A transaction record could not be "
        "deterministically matched to a counterpart record. Decide whether one of the "
        "candidate records below is the true match, accounting for gateway fees/taxes "
        "deducted from settlement amounts, split payments, and messy bank narrations.",
        "",
        f"UNMATCHED RECORD (source={record.source_type}):",
        f"  id: {record.id}",
        f"  amount: {record.amount} {record.currency}",
        f"  date: {record.txn_date}",
        f"  reference_no: {record.reference_no}",
        f"  narration: {record.narration_clean or record.narration_raw}",
        "",
        "CANDIDATE RECORDS:",
    ]
    if not candidates:
        lines.append("  (none found within the date/amount search window)")
    for c in candidates:
        lines.append(
            f"  - id: {c.id} | source={c.source_type} | amount={c.amount} {c.currency} | "
            f"date={c.txn_date} | reference_no={c.reference_no} | "
            f"narration={c.narration_clean or c.narration_raw}"
        )
    lines += [
        "",
        "Reason codes you may choose from: " + ", ".join(REASON_CODES) + ".",
        "If no candidate is a good match, set match_candidate_id to null and choose the "
        "most fitting reason code (e.g. UNKNOWN_COUNTERPARTY if no candidate is plausible, "
        "MISSING_REFERENCE if a reference number would have resolved it, AMT_MISMATCH if "
        "amounts don't reconcile, FEE_DEDUCTED if the gap looks like a gateway fee/tax, "
        "SPLIT_PAYMENT if this looks like part of a multi-part payment, DUPLICATE if this "
        "looks like a duplicate of an already-processed transaction).",
    ]
    return "\n".join(lines)


def _call_groq(prompt: str) -> tuple[AIMatchSuggestion | None, dict]:
    """Returns (suggestion, meta). suggestion is None if the LLM call failed —
    callers must degrade to an unresolved exception rather than raise.
    """
    if not settings.groq_api_key:
        return None, {"error": "GROQ_API_KEY not configured", "model": settings.groq_model}

    from langchain_groq import ChatGroq  # imported lazily so the package is optional until a key is set

    start = time.monotonic()
    try:
        llm = ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key, temperature=0, timeout=20)
        structured_llm = llm.with_structured_output(AIMatchSuggestion, include_raw=True)
        result = structured_llm.invoke(prompt)
        latency_ms = int((time.monotonic() - start) * 1000)

        parsed: AIMatchSuggestion | None = result.get("parsed")
        raw_msg = result.get("raw")
        usage = getattr(raw_msg, "usage_metadata", None) or {}

        meta = {
            "model": settings.groq_model,
            "latency_ms": latency_ms,
            "prompt_tokens": usage.get("input_tokens"),
            "completion_tokens": usage.get("output_tokens"),
            "raw_response": {"content": getattr(raw_msg, "content", None)},
        }
        return parsed, meta
    except Exception as exc:  # noqa: BLE001 — any provider/network failure must degrade, not crash the batch
        latency_ms = int((time.monotonic() - start) * 1000)
        return None, {"error": str(exc), "model": settings.groq_model, "latency_ms": latency_ms}


def resolve_exception_for_record(db: Session, record: NormalizedRecord) -> Exception_:
    candidates = _find_candidates(db, record)
    prompt = _build_prompt_payload(record, candidates)
    suggestion, meta = _call_groq(prompt)

    db.add(
        LLMCall(
            tenant_id=record.tenant_id,
            model_name=meta.get("model", settings.groq_model),
            prompt_tokens=meta.get("prompt_tokens"),
            completion_tokens=meta.get("completion_tokens"),
            latency_ms=meta.get("latency_ms"),
            raw_response=meta.get("raw_response") or {"error": meta.get("error")},
        )
    )

    ai_match_id: uuid.UUID | None = None
    if suggestion is None:
        confidence_tier = None
        reason_code = "UNKNOWN_COUNTERPARTY" if record.entity_id is None else "AMT_MISMATCH"
        explanation = (
            "AI resolution unavailable ("
            + meta.get("error", "unknown error")
            + "). Flagged for manual review."
        )
    else:
        reason_code = suggestion.reason_code
        explanation = suggestion.explanation
        confidence_tier = _confidence_tier(suggestion.confidence)

        if suggestion.match_candidate_id:
            candidate = next((c for c in candidates if str(c.id) == suggestion.match_candidate_id), None)
            if candidate is not None and confidence_tier in ("high", "medium"):
                match = Match(
                    tenant_id=record.tenant_id,
                    ledger_record_id=record.id if record.source_type == "ledger" else candidate.id if candidate.source_type == "ledger" else None,
                    bank_record_id=record.id if record.source_type == "bank" else candidate.id if candidate.source_type == "bank" else None,
                    gateway_record_id=record.id if record.source_type == "gateway" else candidate.id if candidate.source_type == "gateway" else None,
                    match_type="ai_suggested",
                    confidence_score=Decimal(str(round(suggestion.confidence, 3))),
                    matched_by="ai",
                )
                db.add(match)
                db.flush()
                ai_match_id = match.id
                record.status = "ai_suggested"

    if ai_match_id is None:
        record.status = "exception"

    exception = Exception_(
        tenant_id=record.tenant_id,
        record_id=record.id,
        ai_suggested_match_id=ai_match_id,
        confidence_tier=confidence_tier,
        reason_code=reason_code,
        explanation=explanation,
        needs_human_review=True,
        status="open",
    )
    db.add(exception)
    return exception


def resolve_exceptions_with_ai(db: Session, batch_id: uuid.UUID) -> dict:
    from app.models.ingestion_batch import IngestionBatch

    batch = db.get(IngestionBatch, batch_id)
    if batch is None:
        raise ValueError(f"Batch {batch_id} not found")

    batch.status = "ai_resolving"
    db.flush()

    unresolved = (
        db.query(NormalizedRecord)
        .filter(NormalizedRecord.batch_id == batch_id, NormalizedRecord.status == "unmatched")
        .all()
    )

    tiers = {"high": 0, "medium": 0, "low": 0, "none": 0}
    for record in unresolved:
        exception = resolve_exception_for_record(db, record)
        tiers[exception.confidence_tier or "none"] += 1

    batch.status = "completed"
    batch.completed_at = datetime.now(timezone.utc)
    db.commit()

    return {"batch_id": str(batch_id), "resolved": len(unresolved), "by_confidence": tiers}
