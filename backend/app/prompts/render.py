"""Prompt rendering (design §6). Safety rules live ONLY in base_system.md and are identical for every
level and both routes. levels/<level>.md and style/<sequencing>.<detail>.md only change depth and form.

`render_local` may use the full RequestContext (raw question, learner context, history): it only ever goes
to the local model. `render_cloud` takes a CloudRequest and nothing else, so a cloud prompt cannot contain
anything the allow-list does not contain.
"""
from functools import cache
from pathlib import Path

from app.core.schemas import CloudRequest, Detail, Level, RequestContext, Sequencing
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


@cache
def level_partial(level: Level) -> str:
    return (PROMPT_DIR / "levels" / f"{level}.md").read_text(encoding="utf-8").strip()


@cache
def style_partial(sequencing: Sequencing, detail: Detail) -> str:
    return (PROMPT_DIR / "style" / f"{sequencing}.{detail}.md").read_text(encoding="utf-8").strip()


def system_prompt(level: Level | None = None, sequencing: Sequencing | None = None,
                  detail: Detail | None = None) -> str:
    """base (safety) + level partial + style partial.

    The partials only change depth and form; they never repeat or override the safety rules.
    """
    parts = [base_system()]
    if level:
        parts.append(level_partial(level))
    if sequencing and detail:
        parts.append(style_partial(sequencing, detail))
    return "\n\n".join(parts)


def material_block(passages: list[str]) -> str:
    if not passages:
        return "Course material: none was found for this question."
    return "Course material:\n" + "\n\n".join(f"[{i}] {p.strip()}" for i, p in enumerate(passages, 1))


def _user_message(topic: str, passages: list[str], question: str) -> Message:
    content = f"Topic: {topic_name(topic)}\n\n{material_block(passages)}\n\nStudent question: {question}"
    return {"role": "user", "content": content}


def render_local(ctx: RequestContext) -> list[Message]:
    """Messages for the LOCAL model. May contain the original question and the learner context."""
    learner = ctx.learner if ctx.learner and ctx.learner.personalized else None
    if learner:
        prefs = learner.preferences
        system = system_prompt(learner.focus_level, prefs.sequencing, prefs.detail)
    else:
        system = system_prompt()
    messages: list[Message] = [{"role": "system", "content": system}]
    for turn in ctx.history:  # sanitized earlier turns
        messages.append({"role": "user" if turn.role == "student" else "assistant", "content": turn.text})
    messages.append(_user_message(ctx.request.topic, [c.text for c in ctx.passages], ctx.request.question))
    return messages


def render_cloud(req: CloudRequest) -> list[Message]:
    """Messages for the CLOUD model, built from the allow-listed CloudRequest only."""
    labels = req.labels
    system = system_prompt(labels.level, labels.sequencing, labels.detail) + "\n\n" + CLOUD_PLACEHOLDER_RULE
    return [{"role": "system", "content": system},
            _user_message(req.topic, req.passages, req.sanitized_question)]
