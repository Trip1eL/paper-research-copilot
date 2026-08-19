"""Subprocess adapter for an isolated MinerU CLI installation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from collections.abc import Mapping, Sequence
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol, cast

from paper_research_copilot.domain.structured_parse import (
    StructuredBlockType,
    StructuredContentBlock,
    StructuredPageResult,
    StructuredParseMethod,
)


class StructuredParserError(RuntimeError):
    """Raised when MinerU cannot produce a valid structured page result."""


class CommandRunner(Protocol):
    def __call__(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]: ...


def _run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        timeout=timeout,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class MineruCliAdapter:
    """Invoke MinerU out of process so its dependencies never enter the main env."""

    parser_name = "mineru"

    def __init__(
        self,
        *,
        executable: Path,
        parser_version: str,
        project_root: Path,
        config_path: Path,
        backend: str = "pipeline",
        device: str = "cpu",
        model_source: str = "local",
        formula_enabled: bool = False,
        table_enabled: bool = True,
        worker_script: Path | None = None,
        timeout_seconds: float = 900,
        command_runner: CommandRunner = _run_command,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("MinerU timeout_seconds must be positive")
        self.executable = executable.expanduser().resolve()
        self.parser_version = parser_version
        self.project_root = project_root.expanduser().resolve()
        self.config_path = config_path.expanduser().resolve()
        self.backend = backend
        self.device = device
        self.model_source = model_source
        self.formula_enabled = formula_enabled
        self.table_enabled = table_enabled
        self.worker_script = (
            worker_script.expanduser().resolve() if worker_script is not None else None
        )
        self.timeout_seconds = timeout_seconds
        self.command_runner = command_runner

    def parse_page(
        self,
        path: Path,
        *,
        page_number: int,
        output_dir: Path,
        method: StructuredParseMethod,
    ) -> StructuredPageResult:
        pdf_path = path.expanduser().resolve()
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            raise FileNotFoundError(f"Structured parser PDF not found: {pdf_path}")
        if page_number < 1:
            raise ValueError("page_number must be at least 1")
        if not self.executable.is_file():
            raise FileNotFoundError(f"MinerU executable not found: {self.executable}")
        output_root = output_dir.expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)

        command = [str(self.executable)]
        if self.worker_script is not None:
            if not self.worker_script.is_file():
                raise FileNotFoundError(f"MinerU worker script not found: {self.worker_script}")
            command.append(str(self.worker_script))
        command.extend(
            (
                "--path",
                str(pdf_path),
                "--output",
                str(output_root),
                "--method",
                method,
                "--start",
                str(page_number - 1),
                "--end",
                str(page_number - 1),
                "--formula",
                _bool_cli(self.formula_enabled),
                "--table",
                _bool_cli(self.table_enabled),
            )
        )
        if self.worker_script is None:
            command.extend(("--backend", self.backend))
        environment = _isolated_environment(self.executable)
        environment.update(
            {
                "MINERU_DEVICE_MODE": self.device,
                "MINERU_MODEL_SOURCE": self.model_source,
                "MINERU_TOOLS_CONFIG_JSON": str(self.config_path),
                "MINERU_PROCESSING_WINDOW_SIZE": "1",
                "MINERU_API_MAX_CONCURRENT_REQUESTS": "1",
                "MINERU_PDF_RENDER_THREADS": "1",
            }
        )
        started = time.perf_counter()
        try:
            completed = self.command_runner(
                command,
                cwd=self.project_root,
                env=environment,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise StructuredParserError(
                "MinerU timed out after "
                f"{self.timeout_seconds:.0f}s: {pdf_path.name}:p{page_number}"
            ) from exc
        latency_ms = (time.perf_counter() - started) * 1000
        if completed.returncode != 0:
            detail = _last_nonempty_line(completed.stderr) or _last_nonempty_line(completed.stdout)
            raise StructuredParserError(
                f"MinerU failed for {pdf_path.name}:p{page_number}: {detail or 'unknown error'}"
            )

        parse_dir = output_root / pdf_path.stem / method
        content_path = parse_dir / f"{pdf_path.stem}_content_list.json"
        markdown_path = parse_dir / f"{pdf_path.stem}.md"
        if not content_path.is_file() or not markdown_path.is_file():
            raise StructuredParserError(f"MinerU output files are missing under: {parse_dir}")
        content = json.loads(content_path.read_text(encoding="utf-8"))
        if not isinstance(content, list):
            raise StructuredParserError("MinerU content list must be a JSON array")
        ocr_used = True if method == "ocr" else False if method == "txt" else None
        blocks = tuple(
            _normalize_block(
                item,
                block_index=index,
                page_number=page_number,
                parser_version=self.parser_version,
                ocr_used=ocr_used,
            )
            for index, item in enumerate(content, start=1)
            if isinstance(item, dict)
        )
        return StructuredPageResult(
            source_path=str(pdf_path),
            document_sha256=_sha256(pdf_path),
            page_number=page_number,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            backend=self.backend,
            parse_method=method,
            device=self.device,
            latency_ms=round(latency_ms, 2),
            markdown=markdown_path.read_text(encoding="utf-8"),
            blocks=blocks,
            raw_output_dir=str(parse_dir),
        )


def _normalize_block(
    item: dict[str, object],
    *,
    block_index: int,
    page_number: int,
    parser_version: str,
    ocr_used: bool | None,
) -> StructuredContentBlock:
    mineru_type = str(item.get("type", "unknown"))
    block_type = _block_type(mineru_type)
    html = _optional_string(item.get("table_body"))
    text = _block_text(item, html=html)
    raw_bbox = item.get("bbox")
    bbox: tuple[int, int, int, int] | None = None
    if isinstance(raw_bbox, list) and len(raw_bbox) == 4:
        bbox = cast(tuple[int, int, int, int], tuple(int(value) for value in raw_bbox))
    return StructuredContentBlock(
        block_id=f"p{page_number:04d}-b{block_index:04d}",
        page_number=page_number,
        block_type=block_type,
        text=text,
        html=html,
        bbox=bbox,
        parser_name="mineru",
        parser_version=parser_version,
        ocr_used=ocr_used,
    )


def _block_type(mineru_type: str) -> StructuredBlockType:
    mapping: dict[str, StructuredBlockType] = {
        "title": "title",
        "text": "paragraph",
        "list": "list",
        "index": "list",
        "ref_text": "list",
        "table": "table",
        "interline_equation": "formula",
        "equation": "formula",
        "image": "figure",
        "chart": "figure",
        "code": "code",
        "algorithm": "code",
    }
    return mapping.get(mineru_type, "unknown")


def _block_text(item: dict[str, object], *, html: str | None) -> str:
    parts: list[str] = []
    for key in (
        "text",
        "table_caption",
        "table_footnote",
        "image_caption",
        "image_footnote",
        "code_body",
        "code_caption",
        "content",
    ):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
        elif isinstance(value, list):
            parts.extend(str(entry).strip() for entry in value if str(entry).strip())
    if html:
        html_text = _html_text(html)
        if html_text:
            parts.append(html_text)
    return "\n".join(dict.fromkeys(parts))


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def _html_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return " ".join(parser.parts)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _isolated_environment(executable: Path) -> dict[str, str]:
    environment = dict(os.environ)
    for key in tuple(environment):
        if key.casefold().startswith("conda") or key in {"_CE_CONDA", "_CE_M"}:
            environment.pop(key)
    runtime_root = (
        executable.parent.parent
        if executable.parent.name.casefold() in {"scripts", "bin"}
        else executable.parent
    )
    runtime_paths = (
        runtime_root,
        runtime_root / "Scripts",
        runtime_root / "bin",
        runtime_root / "Library" / "bin",
    )
    environment["PATH"] = os.pathsep.join(
        [*(str(path) for path in runtime_paths), environment.get("PATH", "")]
    )
    return environment


def _bool_cli(value: bool) -> str:
    return "true" if value else "false"


def _last_nonempty_line(value: str | None) -> str:
    if not value:
        return ""
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
