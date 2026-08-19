"""Run the frozen pypdf parse benchmark without online dependencies."""

import argparse
from pathlib import Path

from paper_research_copilot.config import PROJECT_ROOT
from paper_research_copilot.evaluation.parse_benchmark import (
    build_parse_benchmark_config,
    build_parse_benchmark_report,
    run_parse_benchmark,
    write_parse_benchmark_artifacts,
)
from paper_research_copilot.evaluation.parse_datasets import load_parse_benchmark


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "parse_benchmark_v1.jsonl",
    )
    parser.add_argument("--baseline-id", default="parse_pypdf_v1")
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=PROJECT_ROOT / "evals" / "baselines",
    )
    args = parser.parse_args()

    cases = load_parse_benchmark(args.dataset, project_root=PROJECT_ROOT)
    results = run_parse_benchmark(cases, project_root=PROJECT_ROOT)
    config = build_parse_benchmark_config(
        baseline_id=args.baseline_id,
        dataset_path=args.dataset,
        project_root=PROJECT_ROOT,
    )
    report = build_parse_benchmark_report(results, config)
    json_path, markdown_path = write_parse_benchmark_artifacts(
        report,
        baseline_dir=args.baseline_dir,
    )
    print(f"Parse benchmark: {report.case_count} cases")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
