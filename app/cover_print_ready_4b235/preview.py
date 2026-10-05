"""Inspection rasters. They mirror the print layout and are not print files."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.cover.renderer.geometry import CoverGeometry, cover_geometry
from app.cover_print_ready_4b235.fonts import ensure_fonts
from app.cover_print_ready_4b235.guard import assert_output_allowed
from app.cover_print_ready_4b235.layout import FaceLayout


def render_preview(
    path: Path,
    layout: FaceLayout,
    *,
    image_path: Path | None,
    fill: tuple[int, int, int] | None,
    geometry: CoverGeometry | None = None,
) -> None:
    assert_output_allowed(path)
    canvas = geometry or cover_geometry()
    if image_path is not None:
        base = Image.open(image_path).convert("RGB")
    else:
        base = Image.new("RGB", (canvas.full_width_px, canvas.full_height_px), fill or (0, 0, 0))
    draw = ImageDraw.Draw(base)
    _paint(draw, layout, canvas.dpi)
    path.parent.mkdir(parents=True, exist_ok=True)
    base.save(path, format="PNG", dpi=(canvas.dpi, canvas.dpi))


def render_contact_sheet(
    path: Path,
    front_preview: Path,
    back_preview: Path,
    *,
    geometry: CoverGeometry | None = None,
) -> None:
    assert_output_allowed(path)
    canvas = geometry or cover_geometry()
    front = Image.open(front_preview).convert("RGB")
    back = Image.open(back_preview).convert("RGB")
    thumb_h = 980
    front_thumb = _thumb(front, thumb_h)
    back_thumb = _thumb(back, thumb_h)
    _guides(front_thumb, canvas, thumb_h, front.height)
    _guides(back_thumb, canvas, thumb_h, back.height)
    gap = 28
    caption_h = 64
    width = front_thumb.width + gap + back_thumb.width + 48
    sheet = Image.new("RGB", (width, thumb_h + caption_h + 36), (244, 241, 234))
    sheet.paste(front_thumb, (24, 24))
    sheet.paste(back_thumb, (24 + front_thumb.width + gap, 24))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(ensure_fonts()["regular"]), 18)
    draw.text(
        (24, thumb_h + 32),
        "INSPECTION ONLY — NOT A PRINT FILE    red = trim    blue = safe area",
        fill=(40, 40, 40),
        font=font,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, format="PNG")


def _paint(draw: ImageDraw.ImageDraw, layout: FaceLayout, dpi: int) -> None:
    fonts = ensure_fonts()
    scale = dpi / 72
    for line in layout.lines:
        font_path = fonts[{"bold": "bold", "italic": "italic", "regular": "regular"}[line.kind]]
        font = ImageFont.truetype(str(font_path), max(1, int(round(line.size_pt * scale))))
        tracking = line.tracking_pt * scale
        widths = [font.getlength(char) for char in line.text]
        total = sum(widths) + tracking * max(0, len(line.text) - 1)
        if line.align == "center":
            x = ((layout.page_width_in * dpi) - total) / 2
        else:
            x = layout.left_in * dpi
        y = line.baseline_from_top_pt * scale
        for char, width in zip(line.text, widths):
            draw.text((x, y), char, font=font, fill=line.color, anchor="ls")
            x += width + tracking
    for rule in layout.rules:
        y = rule.center_from_top_pt * scale
        center = layout.page_width_in * dpi / 2
        half = rule.width_pt * scale / 2
        draw.line((center - half, y, center + half, y), fill=rule.color, width=2)


def _thumb(image: Image.Image, height: int) -> Image.Image:
    width = max(1, int(round(image.width * height / image.height)))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _guides(image: Image.Image, geometry: CoverGeometry, thumb_h: int, full_h: int) -> None:
    scale = thumb_h / full_h
    bleed_x = ((geometry.full_width_px - geometry.trim_width_px) / 2) * scale
    bleed_y = ((geometry.full_height_px - geometry.trim_height_px) / 2) * scale
    safe = geometry.safety_in * geometry.dpi * scale
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (bleed_x, bleed_y, image.width - bleed_x, image.height - bleed_y),
        outline=(220, 60, 60),
        width=2,
    )
    draw.rectangle(
        (
            bleed_x + safe,
            bleed_y + safe,
            image.width - bleed_x - safe,
            image.height - bleed_y - safe,
        ),
        outline=(40, 90, 180),
        width=2,
    )


__all__ = ["render_contact_sheet", "render_preview"]
