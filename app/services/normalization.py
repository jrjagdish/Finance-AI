import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from dateutil import parser as date_parser
from sqlalchemy.orm import Session

from app.models.entity import Entity, EntityAlias
from app.models.ingestion_batch import IngestionBatch
from app.models.normalized_record import NormalizedRecord
from app.models.raw_record import RawRecord

# Recognized column-name variants per logical field, across ledger/bank/gateway CSV
# exports (real-world files never agree on a header name).
AMOUNT_FIELDS = ("amount", "amt", "value", "credit", "debit", "settlement_amount", "net_amount")
TXN_ID_FIELDS = ("txn_id", "transaction_id", "txnid", "utr", "payment_id", "payout_id")
REFERENCE_FIELDS = ("reference_no", "reference", "ref_no", "invoice_no", "order_id", "invoice_number")
DATE_FIELDS = ("date", "txn_date", "value_date", "posting_date", "settlement_date", "payout_date")
NARRATION_FIELDS = ("narration", "description", "particulars", "remarks", "narration_raw")
ENTITY_NAME_FIELDS = ("customer", "vendor", "name", "counterparty", "payer", "payee", "customer_name")
FEE_FIELDS = ("fee", "gateway_fee", "mdr", "charges", "fee_amount")
TAX_FIELDS = ("tax", "gst", "tax_amount")
CURRENCY_FIELDS = ("currency", "ccy")

_NARRATION_PREFIX_RE = re.compile(r"^(NEFT|IMPS|RTGS|UPI)[/\-:]+", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")
_NON_NUMERIC_RE = re.compile(r"[^\d.\-]")


def _get_field(row: dict, candidates: tuple[str, ...]) -> str | None:
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    for candidate in candidates:
        value = lower.get(candidate)
        if value not in (None, ""):
            return value
    return None


def _parse_amount(raw) -> Decimal | None:
    if raw is None:
        return None
    cleaned = _NON_NUMERIC_RE.sub("", str(raw))
    if not cleaned or cleaned in ("-", "."):
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_date(raw) -> date | None:
    if not raw:
        return None
    try:
        return date_parser.parse(str(raw)).date()
    except (ValueError, OverflowError, TypeError):
        return None


def _clean_narration(raw: str | None) -> str | None:
    if not raw:
        return None
    text = _NARRATION_PREFIX_RE.sub("", str(raw).strip())
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text or None


def _resolve_entity(db: Session, tenant_id: str, name: str | None) -> Entity | None:
    """Exact/alias lookup; auto-creates a new customer entity on first sighting.

    Full fuzzy entity resolution (typos, abbreviations) is deferred to the AI
    exception resolver — this stays deterministic on purpose.
    """
    if not name:
        return None
    name_norm = name.strip()
    if not name_norm:
        return None

    entity = (
        db.query(Entity)
        .filter(Entity.tenant_id == tenant_id, Entity.canonical_name.ilike(name_norm))
        .first()
    )
    if entity:
        return entity

    alias = (
        db.query(EntityAlias)
        .join(Entity, Entity.id == EntityAlias.entity_id)
        .filter(Entity.tenant_id == tenant_id, EntityAlias.alias_text.ilike(name_norm))
        .first()
    )
    if alias:
        return db.get(Entity, alias.entity_id)

    entity = Entity(tenant_id=tenant_id, canonical_name=name_norm, type="customer", entity_metadata={})
    db.add(entity)
    db.flush()
    return entity


def normalize_batch(db: Session, batch_id: uuid.UUID) -> dict:
    """Cleans every raw_record in a batch into normalized_records.

    Idempotent: re-running on the same batch skips rows already normalized
    (matched on tenant + source_type + txn_id + amount + txn_date).
    """
    batch = db.get(IngestionBatch, batch_id)
    if batch is None:
        raise ValueError(f"Batch {batch_id} not found")

    batch.status = "normalizing"
    db.flush()

    raw_records = db.query(RawRecord).filter(RawRecord.batch_id == batch_id).all()

    created = 0
    skipped_duplicates = 0
    skipped_invalid = 0

    for raw in raw_records:
        row = raw.raw_payload or {}

        amount = _parse_amount(_get_field(row, AMOUNT_FIELDS))
        txn_date = _parse_date(_get_field(row, DATE_FIELDS))

        if amount is None or txn_date is None:
            skipped_invalid += 1
            continue

        txn_id = _get_field(row, TXN_ID_FIELDS)
        reference_no = _get_field(row, REFERENCE_FIELDS)

        existing = (
            db.query(NormalizedRecord)
            .filter(
                NormalizedRecord.tenant_id == raw.tenant_id,
                NormalizedRecord.source_type == raw.source_type,
                NormalizedRecord.amount == amount,
                NormalizedRecord.txn_date == txn_date,
                NormalizedRecord.txn_id == txn_id,
            )
            .first()
        )
        if existing is not None:
            skipped_duplicates += 1
            continue

        narration_raw = _get_field(row, NARRATION_FIELDS)
        entity = _resolve_entity(db, raw.tenant_id, _get_field(row, ENTITY_NAME_FIELDS))

        db.add(
            NormalizedRecord(
                tenant_id=raw.tenant_id,
                source_type=raw.source_type,
                source_record_id=raw.id,
                batch_id=batch_id,
                txn_id=txn_id,
                reference_no=reference_no,
                entity_id=entity.id if entity else None,
                amount=amount,
                currency=_get_field(row, CURRENCY_FIELDS) or "INR",
                txn_date=txn_date,
                narration_raw=narration_raw,
                narration_clean=_clean_narration(narration_raw),
                fee_amount=_parse_amount(_get_field(row, FEE_FIELDS)),
                tax_amount=_parse_amount(_get_field(row, TAX_FIELDS)),
                status="unmatched",
            )
        )
        created += 1

    batch.status = "completed"
    batch.completed_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "batch_id": str(batch_id),
        "created": created,
        "skipped_duplicates": skipped_duplicates,
        "skipped_invalid": skipped_invalid,
    }
