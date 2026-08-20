from pathlib import Path

import pytest
from pydantic import ValidationError

from paper_research_copilot.agent import (
    CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION,
    CachedResearchPlanner,
    EvidenceAssessment,
    ResearchPlan,
    ResearchTask,
    find_plan_alias_leaks,
)
from paper_research_copilot.integrations import ChatCompletion, ChatTokenUsage


class _SequenceProvider:
    def __init__(self, *responses: str) -> None:
        self.responses = responses
        self.calls = 0
        self.system_prompts: list[str] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        assert "academic paper research assistant" in system_prompt
        self.system_prompts.append(system_prompt)
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


class _ObservableSequenceProvider:
    def __init__(self, *completions: ChatCompletion) -> None:
        self.completions = completions
        self.calls = 0
        self.user_prompts: list[str] = []

    def complete_with_metadata(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> ChatCompletion:
        self.user_prompts.append(user_prompt)
        completion = self.completions[self.calls]
        self.calls += 1
        return completion

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise AssertionError("Planner should use observable completion metadata")


class _FailingProvider:
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise RuntimeError("upstream unavailable")


def _completion(content: str, *, finish_reason: str = "stop") -> ChatCompletion:
    return ChatCompletion(
        content=content,
        finish_reason=finish_reason,
        response_model="test-model-version",
        usage=ChatTokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
    )


def _single_payload(query: str = "episodic memory architecture mechanism") -> str:
    return (
        '{"question_type":"single_paper","rationale":"One mechanism is requested",'
        f'"tasks":[{{"task_id":"T1","query":"{query}",'
        '"goal":"Find direct mechanism evidence"}]}'
    )


def _cross_payload(first_query: str = "thought action observation loop") -> str:
    return (
        '{"question_type":"cross_paper","rationale":"Two mechanisms must be compared",'
        f'"tasks":[{{"task_id":"T1","query":"{first_query}",'
        '"goal":"Find evidence for the first mechanism"},'
        '{"task_id":"T2","query":"sample API calls with loss filtering",'
        '"goal":"Find evidence for the second mechanism"}]}'
    )


def _assessment() -> EvidenceAssessment:
    return EvidenceAssessment(
        sufficient=False,
        reason="Only one distinct paper was retrieved",
        task_candidate_counts={"T1": 30, "T2": 30},
        task_selected_counts={"T1": 5, "T2": 5},
        distinct_paper_count=1,
        retry_recommended=True,
    )


def test_research_plan_enforces_single_and_cross_task_shapes() -> None:
    task = ResearchTask(task_id="T1", query="first mechanism evidence", goal="Find evidence")

    with pytest.raises(ValidationError, match="exactly one"):
        ResearchPlan(
            question="How does the mechanism work?",
            question_type="single_paper",
            rationale="One mechanism",
            tasks=(task, task.model_copy(update={"task_id": "T2", "query": "second query"})),
        )
    with pytest.raises(ValidationError, match="between two and four"):
        ResearchPlan(
            question="Compare two mechanisms in detail",
            question_type="cross_paper",
            rationale="Comparison",
            tasks=(task,),
        )


def test_planner_parses_fenced_json_and_reuses_cache(tmp_path: Path) -> None:
    provider = _SequenceProvider(f"```json\n{_single_payload()}\n```")
    cache_path = tmp_path / "plans.jsonl"
    planner = CachedResearchPlanner(
        provider,
        model="test-model",
        cache_path=cache_path,
    )

    first = planner.plan("How does episodic memory work?")
    second = planner.plan("How does episodic memory work?")

    assert first.plan.question_type == "single_paper"
    assert not first.cache_hit
    assert second.cache_hit
    assert provider.calls == 1

    offline = CachedResearchPlanner(None, model="test-model", cache_path=cache_path)
    assert offline.plan("How does episodic memory work?").cache_hit
    assert offline.trace_for("How does episodic memory work?").final_outcome == "accepted"


def test_planner_retries_invalid_json(tmp_path: Path) -> None:
    provider = _SequenceProvider("not json", _single_payload())
    planner = CachedResearchPlanner(
        provider,
        model="test-model",
        cache_path=tmp_path / "plans.jsonl",
        retry_attempts=2,
    )

    result = planner.plan("How does episodic memory work?")

    assert result.plan.question_type == "single_paper"
    assert provider.calls == 2
    assert result.attempts == 2
    trace = planner.trace_for("How does episodic memory work?")
    assert [item.outcome for item in trace.attempts] == ["invalid_json", "accepted"]
    assert trace.attempts[0].raw_response == "not json"
    assert trace.retry_recovered


@pytest.mark.parametrize(
    ("invalid_response", "expected_outcome"),
    [
        ('{"question_type":"single_paper","rationale":"missing tasks"}', "schema_validation_error"),
        (
            '{"question_type":"cross_paper","rationale":"needs two tasks",'
            '"tasks":[{"task_id":"T1","query":"only one valid query",'
            '"goal":"Find one side only"}]}',
            "invalid_task_shape",
        ),
    ],
)
def test_planner_distinguishes_schema_and_task_shape_failures(
    tmp_path: Path,
    invalid_response: str,
    expected_outcome: str,
) -> None:
    question = "How does episodic memory work?"
    planner = CachedResearchPlanner(
        _SequenceProvider(invalid_response, _single_payload()),
        model="test-model",
        cache_path=tmp_path / "plans.jsonl",
        retry_attempts=2,
    )

    planner.plan(question)

    assert planner.trace_for(question).attempts[0].outcome == expected_outcome


def test_planner_schema_trace_identifies_the_invalid_field(tmp_path: Path) -> None:
    question = "How does episodic memory work?"
    planner = CachedResearchPlanner(
        _SequenceProvider(
            '{"question_type":"single_paper","rationale":"missing tasks"}',
        ),
        model="test-model",
        cache_path=tmp_path / "plans.jsonl",
        retry_attempts=1,
    )

    with pytest.raises(ValueError, match="payload Schema: tasks: Field required"):
        planner.plan(question)

    attempt = planner.trace_for(question).attempts[0]
    assert attempt.error == (
        "Research Planner response does not match the payload Schema: "
        "tasks: Field required"
    )


def test_planner_traces_truncation_and_aggregates_retry_usage(tmp_path: Path) -> None:
    question = "How does episodic memory work?"
    planner = CachedResearchPlanner(
        _ObservableSequenceProvider(
            _completion("partial JSON", finish_reason="length"),
            _completion(_single_payload()),
        ),
        model="test-model",
        cache_path=tmp_path / "plans.jsonl",
        retry_attempts=2,
    )

    result = planner.plan(question)
    trace = planner.trace_for(question)

    assert [item.outcome for item in trace.attempts] == ["truncated", "accepted"]
    assert result.usage.input_tokens == 20
    assert result.usage.output_tokens == 10
    assert result.usage.total_tokens == 30


def test_compact_retry_instruction_is_added_only_after_truncation(tmp_path: Path) -> None:
    question = "How does episodic memory work?"
    provider = _ObservableSequenceProvider(
        _completion("partial JSON", finish_reason="length"),
        _completion(_single_payload()),
    )
    planner = CachedResearchPlanner(
        provider,
        model="test-model",
        cache_path=tmp_path / "plans.jsonl",
        retry_attempts=2,
        retry_mode="compact_json",
    )

    planner.plan(question)
    trace = planner.trace_for(question)

    assert "previous response reached the output token limit" not in provider.user_prompts[0]
    assert "previous response reached the output token limit" in provider.user_prompts[1]
    assert trace.retry_mode == "compact_json"


def test_compact_retry_instruction_is_not_added_after_non_truncation_error(
    tmp_path: Path,
) -> None:
    provider = _ObservableSequenceProvider(
        _completion("not json"),
        _completion(_single_payload()),
    )
    planner = CachedResearchPlanner(
        provider,
        model="test-model",
        cache_path=tmp_path / "plans.jsonl",
        retry_attempts=2,
        retry_mode="compact_json",
    )

    planner.plan("How does episodic memory work?")

    assert all(
        "previous response reached the output token limit" not in prompt
        for prompt in provider.user_prompts
    )


def test_same_prompt_mode_keeps_prompt_unchanged_after_truncation(tmp_path: Path) -> None:
    provider = _ObservableSequenceProvider(
        _completion("partial JSON", finish_reason="length"),
        _completion(_single_payload()),
    )
    planner = CachedResearchPlanner(
        provider,
        model="test-model",
        cache_path=tmp_path / "plans.jsonl",
        retry_attempts=2,
    )

    planner.plan("How does episodic memory work?")

    assert provider.user_prompts[0] == provider.user_prompts[1]


def test_planner_traces_empty_completion_before_retry(tmp_path: Path) -> None:
    question = "How does episodic memory work?"
    planner = CachedResearchPlanner(
        _ObservableSequenceProvider(
            _completion(""),
            _completion(_single_payload()),
        ),
        model="test-model",
        cache_path=tmp_path / "plans.jsonl",
        retry_attempts=2,
    )

    planner.plan(question)

    trace = planner.trace_for(question)
    assert [item.outcome for item in trace.attempts] == ["empty", "accepted"]
    assert trace.attempts[0].error_type == "_PlannerEmptyResponseError"


def test_planner_traces_provider_error_before_reraising(tmp_path: Path) -> None:
    question = "How does episodic memory work?"
    planner = CachedResearchPlanner(
        _FailingProvider(),
        model="test-model",
        cache_path=tmp_path / "plans.jsonl",
    )

    with pytest.raises(RuntimeError, match="upstream unavailable"):
        planner.plan(question)

    attempt = planner.trace_for(question).attempts[0]
    assert attempt.outcome == "provider_error"
    assert attempt.error_type == "RuntimeError"


def test_planner_rejects_inferred_corpus_alias_before_cache_write(tmp_path: Path) -> None:
    planner = CachedResearchPlanner(
        _SequenceProvider(_single_payload("ReAct external tool mechanism")),
        model="test-model",
        cache_path=tmp_path / "plans.jsonl",
        forbidden_aliases=("ReAct",),
        retry_attempts=1,
    )

    with pytest.raises(ValueError, match="forbidden Corpus aliases"):
        planner.plan("How does the described method use external tools?")

    assert not (tmp_path / "plans.jsonl").exists()
    assert planner.trace_for("How does the described method use external tools?").final_outcome == (
        "title_leakage"
    )


def test_plan_alias_check_allows_name_present_in_original_question() -> None:
    plan = ResearchPlan(
        question="How does ReAct use tools?",
        question_type="single_paper",
        rationale="Named method question",
        tasks=(
            ResearchTask(
                task_id="T1",
                query="ReAct external tool mechanism",
                goal="Find direct evidence",
            ),
        ),
    )

    assert find_plan_alias_leaks(plan, ("ReAct",)) == ()


def test_planner_revises_queries_once_and_preserves_question_type(tmp_path: Path) -> None:
    provider = _SequenceProvider(
        _cross_payload(),
        _cross_payload("interleaved reasoning environment feedback trajectory"),
    )
    planner = CachedResearchPlanner(
        provider,
        model="test-model",
        cache_path=tmp_path / "plans.jsonl",
    )
    question = "How do the two described tool-use mechanisms differ?"
    initial = planner.plan(question)

    revised = planner.revise(question, initial.plan, _assessment())

    assert revised.plan.question_type == "cross_paper"
    assert revised.plan.revision == 1
    assert revised.plan.tasks[0].query != initial.plan.tasks[0].query
    with pytest.raises(ValueError, match="only be revised once"):
        planner.revise(question, revised.plan, _assessment())


def test_unchanged_revision_is_rejected_before_cache_write(tmp_path: Path) -> None:
    cache_path = tmp_path / "plans.jsonl"
    provider = _SequenceProvider(_cross_payload(), _cross_payload())
    planner = CachedResearchPlanner(
        provider,
        model="test-model",
        cache_path=cache_path,
        retry_attempts=1,
    )
    question = "How do the two described tool-use mechanisms differ?"
    initial = planner.plan(question)

    with pytest.raises(ValueError, match="did not change"):
        planner.revise(question, initial.plan, _assessment())

    assert len(cache_path.read_text(encoding="utf-8").splitlines()) == 1


def test_prompt_versions_use_separate_cache_keys_and_preserve_old_records(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "plans.jsonl"
    question = "Does the current paper library report a benchmark result?"
    v1_provider = _SequenceProvider(_single_payload("benchmark result"))
    v1_planner = CachedResearchPlanner(
        v1_provider,
        model="test-model",
        cache_path=cache_path,
    )
    v1_result = v1_planner.plan(question)

    v2_provider = _SequenceProvider(_cross_payload("benchmark result main text"))
    v2_planner = CachedResearchPlanner(
        v2_provider,
        model="test-model",
        cache_path=cache_path,
        prompt_version=CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION,
    )
    v2_result = v2_planner.plan(question)

    assert v1_result.prompt_version == "research_planner_v1"
    assert v2_result.prompt_version == CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION
    assert "exactly two independent evidence-channel tasks" in v2_provider.system_prompts[0]
    assert len(cache_path.read_text(encoding="utf-8").splitlines()) == 2
    assert (
        CachedResearchPlanner(
            None,
            model="test-model",
            cache_path=cache_path,
        )
        .plan(question)
        .cache_hit
    )


def test_retry_modes_use_separate_cache_keys_and_preserve_default_cache(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "plans.jsonl"
    question = "How does episodic memory work?"
    default_provider = _ObservableSequenceProvider(_completion(_single_payload()))
    default_planner = CachedResearchPlanner(
        default_provider,
        model="test-model",
        cache_path=cache_path,
    )
    default_planner.plan(question)

    compact_provider = _ObservableSequenceProvider(_completion(_single_payload()))
    compact_planner = CachedResearchPlanner(
        compact_provider,
        model="test-model",
        cache_path=cache_path,
        retry_mode="compact_json",
    )
    compact_result = compact_planner.plan(question)

    assert not compact_result.cache_hit
    assert compact_provider.calls == 1
    assert len(cache_path.read_text(encoding="utf-8").splitlines()) == 2
    assert (
        CachedResearchPlanner(
            None,
            model="test-model",
            cache_path=cache_path,
        )
        .plan(question)
        .cache_hit
    )
    restored = CachedResearchPlanner(
        None,
        model="test-model",
        cache_path=cache_path,
        retry_mode="compact_json",
    )
    assert restored.plan(question).cache_hit
    assert restored.trace_for(question).retry_mode == "compact_json"
