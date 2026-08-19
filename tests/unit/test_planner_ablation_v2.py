import pytest

from paper_research_copilot.agent import PlanningResult, ResearchPlan, ResearchTask
from paper_research_copilot.evaluation import (
    PlannerExpectedFacet,
    PlannerRoutingCase,
    build_planner_ablation_v2_config,
    build_planner_ablation_v2_report,
    build_planner_v2_case_result,
)
from paper_research_copilot.integrations import ChatTokenUsage


def _case(*, case_id: str, label_sensitive: bool = False) -> PlannerRoutingCase:
    return PlannerRoutingCase(
        case_id=case_id,
        category="routing_boundary" if label_sensitive else "cross_comparison",
        difficulty="hard",
        question=f"Compare mechanism A and mechanism B for {case_id}.",
        expected_question_type="cross_paper",
        acceptable_question_types=("cross_paper", "single_paper")
        if label_sensitive
        else ("cross_paper",),
        expected_task_count=2,
        acceptable_task_counts=(2, 1) if label_sensitive else (2,),
        expected_facets=(
            PlannerExpectedFacet(
                facet_id="F1", description="mechanism A", match_any=("mechanism a",)
            ),
            PlannerExpectedFacet(
                facet_id="F2", description="mechanism B", match_any=("mechanism b",)
            ),
        ),
        label_sensitive=label_sensitive,
        annotation_notes="Test annotation notes.",
    )


def _planning(
    case: PlannerRoutingCase,
    *,
    model: str,
    latency_ms: float,
    boundary_alternative: bool = False,
) -> PlanningResult:
    if boundary_alternative:
        question_type = "single_paper"
        tasks = (
            ResearchTask(
                task_id="T1",
                query="mechanism A and mechanism B",
                goal="Compare mechanism A with mechanism B",
            ),
        )
    else:
        question_type = "cross_paper"
        tasks = (
            ResearchTask(task_id="T1", query="mechanism A", goal="Find mechanism A"),
            ResearchTask(task_id="T2", query="mechanism B", goal="Find mechanism B"),
        )
    return PlanningResult(
        plan=ResearchPlan(
            question=case.question,
            question_type=question_type,
            rationale="Retrieve the required facets.",
            tasks=tasks,
        ),
        operation="initial",
        model=model,
        prompt_version="research_planner_v1",
        cache_hit=False,
        latency_ms=latency_ms,
        generation_latency_ms=latency_ms,
        attempts=1,
        usage=ChatTokenUsage(input_tokens=100, output_tokens=40, total_tokens=140),
    )


def _config(tmp_path, cases, models=("model-a",)):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("{}\n", encoding="utf-8")
    return build_planner_ablation_v2_config(
        baseline_id="test",
        dataset_path=dataset,
        cases=cases,
        prompt_version="research_planner_v1",
        retry_attempts=3,
        candidate_models=models,
        project_root=tmp_path,
    )


def test_label_sensitive_alternative_is_acceptable_and_excluded_from_core(tmp_path) -> None:
    core = _case(case_id="PR-998")
    boundary = _case(case_id="PR-999", label_sensitive=True)
    results = (
        build_planner_v2_case_result(
            variant_id="a",
            model="model-a",
            case=core,
            corpus_aliases=(),
            planning=_planning(core, model="model-a", latency_ms=200),
        ),
        build_planner_v2_case_result(
            variant_id="a",
            model="model-a",
            case=boundary,
            corpus_aliases=(),
            planning=_planning(
                boundary,
                model="model-a",
                latency_ms=100,
                boundary_alternative=True,
            ),
        ),
    )

    report = build_planner_ablation_v2_report(results, _config(tmp_path, (core, boundary)))

    summary = report.variants[0]
    assert summary.strict_router_accuracy == 0.5
    assert summary.acceptable_router_accuracy == 1
    assert summary.core_router_accuracy == 1
    assert summary.boundary_strict_router_accuracy == 0
    assert summary.boundary_acceptable_router_accuracy == 1
    assert summary.quality_gate_passed


def test_core_error_fails_gate_and_category_is_grouped(tmp_path) -> None:
    core = _case(case_id="PR-997")
    result = build_planner_v2_case_result(
        variant_id="a",
        model="model-a",
        case=core,
        corpus_aliases=(),
        planning=_planning(core, model="model-a", latency_ms=100, boundary_alternative=True),
    )

    summary = build_planner_ablation_v2_report((result,), _config(tmp_path, (core,))).variants[0]

    assert not summary.quality_gate_passed
    assert summary.core_router_accuracy == 0
    assert summary.categories[0].category == "cross_comparison"
    assert summary.categories[0].case_count == 1


def test_recommends_fastest_complete_gate_passing_variant(tmp_path) -> None:
    case = _case(case_id="PR-996")
    results = tuple(
        build_planner_v2_case_result(
            variant_id=variant,
            model=model,
            case=case,
            corpus_aliases=(),
            planning=_planning(case, model=model, latency_ms=latency),
        )
        for variant, model, latency in (
            ("slow", "slow-model", 500),
            ("fast", "fast-model", 100),
        )
    )

    report = build_planner_ablation_v2_report(
        results,
        _config(tmp_path, (case,), models=("slow-model", "fast-model")),
    )

    assert report.recommended_model == "fast-model"


def test_rejects_incomplete_variant(tmp_path) -> None:
    first = _case(case_id="PR-994")
    second = _case(case_id="PR-995")
    result = build_planner_v2_case_result(
        variant_id="a",
        model="model-a",
        case=first,
        corpus_aliases=(),
        planning=_planning(first, model="model-a", latency_ms=100),
    )

    with pytest.raises(ValueError, match="incomplete Cases"):
        build_planner_ablation_v2_report((result,), _config(tmp_path, (first, second)))


def test_boundary_only_subset_can_be_reported(tmp_path) -> None:
    boundary = _case(case_id="PR-993", label_sensitive=True)
    result = build_planner_v2_case_result(
        variant_id="a",
        model="model-a",
        case=boundary,
        corpus_aliases=(),
        planning=_planning(
            boundary,
            model="model-a",
            latency_ms=100,
            boundary_alternative=True,
        ),
    )

    summary = build_planner_ablation_v2_report((result,), _config(tmp_path, (boundary,))).variants[
        0
    ]

    assert summary.core_case_count == 0
    assert summary.label_sensitive_case_count == 1


def test_acceptable_boundary_route_still_requires_full_facet_coverage(tmp_path) -> None:
    boundary = _case(case_id="PR-992", label_sensitive=True)
    incomplete = _planning(
        boundary,
        model="model-a",
        latency_ms=100,
        boundary_alternative=True,
    )
    incomplete = incomplete.model_copy(
        update={
            "plan": incomplete.plan.model_copy(
                update={
                    "tasks": (
                        ResearchTask(
                            task_id="T1",
                            query="mechanism A",
                            goal="Find mechanism A only",
                        ),
                    )
                }
            )
        }
    )
    result = build_planner_v2_case_result(
        variant_id="a",
        model="model-a",
        case=boundary,
        corpus_aliases=(),
        planning=incomplete,
    )

    summary = build_planner_ablation_v2_report((result,), _config(tmp_path, (boundary,))).variants[
        0
    ]

    assert summary.acceptable_router_accuracy == 1
    assert summary.acceptable_task_count_accuracy == 1
    assert summary.boundary_task_coverage == 0.5
    assert not summary.quality_gate_passed
