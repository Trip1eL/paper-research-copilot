"""Download and verify the versioned Agent seed corpus."""

import argparse
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import httpx

from paper_research_copilot.config import PROJECT_ROOT
from paper_research_copilot.ingestion import PdfParser, PdfParsingError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--spec",
        type=Path,
        default=PROJECT_ROOT / "corpus" / "v1" / "corpus.json",
    )
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec_path = args.spec.expanduser().resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    version = spec["version"]
    paper_dir = PROJECT_ROOT / "data" / "corpus" / f"v{version}" / "papers"
    paper_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(180.0),
        headers={"User-Agent": "PaperResearchCopilot/0.1 (academic corpus builder)"},
    ) as client:
        for index, paper in enumerate(spec["papers"], start=1):
            filename = f"{paper['arxiv_id']}_{paper['slug']}.pdf"
            pdf_path = paper_dir / filename
            print(f"[{index}/{len(spec['papers'])}] {paper['title']}")
            if args.download and (args.force or not pdf_path.exists()):
                _download(client, paper["source_url"], pdf_path)
            records.append(_verify_paper(spec, paper, pdf_path))

    output_dir = spec_path.parent
    _write_manifest(output_dir / "manifest.jsonl", records)
    _write_report(output_dir / "parse_report.md", spec, records)

    counts = Counter(record["parse_status"] for record in records)
    print(
        "Verification complete: "
        f"verified={counts['verified']}, warning={counts['warning']}, failed={counts['failed']}"
    )
    return 1 if counts["failed"] else 0


def _download(client: httpx.Client, url: str, target: Path) -> None:
    temporary = target.with_suffix(".pdf.part")
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with temporary.open("wb") as output:
                    for chunk in response.iter_bytes(1024 * 1024):
                        output.write(chunk)
            if not _has_pdf_header(temporary):
                raise ValueError(f"Downloaded file is not a PDF: {url}")
            temporary.replace(target)
            print(f"  downloaded: {target.name} ({target.stat().st_size} bytes)")
            return
        except (httpx.HTTPError, OSError, ValueError) as exc:
            last_error = exc
            if temporary.exists():
                temporary.unlink()
            if attempt < 3:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Failed to download {url} after 3 attempts") from last_error


def _verify_paper(
    corpus: dict[str, Any],
    paper: dict[str, Any],
    pdf_path: Path,
) -> dict[str, Any]:
    base_record: dict[str, Any] = {
        "corpus_id": corpus["corpus_id"],
        "corpus_version": corpus["version"],
        "paper_id": paper["paper_id"],
        "arxiv_id": paper["arxiv_id"],
        "arxiv_version": paper["arxiv_version"],
        "slug": paper["slug"],
        "title": paper["title"],
        "topics": paper["topics"],
        "source_url": paper["source_url"],
        "local_path": pdf_path.relative_to(PROJECT_ROOT).as_posix(),
        "verified_on": date.today().isoformat(),
    }
    if not pdf_path.exists():
        return {
            **base_record,
            "parse_status": "failed",
            "warnings": ["缺少 PDF 文件；请使用 --download 下载"],
        }
    if not _has_pdf_header(pdf_path):
        return {
            **base_record,
            "file_size_bytes": pdf_path.stat().st_size,
            "sha256": _sha256(pdf_path),
            "parse_status": "failed",
            "warnings": ["文件不以 PDF header 开头"],
        }

    try:
        document = PdfParser().parse(pdf_path)
    except (PdfParsingError, FileNotFoundError, ValueError) as exc:
        return {
            **base_record,
            "file_size_bytes": pdf_path.stat().st_size,
            "sha256": _sha256(pdf_path),
            "parse_status": "failed",
            "warnings": [f"Parser 解析失败：{exc}"],
        }

    page_metrics = [_page_metrics(page.text) for page in document.pages]
    empty_pages = [
        page.page_number
        for page, metrics in zip(document.pages, page_metrics, strict=True)
        if metrics["char_count"] == 0
    ]
    short_pages = [
        page.page_number
        for page, metrics in zip(document.pages, page_metrics, strict=True)
        if 0 < metrics["char_count"] < 100
    ]
    suspicious_pages = [
        page.page_number
        for page, metrics in zip(document.pages, page_metrics, strict=True)
        if metrics["control_ratio"] > 0.002 or metrics["replacement_ratio"] > 0.001
    ]
    title_similarity = _title_similarity(paper["title"], document.metadata.title)
    title_confirmed = _title_appears_on_first_page(paper["title"], document.pages[0].text)
    warnings: list[str] = []
    if empty_pages:
        warnings.append(f"文本抽取为空的页面：{empty_pages}")
    if short_pages:
        warnings.append(f"文本抽取过短的页面：{short_pages}")
    if suspicious_pages:
        warnings.append(f"包含可疑控制字符或替代字符的页面：{suspicious_pages}")
    if not title_confirmed and title_similarity < 0.55:
        warnings.append(
            f"PDF metadata 和首页文本均未确认预期标题（metadata similarity={title_similarity:.3f}）"
        )

    return {
        **base_record,
        "file_size_bytes": pdf_path.stat().st_size,
        "sha256": document.metadata.document_sha256,
        "parsed_title": document.metadata.title,
        "metadata_title_similarity": round(title_similarity, 4),
        "title_confirmed": title_confirmed,
        "page_count": document.metadata.page_count,
        "extracted_char_count": sum(metrics["char_count"] for metrics in page_metrics),
        "nonempty_page_ratio": round(
            (document.metadata.page_count - len(empty_pages)) / document.metadata.page_count,
            4,
        ),
        "empty_pages": empty_pages,
        "short_pages": short_pages,
        "suspicious_pages": suspicious_pages,
        "parse_status": "warning" if warnings else "verified",
        "warnings": warnings,
    }


def _page_metrics(text: str) -> dict[str, float | int]:
    length = len(text)
    if length == 0:
        return {"char_count": 0, "control_ratio": 0.0, "replacement_ratio": 0.0}
    control_count = sum(
        unicodedata.category(character) == "Cc" and character not in "\n\t" for character in text
    )
    replacement_count = text.count("\ufffd") + sum(
        0xE000 <= ord(character) <= 0xF8FF for character in text
    )
    return {
        "char_count": length,
        "control_ratio": control_count / length,
        "replacement_ratio": replacement_count / length,
    }


def _title_similarity(expected: str, actual: str) -> float:
    return SequenceMatcher(None, _normalize_title(expected), _normalize_title(actual)).ratio()


def _title_appears_on_first_page(expected: str, first_page_text: str) -> bool:
    return _normalize_title(expected) in _normalize_title(first_page_text)


def _normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _has_pdf_header(path: Path) -> bool:
    try:
        with path.open("rb") as file:
            return file.read(5) == b"%PDF-"
    except OSError:
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_manifest(path: Path, records: list[dict[str, Any]]) -> None:
    content = "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
    path.write_text(content, encoding="utf-8")


def _write_report(path: Path, spec: dict[str, Any], records: list[dict[str, Any]]) -> None:
    counts = Counter(record["parse_status"] for record in records)
    lines = [
        f"# Agent Seed Corpus v{spec['version']} Parse 检查报告",
        "",
        f"- Corpus ID：`{spec['corpus_id']}`",
        f"- 检查日期：`{date.today().isoformat()}`",
        f"- 论文数：{len(records)}",
        f"- Verified：{counts['verified']}",
        f"- Warning：{counts['warning']}",
        f"- Failed：{counts['failed']}",
        "",
        "| Paper | arXiv revision | Pages | Extracted chars | "
        "Suspicious pages | Title confirmed | Status |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for record in records:
        suspicious = ", ".join(map(str, record.get("suspicious_pages", []))) or "-"
        lines.append(
            f"| {record['slug']} | {record['arxiv_version']} | "
            f"{record.get('page_count', '-')} | "
            f"{record.get('extracted_char_count', '-')} | {suspicious} | "
            f"{record.get('title_confirmed', '-')} | {record['parse_status']} |"
        )

    warning_records = [record for record in records if record.get("warnings")]
    lines.extend(["", "## 警告详情", ""])
    if not warning_records:
        lines.append("没有检测到 Parse 警告。")
    else:
        for record in warning_records:
            lines.append(f"### {record['title']}")
            lines.append("")
            for warning in record["warnings"]:
                lines.append(f"- {warning}")
            lines.append("")

    lines.extend(
        [
            "## 视觉核验",
            "",
            f"- 状态：`{spec['visual_check']['status']}`",
            f"- 检查日期：`{spec['visual_check']['checked_on']}`",
            f"- 工具：`{spec['visual_check']['tool']}`",
            f"- 已检查首页：{spec['visual_check']['first_pages_checked']}",
            f"- 已检查异常页：{spec['visual_check']['suspicious_pages_checked']}",
            "",
        ]
    )
    for note in spec["visual_check"]["notes"]:
        lines.append(f"- {note}")

    lines.extend(
        [
            "",
            "## 判定规则",
            "",
            "- `verified`：PDF 可打开、全部页面有可提取文本，未检测到明显控制字符或标题异常。",
            "- `warning`：PDF 可以使用，但存在空页、极短页、可疑字符或标题匹配问题。",
            "- `failed`：文件缺失、不是 PDF，或当前 Parser 无法提取有效文本。",
            "- 标题优先通过首页正文确认；PDF 内部 Title metadata 缺失不会单独触发警告。",
            "- 该检查只反映文本抽取质量，不代表 Retrieval 相关性或 Citation 正确性。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
