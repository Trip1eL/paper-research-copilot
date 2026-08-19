import pytest
from pydantic import ValidationError

from paper_research_copilot.domain import StructuredContentBlock, StructuredPageResult


def test_structured_block_requires_normalized_positive_bbox() -> None:
    with pytest.raises(ValidationError, match="positive width"):
        StructuredContentBlock(
            block_id="p0001-b0001",
            page_number=1,
            block_type="paragraph",
            text="evidence",
            bbox=(500, 100, 400, 200),
            parser_name="mineru",
            parser_version="3.4.5",
        )


def test_structured_page_rejects_block_from_another_page() -> None:
    block = StructuredContentBlock(
        block_id="p0002-b0001",
        page_number=2,
        block_type="paragraph",
        text="evidence",
        parser_name="mineru",
        parser_version="3.4.5",
    )

    with pytest.raises(ValidationError, match="must match"):
        StructuredPageResult(
            source_path="paper.pdf",
            document_sha256="0" * 64,
            page_number=1,
            parser_name="mineru",
            parser_version="3.4.5",
            backend="pipeline",
            parse_method="ocr",
            device="cpu",
            latency_ms=1,
            markdown="text",
            blocks=(block,),
            raw_output_dir="tmp/output",
        )
