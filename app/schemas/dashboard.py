from datetime import date

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_records: int
    auto_matched: int
    match_rate_pct: float
    ai_suggested: int
    unresolved_exceptions: int
    needs_review: int


class TrendPoint(BaseModel):
    day: date
    total: int
    matched: int
    exceptions: int


class DashboardTrends(BaseModel):
    points: list[TrendPoint]


class ReasonCodeBreakdown(BaseModel):
    reason_code: str
    count: int


class SourcePerformance(BaseModel):
    source_type: str
    total: int
    matched: int
    match_rate_pct: float
