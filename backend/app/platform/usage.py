"""Per-student usage limits (guide section 4.4; counters per student + course + day).

Z1 stand-in: `NoLimits` counts nothing and never refuses. Z10 replaces it with the database counters and
the `limits` values; callers already use the final interface.
"""
from typing import Literal, Protocol

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


class NoLimits:
    def check_usage(self, student_id: str, course_id: int, kind: UsageKind) -> None:
        return None

    def record_usage(self, student_id: str, course_id: int, kind: UsageKind, *, tokens: int = 0) -> None:
        return None
