from pathlib import Path

from paper_research_copilot.agent import (
    AgentEvent,
    AgentResult,
    EvidenceAssessment,
    ResearchPlan,
    ResearchTask,
)
from paper_research_copilot.domain import Answer
from paper_research_copilot.evaluation import (
    AgentEvaluationCase,
    ExpectedTaskFacet,
    build_agent_execution_metrics,
    load_agent_evaluation_cases,
    load_answer_evaluation_cases,
)


def test_versioned_agent_dataset_matches_answer_cases() -> None:
    project_root = Path(__file__).parents[2]
    answer_cases = load_answer_evaluation_cases(
        project_root / "evals" / "datasets" / "answer_generation_v1.jsonl"
    )
    cases = load_agent_evaluation_cases(
        project_root / "evals" / "datasets" / "agent_runtime_v1.jsonl",
        answer_cases={case.case_id: case for case in answer_cases},
    )

    assert [case.case_id for case in cases] == [
        "AE-001",
        "AE-007",
        "AE-014",
        "AE-016",
        "AE-017",
        "AE-018",
        "AE-019",
        "AE-020",
    ]
    assert sum(case.expected_question_type == "cross_paper" for case in cases) == 5
    assert sum(not case.answerable for case in cases) == 2
    assert all(not case.should_retry for case in cases)


def test_v2_agent_dataset_matches_expanded_answer_cases() -> None:
    project_root = Path(__file__).parents[2]
    answer_cases = load_answer_evaluation_cases(
        project_root / "evals" / "datasets" / "answer_generation_v2.jsonl"
    )
    cases = load_agent_evaluation_cases(
        project_root / "evals" / "datasets" / "agent_runtime_v2.jsonl",
        answer_cases={case.case_id: case for case in answer_cases},
    )

    assert [case.case_id for case in cases] == [
        "AE-001",
        "AE-007",
        "AE-016",
        "AE-017",
        "AE-019",
        "AE-020",
        "AE-021",
        "AE-023",
        "AE-025",
        "AE-029",
        "AE-031",
        "AE-032",
    ]
    assert sum(case.expected_question_type == "cross_paper" for case in cases) == 7
    assert sum(case.answerable for case in cases) == 11
    assert sum(not case.answerable for case in cases) == 1
    assert all(not case.should_retry for case in cases)


def test_agent_execution_metrics_restore_cold_planning_latency_and_detect_leakage() -> None:
    question = "How do the first mechanism and loss-filtered API calls differ?"
    case = AgentEvaluationCase(
        case_id="AE-999",
        question=question,
        expected_question_type="cross_paper",
        expected_task_count=2,
        expected_retrieval_strategy="coverage_hybrid_rrf",
        expected_facets=(
            ExpectedTaskFacet(
                facet_id="F1",
                description="first mechanism",
                match_any=("first mechanism",),
            ),
            ExpectedTaskFacet(
                facet_id="F2",
                description="loss-filtered API calls",
                match_any=("loss-filtered api calls",),
            ),
        ),
        answerable=False,
    )
    plan = ResearchPlan(
        question=question,
        question_type="cross_paper",
        rationale="Retrieve both mechanisms independently",
        tasks=(
            ResearchTask(
                task_id="T1",
                query="First mechanism from Secret Paper",
                goal="Find first mechanism evidence",
            ),
            ResearchTask(
                task_id="T2",
                query="Loss-filtered API calls",
                goal="Find API training evidence",
            ),
        ),
    )
    result = AgentResult(
        question=question,
        plan=plan,
        evidence=(),
        assessment=EvidenceAssessment(
            sufficient=False,
            reason="No relevant evidence found",
            task_candidate_counts={"T1": 0, "T2": 0},
            task_selected_counts={"T1": 0, "T2": 0},
            missing_task_ids=("T1", "T2"),
            distinct_paper_count=0,
            retry_recommended=False,
        ),
        answer=Answer(
            question=question,
            text="INSUFFICIENT_EVIDENCE",
            citations=(),
            status="insufficient_evidence",
        ),
        retry_count=0,
        trace=(
            AgentEvent(
                sequence=1,
                node="plan_research",
                outcome="planned",
                latency_ms=1,
                details={
                    "generation_latency_ms": 1200,
                    "planner_input_tokens": 100,
                    "planner_output_tokens": 50,
                },
            ),
            AgentEvent(
                sequence=2,
                node="retrieve_evidence",
                outcome="retrieved",
                latency_ms=300,
                details={"strategy": "coverage_hybrid_rrf"},
            ),
            AgentEvent(
                sequence=3,
                node="write_report",
                outcome="insufficient_evidence",
                latency_ms=2,
                details={"source": "evidence_gate", "citation_count": 0},
            ),
            AgentEvent(
                sequence=4,
                node="validate_citations",
                outcome="valid",
                latency_ms=1,
            ),
        ),
    )

    metrics = build_agent_execution_metrics(
        case,
        result,
        corpus_aliases=("Secret Paper",),
    )

    assert metrics.router_correct
    assert metrics.task_count_correct
    assert metrics.task_coverage == 1
    assert metrics.retrieval_strategy_correct
    assert metrics.title_leaks == ("T1:Secret Paper:First mechanism from Secret Paper",)
    assert metrics.planning_latency_ms == 1200
    assert metrics.workflow_latency_ms == 1502
    assert metrics.planner_input_tokens == 100
    assert metrics.planner_output_tokens == 50
    assert metrics.model_call_count == 1
