"""Run the fast parser router over a frozen Corpus without indexing."""

import argparse

from paper_research_copilot.config import PROJECT_ROOT
from paper_research_copilot.evaluation.corpus_parse_shadow import (
    CorpusShadowPaperResult,
    build_corpus_shadow_config,
    build_corpus_shadow_report,
    run_corpus_parse_shadow,
    write_corpus_shadow_artifacts,
)
from paper_research_copilot.ingestion import CorpusCatalogLoader, FastParserRouter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, default=3)
    parser.add_argument("--report-id", default="parse_shadow_v1")
    args = parser.parse_args()
    if args.version < 1:
        raise ValueError("Corpus version must be positive")

    catalog = CorpusCatalogLoader(PROJECT_ROOT).load(args.version)
    router = FastParserRouter()
    results = run_corpus_parse_shadow(
        catalog,
        router=router,
        progress=_print_progress,
    )
    config = build_corpus_shadow_config(
        report_id=args.report_id,
        catalog=catalog,
        router=router,
    )
    report = build_corpus_shadow_report(results, config)
    json_path, markdown_path = write_corpus_shadow_artifacts(
        report,
        output_dir=PROJECT_ROOT / "corpus" / f"v{args.version}",
    )
    print(
        f"Corpus shadow complete: papers={report.successful_papers}/{report.paper_count}, "
        f"pages={report.page_count}, quarantined={report.selected_quarantined_pages}"
    )
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0 if report.failed_papers == 0 else 1


def _print_progress(result: CorpusShadowPaperResult, index: int, total: int) -> None:
    print(
        f"[{index}/{total}] {result.slug}: {result.status}, "
        f"secondary={result.secondary_selected_pages}, "
        f"quarantined={result.quarantined_pages}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
