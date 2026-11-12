"""Per-student usage limits (guide section 4.4; counters per student + course + day; task Z10).

`DbUsageMeter` keeps counts in `usage_counter` (questions per minute and per day, cloud calls per day; UTC
days) and refuses with `UsageLimitExceeded` (HTTP 429 with `retry_after_seconds`). The limits are
`limits.usage` in config.yaml; a course's `usage_*` setting can only lower them (they stay null for now).

`check_usage` / `record_usage` are the interface (course-structure.md section 9); the app installs the
database meter at startup. `reserve_usage` checks and counts in one transaction, so concurrent requests
cannot all take the last allowed use; `release_usage` gives a reservation back (no answer was produced) and
`add_tokens` adds the tokens once they are known. `NoLimits` stays for scripts and unit tests without the app.
"""
from datetime import datetime, timedelta
from typing import Literal, Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session

from app.storage.models import UsageCounter, utcnow

UsageKind = Literal["question", "cloud_call"]


class UsageLimitExceeded(Exception):
    """Raised by check_usage; the API turns it into 429 with retry_after_seconds."""

    def __init__(self, kind: UsageKind, retry_after_seconds: int) -> None:
        super().__init__(f"usage limit reached: {kind}")
        self.kind = kind
        self.retry_after_seconds = retry_after_seconds


class UsageMeter(Protocol):
    def check_usage(self, student_id: str, course_id: int, kind: UsageKind) -> None: ...

    def record_usage(self, student_id: str, course_id: int, kind: UsageKind, *, tokens: int = 0) -> None: ...

    def reserve_usage(self, student_id: str, course_id: int, kind: UsageKind) -> None: ...

    def release_usage(self, student_id: str, course_id: int, kind: UsageKind) -> None: ...

    def add_tokens(self, student_id: str, course_id: int, kind: UsageKind, tokens: int) -> None: ...


class NoLimits:
    def check_usage(self, student_id: str, course_id: int, kind: UsageKind) -> None:
        return None

    def record_usage(self, student_id: str, course_id: int, kind: UsageKind, *, tokens: int = 0) -> None:
        return None

    def reserve_usage(self, student_id: str, course_id: int, kind: UsageKind) -> None:
        return None

    def release_usage(self, student_id: str, course_id: int, kind: UsageKind) -> None:
        return None

    def add_tokens(self, student_id: str, course_id: int, kind: UsageKind, tokens: int) -> None:
        return None


def _periods(now: datetime) -> dict[str, tuple[datetime, datetime]]:
    minute = now.replace(second=0, microsecond=0)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {"minute": (minute, minute + timedelta(minutes=1)), "day": (day, day + timedelta(days=1))}


class DbUsageMeter:
    """Usage counters in the database. `effective(course_id)` gives the course's effective settings."""

    def __init__(self, engine, limits, effective=None) -> None:
        self.engine = engine
        self.limits = limits  # config `limits.usage` (hard caps)
        self._effective = effective

    def _limit(self, course_id: int, name: str, cap: int) -> int:
        value = getattr(self._effective(course_id), f"usage_{name}", None) if self._effective else None
        return cap if value is None else min(int(value), cap)

    def _windows(self, course_id: int, kind: UsageKind) -> list[tuple[str, int]]:
        caps = self.limits
        if kind == "question":
            return [("minute", self._limit(course_id, "questions_per_minute", caps.questions_per_minute)),
                    ("day", self._limit(course_id, "questions_per_day", caps.questions_per_day))]
        return [("day", self._limit(course_id, "cloud_calls_per_day", caps.cloud_calls_per_day))]

    def check_usage(self, student_id: str, course_id: int, kind: UsageKind) -> None:
        now = utcnow()
        periods = _periods(now)
        with Session(self.engine) as db:
            for period, limit in self._windows(course_id, kind):
                start, end = periods[period]
                used = db.exec(select(func.coalesce(func.sum(UsageCounter.count), 0)).where(
                    UsageCounter.student_id == student_id, UsageCounter.course_id == course_id,
                    UsageCounter.kind == kind, UsageCounter.period == period,
                    UsageCounter.period_start == start)).scalar_one()
                if used >= limit:
                    raise UsageLimitExceeded(kind, max(1, int((end - now).total_seconds()) + 1))

    def record_usage(self, student_id: str, course_id: int, kind: UsageKind, *, tokens: int = 0) -> None:
        now = utcnow()
        periods = _periods(now)
        with Session(self.engine) as db:
            for period, _ in self._windows(course_id, kind):
                start = periods[period][0]
                stmt = insert(UsageCounter).values(student_id=student_id, course_id=course_id, kind=kind,
                                                   period=period, period_start=start, count=1, tokens=tokens)
                db.exec(stmt.on_conflict_do_update(
                    index_elements=["student_id", "course_id", "kind", "period", "period_start"],
                    set_={"count": UsageCounter.count + 1, "tokens": UsageCounter.tokens + tokens}))
            # minute rows are only needed for the current minute
            db.exec(delete(UsageCounter).where(UsageCounter.student_id == student_id,
                                               UsageCounter.period == "minute",
                                               UsageCounter.period_start < periods["minute"][0]))
            db.commit()

    def _upsert(self, student_id: str, course_id: int, kind: UsageKind, period: str, start: datetime,
                count: int, tokens: int):
        stmt = insert(UsageCounter).values(student_id=student_id, course_id=course_id, kind=kind,
                                           period=period, period_start=start, count=max(count, 0),
                                           tokens=tokens)
        return stmt.on_conflict_do_update(
            index_elements=["student_id", "course_id", "kind", "period", "period_start"],
            set_={"count": func.greatest(UsageCounter.count + count, 0),
                  "tokens": UsageCounter.tokens + tokens},
        ).returning(UsageCounter.count)

    def reserve_usage(self, student_id: str, course_id: int, kind: UsageKind) -> None:
        """Counts one use, or raises UsageLimitExceeded and counts nothing. The upsert locks the counter row
        until the commit, so a concurrent request waits and then sees this one's count."""
        now = utcnow()
        periods = _periods(now)
        with Session(self.engine) as db:
            for period, limit in self._windows(course_id, kind):
                start, end = periods[period]
                used = db.exec(self._upsert(student_id, course_id, kind, period, start, 1, 0)).scalar_one()
                if used > limit:
                    db.rollback()
                    raise UsageLimitExceeded(kind, max(1, int((end - now).total_seconds()) + 1))
            db.commit()

    def release_usage(self, student_id: str, course_id: int, kind: UsageKind) -> None:
        periods = _periods(utcnow())
        with Session(self.engine) as db:
            for period, _ in self._windows(course_id, kind):
                db.exec(self._upsert(student_id, course_id, kind, period, periods[period][0], -1, 0))
            db.commit()

    def add_tokens(self, student_id: str, course_id: int, kind: UsageKind, tokens: int) -> None:
        if tokens <= 0:
            return
        periods = _periods(utcnow())
        with Session(self.engine) as db:
            for period, _ in self._windows(course_id, kind):
                db.exec(self._upsert(student_id, course_id, kind, period, periods[period][0], 0, tokens))
            db.commit()


# ------------------------------------------------------------------------------------------ module API
_meter: UsageMeter = NoLimits()


def configure(meter: UsageMeter | None) -> None:
    """Called when the app starts (build_services); None restores `NoLimits`."""
    global _meter
    _meter = meter or NoLimits()


def check_usage(student_id: str, course_id: int, kind: UsageKind) -> None:
    """Raises UsageLimitExceeded when the student reached a limit in this course."""
    _meter.check_usage(student_id, course_id, kind)


def record_usage(student_id: str, course_id: int, kind: UsageKind, *, tokens: int = 0) -> None:
    _meter.record_usage(student_id, course_id, kind, tokens=tokens)


def reserve_usage(student_id: str, course_id: int, kind: UsageKind) -> None:
    """Checks and counts one use atomically; raises UsageLimitExceeded (nothing counted) at the limit."""
    _meter.reserve_usage(student_id, course_id, kind)


def release_usage(student_id: str, course_id: int, kind: UsageKind) -> None:
    _meter.release_usage(student_id, course_id, kind)


def add_tokens(student_id: str, course_id: int, kind: UsageKind, tokens: int) -> None:
    _meter.add_tokens(student_id, course_id, kind, tokens)
