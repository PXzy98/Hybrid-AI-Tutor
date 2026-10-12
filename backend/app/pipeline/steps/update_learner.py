import re

from app.core.registry import steps
from app.core.schemas import Evidence, RequestContext
from app.learner.preference import PreferenceSignal
from app.pipeline.base import BaseStep

# Presentation hints in the student's own wording. Implicit signals: a preference changes only after three
# consistent ones (simple preference model), so a single phrasing never flips it.
HINTS = [
    (re.compile(r"\bexamples?\b|\bfor instance\b", re.I), "sequencing", "example_first"),
    (re.compile(r"\b(?:the (?:general )?idea|the concept|in general|the theory|the principle)\b", re.I),
     "sequencing", "concept_first"),
    (re.compile(r"\b(?:in detail|step by step|more detail|elaborate|thorough(?:ly)?|in depth)\b", re.I),
     "detail", "detailed"),
    (re.compile(r"\b(?:briefly|short answer|in short|quick(?:ly)?|in one sentence|summar(?:y|ise|ize))\b",
                re.I), "detail", "concise"),
]


def weak_evidence(ctx: RequestContext, content) -> list[Evidence]:
    """Weak evidence from the understand step (design §5.1): confusion about the question's KCs and the
    misconceptions the student stated. The facade caps it at one weak update per KC per request."""
    u = ctx.understanding
    if u is None:
        return []
    stated = [content.misconception(m) for m in u.misconception_ids]
    out = [Evidence(kc_id=mc.kc, kind="weak", signal="misconception", misconception_id=mc.id,
                    source="understand") for mc in stated if mc]
    if u.confusion:
        out += [Evidence(kc_id=k, kind="weak", signal="confusion", source="understand") for k in u.kc_ids]
    return out


def preference_hints(question: str) -> list[PreferenceSignal]:
    return [PreferenceSignal(dimension=dim, value=value, explicit=False, source="implicit")
            for pattern, dim, value in HINTS if pattern.search(question)]


@steps.register("update_learner")
class UpdateLearnerStep(BaseStep):
    """Post-response (background): misconceptions the student stated (tracking: suspected, then confirmed on
    a second signal), weak evidence for the knowledge model when learner.weak_evidence is on, and implicit
    presentation hints. All are no-ops without consent (the facade checks it)."""

    name = "update_learner"
    on_error = "skip"

    async def run(self, ctx: RequestContext) -> RequestContext:
        learner, sid = self.services.learner, ctx.request.student_id
        for mc_id in ctx.understanding.misconception_ids if ctx.understanding else []:
            learner.misconception_stated(sid, mc_id)
        if self.services.settings.learner.weak_evidence:
            learner.observe_request(sid, weak_evidence(ctx, self.services.content))
        for signal in preference_hints(ctx.request.question):
            learner.update_preferences(sid, signal)
        return ctx
