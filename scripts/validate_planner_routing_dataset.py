"""Validate Planner routing labels against their versioned source questions."""

import argparse
import json
from collections import Counter
from pathlib import Path

from paper_research_copilot.config import PROJECT_ROOT
from paper_research_copilot.evaluation import load_planner_routing_cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "planner_routing_v2.jsonl",
    )
    parser.add_argument(
        "--retrieval-source",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "retrieval_discovery_v2.jsonl",
    )
    parser.add_argument(
        "--answer-source",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "answer_generation_v1.jsonl",
    )
    args = parser.parse_args()

    source_questions: dict[str, str] = {}
    for path in (args.retrieval_source, args.answer_source):
        for record in _load_jsonl(path):
            case_id = record.get("case_id")
            question = record.get("question")
            if not isinstance(case_id, str) or not isinstance(question, str):
                raise ValueError(f"Source dataset has an invalid Case ID or question: {path}")
            source_questions[case_id] = question
    cases = load_planner_routing_cases(args.dataset, source_questions=source_questions)
    categories = Counter(case.category for case in cases)
    routes = Counter(case.expected_question_type for case in cases)
    print(f"Dataset: {args.dataset}")
    print(f"Cases: {len(cases)}")
    print(f"Categories: {dict(sorted(categories.items()))}")
    print(f"Strict routes: {dict(sorted(routes.items()))}")
    print(f"Label-sensitive: {sum(case.label_sensitive for case in cases)}")
    print(f"Versioned source anchors: {sum(case.source_case_id is not None for case in cases)}")
    return 0


def _load_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    return tuple(
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )


if __name__ == "__main__":
    raise SystemExit(main())
