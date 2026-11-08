"""Privacy profiles per course type, document scanning and web search queries (guide 4.7; tasks Z7, Z11).

Task Z7: one YAML file per profile in this folder. `base.yaml` is the layer every course has; a profile
`extends: base` and adds recognizers, its health-detail policy, checkers and the medical disclaimer. A new
profile (course type) needs one new file. Files are validated when first loaded: unknown recognizers or
checkers stop the app.

Task Z11:
- `scan_document(text, profile)` runs the profile's analyzer over an uploaded document and reports entity
  types and counts (never the matched text); `blocking` lists the types that are student data;
- `search_query(ctx)` is the only source of web search queries (rule 5): built from the sanitized question,
  never from the original, and None whenever a safe general query cannot be made;
- `consent_text(profile)` is the onboarding consent text of the course type (base text + the profile's note).
"""
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import yaml

from app.core.schemas import PrivacyProfile, RequestContext

PROFILE_DIR = Path(__file__).resolve().parent


class ProfileError(ValueError):
    """An invalid profile file."""


@cache
def _raw(name: str) -> dict:
    path = PROFILE_DIR / f"{name}.yaml"
    if not path.is_file():
        raise ProfileError(f"unknown privacy profile: {name}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    unknown = set(data) - {"extends", "recognizers", "health_detail_policy", "checkers", "medical_disclaimer",
                           "consent_note"}
    if unknown:
        raise ProfileError(f"{path.name}: unknown keys {sorted(unknown)}")
    return data


def profile_names() -> list[str]:
    """The course types: every profile file except the base layer."""
    return sorted(p.stem for p in PROFILE_DIR.glob("*.yaml") if p.stem != "base")


@cache
def privacy_profile(course_type: str) -> PrivacyProfile:
    from app.core.registry import checkers as checker_registry
    from app.core.registry import import_submodules, pii_recognizers

    if course_type == "base" or course_type not in profile_names():
        raise ProfileError(f"unknown privacy profile: {course_type}")
    own = _raw(course_type)
    if own.get("extends") != "base":  # guide 4.7: the base layer protects every course
        raise ProfileError(f"{course_type}.yaml must start with 'extends: base'")
    parent = _raw("base")
    if parent.get("extends") or not parent.get("recognizers"):
        raise ProfileError("base.yaml must list the base recognizers and extend nothing")
    merged = {**{k: v for k, v in parent.items() if k != "recognizers"},
              **{k: v for k, v in own.items() if k not in ("recognizers", "extends")}}
    recognizers = tuple(dict.fromkeys([*(parent.get("recognizers") or []), *(own.get("recognizers") or [])]))
    import_submodules("app.privacy.recognizers")
    import_submodules("app.verify.checkers")
    bad = [r for r in recognizers if r not in pii_recognizers.names()]
    bad += [c for c in merged.get("checkers") or [] if c not in checker_registry.names()]
    if bad:
        raise ProfileError(f"{course_type}: unknown recognizer or checker {bad}")
    return PrivacyProfile(name=course_type, recognizers=recognizers,
                          health_detail_policy=merged.get("health_detail_policy", "local_only"),
                          checkers=tuple(merged.get("checkers") or ()),
                          medical_disclaimer=bool(merged.get("medical_disclaimer", False)))


# Found in a course document, these are student data and keep it out of the index: identifiers of a person
# other than a name or contact (course documents name their staff and authors), grades, credentials and
# personal health details. Names, e-mail addresses and phone numbers are reported but do not block.
BLOCKING_TYPES = frozenset({"STUDENT_ID", "GRADE", "HEALTH_CARD", "ID_NUMBER", "DATE_OF_BIRTH", "SECRET",
                            "HEALTH_DETAIL"})
SCAN_CHUNK_CHARS = 20_000  # the analyzer runs on pieces of this size (spaCy and the regexes stay fast)


@dataclass(frozen=True)
class ScanFinding:
    type: str  # entity type, e.g. PERSON, STUDENT_ID; never the matched text
    count: int


@dataclass(frozen=True)
class ScanResult:
    scanned: bool
    findings: tuple[ScanFinding, ...] = field(default_factory=tuple)

    @property
    def blocking(self) -> tuple[str, ...]:
        """The found types that are student data (BLOCKING_TYPES); empty when the document may be indexed."""
        return tuple(f.type for f in self.findings if f.type in BLOCKING_TYPES)


@cache
def _scanner(profile_name: str, recognizers: tuple[str, ...]):
    from app.core.config import get_settings
    from app.privacy.analyzer import PIIAnalyzer

    base = get_settings().privacy
    names = list(recognizers) if base.recognizers is None else list(base.recognizers)
    return PIIAnalyzer(base.model_copy(update={"recognizers": names}))


def _pieces(text: str, size: int = SCAN_CHUNK_CHARS):
    """Pieces of about `size` characters, cut at a line break where possible (no entity is cut in two)."""
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = text.rfind("\n", start + size // 2, end)
            end = cut + 1 if cut > 0 else end
        yield text[start:end]
        start = end


def scan_document(text: str, profile: PrivacyProfile) -> ScanResult:
    """Personal data found in an uploaded document (types and counts only), with the course's profile."""
    analyzer = _scanner(profile.name, tuple(profile.recognizers))
    counts: dict[str, int] = {}
    for piece in _pieces(text or ""):
        for f in analyzer.analyze(piece):
            counts[f.type] = counts.get(f.type, 0) + 1
    return ScanResult(scanned=True, findings=tuple(ScanFinding(t, n) for t, n in sorted(counts.items())))


PLACEHOLDER_RE = re.compile(r"<[A-Z_]+_\d+>")
SEARCH_QUERY_MAX_CHARS = 200


def search_query(ctx: RequestContext) -> str | None:
    """A sanitized, general web search query for the question, or None when none can be made safely.

    Built only from the privacy filter's sanitized text (never the original question). None when the filter
    has not run, when the question must stay local, or when nothing general is left: every sentence that
    held personal data (a placeholder) is dropped, not just the value, because the rest of such a sentence is
    about the student ("my grade in ... is <GRADE_1>, can I ..."). The cloud never sees more than this.
    """
    pii = ctx.pii
    if pii is None or not pii.cloud_safe:
        return None
    sentences = re.split(r"(?<=[.!?])\s+|\n+", pii.sanitized_text)
    kept = [s.strip() for s in sentences if s.strip() and not PLACEHOLDER_RE.search(s)]
    query = re.sub(r"\s+", " ", " ".join(kept)).strip()
    if len(query.split()) < 3:
        return None
    if len(query) > SEARCH_QUERY_MAX_CHARS:
        query = query[:SEARCH_QUERY_MAX_CHARS].rsplit(" ", 1)[0]
    return query


# the reviewed v1 onboarding text (app/api/v1/onboarding.py, unchanged there: API v1 is frozen)
CONSENT_BASE = (
    "To adapt explanations to you, the tutor keeps a learning profile: an estimate of how well you know each "
    "topic part, which common misunderstandings you may have, and how you like explanations presented "
    "(examples first or ideas first, short or detailed). It does not keep your questions in readable form "
    "with your name. The profile is stored only on the course's own servers and is never sent to external "
    "AI services; they may only receive a coarse level such as 'basic'. You can view or reset your profile "
    "at any time under 'What I know', and the instructor can delete your account and its data. Without "
    "consent the tutor still answers, but does not adapt to you."
)


def consent_text(profile: PrivacyProfile) -> str:
    """The consent text shown at onboarding for this course type: the base text plus the profile's note."""
    note = _raw(profile.name).get("consent_note") if profile.name in profile_names() else None
    return f"{CONSENT_BASE} {note.strip()}" if note else CONSENT_BASE
