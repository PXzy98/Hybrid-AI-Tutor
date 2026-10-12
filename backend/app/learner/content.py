"""Domain content: KC map, check-question item bank, misconception catalog (design §4).

One folder per topic: content/topics/<topic>/{kcs,items,misconceptions}.yaml. Everything is validated
when the app starts, so broken content never reaches students:
unique IDs, known prerequisites, no prerequisite cycles, 4 options with a valid key, known misconception
tags, misconceptions attached to known KCs.
"""
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.schemas import CheckItemPublic, Level

OptionKey = Literal["A", "B", "C", "D"]


class ContentError(ValueError):
    """Invalid content. The message lists every problem found, one per line."""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KC(Strict):
    id: str
    name: str
    definition: str = ""
    difficulty: Level
    prerequisites: list[str] = []


class Option(Strict):
    text: str = Field(min_length=1)
    misconception: str | None = None  # the misconception this distractor reveals


class Item(Strict):
    id: str
    kc: str
    level: Level
    stem: str = Field(min_length=1)
    options: dict[OptionKey, Option]
    answer: OptionKey
    explanation: str = ""
    reviewed_by: str | None = None

    @field_validator("options", mode="before")
    @classmethod
    def _plain_strings(cls, v):  # "A: text" is shorthand for {text: ...}
        return {k: ({"text": o} if isinstance(o, str) else o) for k, o in (v or {}).items()}

    @property
    def reviewed(self) -> bool:
        return bool(self.reviewed_by)

    def public(self) -> CheckItemPublic:
        """What the student sees: no answer key, no misconception tags."""
        return CheckItemPublic(id=self.id, kc_id=self.kc, stem=self.stem,
                               options={k: o.text for k, o in sorted(self.options.items())})


class Misconception(Strict):
    id: str
    kc: str
    statement: str
    correction: str
    reviewed_by: str | None = None


class TopicContent(Strict):
    topic: str
    name: str
    guideline: str = ""
    kcs: list[KC]
    items: list[Item] = []
    misconceptions: list[Misconception] = []


def _read_yaml(path: Path):
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_topic(folder: Path) -> TopicContent:
    kcs = _read_yaml(folder / "kcs.yaml") or {}
    data = {
        "topic": kcs.get("topic", folder.name),
        "name": kcs.get("name", folder.name.replace("_", " ").title()),
        "guideline": kcs.get("guideline", ""),
        "kcs": kcs.get("kcs", []),
        "items": _read_yaml(folder / "items.yaml") or [],
        "misconceptions": _read_yaml(folder / "misconceptions.yaml") or [],
    }
    try:
        return TopicContent(**data)
    except ValidationError as e:
        raise ContentError(f"{folder.name}: invalid format\n{e}") from None


def validate(topics: list[TopicContent]) -> list[str]:
    """All cross-reference problems, as readable messages."""
    problems: list[str] = []
    seen: dict[str, str] = {}

    def unique(kind: str, ident: str, where: str) -> None:
        if ident in seen:
            problems.append(f"{where}: duplicate ID '{ident}' (also used by {seen[ident]})")
        seen[ident] = f"{kind} in {where}"

    for t in topics:
        if not t.kcs:
            problems.append(f"{t.topic}: a topic needs at least one KC")
        kc_ids = {k.id for k in t.kcs}
        mc_ids = {m.id for m in t.misconceptions}
        for k in t.kcs:
            unique("KC", k.id, t.topic)
            for p in k.prerequisites:
                if p not in kc_ids:
                    problems.append(f"{t.topic}: KC {k.id} has unknown prerequisite '{p}'")
        for m in t.misconceptions:
            unique("misconception", m.id, t.topic)
            if m.kc not in kc_ids:
                problems.append(f"{t.topic}: misconception {m.id} refers to unknown KC '{m.kc}'")
        for i in t.items:
            unique("item", i.id, t.topic)
            if i.kc not in kc_ids:
                problems.append(f"{t.topic}: item {i.id} refers to unknown KC '{i.kc}'")
            if sorted(i.options) != ["A", "B", "C", "D"]:
                problems.append(f"{t.topic}: item {i.id} must have exactly the options A, B, C, D")
            if i.answer not in i.options:
                problems.append(f"{t.topic}: item {i.id} answer '{i.answer}' is not one of its options")
            elif i.options[i.answer].misconception:
                problems.append(f"{t.topic}: item {i.id} tags its correct answer with a misconception")
            for key, opt in i.options.items():
                if opt.misconception and opt.misconception not in mc_ids:
                    problems.append(f"{t.topic}: item {i.id} option {key} tags unknown misconception "
                                    f"'{opt.misconception}'")
        cycle = find_cycle({k.id: k.prerequisites for k in t.kcs})
        if cycle:
            problems.append(f"{t.topic}: prerequisite cycle {' -> '.join(cycle)}")
    return problems


def find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    """A cycle in the prerequisite graph as a path that starts and ends at the same KC, or None."""
    state: dict[str, int] = {}  # 1 = on the current path, 2 = done
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        path.append(node)
        for nxt in graph.get(node, []):
            if state.get(nxt) == 1:
                return path[path.index(nxt):] + [nxt]
            if nxt in graph and state.get(nxt) is None and (found := visit(nxt)):
                return found
        path.pop()
        state[node] = 2
        return None

    for n in graph:
        if state.get(n) is None and (found := visit(n)):
            return found
    return None


class ContentStore:
    def __init__(self, root: Path, serve_unreviewed: bool = False) -> None:
        self.root = Path(root)
        self.serve_unreviewed = serve_unreviewed
        folders = sorted(p for p in self.root.iterdir() if p.is_dir()) if self.root.exists() else []
        self._topics = {t.topic: t for t in (load_topic(f) for f in folders)}
        problems = validate(list(self._topics.values()))
        if problems:
            raise ContentError("invalid content in " + str(self.root) + ":\n" + "\n".join(problems))
        self._kcs = {k.id: (t.topic, k) for t in self._topics.values() for k in t.kcs}
        self._items = {i.id: i for t in self._topics.values() for i in t.items}
        self._mcs = {m.id: m for t in self._topics.values() for m in t.misconceptions}

    # ------------------------------------------------------------------ topics / KCs
    def topics(self) -> list[str]:
        return list(self._topics)

    def topic(self, topic: str) -> TopicContent | None:
        return self._topics.get(topic)

    def kcs(self, topic: str) -> list[KC]:
        t = self._topics.get(topic)
        return list(t.kcs) if t else []

    def kc(self, kc_id: str) -> KC | None:
        found = self._kcs.get(kc_id)
        return found[1] if found else None

    def topic_of(self, kc_id: str) -> str | None:
        found = self._kcs.get(kc_id)
        return found[0] if found else None

    def prerequisites(self, kc_id: str) -> list[str]:
        k = self.kc(kc_id)
        return list(k.prerequisites) if k else []

    # ----------------------------------------------------------------------- items
    def items(self, kc_id: str, reviewed_only: bool | None = None) -> list[Item]:
        """Items of a KC. By default, unreviewed items are served only if content.serve_unreviewed."""
        only_reviewed = (not self.serve_unreviewed) if reviewed_only is None else reviewed_only
        return [i for i in self._items.values() if i.kc == kc_id and (i.reviewed or not only_reviewed)]

    def item(self, item_id: str) -> Item | None:
        return self._items.get(item_id)

    def reviewed_item_count(self, topic: str) -> int:
        return sum(1 for k in self.kcs(topic) for i in self.items(k.id, reviewed_only=True))

    # -------------------------------------------------------------- misconceptions
    def misconception(self, mc_id: str) -> Misconception | None:
        return self._mcs.get(mc_id)

    def misconceptions(self, kc_id: str) -> list[Misconception]:
        return [m for m in self._mcs.values() if m.kc == kc_id]
