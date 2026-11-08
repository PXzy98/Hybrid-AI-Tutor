"""Privacy profiles per course type, document scanning and web search queries (guide 4.7; tasks Z7, Z11).

Task Z7: one YAML file per profile in this folder. `base.yaml` is the layer every course has; a profile
`extends: base` and adds recognizers, its health-detail policy, checkers and the medical disclaimer. A new
profile (course type) needs one new file. Files are validated when first loaded: unknown recognizers or
checkers stop the app.

Still Z1 stand-ins, safe by default (task Z11):
- `scan_document` reports "not scanned" (it never claims a file is clean);
- `search_query` returns None, so no web search query is ever produced.
"""
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
    unknown = set(data) - {"extends", "recognizers", "health_detail_policy", "checkers", "medical_disclaimer"}
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
