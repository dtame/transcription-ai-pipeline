"""Local print fonts and line breaks. Nothing is downloaded."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.cover_print_ready_4b235.guard import CoverPrintReady4235Error

_REGISTERED = False


def font_set() -> dict[str, Path | str]:
    windows = Path(r"C:\Windows\Fonts")
    constantia = {
        "regular": windows / "constan.ttf",
        "bold": windows / "constanb.ttf",
        "italic": windows / "constani.ttf",
        "family": "Constantia",
    }
    georgia = {
        "regular": windows / "georgia.ttf",
        "bold": windows / "georgiab.ttf",
        "italic": windows / "georgiai.ttf",
        "family": "Georgia",
    }
    for candidate in (constantia, georgia):
        paths = [candidate["regular"], candidate["bold"], candidate["italic"]]
        if all(isinstance(path, Path) and path.is_file() for path in paths):
            return candidate
    raise CoverPrintReady4235Error("no local Constantia or Georgia font is available. STOP.")


def ensure_fonts() -> dict[str, Path | str]:
    global _REGISTERED
    chosen = font_set()
    if not _REGISTERED:
        pdfmetrics.registerFont(TTFont("CoverSerif", str(chosen["regular"])))
        pdfmetrics.registerFont(TTFont("CoverSerif-Bold", str(chosen["bold"])))
        pdfmetrics.registerFont(TTFont("CoverSerif-Italic", str(chosen["italic"])))
        _REGISTERED = True
    return chosen


def reportlab_name(kind: str) -> str:
    return {
        "regular": "CoverSerif",
        "bold": "CoverSerif-Bold",
        "italic": "CoverSerif-Italic",
    }[kind]


def text_width(text: str, kind: str, size_pt: float, tracking_pt: float) -> float:
    ensure_fonts()
    width = pdfmetrics.stringWidth(text, reportlab_name(kind), size_pt)
    if text and tracking_pt:
        width += tracking_pt * (len(text) - 1)
    return width


@lru_cache(maxsize=64)
def font_metrics(kind: str, size_pt: float) -> tuple[float, float]:
    chosen = ensure_fonts()
    path = chosen[{"regular": "regular", "bold": "bold", "italic": "italic"}[kind]]
    font = ImageFont.truetype(str(path), max(1, int(round(size_pt))))
    ascent, descent = font.getmetrics()
    return float(ascent), float(descent)


def wrap_words(text: str, kind: str, size_pt: float, tracking_pt: float, max_width_pt: float) -> list[str]:
    words = [word for word in str(text or "").split() if word]
    if not words:
        return []
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join([*current, word])
        if current and text_width(trial, kind, size_pt, tracking_pt) > max_width_pt:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def fit_display_title(
    title: str,
    max_width_pt: float,
    max_size: float | None = None,
) -> tuple[list[str], float, float]:
    """Largest size whose balanced line break stays inside the safe width."""
    words = title.upper().split()
    tracking = 0.9
    if not words:
        raise CoverPrintReady4235Error("the cover title is empty")
    sizes = (50, 48, 46, 44, 42, 40, 38, 36, 34, 32, 30, 28, 26, 24, 22)
    fallback: tuple[list[str], float, float] | None = None
    for size in sizes:
        if max_size is not None and size > max_size:
            continue
        candidates: list[tuple[tuple[float, float, int], list[str]]] = []
        for count in (3, 2, 4, 1):
            if count > len(words):
                continue
            for groups in _partitions(words, count):
                lines = [" ".join(group) for group in groups]
                widths = [text_width(line, "bold", size, tracking) for line in lines]
                if max(widths) <= max_width_pt:
                    balance = max(widths) - min(widths)
                    orphans = sum(1 for line in lines[:-1] if " " not in line)
                    candidates.append(((orphans, balance, abs(count - 3), count), lines))
        if not candidates:
            continue
        candidates.sort(key=lambda item: item[0])
        lines = candidates[0][1]
        if fallback is None:
            fallback = (lines, float(size), tracking)
        widths = [text_width(line, "bold", size, tracking) for line in lines]
        ratio = max(widths) / max(min(widths), 1)
        if ratio <= 1.65:
            return lines, float(size), tracking
    if fallback is not None:
        return fallback
    raise CoverPrintReady4235Error("the title does not fit inside the safe area")


def fit_wrapped(
    text: str,
    *,
    kind: str,
    sizes: tuple[float, ...],
    tracking_pt: float,
    max_width_pt: float,
    max_lines: int,
) -> tuple[list[str], float]:
    for size in sizes:
        lines = wrap_words(text, kind, size, tracking_pt, max_width_pt)
        if not lines:
            return [], size
        too_wide = any(text_width(line, kind, size, tracking_pt) > max_width_pt + 0.1 for line in lines)
        if not too_wide and len(lines) <= max_lines:
            return lines, size
    lines = wrap_words(text, kind, sizes[-1], tracking_pt, max_width_pt)
    return lines, sizes[-1]


def _partitions(words: list[str], count: int) -> list[list[list[str]]]:
    if count == 1:
        return [[words]]
    results: list[list[list[str]]] = []

    def walk(start: int, remaining: int, prefix: list[list[str]]) -> None:
        if remaining == 1:
            results.append([*prefix, words[start:]])
            return
        last = len(words) - remaining + 1
        for index in range(start + 1, last + 1):
            walk(index, remaining - 1, [*prefix, words[start:index]])

    walk(0, count, [])
    return results


__all__ = [
    "ensure_fonts",
    "fit_display_title",
    "fit_wrapped",
    "font_metrics",
    "font_set",
    "reportlab_name",
    "text_width",
    "wrap_words",
]
