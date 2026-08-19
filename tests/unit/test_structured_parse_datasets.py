from pathlib import Path

import pytest

from paper_research_copilot.evaluation import load_structured_parse_benchmark

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET = PROJECT_ROOT / "evals" / "datasets" / "structured_parse_benchmark_v1.jsonl"


def test_structured_parse_benchmark_loads_frozen_sources() -> None:
    cases = load_structured_parse_benchmark(DATASET, project_root=PROJECT_ROOT)

    assert len(cases) == 11
    assert cases[-1].synthetic is True
    assert cases[-1].category == "scanned_table"
    assert len(cases[-1].table_questions) == 3


def test_structured_parse_benchmark_rejects_missing_categories(tmp_path: Path) -> None:
    dataset = tmp_path / "incomplete.jsonl"
    dataset.write_text(DATASET.read_text(encoding="utf-8").splitlines()[0], encoding="utf-8")

    with pytest.raises(ValueError, match="missing categories"):
        load_structured_parse_benchmark(dataset, project_root=PROJECT_ROOT)
