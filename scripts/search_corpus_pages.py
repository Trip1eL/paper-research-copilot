"""Search parsed corpus pages to support human evaluation annotation."""

import argparse
import re

from paper_research_copilot.config import PROJECT_ROOT
from paper_research_copilot.ingestion import CorpusCatalogLoader, PdfParser


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--paper", required=True, help="Paper slug, paper_id, or arXiv ID")
    parser.add_argument("--query", action="append", required=True)
    parser.add_argument("--context-chars", type=int, default=220)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.version < 1:
        raise ValueError("Version must be positive")
    if args.context_chars < 20:
        raise ValueError("Context chars must be at least 20")

    catalog = CorpusCatalogLoader(PROJECT_ROOT).load(args.version)
    matches = [
        asset
        for asset in catalog.papers
        if args.paper in {asset.spec.slug, asset.spec.paper_id, asset.spec.arxiv_id}
    ]
    if len(matches) != 1:
        raise LookupError(f"Expected one paper for {args.paper!r}, found {len(matches)}")

    asset = matches[0]
    document = PdfParser().parse(asset.pdf_path)
    queries = tuple(query.casefold() for query in args.query)
    print(f"Paper: {asset.spec.slug} ({asset.spec.paper_id})")
    print(f"Queries: {', '.join(args.query)}")
    hit_count = 0
    for page in document.pages:
        normalized = re.sub(r"\s+", " ", page.text).strip()
        folded = normalized.casefold()
        page_hits = [(query, folded.find(query)) for query in queries if query in folded]
        if not page_hits:
            continue
        hit_count += 1
        first_index = min(index for _, index in page_hits)
        start = max(0, first_index - args.context_chars)
        end = min(len(normalized), first_index + args.context_chars)
        labels = ", ".join(query for query, _ in page_hits)
        print(f"\nPage {page.page_number} | matched: {labels}")
        print(normalized[start:end])

    print(f"\nMatched pages: {hit_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
