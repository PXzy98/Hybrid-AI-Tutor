"""Real local semantic/RAG smoke checks; no answer generation or provider API calls.

Run from backend/: python ../eval/semantic_rag_smoke.py
Requires the assets prepared by python -m app.routing.prepare.
"""

import json
from pathlib import Path
from time import perf_counter

from app.core.schemas import PIIResult, RouteInput
from app.rag.medical_hybrid import MedicalHybridRetriever
from app.routing.semantic import SemanticRouter

QUESTIONS = [
    ("high_blood_pressure",
     "Using the course material, explain what systolic and diastolic blood pressure mean."),
    ("type2_diabetes", "According to the course material, what is insulin resistance?"),
    ("asthma", "Using the course material, explain what happens to the airways during asthma."),
    ("migraine", "According to the course material, what symptoms can occur during a migraine?"),
    ("pneumonia", "Using the course material, explain what pneumonia is and which symptoms it can cause."),
    ("asthma", "What is asthma?"),
    ("type2_diabetes", "A person with type 2 diabetes has advanced kidney impairment, repeated low glucose "
     "episodes and several medications. Weigh the interacting risks and justify a management approach."),
    ("pneumonia", "What is the latest official Canadian recommendation for pneumococcal vaccination? "
     "Include the update date and an authoritative source."),
]


def main():
    router, rag = SemanticRouter(), MedicalHybridRetriever()
    rows = []
    for topic, question in QUESTIONS:
        for method in router.cfg.enabled_methods:
            start = perf_counter()
            x = RouteInput(
                sanitized_question=question, topic=topic, pii=PIIResult(sanitized_text=question),
                passage_count=0, method=method,
            )
            analysis = router.analyze(x)
            if router.capable(analysis, router.cfg.threshold):
                x.passages = rag.retrieve(question, topic, 4)
                x.passage_count = len(x.passages)
                x.retrieval_status = "returned" if x.passages else "empty"
            else:
                x.retrieval_status = "skipped"
            score = router.decide(x, analysis, router.cfg.threshold)
            rows.append({
                "topic": topic, "question": question, "method": method, "target": score.target,
                "cloud_probability": analysis.cloud_probability,
                "requires_evidence": analysis.requires_evidence,
                "requires_fresh_evidence": analysis.requires_fresh_evidence,
                "retrieved": len(x.passages), "evidence": score.evidence.model_dump(),
                "elapsed_ms": round((perf_counter() - start) * 1000),
            })
            print(topic, method, score.target, score.evidence.status, flush=True)
    path = Path(__file__).resolve().parent / "results/semantic_rag_smoke.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({
        "note": "Actual local encoder, 500-question weights, medical_hybrid and cross-encoders. "
                "No answer generation or clinical correctness evaluation.",
        "rows": rows,
    }, indent=2) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
