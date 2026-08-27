import itertools
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.match import Match
from app.models.matching_rule import MatchingRule
from app.models.normalized_record import NormalizedRecord

NON_LEDGER_SOURCES = ("bank", "gateway")


def _rule_param(db: Session, tenant_id: str, rule_type: str, key: str, default):
    rule = (
        db.query(MatchingRule)
        .filter(MatchingRule.tenant_id == tenant_id, MatchingRule.is_active.is_(True))
        .filter(MatchingRule.rule_definition["type"].as_string() == rule_type)
        .first()
    )
    if rule and key in rule.rule_definition:
        return rule.rule_definition[key]
    return default


def _mark_matched(db: Session, *records: NormalizedRecord) -> None:
    for r in records:
        r.status = "matched"


def _make_match(db: Session, tenant_id: str, ledger, other, match_type: str) -> Match:
    match = Match(
        tenant_id=tenant_id,
        ledger_record_id=ledger.id,
        bank_record_id=other.id if other.source_type == "bank" else None,
        gateway_record_id=other.id if other.source_type == "gateway" else None,
        match_type=match_type,
        confidence_score=Decimal("1.0"),
        matched_by="rule",
    )
    db.add(match)
    _mark_matched(db, ledger, other)
    return match


def run_matching_engine(db: Session, tenant_id: str) -> dict:
    """Runs the deterministic rule cascade (exact -> reference -> amount tolerance ->
    date window -> one-to-many aggregation) over every unmatched record for a tenant.

    Operates tenant-wide (not per-batch): a ledger row from batch A can legitimately
    match a bank row from batch B, so scoping to one batch would miss real matches.
    """
    amount_tolerance = Decimal(str(_rule_param(db, tenant_id, "amount_tolerance", "tolerance", settings.default_amount_tolerance)))
    date_window_days = int(_rule_param(db, tenant_id, "date_window", "days", settings.default_date_window_days))
    max_group_size = settings.max_aggregation_group_size

    counts = {"exact": 0, "reference": 0, "amount_tolerance": 0, "date_window": 0, "one_to_many": 0}

    ledger_records = (
        db.query(NormalizedRecord)
        .filter(NormalizedRecord.tenant_id == tenant_id, NormalizedRecord.source_type == "ledger", NormalizedRecord.status == "unmatched")
        .all()
    )
    other_records = (
        db.query(NormalizedRecord)
        .filter(NormalizedRecord.tenant_id == tenant_id, NormalizedRecord.source_type.in_(NON_LEDGER_SOURCES), NormalizedRecord.status == "unmatched")
        .all()
    )

    def unmatched(records):
        return [r for r in records if r.status == "unmatched"]

    # Rule 1: exact (txn_id + amount)
    for ledger in unmatched(ledger_records):
        if not ledger.txn_id:
            continue
        for other in unmatched(other_records):
            if other.txn_id == ledger.txn_id and other.amount == ledger.amount:
                _make_match(db, tenant_id, ledger, other, "exact")
                counts["exact"] += 1
                break

    # Rule 2: reference number + amount
    for ledger in unmatched(ledger_records):
        if not ledger.reference_no:
            continue
        for other in unmatched(other_records):
            if other.reference_no == ledger.reference_no and other.amount == ledger.amount:
                _make_match(db, tenant_id, ledger, other, "reference")
                counts["reference"] += 1
                break

    # Rule 3: amount tolerance (same date, amount within tolerance)
    for ledger in unmatched(ledger_records):
        for other in unmatched(other_records):
            if other.txn_date == ledger.txn_date and abs(other.amount - ledger.amount) <= amount_tolerance:
                _make_match(db, tenant_id, ledger, other, "amount_tolerance")
                counts["amount_tolerance"] += 1
                break

    # Rule 4: date window (exact amount, date within N days)
    for ledger in unmatched(ledger_records):
        for other in unmatched(other_records):
            if other.amount == ledger.amount and abs((other.txn_date - ledger.txn_date).days) <= date_window_days:
                _make_match(db, tenant_id, ledger, other, "date_window")
                counts["date_window"] += 1
                break

    # Rule 5: one-to-many aggregation — N ledger rows (split payments) summing to
    # one bank/gateway settlement, for the same entity, within the date window.
    for other in unmatched(other_records):
        candidates = [
            r
            for r in unmatched(ledger_records)
            if r.entity_id is not None
            and r.entity_id == other.entity_id
            and abs((r.txn_date - other.txn_date).days) <= date_window_days
        ][:8]  # bound combinations searched

        found_group: tuple[NormalizedRecord, ...] | None = None
        for size in range(2, min(max_group_size, len(candidates)) + 1):
            for group in itertools.combinations(candidates, size):
                if abs(sum((g.amount for g in group), Decimal("0")) - other.amount) <= amount_tolerance:
                    found_group = group
                    break
            if found_group:
                break

        if found_group:
            for ledger in found_group:
                _make_match(db, tenant_id, ledger, other, "one_to_many")
                counts["one_to_many"] += 1

    db.commit()
    return counts
