"""Leak detection for cloud requests (privacy invariants 2, 3; design §8.2).

Used twice: by the generate step BEFORE a request is sent (a leak blocks it), and by the pii_leak /
profile_leak checkers afterwards (audit, defence in depth).
"""
import re

from app.core.schemas import CloudRequest, RequestContext
from app.learner.content import ContentStore
from app.privacy.analyzer import PIIAnalyzer
from app.privacy.anonymizer import PLACEHOLDER_RE

ITEM_ID_RE = re.compile(r"\b[A-Za-z0-9]+\.\d+-q\d+\b")


def pii_problems(analyzer: PIIAnalyzer, req: CloudRequest) -> list[str]:
    """PII still visible in the student's part of the request (its sanitized question).

    Placeholders are blanked first. Passages are course material and are not scanned: they legitimately
    contain names such as eponyms or authors.
    """
    text = PLACEHOLDER_RE.sub(" ", req.sanitized_question)
    return sorted({f"{f.type} in question" for f in analyzer.analyze(text)})


def profile_problems(req: CloudRequest, ctx: RequestContext, content: ContentStore) -> list[str]:
    """Learner-profile or identity data in the request: the student_id, check-item IDs, or a misconception
    statement from the catalog that the student did not write themselves."""
    payload = req.model_dump_json()
    found = []
    if ctx.request.student_id and ctx.request.student_id in payload:
        found.append("student_id")
    if ITEM_ID_RE.search(payload):
        found.append("check item ID")
    question, own = req.sanitized_question.lower(), ctx.request.question.lower()
    for m in content.all_misconceptions():
        statement = m.statement.lower().rstrip(".")
        if statement in question and statement not in own:
            found.append(f"misconception {m.id}")
    return found


class CloudLeakGuard:
    def __init__(self, analyzer: PIIAnalyzer, content: ContentStore) -> None:
        self.analyzer = analyzer
        self.content = content

    def problems(self, req: CloudRequest, ctx: RequestContext) -> list[str]:
        return pii_problems(self.analyzer, req) + profile_problems(req, ctx, self.content)
