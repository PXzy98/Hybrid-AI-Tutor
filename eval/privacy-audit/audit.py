"""E4 leak analysis (design §11 E4), separate from the scripted run so that it can be tested on its own.

Input: the records written by the recording cloud client (app/llm/audit.py), each tagged with the ask that
produced it, plus the secrets of the run (identities, planted PII values, profile data).

Leak classes:
- field: a key outside the CloudRequest allow-list, or messages that are not exactly render_cloud(request);
- identity: a username, display name, account ID or student_id from the account table reached the cloud
  without the student typing it in that question (or reached the database outside `account`, or a log);
- profile: misconception IDs/statements/corrections, check-item IDs, or a student_id in a cloud payload;
- pii: a value the student typed (name, student number, e-mail, phone, grade) reached the cloud, or the
  PII analyzer still finds something in the sanitized question.
"""
import re
from dataclasses import dataclass, field

from app.core.schemas import CloudLabels, CloudRequest
from app.prompts import render_cloud

ITEM_ID_RE = re.compile(r"\b[A-Z]+\.\d+-q\d+\b")
MC_ID_RE = re.compile(r"\b[A-Z]+\.MC\d+\b")


@dataclass
class Secrets:
    identities: list[str]  # usernames, display names and their surnames
    student_ids: list[str]
    misconception_texts: list[str]  # catalog statements and corrections


@dataclass
class Ask:
    persona: str
    question: str  # what the student typed
    planted: list[str]  # PII values typed in this question
    record_ids: list[int] = field(default_factory=list)  # indexes into the records list
    route: str = ""
    warnings: list[str] = field(default_factory=list)
    expect_local: bool = False  # E6: the question states a personal health detail
    planted_health: list[str] = field(default_factory=list)  # its health spans (allowed in a generalized rewrite)


@dataclass
class Finding:
    kind: str  # field | identity | profile | pii
    where: str  # cloud#<n> | db | log
    detail: str


def allowed_keys() -> dict[str, set[str]]:
    return {"": set(CloudRequest.model_fields), "labels": set(CloudLabels.model_fields)}


def field_findings(i: int, record: dict) -> list[Finding]:
    out = []
    req = record.get("cloud_request", {})
    allow = allowed_keys()
    for key in sorted(set(req) - allow[""]):
        out.append(Finding("field", f"cloud#{i}", f"field outside the allow-list: {key}"))
    for key in sorted(set(req.get("labels") or {}) - allow["labels"]):
        out.append(Finding("field", f"cloud#{i}", f"label outside the allow-list: {key}"))
    if not out:
        try:
            expected = render_cloud(CloudRequest.model_validate(req), safety_retry=bool(record.get("safety_retry")))
        except ValueError as e:
            return [Finding("field", f"cloud#{i}", f"request does not validate: {type(e).__name__}")]
        if record.get("messages") != expected:
            out.append(Finding("field", f"cloud#{i}", "messages differ from render_cloud(request)"))
    return out


def contains(text: str, value: str) -> bool:
    """Whole-word, case-insensitive ("Tom" must not match "symptoms")."""
    return bool(value) and re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text, re.I) is not None


def text_findings(where: str, text: str, secrets: Secrets, typed: str = "", planted: tuple[str, ...] = (),
                  profile: bool = True) -> list[Finding]:
    out = []
    for v in secrets.identities:
        if contains(text, v):
            kind = "pii" if contains(typed, v) else "identity"
            out.append(Finding(kind, where, f"{'typed' if kind == 'pii' else 'account'} value '{v}'"))
    for v in planted:
        if contains(text, v) and not any(contains(v, i) or contains(i, v) for i in secrets.identities):
            out.append(Finding("pii", where, f"typed value '{v}'"))
    if profile:
        for sid in secrets.student_ids:
            if sid in text:
                out.append(Finding("profile", where, "student_id"))
        if ITEM_ID_RE.search(text):
            out.append(Finding("profile", where, f"check item ID {ITEM_ID_RE.search(text).group(0)}"))
        if MC_ID_RE.search(text):
            out.append(Finding("profile", where, f"misconception ID {MC_ID_RE.search(text).group(0)}"))
        for t in secrets.misconception_texts:
            probe = t.lower().rstrip(".")[:60]
            if probe and probe in text.lower() and probe not in typed.lower():
                out.append(Finding("profile", where, f"misconception text '{probe[:40]}…'"))
    return out


def analyze(records: list[dict], asks: list[Ask], secrets: Secrets, analyzer=None) -> list[Finding]:
    """Findings in the cloud payloads. `analyzer` (optional) re-scans each sanitized question for PII."""
    owner = {rid: a for a in asks for rid in a.record_ids}
    out: list[Finding] = []
    for i, rec in enumerate(records):
        out += field_findings(i, rec)
        ask = owner.get(i)
        typed = ask.question if ask else ""
        text = repr(rec)
        out += text_findings(f"cloud#{i}", text, secrets, typed, tuple(ask.planted) if ask else ())
        if analyzer is not None:
            from app.privacy.anonymizer import PLACEHOLDER_RE

            sanitized = PLACEHOLDER_RE.sub(" ", rec.get("cloud_request", {}).get("sanitized_question", ""))
            for f in analyzer.analyze(sanitized):
                out.append(Finding("pii", f"cloud#{i}", f"analyzer finds {f.type} in the sanitized question"))
    return out


def storage_findings(db_dump: str, log_text: str, secrets: Secrets, planted: list[str]) -> list[Finding]:
    """Identity and typed PII must not be in the database outside `account`, nor in the logs."""
    out = []
    for where, text in (("db", db_dump), ("log", log_text)):
        out += text_findings(where, text, Secrets(secrets.identities, [], []), "", tuple(planted), profile=False)
        out = [f if not (f.kind == "pii" and f.detail.startswith("typed value")) else
               Finding("pii", f.where, f.detail.replace("typed value", "raw typed value stored")) for f in out]
    return out
