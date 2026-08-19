import json
from pathlib import Path

import pytest

from paper_research_copilot.evaluation import load_retrieval_diagnostics


def _write_case(
    path: Path,
    case_id: str,
    paper_id: str,
    *,
    question: str = "这个方法如何工作？",
    subset: str = "known_paper",
    contains_paper_name: bool = True,
) -> None:
    record = {
        "case_id": case_id,
        "question": question,
        "question_type": "method",
        "difficulty": "easy",
        "subset": subset,
        "contains_paper_name": contains_paper_name,
        "relevant": [{"paper_id": paper_id, "pages": [1]}],
        "evidence_hint": "方法描述所在页面。",
        "tags": ["method"],
    }
    path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")


def test_load_retrieval_diagnostics_validates_paper_ids(tmp_path: Path) -> None:
    dataset = tmp_path / "diagnostics.jsonl"
    _write_case(dataset, "RD-001", "arxiv:0000.00000")

    cases = load_retrieval_diagnostics(
        dataset,
        allowed_paper_ids={"arxiv:0000.00000"},
    )

    assert len(cases) == 1
    assert cases[0].relevant[0].pages == (1,)


def test_load_retrieval_diagnostics_rejects_unknown_paper(tmp_path: Path) -> None:
    dataset = tmp_path / "diagnostics.jsonl"
    _write_case(dataset, "RD-001", "arxiv:unknown")

    with pytest.raises(ValueError, match="unknown paper IDs"):
        load_retrieval_diagnostics(dataset, allowed_paper_ids={"arxiv:0000.00000"})


def test_load_retrieval_diagnostics_rejects_out_of_range_page(tmp_path: Path) -> None:
    dataset = tmp_path / "diagnostics.jsonl"
    _write_case(dataset, "RD-001", "arxiv:0000.00000")

    record = json.loads(dataset.read_text(encoding="utf-8"))
    record["relevant"][0]["pages"] = [2]
    dataset.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="out-of-range pages"):
        load_retrieval_diagnostics(
            dataset,
            allowed_paper_ids={"arxiv:0000.00000"},
            paper_page_counts={"arxiv:0000.00000": 1},
        )


def test_load_discovery_dataset_without_target_name(tmp_path: Path) -> None:
    dataset = tmp_path / "discovery.jsonl"
    _write_case(
        dataset,
        "DS-001",
        "arxiv:0000.00000",
        question="哪种方法会交错生成推理、行动和环境观察？",
        subset="discovery",
        contains_paper_name=False,
    )

    cases = load_retrieval_diagnostics(
        dataset,
        paper_aliases={"arxiv:0000.00000": ("example-method", "Example Method")},
    )

    assert cases[0].subset == "discovery"
    assert not cases[0].contains_paper_name


def test_load_discovery_dataset_rejects_target_name_leakage(tmp_path: Path) -> None:
    dataset = tmp_path / "discovery.jsonl"
    _write_case(
        dataset,
        "DS-001",
        "arxiv:0000.00000",
        question="Example Method 如何交错生成推理和行动？",
        subset="discovery",
        contains_paper_name=False,
    )

    with pytest.raises(ValueError, match="target paper names"):
        load_retrieval_diagnostics(
            dataset,
            paper_aliases={"arxiv:0000.00000": ("example-method", "Example Method")},
        )


def test_versioned_discovery_dataset_has_no_title_leakage() -> None:
    project_root = Path(__file__).parents[2]
    corpus = json.loads((project_root / "corpus" / "v1" / "corpus.json").read_text("utf-8"))
    papers = corpus["papers"]
    cases = load_retrieval_diagnostics(
        project_root / "evals" / "datasets" / "retrieval_discovery_v1.jsonl",
        allowed_paper_ids={paper["paper_id"] for paper in papers},
        paper_aliases={
            paper["paper_id"]: (
                paper["slug"],
                paper["title"],
                paper["title"].partition(":")[0],
            )
            for paper in papers
        },
    )

    assert len(cases) == 25
    assert all(case.subset == "discovery" for case in cases)
    assert sum(case.question_type == "cross_paper" for case in cases) == 5
    assert sum(case.hard_negative for case in cases) == 5


def test_v2_discovery_dataset_is_harder_and_preserves_v1_anchors() -> None:
    project_root = Path(__file__).parents[2]
    corpus = json.loads((project_root / "corpus" / "v2" / "corpus.json").read_text("utf-8"))
    manifest = [
        json.loads(line)
        for line in (project_root / "corpus" / "v2" / "manifest.jsonl")
        .read_text("utf-8")
        .splitlines()
        if line.strip()
    ]
    papers = corpus["papers"]
    aliases = {
        paper["paper_id"]: (
            paper["slug"],
            paper["title"],
            paper["title"].partition(":")[0],
        )
        for paper in papers
    }
    v1_cases = load_retrieval_diagnostics(
        project_root / "evals" / "datasets" / "retrieval_discovery_v1.jsonl"
    )
    v2_cases = load_retrieval_diagnostics(
        project_root / "evals" / "datasets" / "retrieval_discovery_v2.jsonl",
        allowed_paper_ids={paper["paper_id"] for paper in papers},
        paper_page_counts={record["paper_id"]: record["page_count"] for record in manifest},
        paper_aliases=aliases,
    )

    assert len(v2_cases) == 50
    assert sum(case.question_type == "cross_paper" for case in v2_cases) == 15
    assert sum(case.hard_negative for case in v2_cases) == 30
    assert all(case.hard_negative for case in v2_cases[25:])
    assert {item.paper_id for case in v2_cases for item in case.relevant} == {
        paper["paper_id"] for paper in papers
    }
    assert [case.question for case in v2_cases[:25]] == [case.question for case in v1_cases]
    assert [case.relevant for case in v2_cases[:25]] == [case.relevant for case in v1_cases]


def test_v3_discovery_dataset_covers_expanded_corpus_and_preserves_v2() -> None:
    project_root = Path(__file__).parents[2]
    v2_corpus = json.loads((project_root / "corpus" / "v2" / "corpus.json").read_text("utf-8"))
    v3_corpus = json.loads((project_root / "corpus" / "v3" / "corpus.json").read_text("utf-8"))
    manifest = [
        json.loads(line)
        for line in (project_root / "corpus" / "v3" / "manifest.jsonl")
        .read_text("utf-8")
        .splitlines()
        if line.strip()
    ]
    papers = v3_corpus["papers"]
    v2_cases = load_retrieval_diagnostics(
        project_root / "evals" / "datasets" / "retrieval_discovery_v2.jsonl"
    )
    v3_cases = load_retrieval_diagnostics(
        project_root / "evals" / "datasets" / "retrieval_discovery_v3.jsonl",
        allowed_paper_ids={paper["paper_id"] for paper in papers},
        paper_page_counts={record["paper_id"]: record["page_count"] for record in manifest},
        paper_aliases={
            paper["paper_id"]: (
                paper["slug"],
                paper["title"],
                paper["title"].partition(":")[0],
            )
            for paper in papers
        },
    )

    new_paper_ids = {paper["paper_id"] for paper in papers} - {
        paper["paper_id"] for paper in v2_corpus["papers"]
    }
    new_case_paper_ids = {item.paper_id for case in v3_cases[50:] for item in case.relevant}
    assert len(v3_cases) == 100
    assert sum(case.question_type == "cross_paper" for case in v3_cases) == 35
    assert sum(case.hard_negative for case in v3_cases) == 80
    assert all(case.hard_negative for case in v3_cases[50:])
    assert new_paper_ids <= new_case_paper_ids
    assert {item.paper_id for case in v3_cases for item in case.relevant} == {
        paper["paper_id"] for paper in papers
    }
    assert [case.question for case in v3_cases[:50]] == [case.question for case in v2_cases]
    assert [case.relevant for case in v3_cases[:50]] == [case.relevant for case in v2_cases]
