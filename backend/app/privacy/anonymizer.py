"""Reversible anonymization: numbered placeholders per type, the same value always gets the same one."""
import re

from app.core.schemas import PIIEntity
from app.privacy.analyzer import Finding

# tolerant: the cloud model may write <person_1>, < PERSON_1 > or [PERSON_1]
PLACEHOLDER_RE = re.compile(r"[<\[]\s*([A-Za-z]+(?:_[A-Za-z]+)*)_(\d+)\s*[>\]]")


def anonymize(text: str, findings: list[Finding]) -> tuple[str, list[PIIEntity], dict[str, str]]:
    """Returns (sanitized text, entities with placeholders, placeholder -> original value)."""
    counters: dict[str, int] = {}
    by_value: dict[tuple[str, str], str] = {}
    entities: list[PIIEntity] = []
    for f in sorted(findings, key=lambda f: f.start):
        value = text[f.start:f.end]
        key = (f.type, " ".join(value.lower().split()))
        if key not in by_value:
            counters[f.type] = counters.get(f.type, 0) + 1
            by_value[key] = f"<{f.type}_{counters[f.type]}>"
        entities.append(PIIEntity(type=f.type, text=value, start=f.start, end=f.end, score=round(f.score, 3),
                                  placeholder=by_value[key]))
    out = text
    for e in sorted(entities, key=lambda e: e.start, reverse=True):
        out = out[:e.start] + e.placeholder + out[e.end:]
    mapping: dict[str, str] = {}
    for e in entities:
        mapping.setdefault(e.placeholder, e.text)  # repeated values: the first spelling is restored
    return out, entities, mapping


def restore(text: str, mapping: dict[str, str]) -> str:
    """Put original values back for placeholders, accepting small formatting changes by the model."""
    if not mapping:
        return text
    lookup = {k.upper(): v for k, v in mapping.items()}

    def sub(m: re.Match) -> str:
        return lookup.get(f"<{m.group(1).upper()}_{m.group(2)}>", m.group(0))

    return PLACEHOLDER_RE.sub(sub, text)
