"""V16: the messages of an instructor draft for the cloud model, from a validated DraftCloudRequest only.

Called by `CloudClient.complete_draft` (the cloud gate); the same fixed instructions as the local drafts.
"""
from app.core.schemas import DraftCloudRequest
from app.instructor_ai import structure_drafts as tier2
from app.instructor_ai.drafts import _Generated, tier1_messages

TIER1 = ("project_ideas", "sample_proposal", "faq", "custom")


def render_draft(req: DraftCloudRequest) -> tuple[list[dict[str, str]], dict, int | None]:
    """(messages, answer schema, output limit) of the request."""
    material = [{"number": p.number, "source": p.source, "text": p.text} for p in req.passages]
    if req.kind in TIER1:
        return tier1_messages(req.kind, material, req.request), _Generated.model_json_schema(), None
    return (tier2.structure_messages(req.kind, material, req.kc_names),
            tier2.response_schema(req.kind, req.kc_names), None)  # the cloud's own limit (V13)
