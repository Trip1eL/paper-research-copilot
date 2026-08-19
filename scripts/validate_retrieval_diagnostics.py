"""Validate the retrieval diagnostic dataset against the corpus paper IDs."""

import argparse
import json
from pathlib import Path

from paper_research_copilot.config import PROJECT_ROOT
from paper_research_copilot.evaluation import load_retrieval_diagnostics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evals" / "datasets" / "retrieval_diagnostic_v1.jsonl",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=PROJECT_ROOT / "corpus" / "v1" / "corpus.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "corpus" / "v1" / "manifest.jsonl",
    )
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    paper_ids = {paper["paper_id"] for paper in corpus["papers"]}
    manifest = [
        json.loads(line)
        for line in args.manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    page_counts = {record["paper_id"]: record["page_count"] for record in manifest}
    cases = load_retrieval_diagnostics(
        args.dataset,
        allowed_paper_ids=paper_ids,
        paper_page_counts=page_counts,
        paper_aliases={
            paper["paper_id"]: (
                paper["slug"],
                paper["title"],
                paper["title"].partition(":")[0],
            )
            for paper in corpus["papers"]
        },
    )
    print(f"Valid retrieval diagnostic cases: {len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
