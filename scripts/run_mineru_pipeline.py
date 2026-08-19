"""Run MinerU pipeline in-process with a low-memory Windows PDF renderer.

MinerU 3.4.5 always uses a ProcessPoolExecutor for PDF rendering. On Windows,
the spawned renderer imports the full API module and PyTorch again. This worker
keeps rendering in the already isolated process while leaving MinerU's layout,
OCR, table, formula, and output generation pipeline unchanged.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


def _parse_bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value}")


def _use_in_process_pdf_renderer() -> None:
    from mineru.backend.pipeline import pipeline_analyze
    from mineru.utils.pdf_image_tools import load_images_from_pdf_doc

    def load_images_without_process_pool(
        pdf_doc: Any,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        kwargs["pdf_bytes"] = None
        return load_images_from_pdf_doc(pdf_doc, **kwargs)

    pipeline_analyze.load_images_from_pdf_doc = load_images_without_process_pool


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--method", choices=("auto", "txt", "ocr"), required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--formula", type=_parse_bool, required=True)
    parser.add_argument("--table", type=_parse_bool, required=True)
    parser.add_argument("--lang", default="ch")
    args = parser.parse_args()

    if args.start < 0 or args.end < args.start:
        parser.error("page range must satisfy 0 <= start <= end")
    pdf_path = args.path.expanduser().resolve()
    if not pdf_path.is_file() or pdf_path.suffix.casefold() != ".pdf":
        parser.error(f"PDF not found: {pdf_path}")

    _use_in_process_pdf_renderer()
    from mineru.cli.common import do_parse

    do_parse(
        output_dir=str(args.output.expanduser().resolve()),
        pdf_file_names=[pdf_path.stem],
        pdf_bytes_list=[pdf_path.read_bytes()],
        p_lang_list=[args.lang],
        backend="pipeline",
        parse_method=args.method,
        formula_enable=args.formula,
        table_enable=args.table,
        f_draw_layout_bbox=False,
        f_draw_span_bbox=False,
        f_dump_md=True,
        f_dump_middle_json=True,
        f_dump_model_output=False,
        f_dump_orig_pdf=False,
        f_dump_content_list=True,
        start_page_id=args.start,
        end_page_id=args.end,
    )


if __name__ == "__main__":
    main()
