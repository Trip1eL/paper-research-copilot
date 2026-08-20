"""Structured, cached research planning and one-shot query revision."""

import hashlib
import json
import re
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from paper_research_copilot.agent.models import (
    EvidenceAssessment,
    PlanningResult,
    QuestionType,
    ResearchPlan,
    ResearchTask,
)
from paper_research_copilot.integrations import (
    ChatCompletion,
    ChatProvider,
    ChatTokenUsage,
    ObservableChatProvider,
)

PlannerPromptVersion = Literal[
    "research_planner_v1",
    "research_planner_corpus_verification_v2",
]
PlannerRetryMode = Literal["same_prompt", "compact_json"]
RESEARCH_PLANNER_PROMPT_VERSION: PlannerPromptVersion = "research_planner_v1"
CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION: PlannerPromptVersion = (
    "research_planner_corpus_verification_v2"
)

_SYSTEM_PROMPT = """You plan retrieval for an academic paper research assistant.
Return valid JSON only. Do not answer the user's research question.
Classify the question as single_paper or cross_paper.
Use exactly one task for single_paper and two to four independent tasks for cross_paper.
Do not name, identify, or guess paper titles, method names, system names, authors, datasets,
or arXiv identifiers unless that exact name already appears in the user's question.
Each task query must stand alone, preserve the user's descriptive wording, and retrieve evidence
for exactly one side or mechanism. Task IDs must be T1, T2, ... in order."""

_CORPUS_VERIFICATION_SYSTEM_PROMPT = (
    _SYSTEM_PROMPT
    + """

Apply these routing rules before creating tasks:
- Keep multiple facts or metrics from the same explicitly described paper, method, or benchmark in
  one single_paper task. Two requested values do not by themselves imply two retrieval sides.
- A corpus-wide verification asks whether the current corpus, paper library, or papers contain or
  directly report a specific fact or result. For this existence or absence check, use cross_paper
  with exactly two independent evidence-channel tasks: T1 searches main-text statements for the
  exact entity, benchmark, metric, and value requested by the user; T2 independently checks
  evaluation/results sections, tables, figures, or appendices for the same requested evidence.
- A corpus-wide synthesis asking which works satisfy a property is cross_paper. Separate discovery
  of matching works from extraction of the requested attributes when those are distinct needs.
- A question that asks which one method has a property is still single_paper when it does not ask
  to verify corpus-wide absence or compare independent methods. Phrases such as 'these papers' or
  'which method' alone do not imply cross_paper.
Do not add generic verification tasks. Every verification query must preserve the exact entities,
benchmarks, metrics, or mechanisms named or described in the user's question."""
)

_SYSTEM_PROMPTS: dict[PlannerPromptVersion, str] = {
    RESEARCH_PLANNER_PROMPT_VERSION: _SYSTEM_PROMPT,
    CORPUS_VERIFICATION_PLANNER_PROMPT_VERSION: _CORPUS_VERIFICATION_SYSTEM_PROMPT,
}

_COMPACT_JSON_RETRY_INSTRUCTION = """

The previous response reached the output token limit. Retry with compact JSON only:
- use one short sentence for rationale;
- keep each query under 160 characters and each goal under 100 characters;
- include only the required question_type, rationale, tasks, task_id, query, and goal fields;
- do not include analysis, Markdown, comments, or extra fields.
"""

_REVISION_RECOVERY_VERSION = "schema_repair_fallback_v1"
_SCHEMA_REPAIR_INSTRUCTION = """

The previous response failed validation. Correct that response instead of repeating it.
Keep the original question type and task count. Preserve consecutive task IDs and change at least
one retrieval query. Return JSON only with question_type, rationale, and tasks; each task must have
only task_id, query, and goal.

Validation error:
{error}

Previous invalid response:
<previous_response>
{raw_response}
</previous_response>
"""


class ResearchPlanner(Protocol):
    def plan(self, question: str) -> PlanningResult: ...

    def revise(
        self,
        question: str,
        previous_plan: ResearchPlan,
        assessment: EvidenceAssessment,
    ) -> PlanningResult: ...


class _PlanPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    question_type: QuestionType
    rationale: str
    tasks: tuple[ResearchTask, ...]


class _InvalidPlannerJsonError(ValueError):
    pass


class _PlannerPayloadSchemaError(ValueError):
    pass


class _InvalidPlannerPlanError(ValueError):
    pass


class _UnchangedPlannerRevisionError(ValueError):
    pass


class _PlannerTitleLeakageError(ValueError):
    pass


class _PlannerTruncatedError(ValueError):
    pass


class _PlannerEmptyResponseError(ValueError):
    pass


PlannerAttemptOutcome = Literal[
    "accepted",
    "empty",
    "truncated",
    "provider_error",
    "invalid_json",
    "schema_validation_error",
    "invalid_task_shape",
    "invalid_plan",
    "unchanged_revision",
    "title_leakage",
    "deterministic_fallback",
]


class PlannerAttemptTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    attempt: int = Field(ge=1)
    outcome: PlannerAttemptOutcome
    finish_reason: str
    content_length: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    response_model: str | None = None
    usage: ChatTokenUsage = Field(default_factory=ChatTokenUsage)
    error_type: str | None = None
    error: str | None = None
    raw_response: str = ""
    repair_prompt_used: bool = False


class PlannerGenerationTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation: Literal["initial", "revision"]
    question: str
    model: str
    prompt_version: str
    retry_mode: PlannerRetryMode = "same_prompt"
    input_sha256: str
    attempts: tuple[PlannerAttemptTrace, ...]
    retry_triggered: bool
    retry_recovered: bool
    repair_attempts: int = Field(default=0, ge=0)
    fallback_used: bool = False
    fallback_reason: str | None = None
    final_outcome: PlannerAttemptOutcome


class PlannerCacheRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    cache_key: str
    operation: Literal["initial", "revision"]
    input_sha256: str
    model: str
    prompt_version: str
    retry_mode: PlannerRetryMode = "same_prompt"
    generation_latency_ms: float
    attempts: int = Field(default=1, ge=1)
    repair_attempts: int = Field(default=0, ge=0)
    fallback_used: bool = False
    fallback_reason: str | None = None
    usage: ChatTokenUsage = Field(default_factory=ChatTokenUsage)
    response_model: str | None = None
    raw_response: str
    plan: ResearchPlan
    generation_trace: PlannerGenerationTrace | None = None


class CachedResearchPlanner:
    def __init__(
        self,
        provider: ChatProvider | None,
        *,
        model: str,
        cache_path: Path,
        forbidden_aliases: Iterable[str] = (),
        retry_attempts: int = 3,
        prompt_version: PlannerPromptVersion = RESEARCH_PLANNER_PROMPT_VERSION,
        retry_mode: PlannerRetryMode = "same_prompt",
    ) -> None:
        if retry_attempts < 1:
            raise ValueError("Planner retry attempts must be at least 1")
        self._provider = provider
        self.model = model
        self.cache_path = cache_path
        self.retry_attempts = retry_attempts
        self.prompt_version = prompt_version
        self.retry_mode = retry_mode
        self._system_prompt = _SYSTEM_PROMPTS[prompt_version]
        self._aliases = tuple(
            dict.fromkeys(alias.strip() for alias in forbidden_aliases if alias.strip())
        )
        self._records = self._load_cache()
        self._traces: dict[tuple[str, str], PlannerGenerationTrace] = {}

    def plan(self, question: str) -> PlanningResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("Research question must not be empty")
        prompt = _initial_prompt(normalized_question)
        return self._execute(
            operation="initial",
            question=normalized_question,
            user_prompt=prompt,
            revision=0,
        )

    def revise(
        self,
        question: str,
        previous_plan: ResearchPlan,
        assessment: EvidenceAssessment,
    ) -> PlanningResult:
        normalized_question = question.strip()
        if previous_plan.question != normalized_question:
            raise ValueError("Previous Research Plan belongs to a different question")
        if previous_plan.revision >= 1:
            raise ValueError("Research Plan can only be revised once")
        prompt = _revision_prompt(normalized_question, previous_plan, assessment)
        result = self._execute(
            operation="revision",
            question=normalized_question,
            user_prompt=prompt,
            revision=previous_plan.revision + 1,
            expected_question_type=previous_plan.question_type,
            previous_plan=previous_plan,
            assessment=assessment,
        )
        return result

    def _execute(
        self,
        *,
        operation: Literal["initial", "revision"],
        question: str,
        user_prompt: str,
        revision: int,
        expected_question_type: QuestionType | None = None,
        previous_plan: ResearchPlan | None = None,
        assessment: EvidenceAssessment | None = None,
    ) -> PlanningResult:
        input_sha256 = _input_hash(
            operation,
            self.model,
            self.prompt_version,
            self._system_prompt,
            user_prompt,
            self.retry_mode,
        )
        cached = self._records.get(input_sha256)
        lookup_started = time.perf_counter()
        if cached is not None:
            if cached.generation_trace is not None:
                self._traces[(operation, question)] = cached.generation_trace
            return PlanningResult(
                plan=cached.plan,
                operation=operation,
                model=self.model,
                prompt_version=self.prompt_version,
                cache_hit=True,
                latency_ms=round((time.perf_counter() - lookup_started) * 1000, 2),
                generation_latency_ms=cached.generation_latency_ms,
                attempts=cached.attempts,
                repair_attempts=cached.repair_attempts,
                fallback_used=cached.fallback_used,
                fallback_reason=cached.fallback_reason,
                usage=cached.usage,
                response_model=cached.response_model,
            )
        if self._provider is None:
            raise LookupError("Research Plan is missing from cache and no provider is configured")

        generation_started = time.perf_counter()
        attempt_traces: list[PlannerAttemptTrace] = []
        last_error: Exception | None = None
        for attempt in range(1, self.retry_attempts + 1):
            attempt_started = time.perf_counter()
            attempt_user_prompt, repair_prompt_used = _planner_attempt_prompt(
                user_prompt,
                attempt_traces,
                retry_mode=self.retry_mode,
            )
            try:
                completion = self._complete_with_metadata(
                    self._system_prompt,
                    attempt_user_prompt,
                )
            except Exception as exc:
                attempt_traces.append(
                    self._attempt_trace(
                        attempt,
                        round((time.perf_counter() - attempt_started) * 1000, 2),
                        outcome="provider_error",
                        finish_reason="provider_error",
                        error=exc,
                        repair_prompt_used=repair_prompt_used,
                    )
                )
                self._store_trace(operation, question, input_sha256, attempt_traces)
                last_error = exc
                if previous_plan is not None or isinstance(exc, ValueError):
                    if attempt < self.retry_attempts:
                        time.sleep(0.5 * (2 ** (attempt - 1)))
                        continue
                    break
                raise

            attempt_latency_ms = round(
                (time.perf_counter() - attempt_started) * 1000,
                2,
            )
            raw_response = completion.content
            if completion.finish_reason == "length":
                truncated_error = _PlannerTruncatedError(
                    "Research Planner returned a truncated response"
                )
                attempt_traces.append(
                    self._attempt_trace(
                        attempt,
                        attempt_latency_ms,
                        outcome="truncated",
                        completion=completion,
                        error=truncated_error,
                        repair_prompt_used=repair_prompt_used,
                    )
                )
                last_error = truncated_error
            elif not raw_response.strip():
                empty_error = _PlannerEmptyResponseError(
                    "Research Planner returned an empty response"
                )
                attempt_traces.append(
                    self._attempt_trace(
                        attempt,
                        attempt_latency_ms,
                        outcome="empty",
                        completion=completion,
                        error=empty_error,
                        repair_prompt_used=repair_prompt_used,
                    )
                )
                last_error = empty_error
            else:
                try:
                    payload = _parse_plan_payload(raw_response)
                    if (
                        expected_question_type is not None
                        and payload.question_type != expected_question_type
                    ):
                        raise _InvalidPlannerPlanError(
                            "Query revision changed the Research Plan question type"
                        )
                    plan = ResearchPlan(
                        question=question,
                        question_type=payload.question_type,
                        rationale=payload.rationale,
                        tasks=payload.tasks,
                        revision=revision,
                    )
                    if previous_plan is not None and _queries(plan) == _queries(previous_plan):
                        raise _UnchangedPlannerRevisionError(
                            "Revised Research Plan did not change any retrieval query"
                        )
                    leaks = find_plan_alias_leaks(plan, self._aliases)
                    if leaks:
                        raise _PlannerTitleLeakageError(
                            f"Research Plan contains forbidden Corpus aliases: {leaks}"
                        )
                except (
                    _InvalidPlannerJsonError,
                    _PlannerPayloadSchemaError,
                    _InvalidPlannerPlanError,
                    _UnchangedPlannerRevisionError,
                    _PlannerTitleLeakageError,
                    ValidationError,
                ) as exc:
                    outcome = _planner_error_outcome(exc)
                    attempt_traces.append(
                        self._attempt_trace(
                            attempt,
                            attempt_latency_ms,
                            outcome=outcome,
                            completion=completion,
                            error=exc,
                            repair_prompt_used=repair_prompt_used,
                        )
                    )
                    last_error = exc
                else:
                    attempt_traces.append(
                        self._attempt_trace(
                            attempt,
                            attempt_latency_ms,
                            outcome="accepted",
                            completion=completion,
                            repair_prompt_used=repair_prompt_used,
                        )
                    )
                    trace = self._store_trace(
                        operation,
                        question,
                        input_sha256,
                        attempt_traces,
                    )
                    latency_ms = round((time.perf_counter() - generation_started) * 1000, 2)
                    usage = _aggregate_attempt_usage(attempt_traces)
                    record = PlannerCacheRecord(
                        cache_key=input_sha256,
                        operation=operation,
                        input_sha256=input_sha256,
                        model=self.model,
                        prompt_version=self.prompt_version,
                        retry_mode=self.retry_mode,
                        generation_latency_ms=latency_ms,
                        attempts=attempt,
                        repair_attempts=trace.repair_attempts,
                        usage=usage,
                        response_model=completion.response_model,
                        raw_response=raw_response,
                        plan=plan,
                        generation_trace=trace,
                    )
                    self._records[input_sha256] = record
                    self._write_cache()
                    return PlanningResult(
                        plan=plan,
                        operation=operation,
                        model=self.model,
                        prompt_version=self.prompt_version,
                        cache_hit=False,
                        latency_ms=latency_ms,
                        generation_latency_ms=latency_ms,
                        attempts=attempt,
                        repair_attempts=trace.repair_attempts,
                        usage=usage,
                        response_model=completion.response_model,
                    )

            self._store_trace(operation, question, input_sha256, attempt_traces)
            if attempt < self.retry_attempts:
                time.sleep(0.5 * (2 ** (attempt - 1)))
                continue
            break
        if previous_plan is not None and last_error is not None:
            latency_ms = round((time.perf_counter() - generation_started) * 1000, 2)
            plan = _deterministic_revision_plan(previous_plan, assessment)
            fallback_reason = f"{type(last_error).__name__}: {last_error}"
            trace = self._store_trace(
                operation,
                question,
                input_sha256,
                attempt_traces,
                final_outcome="deterministic_fallback",
                fallback_reason=fallback_reason,
            )
            usage = _aggregate_attempt_usage(attempt_traces)
            last_completion = next(
                (item for item in reversed(attempt_traces) if item.raw_response),
                None,
            )
            record = PlannerCacheRecord(
                cache_key=input_sha256,
                operation=operation,
                input_sha256=input_sha256,
                model=self.model,
                prompt_version=self.prompt_version,
                retry_mode=self.retry_mode,
                generation_latency_ms=latency_ms,
                attempts=len(attempt_traces),
                repair_attempts=trace.repair_attempts,
                fallback_used=True,
                fallback_reason=fallback_reason,
                usage=usage,
                response_model=(
                    next(
                        (
                            item.response_model
                            for item in reversed(attempt_traces)
                            if item.response_model is not None
                        ),
                        None,
                    )
                ),
                raw_response=last_completion.raw_response if last_completion else "",
                plan=plan,
                generation_trace=trace,
            )
            if attempt_traces[-1].outcome != "provider_error":
                self._records[input_sha256] = record
                self._write_cache()
            return PlanningResult(
                plan=plan,
                operation=operation,
                model=self.model,
                prompt_version=self.prompt_version,
                cache_hit=False,
                latency_ms=latency_ms,
                generation_latency_ms=latency_ms,
                attempts=len(attempt_traces),
                repair_attempts=trace.repair_attempts,
                fallback_used=True,
                fallback_reason=fallback_reason,
                usage=usage,
                response_model=record.response_model,
            )
        raise ValueError(
            f"Research Planner failed after {self.retry_attempts} attempts: {last_error}"
        ) from last_error

    def trace_for(
        self,
        question: str,
        *,
        operation: Literal["initial", "revision"] = "initial",
    ) -> PlannerGenerationTrace:
        try:
            return self._traces[(operation, question.strip())]
        except KeyError as exc:
            raise LookupError("Research question has no Planner generation trace") from exc

    @staticmethod
    def _attempt_trace(
        attempt: int,
        latency_ms: float,
        *,
        outcome: PlannerAttemptOutcome,
        finish_reason: str = "unknown",
        completion: ChatCompletion | None = None,
        error: Exception | None = None,
        repair_prompt_used: bool = False,
    ) -> PlannerAttemptTrace:
        return PlannerAttemptTrace(
            attempt=attempt,
            outcome=outcome,
            finish_reason=(completion.finish_reason or "unknown") if completion else finish_reason,
            content_length=len(completion.content) if completion else 0,
            latency_ms=latency_ms,
            response_model=completion.response_model if completion else None,
            usage=completion.usage if completion else ChatTokenUsage(),
            error_type=type(error).__name__ if error else None,
            error=str(error) if error else None,
            raw_response=completion.content if completion else "",
            repair_prompt_used=repair_prompt_used,
        )

    def _store_trace(
        self,
        operation: Literal["initial", "revision"],
        question: str,
        input_sha256: str,
        attempts: Sequence[PlannerAttemptTrace],
        *,
        final_outcome: PlannerAttemptOutcome | None = None,
        fallback_reason: str | None = None,
    ) -> PlannerGenerationTrace:
        resolved_outcome = final_outcome or attempts[-1].outcome
        trace = PlannerGenerationTrace(
            operation=operation,
            question=question,
            model=self.model,
            prompt_version=self.prompt_version,
            retry_mode=self.retry_mode,
            input_sha256=input_sha256,
            attempts=tuple(attempts),
            retry_triggered=len(attempts) > 1,
            retry_recovered=len(attempts) > 1 and resolved_outcome == "accepted",
            repair_attempts=sum(item.repair_prompt_used for item in attempts),
            fallback_used=resolved_outcome == "deterministic_fallback",
            fallback_reason=fallback_reason,
            final_outcome=resolved_outcome,
        )
        self._traces[(operation, question)] = trace
        return trace

    def _complete_with_metadata(self, system_prompt: str, user_prompt: str) -> ChatCompletion:
        if self._provider is None:
            raise LookupError("Research Planner provider is not configured")
        if hasattr(self._provider, "complete_with_metadata"):
            provider = cast(ObservableChatProvider, self._provider)
            return provider.complete_with_metadata(system_prompt, user_prompt)
        return ChatCompletion(
            content=self._provider.complete(system_prompt, user_prompt),
            usage=ChatTokenUsage(),
        )

    def _load_cache(self) -> dict[str, PlannerCacheRecord]:
        if not self.cache_path.is_file():
            return {}
        records = tuple(
            PlannerCacheRecord.model_validate_json(line)
            for line in self.cache_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        return {record.input_sha256: record for record in records}

    def _write_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(self._records[key].model_dump_json() for key in sorted(self._records))
        self.cache_path.write_text(content + "\n", encoding="utf-8")


def find_plan_alias_leaks(
    plan: ResearchPlan,
    aliases: Iterable[str],
) -> tuple[str, ...]:
    normalized_aliases = tuple(alias.strip() for alias in aliases if alias.strip())
    return tuple(
        f"{task.task_id}:{alias}:{task.query}"
        for task in plan.tasks
        for alias in normalized_aliases
        if alias.casefold() in task.query.casefold()
        and alias.casefold() not in plan.question.casefold()
    )


def _initial_prompt(question: str) -> str:
    return (
        "Create a minimal retrieval plan for the question below.\n\n"
        f"Question:\n{question}\n\n"
        "Return this JSON shape:\n"
        '{"question_type":"single_paper|cross_paper","rationale":"...",'
        '"tasks":[{"task_id":"T1","query":"...","goal":"..."}]}\n'
        "For a comparison with two independently described methods, use cross_paper and one task "
        "per comparison side."
    )


def _revision_prompt(
    question: str,
    previous_plan: ResearchPlan,
    assessment: EvidenceAssessment,
) -> str:
    previous_payload = _PlanPayload(
        question_type=previous_plan.question_type,
        rationale=previous_plan.rationale,
        tasks=previous_plan.tasks,
    )
    return (
        "Revise the retrieval queries once because the deterministic evidence check failed. "
        "Preserve the question type and number of tasks. Change at least one query. Do not add "
        "paper or method names that are absent from the original question.\n\n"
        f"Question:\n{question}\n\n"
        f"Previous plan payload:\n{previous_payload.model_dump_json()}\n\n"
        f"Evidence assessment:\n{assessment.model_dump_json()}\n\n"
        "Return exactly the same JSON fields as the previous plan payload. Do not include "
        "question, revision, assessment, or any other fields."
    )


def _parse_plan_payload(response: str) -> _PlanPayload:
    cleaned = response.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise _InvalidPlannerJsonError("Research Planner must return valid JSON") from exc
    try:
        return _PlanPayload.model_validate(payload)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_url=False)
        )
        raise _PlannerPayloadSchemaError(
            f"Research Planner response does not match the payload Schema: {details}"
        ) from exc


def _input_hash(
    operation: str,
    model: str,
    prompt_version: str,
    system_prompt: str,
    user_prompt: str,
    retry_mode: PlannerRetryMode = "same_prompt",
) -> str:
    payload = json.dumps(
        {
            "operation": operation,
            "model": model,
            "prompt_version": prompt_version,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            **(
                {"revision_recovery": _REVISION_RECOVERY_VERSION}
                if operation == "revision"
                else {}
            ),
            **({"retry_mode": retry_mode} if retry_mode != "same_prompt" else {}),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _queries(plan: ResearchPlan) -> tuple[str, ...]:
    return tuple(" ".join(task.query.casefold().split()) for task in plan.tasks)


def _planner_attempt_prompt(
    user_prompt: str,
    attempts: Sequence[PlannerAttemptTrace],
    *,
    retry_mode: PlannerRetryMode,
) -> tuple[str, bool]:
    if not attempts:
        return user_prompt, False
    previous = attempts[-1]
    if previous.outcome == "provider_error":
        return user_prompt, False
    if previous.outcome == "truncated":
        if retry_mode == "compact_json":
            return user_prompt + _COMPACT_JSON_RETRY_INSTRUCTION, False
        return user_prompt, False
    raw_response = previous.raw_response[-4000:] or "<empty>"
    error = (previous.error or previous.outcome)[-1200:]
    return (
        user_prompt
        + _SCHEMA_REPAIR_INSTRUCTION.format(
            error=error,
            raw_response=raw_response,
        ),
        True,
    )


def _deterministic_revision_plan(
    previous_plan: ResearchPlan,
    assessment: EvidenceAssessment | None,
) -> ResearchPlan:
    if assessment is not None and assessment.missing_task_ids:
        suffix = "primary source implementation mechanism evidence"
    elif assessment is not None and assessment.distinct_paper_count < 2:
        suffix = "independent paper comparative evidence"
    else:
        suffix = "implementation mechanism evaluation primary evidence"
    tasks = tuple(
        task.model_copy(update={"query": f"{task.query} {suffix}"})
        for task in previous_plan.tasks
    )
    return ResearchPlan(
        question=previous_plan.question,
        question_type=previous_plan.question_type,
        rationale="Deterministic query expansion after Planner validation failure",
        tasks=tasks,
        revision=previous_plan.revision + 1,
    )


def _planner_error_outcome(exc: Exception) -> PlannerAttemptOutcome:
    if isinstance(exc, _InvalidPlannerJsonError):
        return "invalid_json"
    if isinstance(exc, _PlannerPayloadSchemaError):
        return "schema_validation_error"
    if isinstance(exc, ValidationError):
        return "invalid_task_shape"
    if isinstance(exc, _UnchangedPlannerRevisionError):
        return "unchanged_revision"
    if isinstance(exc, _PlannerTitleLeakageError):
        return "title_leakage"
    return "invalid_plan"


def _aggregate_attempt_usage(attempts: Sequence[PlannerAttemptTrace]) -> ChatTokenUsage:
    return ChatTokenUsage(
        input_tokens=_sum_known(item.usage.input_tokens for item in attempts),
        output_tokens=_sum_known(item.usage.output_tokens for item in attempts),
        total_tokens=_sum_known(item.usage.total_tokens for item in attempts),
    )


def _sum_known(values: Iterable[int | None]) -> int | None:
    materialized = tuple(values)
    known = tuple(value for value in materialized if value is not None)
    return sum(known) if known else None
