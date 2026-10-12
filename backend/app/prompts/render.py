"""Prompt rendering (design §6). Safety rules live ONLY in base_system.md and are identical for every
level and both routes.

`render_local` may use the full RequestContext (raw question, learner context, history): it only ever goes
to the local model. `render_cloud` takes a CloudRequest and nothing else, so a cloud prompt cannot contain
anything the allow-list does not contain.
"""
from functools import cache
from pathlib import Path

from app.core.schemas import CloudRequest, Level, RequestContext
from app.core.topics import topic_name
from app.llm.base import Message

PROMPT_DIR = Path(__file__).parent

CLOUD_PLACEHOLDER_RULE = (
    "The question may contain placeholders such as <PERSON_1> or <STUDENT_ID_1>. "
    "Keep them exactly as written and never guess what they stand for."
)


@cache
def base_system() -> str:
    return (PROMPT_DIR / "base_system.md").read_text(encoding="utf-8").strip()


def level_line(level: Level) -> str:
    # one line until the level/style partials of Step 7
    return f"Teaching level for this student: {level}. Adjust depth and vocabulary to it, never accuracy."


def material_block(passages: list[str]) -> str:
    if not passages:
        return "Course material: none was found for this question."
    return "Course material:\n" + "\n\n".join(f"[{i}] {p.strip()}" for i, p in enumerate(passages, 1))


def _user_message(topic: str, passages: list[str], question: str) -> Message:
    content = f"Topic: {topic_name(topic)}\n\n{material_block(passages)}\n\nStudent question: {question}"
    return {"role": "user", "content": content}


def render_local(ctx: RequestContext) -> list[Message]:
    """Messages for the LOCAL model. May contain the original question and the learner context."""
    system = base_system()
    if ctx.learner and ctx.learner.personalized:
        system += "\n\n" + level_line(ctx.learner.focus_level)
    messages: list[Message] = [{"role": "system", "content": system}]
    for turn in ctx.history:  # sanitized earlier turns
        messages.append({"role": "user" if turn.role == "student" else "assistant", "content": turn.text})
    messages.append(_user_message(ctx.request.topic, [c.text for c in ctx.passages], ctx.request.question))
    return messages


def render_cloud(req: CloudRequest) -> list[Message]:
    """Messages for the CLOUD model, built from the allow-listed CloudRequest only."""
    system = "\n\n".join([base_system(), level_line(req.labels.level), CLOUD_PLACEHOLDER_RULE])
    return [{"role": "system", "content": system},
            _user_message(req.topic, req.passages, req.sanitized_question)]
