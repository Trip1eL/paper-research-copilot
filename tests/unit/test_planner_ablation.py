from paper_research_copilot.agent import PlanningResult, ResearchPlan, ResearchTask
from paper_research_copilot.evaluation import (
    AgentEvaluationCase,
    ExpectedTaskFacet,
    build_planner_ablation_config,
    build_planner_ablation_report,
    build_planner_case_result,
)
from paper_research_copilot.integrations import ChatTokenUsage


def _case() -> AgentEvaluationCase:
    return AgentEvaluationCase(
        case_id="AE-999",
        question="How do mechanism A and mechanism B differ?",
        expected_question_type="cross_paper",
        expected_task_count=2,
        expected_retrieval_strategy="coverage_hybrid_rrf",
        expected_facets=(
            ExpectedTaskFacet(
                facet_id="F1",
                description="mechanism A",
                match_any=("mechanism a",),
            ),
            ExpectedTaskFacet(
                facet_id="F2",
                description="mechanism B",
                match_any=("mechanism b",),
            ),
        ),
        answerable=False,
    )


def _planning(model: str, latency_ms: float) -> PlanningResult:
    question = _case().question
    return PlanningResult(
        plan=ResearchPlan(
            question=question,
            question_type="cross_paper",
            rationale="Retrieve both mechanisms independently",
            tasks=(
                ResearchTask(
                    task_id="T1",
                    query="mechanism A evidence",
                    goal="Find mechanism A details",
                ),
                ResearchTask(
                    task_id="T2",
                    query="mechanism B evidence",
                    goal="Find mechanism B details",
                ),
            ),
        ),
        operation="initial",
        model=model,
        prompt_version="research_planner_v1",
        cache_hit=False,
        latency_ms=latency_ms,
        generation_latency_ms=latency_ms,
        attempts=1,
        usage=ChatTokenUsage(input_tokens=100, output_tokens=50, total_tokens=150),
    )


def test_planner_ablation_recommends_fastest_model_that_passes_gate(tmp_path) -> None:
    case = _case()
    results = (
        build_planner_case_result(
            variant_id="slow",
            model="slow-model",
            case=case,
            corpus_aliases=(),
            planning=_planning("slow-model", 1000),
        ),
        build_planner_case_result(
            variant_id="fast",
            model="fast-model",
            case=case,
            corpus_aliases=(),
            planning=_planning("fast-model", 100),
        ),
    )
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("{}\n", encoding="utf-8")
    config = build_planner_ablation_config(
        baseline_id="test",
        dataset_path=dataset,
        case_ids=(case.case_id,),
        prompt_version="research_planner_v1",
        retry_attempts=3,
        candidate_models=("slow-model", "fast-model"),
        project_root=tmp_path,
    )

    report = build_planner_ablation_report(results, config)

    assert all(variant.quality_gate_passed for variant in report.variants)
    assert report.recommended_model == "fast-model"
    assert report.variants[1].known_input_tokens == 100


def test_planner_failure_counts_against_every_quality_metric(tmp_path) -> None:
    case = _case()
    result = build_planner_case_result(
        variant_id="broken",
        model="broken-model",
        case=case,
        corpus_aliases=(),
        planning=None,
        error="invalid JSON",
        failure_latency_ms=500,
        failure_attempts=3,
    )
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("{}\n", encoding="utf-8")
    config = build_planner_ablation_config(
        baseline_id="test",
        dataset_path=dataset,
        case_ids=(case.case_id,),
        prompt_version="research_planner_v1",
        retry_attempts=3,
        candidate_models=("broken-model",),
        project_root=tmp_path,
    )

    report = build_planner_ablation_report((result,), config)

    summary = report.variants[0]
    assert summary.planning_success_rate == 0
    assert summary.router_accuracy == 0
    assert summary.task_count_accuracy == 0
    assert summary.task_coverage == 0
    assert summary.schema_retry_rate == 1
    assert not summary.quality_gate_passed
    assert report.recommended_model is None
