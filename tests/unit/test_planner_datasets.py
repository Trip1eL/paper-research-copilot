import json
from collections import Counter
from pathlib import Path

import pytest

from paper_research_copilot.evaluation import load_planner_routing_cases


def _source_questions(project_root: Path) -> dict[str, str]:
    paths = (
        project_root / "evals" / "datasets" / "retrieval_discovery_v2.jsonl",
        project_root / "evals" / "datasets" / "answer_generation_v1.jsonl",
    )
    return {
        record["case_id"]: record["question"]
        for path in paths
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for record in (json.loads(line),)
    }


def test_planner_routing_v2_has_balanced_versioned_contract() -> None:
    project_root = Path(__file__).parents[2]
    cases = load_planner_routing_cases(
        project_root / "evals" / "datasets" / "planner_routing_v2.jsonl",
        source_questions=_source_questions(project_root),
    )

    assert len(cases) == 40
    assert Counter(case.category for case in cases) == {
        "single_lookup": 16,
        "cross_comparison": 13,
        "multi_method_synthesis": 2,
        "corpus_verification": 5,
        "routing_boundary": 4,
    }
    assert Counter(case.expected_question_type for case in cases) == {
        "single_paper": 18,
        "cross_paper": 22,
    }
    assert sum(case.label_sensitive for case in cases) == 3
    assert sum(case.source_case_id is not None for case in cases) == 34
    assert {len(case.expected_facets) for case in cases} == {1, 2, 3, 4}
    pr_032 = next(case for case in cases if case.case_id == "PR-032")
    assert "结果 表格" in pr_032.expected_facets[1].match_any


def test_planner_routing_loader_rejects_changed_source_question(tmp_path: Path) -> None:
    dataset = tmp_path / "planner.jsonl"
    record = {
        "case_id": "PR-001",
        "source_case_id": "DS-001",
        "category": "single_lookup",
        "difficulty": "medium",
        "question": "A changed source question?",
        "expected_question_type": "single_paper",
        "acceptable_question_types": ["single_paper"],
        "expected_task_count": 1,
        "acceptable_task_counts": [1],
        "expected_facets": [{"facet_id": "F1", "description": "One facet", "match_any": ["facet"]}],
        "label_sensitive": False,
        "annotation_notes": "This should fail source validation.",
    }
    dataset.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="changed source questions"):
        load_planner_routing_cases(
            dataset,
            source_questions={"DS-001": "The original source question?"},
        )
