"""Generate the deterministic image-only table fixture for Structured Parse Benchmark v1."""

from __future__ import annotations

import argparse
import io
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "evals" / "fixtures" / "parse" / "scanned_agent_table_v1.pdf"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf")
        if bold
        else ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf")
    )
    roots = (
        Path("C:/Windows/Fonts"),
        Path("/usr/share/fonts/truetype/dejavu"),
    )
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _centered_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.ImageFont,
    *,
    fill: str = "#111111",
) -> None:
    left, top, right, bottom = box
    bounds = draw.textbbox((0, 0), text, font=font)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    draw.text(
        (left + (right - left - width) / 2, top + (bottom - top - height) / 2),
        text,
        font=font,
        fill=fill,
    )


def _page_image() -> Image.Image:
    width, height = 1275, 1650
    image = Image.new("RGB", (width, height), "#f8f8f6")
    draw = ImageDraw.Draw(image)
    title_font = _font(42, bold=True)
    body_font = _font(25)
    header_font = _font(24, bold=True)
    small_font = _font(20)

    draw.text((110, 125), "Agent Evaluation Results", font=title_font, fill="#111111")
    draw.text(
        (112, 190),
        "Scanned benchmark table - validation set",
        font=body_font,
        fill="#333333",
    )

    table_left, table_top = 105, 360
    row_height = 105
    column_widths = (330, 220, 220, 295)
    rows = (
        ("System", "Planning", "Tool Use", "Citation Accuracy"),
        ("Baseline RAG", "61.2", "48.5", "72.0"),
        ("ReAct Agent", "74.8", "81.3", "86.4"),
        ("Research Copilot", "88.6", "91.7", "96.2"),
    )
    table_right = table_left + sum(column_widths)
    table_bottom = table_top + row_height * len(rows)
    draw.rectangle((table_left, table_top, table_right, table_bottom), fill="#ffffff")
    draw.rectangle(
        (table_left, table_top, table_right, table_top + row_height),
        fill="#dce6ea",
    )

    y = table_top
    for row_index, row in enumerate(rows):
        x = table_left
        for column_index, (value, column_width) in enumerate(zip(row, column_widths, strict=True)):
            box = (x, y, x + column_width, y + row_height)
            _centered_text(
                draw,
                box,
                value,
                header_font if row_index == 0 else body_font,
            )
            if column_index > 0:
                draw.line((x, table_top, x, table_bottom), fill="#404040", width=3)
            x += column_width
        draw.line((table_left, y, table_right, y), fill="#404040", width=3)
        y += row_height
    draw.rectangle((table_left, table_top, table_right, table_bottom), outline="#303030", width=4)
    draw.line((table_left, table_bottom, table_right, table_bottom), fill="#303030", width=4)

    draw.text(
        (110, table_bottom + 60),
        "All values are percentages. Higher is better.",
        font=small_font,
        fill="#252525",
    )
    draw.text(
        (110, table_bottom + 105),
        "Source: synthetic fixture for deterministic OCR and table-structure evaluation.",
        font=small_font,
        fill="#454545",
    )

    randomizer = random.Random(20260819)
    pixels = image.load()
    for _ in range(6500):
        x = randomizer.randrange(width)
        y = randomizer.randrange(height)
        shade = randomizer.randrange(220, 246)
        pixels[x, y] = (shade, shade, shade)
    return image.rotate(0.18, resample=Image.Resampling.BICUBIC, fillcolor="#f8f8f6").filter(
        ImageFilter.GaussianBlur(radius=0.18)
    )


def generate_fixture(output: Path) -> Path:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    jpeg = io.BytesIO()
    _page_image().save(jpeg, format="JPEG", quality=91, optimize=False, progressive=False)
    jpeg.seek(0)

    pdf = canvas.Canvas(
        str(output),
        pagesize=letter,
        pageCompression=1,
        invariant=1,
    )
    pdf.setTitle("Synthetic Scanned Agent Evaluation Table")
    pdf.setAuthor("Paper Research Copilot")
    pdf.drawImage(ImageReader(jpeg), 0, 0, width=letter[0], height=letter[1])
    pdf.showPage()
    pdf.save()
    return output


def main() -> int:
    output = generate_fixture(build_parser().parse_args().output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
