"""Trim, bleed, and safety geometry for two separate 6×9 covers."""

from __future__ import annotations

from dataclasses import dataclass

from app.cover.constants import (
    DEFAULT_BLEED_MM,
    DEFAULT_DPI,
    DEFAULT_SAFETY_IN,
    MM_PER_INCH,
    TRIM_HEIGHT_IN,
    TRIM_WIDTH_IN,
)


@dataclass(frozen=True)
class CoverGeometry:
    width_in: float
    height_in: float
    bleed_mm: float
    safety_in: float
    dpi: int
    trim_width_px: int
    trim_height_px: int
    full_width_px: int
    full_height_px: int
    bleed_width_px: int
    bleed_height_px: int
    safety_width_px: int
    safety_height_px: int
    aspect_ratio: str

    def to_dict(self) -> dict[str, int | float | str | bool]:
        return {
            "width_in": self.width_in,
            "height_in": self.height_in,
            "bleed_mm": self.bleed_mm,
            "safety_in": self.safety_in,
            "dpi": self.dpi,
            "trim_width_px": self.trim_width_px,
            "trim_height_px": self.trim_height_px,
            "full_width_px": self.full_width_px,
            "full_height_px": self.full_height_px,
            "bleed_width_px": self.bleed_width_px,
            "bleed_height_px": self.bleed_height_px,
            "safety_width_px": self.safety_width_px,
            "safety_height_px": self.safety_height_px,
            "aspect_ratio": self.aspect_ratio,
            "printer_universal": False,
        }


def cover_geometry(
    *,
    width_in: float = TRIM_WIDTH_IN,
    height_in: float = TRIM_HEIGHT_IN,
    bleed_mm: float = DEFAULT_BLEED_MM,
    safety_in: float = DEFAULT_SAFETY_IN,
    dpi: int = DEFAULT_DPI,
) -> CoverGeometry:
    if width_in <= 0 or height_in <= 0 or dpi <= 0:
        raise ValueError("cover dimensions and dpi must be positive")
    if bleed_mm < 0 or safety_in < 0:
        raise ValueError("bleed and safety insets cannot be negative")
    bleed_in = bleed_mm / MM_PER_INCH
    trim_w = _round_px(width_in * dpi)
    trim_h = _round_px(height_in * dpi)
    full_w = _round_px((width_in + (2 * bleed_in)) * dpi)
    full_h = _round_px((height_in + (2 * bleed_in)) * dpi)
    safety_inset = _round_px(safety_in * dpi)
    return CoverGeometry(
        width_in=width_in,
        height_in=height_in,
        bleed_mm=bleed_mm,
        safety_in=safety_in,
        dpi=dpi,
        trim_width_px=trim_w,
        trim_height_px=trim_h,
        full_width_px=full_w,
        full_height_px=full_h,
        bleed_width_px=full_w - trim_w,
        bleed_height_px=full_h - trim_h,
        safety_width_px=trim_w - (2 * safety_inset),
        safety_height_px=trim_h - (2 * safety_inset),
        aspect_ratio=_ratio(width_in, height_in),
    )


def _round_px(value: float) -> int:
    return int(value + 0.5)


def _ratio(width_in: float, height_in: float) -> str:
    if abs(width_in - 6.0) < 1e-9 and abs(height_in - 9.0) < 1e-9:
        return "2:3"
    return f"{width_in:g}:{height_in:g}"


__all__ = ["CoverGeometry", "cover_geometry"]
