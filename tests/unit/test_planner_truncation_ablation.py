from scripts.run_planner_truncation_ablation import (
    Strategy,
    _recommend,
    _summarize_strategy,
)


def _record(*, retries: int = 0, latency_ms: float = 100) -> dict[str, object]:
    attempts = [
        {
            "outcome": "truncated" if index < retries else "accepted",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            },
        }
        for index in range(retries + 1)
    ]
    return {
        "success": True,
        "strict_route": True,
        "acceptable_route": True,
        "strict_task_count": True,
        "acceptable_task_count": True,
        "facet_coverage": 1.0,
        "title_leaks": [],
        "cache_hit": False,
        "generation_latency_ms": latency_ms,
        "attempt_count": len(attempts),
        "retry_recovered": retries > 0,
        "attempts": attempts,
    }


def test_strategy_summary_counts_retries_truncations_and_all_attempt_tokens() -> None:
    summary = _summarize_strategy(
        Strategy("compact_1800", 1800, "compact_json", 1),
        [_record(retries=1, latency_ms=200), _record(latency_ms=100)],
    )

    assert summary["quality_gate_passed"]
    assert summary["retry_rate"] == 0.5
    assert summary["retry_recovery_rate"] == 1
    assert summary["truncated_attempt_count"] == 1
    assert summary["model_call_count"] == 3
    assert summary["total_output_tokens"] == 15
    assert summary["total_tokens"] == 45


def test_recommendation_prioritizes_retry_rate_before_latency() -> None:
    summaries = [
        {
            "strategy_id": "faster_with_retry",
            "quality_gate_passed": True,
            "retry_rate": 0.2,
            "p95_generation_latency_ms": 100,
            "total_output_tokens": 100,
            "complexity_rank": 0,
        },
        {
            "strategy_id": "slower_without_retry",
            "quality_gate_passed": True,
            "retry_rate": 0,
            "p95_generation_latency_ms": 200,
            "total_output_tokens": 120,
            "complexity_rank": 0,
        },
    ]

    recommended, _ = _recommend(summaries)

    assert recommended == "slower_without_retry"
