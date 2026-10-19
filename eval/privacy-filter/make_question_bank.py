"""Generate a bank of PII-free, student-style health questions with the local model (run once; output committed).

    .venv\\Scripts\\python eval\\privacy-filter\\make_question_bank.py

The bank gives the E6 templates varied carrier questions, so the test set is not 400 copies of ten sentences.
Lines containing digits, '@', capitalized words that look like names, or first-person health statements are
dropped automatically; the rest is reviewed by hand before use (see README in this folder).
"""
import json
import re
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))
from app.core.config import get_settings  # noqa: E402

TOPICS = ["high blood pressure", "type 2 diabetes", "asthma", "migraine", "pneumonia"]
PROMPT = ("Write 20 different short questions that a university student might ask a tutor about {topic}. "
          "Vary the style: some casual, some formal, some with typos, some very short. Do NOT include any names, "
          "numbers, personal details or anything about the student's own health. One question per line, "
          "no numbering.")
BAD = re.compile(r"\d|@|\b(?:I|my|me|mine)\b|\b(?:Dr|Mr|Mrs|Ms)\.?\s", re.I)


def main() -> None:
    s = get_settings()
    bank = {}
    for topic in TOPICS:
        r = httpx.post(f"{s.ollama_url}/api/chat", timeout=300, json={
            "model": s.llm.local.model, "stream": False, "think": False,
            "options": {"temperature": 0.9, "seed": 6},
            "messages": [{"role": "user", "content": PROMPT.format(topic=topic)}]})
        lines = [re.sub(r"^[-*•\s]+", "", ln).strip() for ln in r.json()["message"]["content"].splitlines()]
        keep = [ln for ln in lines if 8 <= len(ln) <= 160 and ln.endswith("?") and not BAD.search(ln)]
        bank[topic] = list(dict.fromkeys(keep))
        print(f"{topic}: {len(bank[topic])} kept of {len(lines)}")
    (HERE / "question_bank.json").write_text(json.dumps(bank, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
