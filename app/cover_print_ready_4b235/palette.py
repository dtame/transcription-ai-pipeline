"""Choose a dark slate back-cover field from the approved front image."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image


def _luminance(rgb: tuple[int, int, int]) -> float:
    red, green, blue = rgb
    return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def select_back_color(source: Path) -> dict[str, Any]:
    """Median of the dark upper sky, then a cool slate bias. No second image."""
    with Image.open(source) as opened:
        image = opened.convert("RGB")
        width, height = image.size
        band_height = max(1, int(height * 0.22))
        band = image.crop((0, 0, width, band_height))
        raw = band.tobytes()
        pixels = list(zip(raw[0::3], raw[1::3], raw[2::3]))
    dark = [pixel for pixel in pixels if _luminance(pixel) < 90]
    sample = dark or pixels
    reds = sorted(pixel[0] for pixel in sample)
    greens = sorted(pixel[1] for pixel in sample)
    blues = sorted(pixel[2] for pixel in sample)
    mid = len(sample) // 2
    red, green, blue = reds[mid], greens[mid], blues[mid]
    median = (red, green, blue)
    if red > blue:
        red = (red + blue) // 2
    if blue < green:
        blue = green
    while _luminance((red, green, blue)) > 36 and (red > 10 or green > 10 or blue > 10):
        red = int(red * 0.90)
        green = int(green * 0.90)
        blue = int(blue * 0.90)
    if _luminance((red, green, blue)) < 14:
        red = min(255, red + 8)
        green = min(255, green + 10)
        blue = min(255, blue + 14)
    rgb = (max(0, min(255, red)), max(0, min(255, green)), max(0, min(255, blue)))
    return {
        "rgb": list(rgb),
        "hex": _hex(rgb),
        "luminance": round(_luminance(rgb), 2),
        "method": (
            "median_rgb_of_pixels_under_luminance_90_in_the_upper_22_percent"
            "_then_slate_bias_and_darken"
        ),
        "sample_region": "upper_22_percent",
        "sample_count": len(sample),
        "median_before_bias": list(median),
        "second_generated_image": False,
    }


def contrast_ratio(ink: tuple[int, int, int], ground: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        unit = value / 255
        if unit <= 0.04045:
            return unit / 12.92
        return ((unit + 0.055) / 1.055) ** 2.4

    def luminance(rgb: tuple[int, int, int]) -> float:
        red, green, blue = (channel(item) for item in rgb)
        return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)

    lighter = max(luminance(ink), luminance(ground))
    darker = min(luminance(ink), luminance(ground))
    return (lighter + 0.05) / (darker + 0.05)


__all__ = ["contrast_ratio", "select_back_color"]
