"""One-page cover PDFs. Images stay Flate-compressed; type is real text."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas

from app.cover_print_ready_4b235.fonts import ensure_fonts, reportlab_name, text_width
from app.cover_print_ready_4b235.guard import assert_output_allowed
from app.cover_print_ready_4b235.layout import FaceLayout


def render_front_pdf(path: Path, layout: FaceLayout, image_path: Path) -> None:
    _render(path, layout, image_path=image_path, fill=None, title="Front cover")


def render_back_pdf(path: Path, layout: FaceLayout, fill: tuple[int, int, int]) -> None:
    _render(path, layout, image_path=None, fill=fill, title="Back cover")


def _render(
    path: Path,
    layout: FaceLayout,
    *,
    image_path: Path | None,
    fill: tuple[int, int, int] | None,
    title: str,
) -> None:
    assert_output_allowed(path)
    ensure_fonts()
    path.parent.mkdir(parents=True, exist_ok=True)
    page = (layout.page_width_in * 72, layout.page_height_in * 72)
    document = canvas.Canvas(str(path), pagesize=page, pageCompression=0)
    document.setTitle(title)
    document.setAuthor("")
    if image_path is not None:
        document.drawImage(
            str(image_path),
            0,
            0,
            width=page[0],
            height=page[1],
            preserveAspectRatio=False,
            mask="auto",
            anchor="sw",
        )
    elif fill is not None:
        document.setFillColor(_color(fill))
        document.rect(0, 0, page[0], page[1], stroke=0, fill=1)
    for line in layout.lines:
        _draw_line(document, layout, line, page[0], page[1])
    for rule in layout.rules:
        _draw_rule(document, rule, page[0], page[1])
    document.showPage()
    document.save()


def _draw_line(document, layout: FaceLayout, line, page_w: float, page_h: float) -> None:
    width = text_width(line.text, line.kind, line.size_pt, line.tracking_pt)
    if line.align == "center":
        origin_x = (page_w - width) / 2
    else:
        origin_x = layout.left_in * 72
    baseline = page_h - line.baseline_from_top_pt
    block = document.beginText()
    block.setTextOrigin(origin_x, baseline)
    block.setFont(reportlab_name(line.kind), line.size_pt)
    block.setFillColor(_color(line.color))
    block.setCharSpace(line.tracking_pt)
    block.textOut(line.text)
    document.drawText(block)


def _draw_rule(document, rule, page_w: float, page_h: float) -> None:
    y = page_h - rule.center_from_top_pt
    document.setStrokeColor(_color(rule.color))
    document.setLineWidth(0.6)
    center = page_w / 2
    document.line(center - (rule.width_pt / 2), y, center + (rule.width_pt / 2), y)


def _color(rgb: tuple[int, int, int]) -> Color:
    return Color(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)


__all__ = ["render_back_pdf", "render_front_pdf"]
