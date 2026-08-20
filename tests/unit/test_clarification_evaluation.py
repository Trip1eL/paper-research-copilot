from pathlib import Path

from paper_research_copilot.agent import (
    AgentEvent,
    AgentResult,
    ClarificationRequest,
    EvidenceAssessment,
    QuestionScreening,
    ResearchPlan,
    ResearchTask,
)
from paper_research_copilot.domain import Answer
from paper_research_copilot.evaluation import (
    build_clarification_report,
    evaluate_clarification_case,
    load_clarification_cases,
)


def _result(question: str, *, ambiguous: bool) -> AgentResult:
    plan = ResearchPlan(
        question=question,
        question_type="single_paper",
        rationale="Retrieve evidence for the requested mechanism",
        tasks=(
            ResearchTask(
                task_id="T1",
                query="ReAct reasoning and acting mechanism",
                goal="Find direct mechanism evidence",
            ),
        ),
    )
    screening = QuestionScreening(
        decision="ambiguous" if ambiguous else "clear",
        rule_id="unresolved_reference" if ambiguous else None,
        reason=(
            "问题引用了当前请求中不存在的前文对象"
            if ambiguous
            else "问题包含可直接检索的研究目标"
        ),
    )
    clarification = (
        ClarificationRequest(
            rule_id="unresolved_reference",
            prompt="你指的是哪一篇论文或哪一个方法？",
            required_information=("论文标题、作者、arXiv ID 或明确的方法名称",),
        )
        if ambiguous
        else None
    )
    nodes = (
        ("plan_research", "screen_question", "write_report", "validate_citations")
        if ambiguous
        else (
            "plan_research",
            "screen_question",
            "retrieve_evidence",
            "assess_evidence",
            "write_report",
            "validate_citations",
        )
    )
    return AgentResult(
        question=question,
        screening=screening,
        clarification=clarification,
        plan=plan,
        evidence=(),
        assessment=EvidenceAssessment(
            sufficient=not ambiguous,
            reason="Evidence state was evaluated for this protocol case",
            task_candidate_counts={},
            task_selected_counts={},
            distinct_paper_count=0,
            retry_recommended=False,
        ),
        answer=Answer(
            question=question,
            text="INSUFFICIENT_EVIDENCE" if ambiguous else "Grounded answer",
            citations=(),
            status="insufficient_evidence" if ambiguous else "answered",
        ),
        retry_count=0,
        trace=tuple(
            AgentEvent(
                sequence=index,
                node=node,
                outcome="completed",
                latency_ms=1,
            )
            for index, node in enumerate(nodes, 1)
        ),
    )


def test_clarification_dataset_and_protocol_metrics() -> None:
    case = load_clarification_cases(
        Path("evals/datasets/clarification_v1.jsonl")
    )[0]
    evaluated = evaluate_clarification_case(
        case,
        original_result=_result(case.question, ambiguous=True),
        child_result=_result("Original question with a ReAct title", ambiguous=False),
        parent_task_id="parent-task",
        child_parent_task_id="parent-task",
        persisted_response=case.clarification_response,
    )
    report = build_clarification_report((evaluated,))

    assert evaluated.strict_pass is True
    assert report.strict_pass_rate == 1
    assert report.side_effect_free_rate == 1
    assert report.child_reentry_rate == 1
    assert evaluated.child_answer_behavior_correct is True
    assert report.child_answer_behavior_accuracy == 1
    assert report.provenance_rate == 1


def test_clarification_evaluation_fails_invalid_provenance() -> None:
    case = load_clarification_cases(
        Path("evals/datasets/clarification_v1.jsonl")
    )[0]
    evaluated = evaluate_clarification_case(
        case,
        original_result=_result(case.question, ambiguous=True),
        child_result=_result("Clarified ReAct question", ambiguous=False),
        parent_task_id="parent-task",
        child_parent_task_id="different-parent",
        persisted_response=case.clarification_response,
    )

    assert evaluated.provenance_valid is False
    assert evaluated.strict_pass is False


def test_clarification_answer_metric_checks_status_not_semantics() -> None:
    case = load_clarification_cases(
        Path("evals/datasets/clarification_v1.jsonl")
    )[0]
    child = _result("Clarified ReAct question", ambiguous=False).model_copy(
        update={
            "answer": Answer(
                question="Clarified ReAct question",
                text="Fluent but not semantically judged by this metric",
                citations=(),
                status="insufficient_evidence",
            )
        }
    )

    evaluated = evaluate_clarification_case(
        case,
        original_result=_result(case.question, ambiguous=True),
        child_result=child,
        parent_task_id="parent-task",
        child_parent_task_id="parent-task",
        persisted_response=case.clarification_response,
    )

    assert evaluated.child_answer_behavior_correct is False
    assert evaluated.strict_pass is False
