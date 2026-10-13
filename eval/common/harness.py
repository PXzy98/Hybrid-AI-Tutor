"""Shared by the E3 and E4 harnesses: an in-process app, an instructor, and personas set up through the API.

The app runs in-process (FastAPI TestClient) against its own temporary database, so the harnesses never
touch data/app.db. Configuration goes through SECTION__FIELD environment variables, exactly as an operator
would set them. `fake=True` (smoke mode, CI) replaces the local models by scripted fakes; otherwise the real
Ollama server from OLLAMA_URL / .env is used.
"""
import json
import logging
import os
import re
import secrets
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402

TOPIC = "high_blood_pressure"
QUESTIONS = ROOT / "eval" / "personalization" / "questions.jsonl"
UNDERSTOOD_NOTHING = '{"k": [], "t": "other", "c": false, "m": []}'


@dataclass
class Persona:
    key: str
    username: str
    display_name: str  # fictional; used to check that identity never leaves the account table
    description: str  # what the judge is told about the student (E3)
    preferences: dict
    diagnostic: dict[str, bool]  # KC -> answer correctly? (missing KC = skipped)
    checks: list[tuple[str, str]] = field(default_factory=list)  # (item_id, "correct" | "wrong" | "MC id")
    misconception: str | None = None  # the misconception this persona holds (E3: should be addressed)


PERSONAS = [
    Persona("novice", "p.novice", "Maya Okafor",
            "Novice: basic level on every part of the topic. Prefers an example first and short answers.",
            {"sequencing": "example_first", "detail": "concise"},
            {"HBP.1": False}),
    Persona("intermediate_mc", "p.intermediate", "Lucas Bergeron",
            "Intermediate level. Believes the bottom number is the pressure when the heart stops (a known "
            "misconception). Prefers an example first and detailed answers.",
            {"sequencing": "example_first", "detail": "detailed"},
            {k: True for k in ("HBP.1", "HBP.2", "HBP.3", "HBP.4", "HBP.5", "HBP.6")},
            [("HBP.1-q2", "HBP.MC5")], misconception="HBP.MC5"),
    Persona("advanced", "p.advanced", "Priya Raman",
            "Advanced level on every part of the topic. Prefers the idea first and detailed answers.",
            {"sequencing": "concept_first", "detail": "detailed"},
            {k: True for k in ("HBP.1", "HBP.2", "HBP.3", "HBP.4", "HBP.5", "HBP.6")},
            [(f"HBP.{k}-q{q}", "correct") for k in range(1, 7) for q in (3, 4)]),
    Persona("mixed", "p.mixed", "Tom Nguyen",
            "Mixed: knows the numbers, risk factors and lifestyle well, but is weak on diagnosis, "
            "complications and medication. Prefers the idea first and short answers.",
            {"sequencing": "concept_first", "detail": "concise"},
            {"HBP.1": True, "HBP.2": False, "HBP.3": True, "HBP.5": True},
            [(f"HBP.{k}-q{q}", "correct") for k in (1, 3, 5) for q in (3, 4)]),
]


def load_questions(limit: int | None = None) -> list[dict]:
    rows = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[:limit] if limit else rows


def fake_answer(messages) -> str:
    """Smoke-mode local model: says which level and style partials it was given, so on/off differ."""
    system = messages[0]["content"]
    level = re.search(r"Teaching level for this student: (\w+)", system)
    tags = [level.group(1) if level else "unpersonalized"]
    tags += [t for t in ("example", "concept", "Known misunderstandings") if t.lower() in system.lower()]
    return f"[{' / '.join(tags)}] Blood pressure is the force of blood on the artery walls."


class Harness:
    """`with Harness(env, fake=True) as h:` starts the app; h.services, h.admin, h.persona_client(p)."""

    def __init__(self, env: dict[str, str] | None = None, fake: bool = True) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="tutor-eval-"))
        self.env = {
            "DATABASE_URL": f"sqlite:///{(self.tmp / 'eval.db').as_posix()}",
            "CONTENT__SERVE_UNREVIEWED": "true",
            "PRIVACY__SPACY_MODEL": os.environ.get("EVAL_SPACY_MODEL", "en_core_web_sm"),
            "INSTRUCTOR_USERNAME": "", "INSTRUCTOR_INITIAL_PASSWORD": "",
            **({"OLLAMA_URL": "http://127.0.0.1:9"} if fake else {}),
            **(env or {}),
        }
        self.fake = fake
        self._saved: dict[str, str | None] = {}
        self.log_lines: list[str] = []

    def __enter__(self) -> "Harness":
        for k, v in self.env.items():
            self._saved[k] = os.environ.get(k)
            os.environ[k] = v
        get_settings.cache_clear()
        from app.main import create_app

        self._log_handler = _ListHandler(self.log_lines)
        logging.getLogger().addHandler(self._log_handler)
        self.app = create_app()
        self.client = TestClient(self.app).__enter__()
        self.services = self.app.state.services
        if self.fake:
            from app.llm.fake import FakeLLMClient

            self.services.local_llm = FakeLLMClient(fake_answer, model="fake-local")
            self.services.understand_llm = FakeLLMClient(UNDERSTOOD_NOTHING, model="fake-understand")
        self.instructor_password = "Eval-" + secrets.token_urlsafe(12)
        self.services.accounts.create_instructor("eval.prof", self.instructor_password, must_change=False)
        self.admin = self.new_client()
        r = self.admin.post("/api/v1/auth/login", json={"username": "eval.prof",
                                                         "password": self.instructor_password})
        assert r.status_code == 200, r.text
        return self

    def __exit__(self, *exc) -> None:
        self.client.__exit__(*exc)
        logging.getLogger().removeHandler(self._log_handler)
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()

    def new_client(self) -> TestClient:
        """A second browser: same app, its own cookie jar (no second lifespan)."""
        return TestClient(self.app)

    def persona_client(self, p: Persona) -> tuple[TestClient, dict]:
        """Create the persona's account through admin/students, log in, change the password, onboard, and
        answer the scripted checks. Returns the logged-in client and the account JSON."""
        content = self.services.content
        r = self.admin.post("/api/v1/admin/students", json={"username": p.username, "display_name": p.display_name})
        assert r.status_code == 201, r.text
        account, temp = r.json()["account"], r.json()["temporary_password"]
        c = self.new_client()
        assert c.post("/api/v1/auth/login", json={"username": p.username, "password": temp}).status_code == 200
        new = "Persona-" + secrets.token_urlsafe(12)
        r = c.post("/api/v1/auth/change-password", json={"current_password": temp, "new_password": new})
        assert r.status_code == 200, r.text
        from app.learner.checks import diagnostic_items

        answers = []
        for item in diagnostic_items(content, TOPIC):
            if item.kc in p.diagnostic:
                answers.append({"item_id": item.id, "choice": choose(item, "correct" if p.diagnostic[item.kc] else "wrong")})
        r = c.post("/api/v1/onboarding", json={"topic": TOPIC, "consent": True, "preferences": p.preferences,
                                               "answers": answers})
        assert r.status_code == 200, r.text
        for item_id, how in p.checks:
            r = c.post("/api/v1/check", json={"item_id": item_id, "choice": choose(content.item(item_id), how)})
            assert r.status_code == 200, r.text
        return c, account


def choose(item, how: str) -> str:
    """'correct', 'wrong' (an untagged distractor if there is one) or a misconception ID (its distractor)."""
    if how == "correct":
        return item.answer
    if how == "wrong":
        wrong = [k for k, o in item.options.items() if k != item.answer]
        return next((k for k in wrong if not item.options[k].misconception), wrong[0])
    return next(k for k, o in item.options.items() if o.misconception == how)


class _ListHandler(logging.Handler):
    def __init__(self, sink: list[str]) -> None:
        super().__init__(logging.DEBUG)
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.sink.append(record.getMessage())
        except Exception:  # noqa: BLE001
            pass
