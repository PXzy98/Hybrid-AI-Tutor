"""Run two-course, independently labelled RAG evaluation (no query text in output)."""
import argparse
import json
from pathlib import Path

from app.rag.course_retriever import CourseRetriever
from app.rag.evaluation import evaluate_two_course_rag, load_labels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-root", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_two_course_rag(
        retriever=CourseRetriever(args.index_root), index_root=args.index_root,
        labels=load_labels(args.labels), k=args.k,
    )
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
