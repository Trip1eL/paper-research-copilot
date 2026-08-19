"""Run the fast parser router against the frozen Parse Benchmark."""

import argparse
from pathlib import Path

from paper_research_copilot.config import PROJECT_ROOT
from paper_research_copilot.evaluation.parse_datasets import load_parse_benchmark
from paper_research_copilot.evaluation.parse_shadow import (
    build_shadow_parse_config,
    build_shadow_parse_report,
    run_shadow_parse_benchmark,
    write_shadow_parse_artifacts,
)
from paper_research_copilot.ingestion import FastParserRouter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "parse_benchmark_v1.jsonl",
    )
    parser.add_argument("--baseline-id", default="parse_router_shadow_v1")
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=PROJECT_ROOT / "evals" / "baselines",
    )
    args = parser.parse_args()

    router = FastParserRouter()
    cases = load_parse_benchmark(args.dataset, project_root=PROJECT_ROOT)
    results = run_shadow_parse_benchmark(
        cases,
        project_root=PROJECT_ROOT,
        router=router,
    )
    config = build_shadow_parse_config(
        baseline_id=args.baseline_id,
        dataset_path=args.dataset,
        project_root=PROJECT_ROOT,
        router=router,
    )
    report = build_shadow_parse_report(results, config)
    json_path, markdown_path = write_shadow_parse_artifacts(
        report,
        baseline_dir=args.baseline_dir,
    )
    print(f"Shadow parse benchmark: {report.case_count} cases")
    print(
        "Issue detection / selected accepted / fallback: "
        f"{report.primary_issue_detection_rate:.2%} / "
        f"{report.selected_accepted_rate:.2%} / "
        f"{report.structured_fallback_rate:.2%}"
    )
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
