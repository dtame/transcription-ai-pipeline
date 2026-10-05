"""Typographic placement inside the 6×9 bleed page. No spine and no wraparound."""

from __future__ import annotations

from dataclasses import dataclass

from app.cover.renderer.geometry import CoverGeometry, cover_geometry
from app.cover_print_ready_4b235.constants import (
    DESCRIPTION_STATUS_APPROVED,
    DESCRIPTION_STATUS_PROPOSED,
    DRAFT_INK,
    OFF_WHITE,
)
from app.cover_print_ready_4b235.fonts import fit_display_title, fit_wrapped, font_metrics


@dataclass(frozen=True)
class DrawnLine:
    text: str
    kind: str
    size_pt: float
    tracking_pt: float
    color: tuple[int, int, int]
    align: str
    baseline_from_top_pt: float


@dataclass(frozen=True)
class DrawnRule:
    center_from_top_pt: float
    width_pt: float
    color: tuple[int, int, int]


@dataclass(frozen=True)
class FaceLayout:
    face: str
    page_width_in: float
    page_height_in: float
    left_in: float
    right_in: float
    top_in: float
    bottom_in: float
    content_width_pt: float
    lines: tuple[DrawnLine, ...]
    rules: tuple[DrawnRule, ...]
    text_bottom_from_top_pt: float


def page_inches(geometry: CoverGeometry | None = None) -> tuple[float, float]:
    canvas = geometry or cover_geometry()
    bleed_in = canvas.bleed_mm / 25.4
    return (
        canvas.width_in + (2 * bleed_in),
        canvas.height_in + (2 * bleed_in),
    )


def layout_front(
    *,
    title: str,
    subtitle: str | None,
    author: str | None,
    geometry: CoverGeometry | None = None,
) -> FaceLayout:
    canvas = geometry or cover_geometry()
    page_w, page_h = page_inches(canvas)
    bleed_in = canvas.bleed_mm / 25.4
    side_in = 0.40
    top_in = 0.48
    bottom_in = 0.36
    left = bleed_in + side_in
    content_width = (canvas.width_in - (2 * side_in)) * 72
    origin = (bleed_in + top_in) * 72
    limit = page_h * 72 * 0.42
    max_size: float | None = None
    chosen: tuple[list[str], float, float] | None = None
    while True:
        title_lines, title_size, tracking = fit_display_title(
            title, content_width, max_size=max_size
        )
        chosen = (title_lines, title_size, tracking)
        probe = _stack_front(
            title_lines,
            title_size,
            tracking,
            subtitle,
            content_width,
            origin,
        )
        if probe <= limit or title_size <= 22:
            break
        max_size = title_size - 2
    assert chosen is not None
    title_lines, title_size, tracking = chosen
    lines, bottom = _materialize_front(
        title_lines,
        title_size,
        tracking,
        subtitle,
        author,
        content_width,
        origin,
        page_h * 72,
        (bleed_in + bottom_in) * 72,
    )
    return FaceLayout(
        face="front",
        page_width_in=page_w,
        page_height_in=page_h,
        left_in=left,
        right_in=left,
        top_in=bleed_in + top_in,
        bottom_in=bleed_in + bottom_in,
        content_width_pt=content_width,
        lines=tuple(lines),
        rules=(),
        text_bottom_from_top_pt=bottom,
    )


def layout_back(
    *,
    title: str,
    subtitle: str | None,
    author: str | None,
    description: str | None,
    description_status: str,
    biography: str | None,
    geometry: CoverGeometry | None = None,
) -> FaceLayout:
    canvas = geometry or cover_geometry()
    page_w, page_h = page_inches(canvas)
    bleed_in = canvas.bleed_mm / 25.4
    side_in = 0.58
    top_in = 0.42
    bottom_in = 1.35
    left = bleed_in + side_in
    content_width = (canvas.width_in - (2 * side_in)) * 72
    page_h_pt = page_h * 72
    top_pt = (bleed_in + top_in) * 72
    bottom_pt = (bleed_in + bottom_in) * 72
    body_size = 11.5
    lines: list[DrawnLine] = []
    rules: list[DrawnRule] = []
    for size in (11.5, 11.0, 10.5, 10.0):
        lines, rules, block_bottom = _back_block(
            title=title,
            subtitle=subtitle,
            author=author,
            description=description,
            description_status=description_status,
            biography=biography,
            content_width=content_width,
            origin=top_pt,
            body_size=size,
        )
        block_height = block_bottom - top_pt
        available = page_h_pt - top_pt - bottom_pt
        if block_height <= available or size == 10.0:
            body_size = size
            shift = max(0.0, (available - block_height) * 0.36)
            if block_bottom + shift > page_h_pt - bottom_pt:
                shift = max(0.0, page_h_pt - bottom_pt - block_bottom)
            lines = [_shift_line(line, shift) for line in lines]
            rules = [_shift_rule(rule, shift) for rule in rules]
            block_bottom += shift
            break
    return FaceLayout(
        face="back",
        page_width_in=page_w,
        page_height_in=page_h,
        left_in=left,
        right_in=left,
        top_in=min(line.baseline_from_top_pt for line in lines) / 72 if lines else top_pt / 72,
        bottom_in=bleed_in + bottom_in,
        content_width_pt=content_width,
        lines=tuple(lines),
        rules=tuple(rules),
        text_bottom_from_top_pt=block_bottom,
    )


def _stack_front(title_lines, title_size, tracking, subtitle, content_width, origin) -> float:
    cursor = origin
    for index, text in enumerate(title_lines):
        cursor = _advance(cursor, "bold", title_size, 0 if index == 0 else title_size * 0.06)
    if subtitle:
        wrapped, size = fit_wrapped(
            subtitle,
            kind="italic",
            sizes=(15, 14, 13, 12, 11),
            tracking_pt=0.15,
            max_width_pt=content_width,
            max_lines=4,
        )
        cursor += 12
        for text in wrapped:
            cursor = _advance(cursor, "italic", size, 1)
    _, descent = font_metrics("bold", title_size)
    return cursor + descent


def _materialize_front(
    title_lines,
    title_size,
    tracking,
    subtitle,
    author,
    content_width,
    origin,
    page_h_pt,
    bottom_limit_pt,
) -> tuple[list[DrawnLine], float]:
    lines: list[DrawnLine] = []
    cursor = origin
    for index, text in enumerate(title_lines):
        if index:
            cursor += title_size * 0.06
        baseline = _baseline(cursor, "bold", title_size)
        lines.append(
            DrawnLine(text, "bold", title_size, tracking, OFF_WHITE, "center", baseline)
        )
        cursor = _advance(cursor, "bold", title_size, 0)
    bottom = cursor
    if subtitle:
        wrapped, size = fit_wrapped(
            subtitle,
            kind="italic",
            sizes=(15, 14, 13, 12, 11),
            tracking_pt=0.15,
            max_width_pt=content_width,
            max_lines=4,
        )
        cursor += 12
        for text in wrapped:
            baseline = _baseline(cursor, "italic", size)
            lines.append(
                DrawnLine(text, "italic", size, 0.15, (232, 226, 214), "center", baseline)
            )
            cursor = _advance(cursor, "italic", size, 1)
        bottom = cursor
    if author:
        size = 15.0
        _, descent = font_metrics("regular", size)
        baseline = page_h_pt - bottom_limit_pt - descent
        lines.append(
            DrawnLine(author, "regular", size, 1.4, OFF_WHITE, "center", baseline)
        )
    return lines, bottom


def _back_block(
    *,
    title,
    subtitle,
    author,
    description,
    description_status,
    biography,
    content_width,
    origin,
    body_size,
) -> tuple[list[DrawnLine], list[DrawnRule], float]:
    lines: list[DrawnLine] = []
    rules: list[DrawnRule] = []
    cursor = origin
    title_lines, title_size = fit_wrapped(
        title,
        kind="bold",
        sizes=(22, 20, 18, 16),
        tracking_pt=0.3,
        max_width_pt=content_width,
        max_lines=3,
    )
    for text in title_lines:
        baseline = _baseline(cursor, "bold", title_size)
        lines.append(DrawnLine(text, "bold", title_size, 0.3, OFF_WHITE, "center", baseline))
        cursor = _advance(cursor, "bold", title_size, 2)
    if subtitle:
        cursor += 8
        wrapped, size = fit_wrapped(
            subtitle,
            kind="italic",
            sizes=(12, 11, 10.5),
            tracking_pt=0.1,
            max_width_pt=content_width,
            max_lines=4,
        )
        for text in wrapped:
            baseline = _baseline(cursor, "italic", size)
            lines.append(DrawnLine(text, "italic", size, 0.1, (226, 220, 208), "center", baseline))
            cursor = _advance(cursor, "italic", size, 1)
    if author:
        cursor += 10
        baseline = _baseline(cursor, "regular", 12)
        lines.append(DrawnLine(author, "regular", 12, 0.8, OFF_WHITE, "center", baseline))
        cursor = _advance(cursor, "regular", 12, 0)
    if description:
        cursor += 18
        lines, cursor = _append_body(lines, description, cursor, body_size, content_width)
    if description and biography:
        cursor += 14
        rules.append(DrawnRule(cursor, 42, (186, 178, 164)))
        cursor += 14
        lines, cursor = _append_body(lines, biography, cursor, body_size - 0.5, content_width)
    if description_status != DESCRIPTION_STATUS_APPROVED:
        cursor += 20
        draft_lines = [("PRINT REVIEW DRAFT", 9.0)]
        if description_status == DESCRIPTION_STATUS_PROPOSED:
            draft_lines.append(("Back-cover text not editorially approved", 8.5))
        for text, size in draft_lines:
            baseline = _baseline(cursor, "regular", size)
            lines.append(DrawnLine(text, "regular", size, 0.6, DRAFT_INK, "center", baseline))
            cursor = _advance(cursor, "regular", size, 1)
    _, descent = font_metrics("regular", body_size)
    return lines, rules, cursor + descent


def _append_body(lines, text, cursor, size, content_width):
    paragraphs = [part.strip() for part in str(text).split("\n\n") if part.strip()]
    leading = size * 1.38
    for index, paragraph in enumerate(paragraphs):
        if index:
            cursor += 10
        wrapped = wrap_body(paragraph, size, content_width)
        for text_line in wrapped:
            ascent, descent = font_metrics("regular", size)
            total = max(1.0, ascent + descent)
            baseline = cursor + (ascent / total) * leading
            lines.append(DrawnLine(text_line, "regular", size, 0.0, OFF_WHITE, "left", baseline))
            cursor += leading
    return lines, cursor


def wrap_body(text: str, size: float, content_width: float) -> list[str]:
    from app.cover_print_ready_4b235.fonts import wrap_words

    return wrap_words(text, "regular", size, 0.0, content_width)


def _baseline(cursor: float, kind: str, size: float) -> float:
    ascent, descent = font_metrics(kind, size)
    total = max(1.0, ascent + descent)
    leading = _leading(kind, size)
    return cursor + (ascent / total) * leading


def _advance(cursor: float, kind: str, size: float, extra: float) -> float:
    return cursor + _leading(kind, size) + extra


def _leading(kind: str, size: float) -> float:
    del kind
    return size * 1.08


def _shift_line(line: DrawnLine, shift: float) -> DrawnLine:
    return DrawnLine(
        line.text,
        line.kind,
        line.size_pt,
        line.tracking_pt,
        line.color,
        line.align,
        line.baseline_from_top_pt + shift,
    )


def _shift_rule(rule: DrawnRule, shift: float) -> DrawnRule:
    return DrawnRule(rule.center_from_top_pt + shift, rule.width_pt, rule.color)


__all__ = ["DrawnLine", "DrawnRule", "FaceLayout", "layout_back", "layout_front", "page_inches"]
