from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.exception import Exception_
from app.models.match import Match
from app.models.normalized_record import NormalizedRecord
from app.schemas.dashboard import (
    DashboardSummary,
    DashboardTrends,
    ReasonCodeBreakdown,
    SourcePerformance,
    TrendPoint,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    total_records = db.query(NormalizedRecord).count()
    matched_records = db.query(NormalizedRecord).filter(NormalizedRecord.status == "matched").count()
    auto_matched = db.query(Match).filter(Match.matched_by == "rule").count()
    ai_suggested = db.query(Exception_).filter(Exception_.ai_suggested_match_id.isnot(None)).count()
    unresolved_exceptions = db.query(Exception_).filter(Exception_.status == "open").count()
    needs_review = (
        db.query(Exception_).filter(Exception_.status == "open", Exception_.needs_human_review.is_(True)).count()
    )

    match_rate_pct = round((matched_records / total_records) * 100, 2) if total_records else 0.0

    return DashboardSummary(
        total_records=total_records,
        auto_matched=auto_matched,
        match_rate_pct=match_rate_pct,
        ai_suggested=ai_suggested,
        unresolved_exceptions=unresolved_exceptions,
        needs_review=needs_review,
    )


@router.get("/trends", response_model=DashboardTrends)
def dashboard_trends(days: int = Query(default=30, le=365), db: Session = Depends(get_db)):
    since = date.today() - timedelta(days=days)

    totals = dict(
        db.query(func.date(NormalizedRecord.created_at), func.count())
        .filter(func.date(NormalizedRecord.created_at) >= since)
        .group_by(func.date(NormalizedRecord.created_at))
        .all()
    )
    matched = dict(
        db.query(func.date(NormalizedRecord.created_at), func.count())
        .filter(func.date(NormalizedRecord.created_at) >= since, NormalizedRecord.status == "matched")
        .group_by(func.date(NormalizedRecord.created_at))
        .all()
    )
    exceptions = dict(
        db.query(func.date(Exception_.created_at), func.count())
        .filter(func.date(Exception_.created_at) >= since)
        .group_by(func.date(Exception_.created_at))
        .all()
    )

    all_days = sorted(set(totals) | set(matched) | set(exceptions))
    points = [
        TrendPoint(day=d, total=totals.get(d, 0), matched=matched.get(d, 0), exceptions=exceptions.get(d, 0))
        for d in all_days
    ]
    return DashboardTrends(points=points)


@router.get("/reason-codes", response_model=list[ReasonCodeBreakdown])
def reason_code_breakdown(db: Session = Depends(get_db)):
    rows = (
        db.query(Exception_.reason_code, func.count())
        .group_by(Exception_.reason_code)
        .order_by(func.count().desc())
        .all()
    )
    return [ReasonCodeBreakdown(reason_code=code, count=count) for code, count in rows]


@router.get("/performance-by-source", response_model=list[SourcePerformance])
def performance_by_source(db: Session = Depends(get_db)):
    totals = Counter(dict(db.query(NormalizedRecord.source_type, func.count()).group_by(NormalizedRecord.source_type).all()))
    matched = Counter(
        dict(
            db.query(NormalizedRecord.source_type, func.count())
            .filter(NormalizedRecord.status == "matched")
            .group_by(NormalizedRecord.source_type)
            .all()
        )
    )
    results = []
    for source_type, total in totals.items():
        m = matched.get(source_type, 0)
        results.append(
            SourcePerformance(
                source_type=source_type,
                total=total,
                matched=m,
                match_rate_pct=round((m / total) * 100, 2) if total else 0.0,
            )
        )
    return results
