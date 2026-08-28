import inngest

from app.db.session import SessionLocal
from app.inngest_client import inngest_client
from app.models.ingestion_batch import IngestionBatch
from app.services.ai_resolver import resolve_exceptions_with_ai
from app.services.normalization import normalize_batch


def _mark_failed(batch_id: str) -> None:
    # Uses a fresh session — the session the failing service call used may itself be
    # in a broken transaction state after the exception, so don't reuse it.
    db = SessionLocal()
    try:
        batch = db.get(IngestionBatch, batch_id)
        if batch is not None:
            batch.status = "failed"
            db.commit()
    finally:
        db.close()


def _run_normalize(batch_id: str) -> dict:
    db = SessionLocal()
    try:
        return normalize_batch(db, batch_id)
    except Exception as exc:
        db.rollback()
        _mark_failed(batch_id)
        # Swallowed rather than re-raised: Inngest would otherwise retry, and
        # normalize_batch isn't guaranteed safe to re-run from scratch. The batch's
        # "failed" status is the signal the frontend polls for either way.
        return {"error": str(exc)}
    finally:
        db.close()


def _run_ai_resolve(batch_id: str) -> dict:
    db = SessionLocal()
    try:
        return resolve_exceptions_with_ai(db, batch_id)
    except Exception as exc:
        db.rollback()
        _mark_failed(batch_id)
        return {"error": str(exc)}
    finally:
        db.close()


@inngest_client.create_function(
    fn_id="normalize-batch",
    trigger=inngest.TriggerEvent(event="finance/batch.normalize"),
)
def normalize_batch_fn(ctx: inngest.ContextSync) -> dict:
    batch_id = ctx.event.data["batch_id"]
    return ctx.step.run("normalize-batch", _run_normalize, batch_id)


@inngest_client.create_function(
    fn_id="ai-resolve-exceptions",
    trigger=inngest.TriggerEvent(event="finance/exceptions.ai_resolve"),
)
def ai_resolve_fn(ctx: inngest.ContextSync) -> dict:
    batch_id = ctx.event.data["batch_id"]
    return ctx.step.run("ai-resolve-exceptions", _run_ai_resolve, batch_id)


inngest_functions = [normalize_batch_fn, ai_resolve_fn]
