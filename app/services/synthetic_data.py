import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.ingestion_batch import IngestionBatch
from app.models.raw_record import RawRecord

CUSTOMER_NAMES = [
    "Acme Corp", "Beta LLC", "Gamma Inc", "Delta Traders", "Epsilon Retail",
    "Zeta Foods", "Eta Textiles", "Theta Logistics", "Iota Media", "Kappa Studios",
    "Lambda Health", "Mu Electronics", "Nu Consulting", "Xi Hospitality", "Omicron Auto",
]

NARRATION_TEMPLATES = [
    "NEFT/{ref}/{name}",
    "IMPS/{ref}/PAYMENT FROM {name}",
    "UPI/{ref}/{name}/Payment",
    "Payment received from {name} ref {ref}",
]


def _rand_amount(lo=500, hi=50000) -> Decimal:
    return Decimal(random.randint(lo, hi))


def _rand_date(start: date, span_days: int = 60) -> date:
    return start + timedelta(days=random.randint(0, span_days))


def generate_synthetic_dataset(db: Session, total_records: int = 100, seed: int | None = None) -> dict:
    """Generates a ledger batch + a bank batch with controlled edge cases:
    exact/reference matches, fee-deducted settlements, missing references,
    aggregated deposits (many ledger rows -> one bank row), duplicate bank
    rows, and unknown-counterparty bank rows with no ledger counterpart.

    Lands directly in raw_records (skipping file upload) so the full
    normalize -> match -> AI-resolve pipeline can be exercised immediately.
    """
    if seed is not None:
        random.seed(seed)

    total_records = max(50, min(500, total_records))
    start_date = date.today() - timedelta(days=60)

    ledger_batch = IngestionBatch(source_type="ledger", status="pending", original_filename="synthetic_ledger.csv")
    bank_batch = IngestionBatch(source_type="bank", status="pending", original_filename="synthetic_bank.csv")
    db.add_all([ledger_batch, bank_batch])
    db.flush()

    edge_case_counts = {
        "exact": 0,
        "fee_deducted": 0,
        "missing_reference": 0,
        "aggregated_deposit": 0,
        "duplicate": 0,
        "unknown_counterparty": 0,
    }

    ledger_rows = 0
    bank_rows = 0
    i = 0

    while ledger_rows < total_records:
        i += 1
        customer = random.choice(CUSTOMER_NAMES)
        amount = _rand_amount()
        txn_date = _rand_date(start_date)
        ref = f"INV-{1000 + i}"
        txn_id = f"TXN{i:05d}"
        narration = random.choice(NARRATION_TEMPLATES).format(ref=ref, name=customer)

        scenario = random.choices(
            ["exact", "fee_deducted", "missing_reference", "aggregated_deposit", "unknown_counterparty"],
            weights=[45, 20, 15, 10, 10],
            k=1,
        )[0]

        if scenario == "aggregated_deposit" and ledger_rows + 3 <= total_records:
            # 2-3 ledger invoices for the same customer, bundled into one bank deposit
            n_parts = random.choice([2, 3])
            part_amounts = [_rand_amount(500, 15000) for _ in range(n_parts)]
            for j, part_amount in enumerate(part_amounts):
                part_ref = f"{ref}-{j + 1}"
                db.add(
                    RawRecord(
                        source_type="ledger",
                        raw_payload={
                            "txn_id": f"{txn_id}-{j + 1}",
                            "reference_no": part_ref,
                            "customer": customer,
                            "amount": str(part_amount),
                            "currency": "INR",
                            "date": txn_date.isoformat(),
                            "narration": f"Invoice payment for {part_ref}",
                        },
                        batch_id=ledger_batch.id,
                    )
                )
                ledger_rows += 1
            db.add(
                RawRecord(
                    source_type="bank",
                    raw_payload={
                        "txn_id": f"BANK{i:05d}",
                        "reference_no": "",
                        "customer": customer,
                        "amount": str(sum(part_amounts)),
                        "currency": "INR",
                        "date": (txn_date + timedelta(days=1)).isoformat(),
                        "narration": f"NEFT/{customer}/AGGREGATED SETTLEMENT",
                    },
                    batch_id=bank_batch.id,
                )
            )
            bank_rows += 1
            edge_case_counts["aggregated_deposit"] += 1
            continue

        db.add(
            RawRecord(
                source_type="ledger",
                raw_payload={
                    "txn_id": txn_id,
                    "reference_no": ref,
                    "customer": customer,
                    "amount": str(amount),
                    "currency": "INR",
                    "date": txn_date.isoformat(),
                    "narration": f"Invoice payment for {ref}",
                },
                batch_id=ledger_batch.id,
            )
        )
        ledger_rows += 1

        if scenario == "exact":
            db.add(
                RawRecord(
                    source_type="bank",
                    raw_payload={
                        "txn_id": txn_id,
                        "reference_no": ref,
                        "customer": customer,
                        "amount": str(amount),
                        "currency": "INR",
                        "date": txn_date.isoformat(),
                        "narration": narration,
                    },
                    batch_id=bank_batch.id,
                )
            )
            bank_rows += 1
            edge_case_counts["exact"] += 1

        elif scenario == "fee_deducted":
            fee = _rand_amount(5, 50)
            settled = amount - fee
            db.add(
                RawRecord(
                    source_type="bank",
                    raw_payload={
                        "txn_id": txn_id,
                        "reference_no": ref,
                        "customer": customer,
                        "amount": str(settled),
                        "fee": str(fee),
                        "currency": "INR",
                        "date": txn_date.isoformat(),
                        "narration": narration,
                    },
                    batch_id=bank_batch.id,
                )
            )
            bank_rows += 1
            edge_case_counts["fee_deducted"] += 1

        elif scenario == "missing_reference":
            db.add(
                RawRecord(
                    source_type="bank",
                    raw_payload={
                        "txn_id": f"BANK{i:05d}",
                        "reference_no": "",
                        "customer": customer,
                        "amount": str(amount),
                        "currency": "INR",
                        "date": txn_date.isoformat(),
                        "narration": f"NEFT/{customer}/PAYMENT",
                    },
                    batch_id=bank_batch.id,
                )
            )
            bank_rows += 1
            edge_case_counts["missing_reference"] += 1

        elif scenario == "unknown_counterparty":
            db.add(
                RawRecord(
                    source_type="bank",
                    raw_payload={
                        "txn_id": f"UNKNOWN{i:05d}",
                        "reference_no": "",
                        "customer": f"Unrecognized Payer {i}",
                        "amount": str(_rand_amount()),
                        "currency": "INR",
                        "date": _rand_date(start_date).isoformat(),
                        "narration": "UPI/UNKNOWN SENDER/Payment",
                    },
                    batch_id=bank_batch.id,
                )
            )
            bank_rows += 1
            edge_case_counts["unknown_counterparty"] += 1

    # A handful of exact-duplicate bank rows, to exercise dedup.
    db.flush()  # ensure this batch's rows are queryable below before autocommit-on-query kicks in
    n_duplicates = max(1, total_records // 25)
    existing_bank = db.query(RawRecord).filter(RawRecord.batch_id == bank_batch.id).limit(n_duplicates).all()
    for original in existing_bank:
        db.add(RawRecord(source_type="bank", raw_payload=dict(original.raw_payload), batch_id=bank_batch.id))
        bank_rows += 1
        edge_case_counts["duplicate"] += 1

    ledger_batch.total_records = ledger_rows
    ledger_batch.status = "completed"
    bank_batch.total_records = bank_rows
    bank_batch.status = "completed"
    db.commit()

    return {
        "ledger_batch_id": str(ledger_batch.id),
        "bank_batch_id": str(bank_batch.id),
        "ledger_records": ledger_rows,
        "bank_records": bank_rows,
        "edge_cases": edge_case_counts,
    }
