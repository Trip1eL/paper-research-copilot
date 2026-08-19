"""Run the isolated MinerU structured parsing benchmark."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from paper_research_copilot.config import PROJECT_ROOT
from paper_research_copilot.evaluation.structured_parse import (
    build_structured_parse_config,
    build_structured_parse_error_result,
    build_structured_parse_report,
    evaluate_structured_parse_case,
    write_structured_parse_artifacts,
)
from paper_research_copilot.evaluation.structured_parse_datasets import (
    load_structured_parse_benchmark,
)
from paper_research_copilot.ingestion.structured import MineruCliAdapter

MINERU_VERSION = "3.4.5"
DEFAULT_MINERU_PYTHON = PROJECT_ROOT / "tmp" / "mineru" / "env" / (
    "python.exe" if os.name == "nt" else "bin/python"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "structured_parse_benchmark_v1.jsonl",
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--baseline-id", default="mineru_structured_v1")
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=PROJECT_ROOT / "evals" / "baselines",
    )
    parser.add_argument(
        "--raw-output-dir",
        type=Path,
        default=PROJECT_ROOT / "tmp" / "mineru" / "structured_benchmark_v1",
    )
    parser.add_argument(
        "--mineru-python",
        type=Path,
        default=DEFAULT_MINERU_PYTHON,
    )
    parser.add_argument(
        "--mineru-config",
        type=Path,
        default=PROJECT_ROOT / "tmp" / "mineru" / "mineru.json",
    )
    parser.add_argument(
        "--worker-script",
        type=Path,
        default=PROJECT_ROOT / "scripts" / "run_mineru_pipeline.py",
    )
    parser.add_argument("--timeout-seconds", type=float, default=900)
    args = parser.parse_args()

    all_cases = load_structured_parse_benchmark(args.dataset, project_root=PROJECT_ROOT)
    selected_ids = set(args.case_id)
    unknown_ids = selected_ids - {case.case_id for case in all_cases}
    if unknown_ids:
        parser.error(f"unknown case IDs: {sorted(unknown_ids)}")
    cases = tuple(case for case in all_cases if not selected_ids or case.case_id in selected_ids)

    results = []
    for index, case in enumerate(cases, start=1):
        print(
            f"[{index}/{len(cases)}] {case.case_id} {case.category} method={case.method}",
            flush=True,
        )
        adapter = MineruCliAdapter(
            executable=args.mineru_python,
            parser_version=MINERU_VERSION,
            project_root=PROJECT_ROOT,
            config_path=args.mineru_config,
            backend="pipeline",
            device="cpu",
            model_source="local",
            formula_enabled=case.category == "formula_dense",
            table_enabled="table" in case.required_block_types,
            worker_script=args.worker_script,
            timeout_seconds=args.timeout_seconds,
        )
        started = time.perf_counter()
        try:
            parsed = adapter.parse_page(
                PROJECT_ROOT / case.pdf_path,
                page_number=case.page_number,
                output_dir=args.raw_output_dir / case.case_id,
                method=case.method,
            )
            result = evaluate_structured_parse_case(case, parsed)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            result = build_structured_parse_error_result(
                case,
                error=f"{type(exc).__name__}: {exc}",
                latency_ms=round(elapsed_ms, 2),
            )
        results.append(result)
        print(
            f"  {result.status}: anchors={result.anchor_recall:.0%}, "
            f"blocks={result.block_count}, latency={result.latency_ms:.0f} ms",
            flush=True,
        )

    config = build_structured_parse_config(
        baseline_id=args.baseline_id,
        dataset_path=args.dataset,
        project_root=PROJECT_ROOT,
        parser_version=MINERU_VERSION,
        backend="pipeline",
        device="cpu",
        worker_mode="isolated subprocess + in-process PDF render compatibility",
        formula_policy="formula_dense only; table model only when required",
    )
    report = build_structured_parse_report(results, config)
    json_path, markdown_path = write_structured_parse_artifacts(
        report,
        baseline_dir=args.baseline_dir,
    )
    print(f"Case pass: {report.case_success_rate:.2%}")
    print(f"Text anchor recall: {report.text_anchor_recall:.2%}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
