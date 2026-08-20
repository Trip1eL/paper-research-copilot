import json
from pathlib import Path

import pytest

from paper_research_copilot.agent import (
    AgentAcquisitionSummary,
    AgentEvent,
    AgentResult,
    EvidenceAssessment,
    ResearchPlan,
    ResearchTask,
)
from paper_research_copilot.domain import Answer, Citation, PaperChunk, RetrievedChunk
from paper_research_copilot.evaluation import (
    OpenWorldEvaluationCase,
    build_open_world_config,
    build_open_world_report,
    evaluate_open_world_case,
    load_open_world_cases,
)


def _case(category: str) -> OpenWorldEvaluationCase:
    values = {
        "in_corpus": {
            "case_id": "OW-IC-001",
            "acquisition_expectation": "forbidden",
            "expected_answer_status": "answered",
            "expected_curated_paper_ids": ("arxiv:2210.03629",),
        },
        "recoverable": {
            "case_id": "OW-RC-001",
            "acquisition_expectation": "required",
            "expected_answer_status": "answered",
            "target_arxiv_ids": ("2605.06132",),
        },
        "unrecoverable": {
            "case_id": "OW-UR-001",
            "acquisition_expectation": "optional",
            "expected_answer_status": "insufficient_evidence",
        },
        "ambiguous": {
            "case_id": "OW-AM-001",
            "acquisition_expectation": "forbidden",
            "expected_answer_status": "insufficient_evidence",
        },
    }[category]
    return OpenWorldEvaluationCase(
        category=category,  # type: ignore[arg-type]
        question=f"A sufficiently detailed {category} research question?",
        rationale="Human-reviewed test rationale.",
        **values,  # type: ignore[arg-type]
    )


def _evidence(*, dynamic: bool, arxiv_id: str, paper_id: str) -> RetrievedChunk:
    text = "Grounded evidence for the requested research question."
    chunk = PaperChunk(
        chunk_id=f"chunk-{arxiv_id}",
        document_sha256="a" * 64,
        chunk_index=0,
        chunking_version="chunking_v1",
        corpus_id="paper-dynamic" if dynamic else "agent-seed-v3",
        corpus_version=1 if dynamic else 3,
        paper_id=paper_id,
        arxiv_id=arxiv_id,
        arxiv_version="v1",
        title="Target Paper",
        source_path="target.pdf",
        page_number=1,
        parser_version="6.10.2",
        char_start=0,
        char_end=len(text),
        text=text,
    )
    return RetrievedChunk(citation_id="C1", score=1, chunk=chunk)


def _result(
    case: OpenWorldEvaluationCase,
    *,
    evidence: RetrievedChunk | None,
    acquisition: bool,
) -> AgentResult:
    answered = case.expected_answer_status == "answered"
    citations = ()
    if answered and evidence is not None:
        chunk = evidence.chunk
        citations = (
            Citation(
                citation_id="C1",
                chunk_id=chunk.chunk_id,
                paper_id=chunk.paper_id,
                title=chunk.title,
                source_path=chunk.source_path,
                page_number=chunk.page_number,
                excerpt=chunk.text,
                retrieval_score=evidence.score,
            ),
        )
    trace = [
        AgentEvent(
            sequence=1,
            node="plan_research",
            outcome="planned",
            latency_ms=10,
            details={"planner_input_tokens": 10, "planner_output_tokens": 5},
        )
    ]
    if acquisition:
        trace.append(
            AgentEvent(
                sequence=2,
                node="acquire_evidence",
                outcome="succeeded",
                latency_ms=100,
            )
        )
    trace.append(
        AgentEvent(
            sequence=len(trace) + 1,
            node="validate_citations",
            outcome="valid",
            latency_ms=1,
        )
    )
    return AgentResult(
        question=case.question,
        plan=ResearchPlan(
            question=case.question,
            question_type="single_paper",
            rationale="Find evidence for the requested method",
            tasks=(
                ResearchTask(
                    task_id="T1",
                    query="requested method evidence",
                    goal="Find grounded method evidence",
                ),
            ),
        ),
        evidence=(evidence,) if evidence else (),
        assessment=EvidenceAssessment(
            sufficient=answered,
            reason="Evidence state matches expected behavior",
            task_candidate_counts={"T1": 1 if evidence else 0},
            task_selected_counts={"T1": 1 if evidence else 0},
            distinct_paper_count=1 if evidence else 0,
            retry_recommended=False,
        ),
        answer=Answer(
            question=case.question,
            text="Grounded answer [C1]." if answered else "INSUFFICIENT_EVIDENCE",
            citations=citations,
            status=case.expected_answer_status,
        ),
        retry_count=0,
        acquisition_rounds=int(acquisition),
        acquisition=(
            AgentAcquisitionSummary(
                query="target method",
                acquisition_id="acquisition-1",
                status="succeeded",
                downloaded_count=1,
                indexed_count=1,
            )
            if acquisition
            else None
        ),
        trace=tuple(trace),
    )


def test_versioned_open_world_dataset_has_four_balanced_categories() -> None:
    dataset = Path(__file__).parents[2] / "evals" / "datasets" / "open_world_v1.jsonl"
    cases = load_open_world_cases(dataset)

    assert len(cases) == 16
    assert sum(case.category == "in_corpus" for case in cases) == 5
    assert sum(case.category == "recoverable" for case in cases) == 5
    assert sum(case.category == "unrecoverable" for case in cases) == 3
    assert sum(case.category == "ambiguous" for case in cases) == 3
    assert len({target for case in cases for target in case.target_arxiv_ids}) == 5


def test_dataset_rejects_duplicate_questions(tmp_path: Path) -> None:
    record = _case("unrecoverable").model_dump(mode="json")
    duplicate = {**record, "case_id": "OW-UR-002"}
    path = tmp_path / "duplicate.jsonl"
    path.write_text(
        json.dumps(record) + "\n" + json.dumps(duplicate) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate questions"):
        load_open_world_cases(path)


def test_four_category_success_builds_expected_open_world_metrics(tmp_path: Path) -> None:
    cases = tuple(_case(category) for category in (
        "in_corpus",
        "recoverable",
        "unrecoverable",
        "ambiguous",
    ))
    curated = _evidence(
        dynamic=False,
        arxiv_id="2210.03629",
        paper_id="arxiv:2210.03629",
    )
    dynamic = _evidence(
        dynamic=True,
        arxiv_id="2605.06132",
        paper_id="dynamic-paper-id",
    )
    agent_results = (
        _result(cases[0], evidence=curated, acquisition=False),
        _result(cases[1], evidence=dynamic, acquisition=True),
        _result(cases[2], evidence=None, acquisition=True),
        _result(cases[3], evidence=None, acquisition=False),
    )
    results = tuple(
        evaluate_open_world_case(
            case,
            result,
            elapsed_ms=1000 + index,
            points_before=0,
            points_after=1 if index == 1 else 0,
        )
        for index, (case, result) in enumerate(zip(cases, agent_results, strict=True))
    )
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("{}\n", encoding="utf-8")
    config = build_open_world_config(
        baseline_id="open_world_test",
        dataset_path=dataset,
        cases=cases,
        corpus_version=3,
        curated_collection="curated",
        planner_model="planner",
        answer_model="answer",
        max_retries=1,
        max_acquisition_rounds=1,
        project_root=tmp_path,
    )
    report = build_open_world_report(results, config)

    assert all(result.strict_pass for result in results)
    assert report.summary.strict_pass_rate == 1
    assert report.summary.acquisition_trigger_precision == 0.5
    assert report.summary.acquisition_trigger_recall == 1
    assert report.summary.in_corpus_false_trigger_rate == 0
    assert report.summary.recoverable_success_rate == 1
    assert report.summary.unrecoverable_abstention_rate == 1
    assert report.summary.unrecoverable_no_index_rate == 1
    assert report.summary.ambiguous_abstention_rate == 1
    assert report.summary.dynamic_evidence_hit_rate == 1
    assert report.summary.target_citation_hit_rate == 1
    assert report.summary.total_downloaded == 2
    assert report.summary.total_indexed == 2


def test_in_corpus_acquisition_is_a_strict_failure() -> None:
    case = _case("in_corpus")
    result = _result(
        case,
        evidence=_evidence(
            dynamic=False,
            arxiv_id="2210.03629",
            paper_id="arxiv:2210.03629",
        ),
        acquisition=True,
    )

    evaluated = evaluate_open_world_case(
        case,
        result,
        elapsed_ms=10,
        points_before=0,
        points_after=1,
    )

    assert evaluated.acquisition_triggered
    assert not evaluated.acquisition_correct
    assert not evaluated.strict_pass


def test_unrecoverable_case_rejects_but_fails_when_irrelevant_paper_is_indexed() -> None:
    case = _case("unrecoverable")
    result = _result(case, evidence=None, acquisition=True)

    evaluated = evaluate_open_world_case(
        case,
        result,
        elapsed_ms=10,
        points_before=0,
        points_after=20,
    )

    assert evaluated.answer_behavior_correct
    assert evaluated.answer_status == "insufficient_evidence"
    assert not evaluated.strict_pass


def test_open_world_evaluation_reports_revision_repair_and_fallback() -> None:
    case = _case("unrecoverable")
    result = _result(case, evidence=None, acquisition=True)
    revision = AgentEvent(
        sequence=2,
        node="revise_queries",
        outcome="revised",
        latency_ms=20,
        details={
            "planner_attempts": 3,
            "planner_repair_attempts": 2,
            "planner_fallback_used": True,
        },
    )
    result = result.model_copy(
        update={
            "retry_count": 1,
            "trace": (result.trace[0], revision, *result.trace[1:]),
        }
    )

    evaluated = evaluate_open_world_case(
        case,
        result,
        elapsed_ms=10,
        points_before=0,
        points_after=0,
    )

    assert evaluated.revision_triggered
    assert evaluated.planner_revision_attempts == 3
    assert evaluated.planner_repair_attempts == 2
    assert evaluated.planner_fallback_used
