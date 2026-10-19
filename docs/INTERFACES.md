# Interfaces for teammates (routing and RAG)

> Status 19 Oct 2026: both components are integrated (semantic router `routing.impl: semantic`, medical RAG `rag.impl: medical_hybrid`). This page describes the plug-in contract, which is unchanged; as-built details are in [ROUTING_PATCH.md](ROUTING_PATCH.md), [RAG_INTEGRATION.md](RAG_INTEGRATION.md) and [System_Design_v3.md §16](System_Design_v3.md).

For **Tongkai** (routing score) and **Siyun** (RAG retrieval). This document covers what your code receives, what it must return, and how it plugs in. You do not need to touch the pipeline or any other code.

Source of truth: [`backend/app/core/schemas.py`](../backend/app/core/schemas.py). Design background: [System_Design_v3.md](System_Design_v3.md) §7.1 and §9.

## How plugging in works

1. Add **one file** in `backend/app/routing/` (Tongkai) or `backend/app/rag/` (Siyun).
2. Put a class with a **no-argument constructor** in it, registered under a name of your choice.
3. Set that name in `config.yaml` (`routing.impl` or `rag.impl`).
4. Run the contract tests. They find your implementation automatically.

You can read settings inside your constructor with `from app.core.config import get_settings`. Secrets (API keys, paths) go in `.env`, not in `config.yaml`. Add your own options to `config.yaml` only after agreeing on the key names, because unknown keys are rejected at startup.

---

## Routing score (Tongkai)

```python
# backend/app/routing/<your_name>.py
from app.core.registry import routers
from app.core.schemas import RouteInput, RouteScore

@routers.register("<your_name>")
class MyRouter:
    def __init__(self) -> None:
        ...  # load a model, read settings, etc.

    def route_score(self, x: RouteInput) -> RouteScore:
        return RouteScore(score=0.42, reasons=["multi-step question", "no passages found"])
```

**What you get**

```python
class RouteInput(BaseModel):
    sanitized_question: str      # PII already replaced, e.g. "<PERSON_1> asked ..."
    topic: str                   # high_blood_pressure | type2_diabetes | asthma | migraine | pneumonia
    pii: PIIResult               # entities, is_sensitive, cloud_safe, sanitized_text
    passage_count: int           # how many RAG passages were found (0 = none)
    level: Level | None = None   # "basic" | "intermediate" | "advanced": student's level for this question
    kc_ids: list[str] = []       # knowledge components of the question (filled from the Beta on)

class PIIResult(BaseModel):
    entities: list[PIIEntity] = []   # type, text, start, end, score, placeholder
    is_sensitive: bool = False
    cloud_safe: bool = True          # False -> the cloud gate keeps it local whatever you return
    sanitized_text: str
```

**What you return:** `RouteScore(score: float in [0, 1], reasons: list[str] = [])`.
- `score >= routing.threshold` (currently 0.6, a placeholder for you to set) → cloud; otherwise local.
- Use `reasons` for short explanations; they are logged and shown on the instructor dashboard.

**Rules**
- Synchronous, deterministic (same input → same score), under 1 s.
- Never raise on unusual input, such as an empty question.
- Use only the fields of `RouteInput`; it is all you get.
- You do **not** need to handle `cloud_safe = False`. Decided 19 Oct 2026: the cloud gate in the generate step applies the privacy rules whichever router chose the cloud (`privacy.health_detail_policy`: `local_only` by default, `generalize` optional), runs the leak guard, and falls back to the local model with a notice. The stub router additionally keeps `routing.force_local_if_not_cloud_safe`.

---

## RAG retrieval (Siyun)

```python
# backend/app/rag/<your_name>.py
from app.core.registry import retrievers
from app.core.schemas import Chunk, Level

@retrievers.register("<your_name>")
class MyRetriever:
    def __init__(self) -> None:
        ...  # open the vector store, load the embedding model

    def retrieve(self, query: str, topic: str, k: int = 4,
                 kc_ids: list[str] | None = None, level: Level | None = None) -> list[Chunk]:
        ...

    # optional, used by the instructor dashboard upload (Beta)
    def ingest(self, topic: str, path: str) -> None:
        ...
```

**What you get:** the **sanitized** question, the topic, `k`, and optionally the KC IDs and the student's level.

**What you return**

```python
class Chunk(BaseModel):
    text: str
    source: str                  # file name or URL, shown to the student as the source
    topic: str
    score: float                 # your relevance score, higher = better
    kc_ids: list[str] = []       # which knowledge components this chunk teaches, e.g. ["HBP.5"]
    level: Level | None = None   # "basic" | "intermediate" | "advanced"
```

**Rules**
- At most `k` chunks, all with `chunk.topic == topic`.
- When `kc_ids` or `level` are given, return matching chunks first. **If the filter finds too few, fill up with topic-only results.** Never return nothing just because of the filter.
- Never raise on an unknown KC or topic; return what you can, possibly `[]`.
- Synchronous. The pipeline runs it in a worker thread.

**Chunk tagging.** Every chunk needs `kc_ids` and `level`. KC IDs are defined per topic in `content/topics/<topic>/kcs.yaml` (from Step 5; High Blood Pressure first: `HBP.1` … `HBP.6`, see design §4.1). An LLM can propose the tags; please check a sample by hand.

**Reference implementation.** `backend/app/rag/stub.py` has a `fixture` retriever: keyword overlap over `data/synthetic/rag_fixture.jsonl`, with the filter-then-fallback behaviour above. Set `rag.impl: fixture` to try the pipeline with it.

---

## Running the contract tests

Setup is in the [README](../README.md#development-setup). Then, from `backend/`:

```powershell
..\.venv\Scripts\python -m pytest tests/contracts -k routing   # Tongkai
..\.venv\Scripts\python -m pytest tests/contracts -k rag       # Siyun
```

Every registered implementation is tested; your class shows up as `[<your_name>]` in the test IDs. If your implementation needs a running service (for example a vector database), start it before running the tests.

## If you need an interface change

Changes to `schemas.py` affect everyone. Tell Zhenyan which field you need and why. Changes are recorded under "Interface changes" in [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md).
