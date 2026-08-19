from paper_research_copilot.agent import PlannerAttemptTrace
from paper_research_copilot.integrations import ChatTokenUsage
from scripts.run_planner_retry_diagnostics import _sanitize_attempt


def test_sanitized_planner_attempt_excludes_raw_response() -> None:
    attempt = PlannerAttemptTrace(
        attempt=1,
        outcome="invalid_json",
        finish_reason="stop",
        content_length=8,
        latency_ms=100,
        usage=ChatTokenUsage(input_tokens=10, output_tokens=2, total_tokens=12),
        error_type="InvalidPlannerJsonError",
        error="invalid JSON",
        raw_response="not json",
    )

    sanitized = _sanitize_attempt(attempt)

    assert "raw_response" not in sanitized
    assert sanitized["raw_response_sha256"] == (
        "7ccfa1fbf3940e6f0c0375d87c0f9235a50514e14cb427bdfaf5077987b26ccf"
    )
