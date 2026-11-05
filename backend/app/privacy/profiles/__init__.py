"""Privacy profiles per course type, document scanning and web search queries (guide 4.7; tasks Z7, Z11).

Z1 stand-ins, safe by default:
- `privacy_profile` returns built-in profiles; Z7 loads them from one config file per profile;
- `scan_document` reports "not scanned" (it never claims a file is clean); Z11 runs the analyzer;
- `search_query` returns None, so no web search query is ever produced; Z11 builds the sanitized query.
"""
from dataclasses import dataclass, field

from app.core.schemas import CourseType, PrivacyProfile, RequestContext

# The medical profile is the v3 behaviour: health-detail rules, rewrite policy, medical safety checker.
_PROFILES: dict[str, PrivacyProfile] = {
    "medical_science": PrivacyProfile(
        name="medical_science", recognizers=("health_detail", "health_context", "health_extra"),
        health_detail_policy="generalize", checkers=("medical_safety",), medical_disclaimer=True),
    "life_science": PrivacyProfile(name="life_science"),
    "ece": PrivacyProfile(name="ece"),
    "general": PrivacyProfile(name="general"),
}


def privacy_profile(course_type: CourseType) -> PrivacyProfile:
    return _PROFILES[course_type]


@dataclass(frozen=True)
class ScanFinding:
    type: str  # entity type, e.g. PERSON, STUDENT_ID; never the matched text
    count: int


@dataclass(frozen=True)
class ScanResult:
    scanned: bool
    findings: tuple[ScanFinding, ...] = field(default_factory=tuple)


def scan_document(text: str, profile: PrivacyProfile) -> ScanResult:
    """Personal data found in an uploaded document (types and counts only)."""
    return ScanResult(scanned=False)


def search_query(ctx: RequestContext) -> str | None:
    """A sanitized, general web search query for the question, or None when none can be made safely."""
    return None
