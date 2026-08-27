from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.reports import (
    VALID_FORMATS,
    VALID_REPORTS,
    audit_trail_rows,
    exception_report_rows,
    get_report_rows,
    reconciliation_summary_rows,
    rows_to_csv,
    rows_to_pdf,
    rows_to_xlsx,
)

router = APIRouter(prefix="/reports", tags=["reports"])

_CONTENT_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


@router.get("/reconciliation-summary")
def reconciliation_summary(db: Session = Depends(get_db)):
    return reconciliation_summary_rows(db)


@router.get("/exception-report")
def exception_report(db: Session = Depends(get_db)):
    return exception_report_rows(db)


@router.get("/audit-trail")
def audit_trail(db: Session = Depends(get_db)):
    return audit_trail_rows(db)


@router.get("/export")
def export_report(
    format: str = Query(..., description="csv|xlsx|pdf"),
    report: str = Query(default="exception-report", description="|".join(VALID_REPORTS)),
    db: Session = Depends(get_db),
):
    if format not in VALID_FORMATS:
        raise HTTPException(status_code=422, detail=f"format must be one of {VALID_FORMATS}")
    if report not in VALID_REPORTS:
        raise HTTPException(status_code=422, detail=f"report must be one of {VALID_REPORTS}")

    rows = get_report_rows(db, report)

    if format == "csv":
        content = rows_to_csv(rows)
    elif format == "xlsx":
        content = rows_to_xlsx(rows)
    else:
        content = rows_to_pdf(rows, title=report.replace("-", " ").title())

    filename = f"{report}.{format}"
    return Response(
        content=content,
        media_type=_CONTENT_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
