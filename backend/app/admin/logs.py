"""Request logs for the instructor (design §9): sanitized text only, no student or session IDs."""
import statistics
from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Session, col, func, select

from app.storage.models import RequestLog

MAX_PAGE_SIZE = 100


class LogEntry(BaseModel):
    request_id: str
    created_at: datetime
    topic: str
    sanitized_question: str
    target: str | None
    route_score: float | None
    model: str | None
    latency_ms: float  # sum of the step timings
    checks: dict[str, str]  # checker -> pass | warn | fail
    warnings: list[str]


class LogStats(BaseModel):
    requests: int
    local: int
    cloud: int
    cloud_share: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None


class LogPage(BaseModel):
    page: int
    page_size: int
    total: int
    stats: LogStats
    entries: list[LogEntry]


def latency(row: RequestLog) -> float:
    return round(sum(float(v) for v in (row.timings or {}).values()), 1)


def percentile(sorted_values: list[float], q: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    return round(statistics.quantiles(sorted_values, n=100, method="inclusive")[int(q * 100) - 1], 1)


def entry(row: RequestLog) -> LogEntry:
    checks = {c.get("name", "?"): c.get("status", "?") for c in (row.checks or []) if isinstance(c, dict)}
    return LogEntry(request_id=row.request_id, created_at=row.created_at, topic=row.topic,
                    sanitized_question=row.sanitized_question, target=row.target,
                    route_score=row.route_score, model=row.model, latency_ms=latency(row), checks=checks,
                    warnings=list(row.warnings or []))


def log_page(engine, page: int = 1, page_size: int = 20, topic: str | None = None) -> LogPage:
    page, page_size = max(page, 1), min(max(page_size, 1), MAX_PAGE_SIZE)
    where = [RequestLog.topic == topic] if topic else []
    with Session(engine) as db:
        total = db.exec(select(func.count()).select_from(RequestLog).where(*where)).one()
        rows = db.exec(select(RequestLog).where(*where).order_by(col(RequestLog.id).desc())
                       .offset((page - 1) * page_size).limit(page_size)).all()
        everything = db.exec(select(RequestLog.target, RequestLog.timings).where(*where)).all()
    local = sum(1 for t, _ in everything if t == "local")
    cloud = sum(1 for t, _ in everything if t == "cloud")
    lat = sorted(round(sum(float(v) for v in (timings or {}).values()), 1) for _, timings in everything)
    stats = LogStats(requests=total, local=local, cloud=cloud,
                     cloud_share=round(cloud / (local + cloud), 3) if local + cloud else None,
                     latency_p50_ms=percentile(lat, 0.50), latency_p95_ms=percentile(lat, 0.95))
    return LogPage(page=page, page_size=page_size, total=total, stats=stats, entries=[entry(r) for r in rows])
