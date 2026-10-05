"""Create Book* paragraph styles from a print profile."""

from __future__ import annotations

from typing import Any, Mapping

from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.shared import Inches, Pt, RGBColor

from app.word_renderer.constants import (
    STYLE_BODY,
    STYLE_BODY_FIRST,
    STYLE_CHAPTER_NUMBER,
    STYLE_CHAPTER_TITLE,
    STYLE_DRAFT_NOTICE,
    STYLE_HALF_TITLE,
    STYLE_SECTION_TITLE,
    STYLE_TITLE_PAGE_SUBTITLE,
    STYLE_TITLE_PAGE_TITLE,
    STYLE_TOC_TITLE,
)
from app.word_renderer.oxml import outline_level, set_outline_level, set_rfonts, suppress_hyphenation
from app.word_renderer.profile import style_spec

_ALIGN = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}

REQUIRED_STYLES = (
    STYLE_BODY,
    STYLE_BODY_FIRST,
    STYLE_CHAPTER_TITLE,
    STYLE_CHAPTER_NUMBER,
    STYLE_SECTION_TITLE,
    STYLE_HALF_TITLE,
    STYLE_TITLE_PAGE_TITLE,
    STYLE_TITLE_PAGE_SUBTITLE,
    STYLE_DRAFT_NOTICE,
    STYLE_TOC_TITLE,
)


def apply_styles(doc, profile: Mapping[str, Any]) -> None:
    for name in REQUIRED_STYLES:
        _upsert_style(doc, profile, name)


def _upsert_style(doc, profile: Mapping[str, Any], name: str):
    spec = style_spec(profile, name)
    try:
        style = doc.styles[name]
    except KeyError:
        style = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    based_on = spec.get("based_on")
    if based_on:
        try:
            style.base_style = doc.styles[str(based_on)]
        except KeyError:
            style.base_style = None
    font_name = str(spec.get("font_name") or "Georgia")
    style.font.name = font_name
    set_rfonts(style, font_name)
    if spec.get("font_size_pt") is not None:
        style.font.size = Pt(float(spec["font_size_pt"]))
    if "bold" in spec:
        style.font.bold = bool(spec["bold"])
    if spec.get("italic"):
        style.font.italic = True
    style.font.color.rgb = RGBColor(0, 0, 0)
    fmt = style.paragraph_format
    fmt.alignment = _ALIGN[str(spec.get("alignment") or "left")]
    fmt.space_before = Pt(float(spec.get("space_before_pt") or 0))
    fmt.space_after = Pt(float(spec.get("space_after_pt") or 0))
    line_spacing = spec.get("line_spacing")
    if line_spacing is not None:
        fmt.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        fmt.line_spacing = float(line_spacing)
    indent = float(spec.get("first_line_indent_inches") or 0)
    fmt.first_line_indent = Inches(indent) if indent else None
    fmt.keep_with_next = bool(spec.get("keep_with_next"))
    fmt.widow_control = bool(spec.get("widow_control", True))
    set_outline_level(style, spec.get("outline_level"))
    suppress_hyphenation(style)
    return style


def inspect_style(doc, name: str) -> dict[str, Any]:
    style = doc.styles[name]
    fmt = style.paragraph_format
    font = style.font
    indent = fmt.first_line_indent
    return {
        "name": style.name,
        "font_name": font.name,
        "font_size_pt": font.size.pt if font.size is not None else None,
        "bold": bool(font.bold),
        "italic": bool(font.italic),
        "alignment": str(fmt.alignment),
        "space_before_pt": fmt.space_before.pt if fmt.space_before is not None else 0,
        "space_after_pt": fmt.space_after.pt if fmt.space_after is not None else 0,
        "line_spacing": float(fmt.line_spacing) if fmt.line_spacing is not None else None,
        "first_line_indent_inches": float(indent.inches) if indent is not None else 0.0,
        "keep_with_next": bool(fmt.keep_with_next),
        "widow_control": bool(fmt.widow_control),
        "outline_level": outline_level(style),
        "base_style": style.base_style.name if style.base_style is not None else None,
    }


__all__ = ["REQUIRED_STYLES", "apply_styles", "inspect_style"]
