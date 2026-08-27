import csv
import io

from sqlalchemy.orm import Session

from app.models.audit_log import MatchAuditLog
from app.models.exception import Exception_
from app.models.normalized_record import NormalizedRecord

VALID_REPORTS = ("reconciliation-summary", "exception-report", "audit-trail")
VALID_FORMATS = ("csv", "xlsx", "pdf")


def reconciliation_summary_rows(db: Session) -> list[dict]:
    from app.api.routes.dashboard import dashboard_summary, performance_by_source, reason_code_breakdown

    summary = dashboard_summary(db)
    rows = [{"section": "summary", "metric": k, "value": v} for k, v in summary.model_dump().items()]
    for perf in performance_by_source(db):
        rows.append(
            {
                "section": f"source:{perf.source_type}",
                "metric": "match_rate_pct",
                "value": perf.match_rate_pct,
            }
        )
    for rc in reason_code_breakdown(db):
        rows.append({"section": "reason_code", "metric": rc.reason_code, "value": rc.count})
    return rows


def exception_report_rows(db: Session) -> list[dict]:
    exceptions = db.query(Exception_).order_by(Exception_.created_at.desc()).all()
    records_by_id = {
        r.id: r for r in db.query(NormalizedRecord).filter(NormalizedRecord.id.in_([e.record_id for e in exceptions])).all()
    } if exceptions else {}

    rows = []
    for e in exceptions:
        record = records_by_id.get(e.record_id)
        rows.append(
            {
                "exception_id": str(e.id),
                "record_id": str(e.record_id),
                "source_type": record.source_type if record else None,
                "amount": str(record.amount) if record else None,
                "txn_date": record.txn_date.isoformat() if record else None,
                "reason_code": e.reason_code,
                "confidence_tier": e.confidence_tier,
                "status": e.status,
                "needs_human_review": e.needs_human_review,
                "explanation": e.explanation,
                "created_at": e.created_at.isoformat(),
                "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
            }
        )
    return rows


def audit_trail_rows(db: Session) -> list[dict]:
    logs = db.query(MatchAuditLog).order_by(MatchAuditLog.created_at.desc()).limit(1000).all()
    return [
        {
            "id": str(log.id),
            "subject_id": str(log.subject_id),
            "action": log.action,
            "actor": log.actor,
            "actor_id": log.actor_id,
            "payload": str(log.payload),
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


def get_report_rows(db: Session, report: str) -> list[dict]:
    if report == "reconciliation-summary":
        return reconciliation_summary_rows(db)
    if report == "exception-report":
        return exception_report_rows(db)
    if report == "audit-trail":
        return audit_trail_rows(db)
    raise ValueError(f"Unknown report: {report}")


def rows_to_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def rows_to_xlsx(rows: list[dict]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def rows_to_pdf(rows: list[dict], title: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles["Title"]), Spacer(1, 12)]

    if rows:
        headers = list(rows[0].keys())
        data = [headers] + [[str(row.get(h, "")) for h in headers] for row in rows]
        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(table)
    else:
        elements.append(Paragraph("No data.", styles["Normal"]))

    doc.build(elements)
    return buf.getvalue()
