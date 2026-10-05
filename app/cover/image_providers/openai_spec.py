"""Verified OpenAI GPT Image 2 facts used by the sealed cover adapter.

Values were read from official documentation on 2026-10-04. A fact the pages
do not state stays unset. This module does not open a socket.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.cover.renderer.geometry import cover_geometry

PROVIDER_ID = "openai"
OFFICIAL_MODEL_ID = "gpt-image-2"
SNAPSHOT_MODEL_ID = "gpt-image-2-2026-04-21"
ENV_API_KEY = "OPENAI_API_KEY"
AUTH_SCHEME = "Bearer"

API_HOST = "api.openai.com"
GENERATION_URL = "https://api.openai.com/v1/images/generations"

OUTPUT_FORMATS = ("png", "jpeg", "webp")
REQUESTED_OUTPUT_FORMAT = "png"
ACCEPTED_QUALITIES = ("low", "medium", "high")
REFUSED_QUALITIES = ("auto", "xhigh", "max", "standard", "hd")
REQUESTED_QUALITY = "medium"
REQUESTED_BACKGROUND = "opaque"

SELECTED_WIDTH = 1024
SELECTED_HEIGHT = 1536

MIN_PIXELS = 655_360
MAX_PIXELS = 8_294_400
MAX_EDGE_PX = 3840
DIMENSION_MULTIPLE = 16
MAX_LONG_TO_SHORT = 3
EXPERIMENTAL_PIXELS = 3_686_400
PROMPT_MAX_CHARS = 32_000
MAX_IMAGES_PER_REQUEST = 10
PARTIAL_IMAGE_EXTRA_OUTPUT_TOKENS = 100
MAX_IMAGE_BYTES = 32 * 1024 * 1024

DOC_MODEL = "https://developers.openai.com/api/docs/models/gpt-image-2"
DOC_GUIDE = "https://developers.openai.com/api/docs/guides/image-generation"
DOC_PRICING = "https://developers.openai.com/api/docs/pricing"
DOC_REFERENCE = "https://developers.openai.com/api/reference/resources/images/methods/generate"
DOC_PROMPTING = "https://developers.openai.com/api/docs/guides/image-prompting"
DOC_SERVICES = "https://openai.com/policies/services-agreement/"
DOC_SERVICE_TERMS = "https://openai.com/policies/service-terms/"
VERIFIED_ON = "2026-10-04"

# Image-output dollar figures from the guide's comparison table.
# They exclude text input tokens and are rounded estimates, not ceilings.
PUBLISHED_IMAGE_OUTPUT_ESTIMATES_USD = {
    ("1024x1024", "low"): "0.006",
    ("1024x1024", "medium"): "0.053",
    ("1024x1024", "high"): "0.211",
    ("1024x1536", "low"): "0.005",
    ("1024x1536", "medium"): "0.041",
    ("1024x1536", "high"): "0.165",
    ("1536x1024", "low"): "0.005",
    ("1536x1024", "medium"): "0.041",
    ("1536x1024", "high"): "0.165",
}


class SpecError(ValueError):
    """A cover request does not match the verified API limits."""


def size_label(width_px: int, height_px: int) -> str:
    return f"{width_px}x{height_px}"


def api_dimension_problems(width_px: int, height_px: int) -> list[str]:
    """Constraints the image guide and the Images API reference both state."""

    problems: list[str] = []
    if width_px <= 0 or height_px <= 0:
        return ["non_positive"]
    if width_px % DIMENSION_MULTIPLE or height_px % DIMENSION_MULTIPLE:
        problems.append("not_multiple_of_16")
    if width_px > MAX_EDGE_PX or height_px > MAX_EDGE_PX:
        problems.append("edge_above_3840")
    long_edge = max(width_px, height_px)
    short_edge = min(width_px, height_px)
    if short_edge and long_edge > short_edge * MAX_LONG_TO_SHORT:
        problems.append("aspect_ratio_above_3_to_1")
    pixels = width_px * height_px
    if pixels < MIN_PIXELS:
        problems.append("below_655360_pixels")
    if pixels > MAX_PIXELS:
        problems.append("above_8294400_pixels")
    return problems


def cover_dimension_problems(width_px: int, height_px: int) -> list[str]:
    problems = api_dimension_problems(width_px, height_px)
    if height_px <= width_px:
        problems.append("not_portrait")
    return problems


def is_experimental(width_px: int, height_px: int) -> bool:
    """The prompting guide: more than 3,686,400 pixels (2560×1440) is experimental."""

    return width_px * height_px > EXPERIMENTAL_PIXELS


def published_image_output_estimate_usd(width_px: int, height_px: int, quality: str) -> str | None:
    return PUBLISHED_IMAGE_OUTPUT_ESTIMATES_USD.get((size_label(width_px, height_px), quality))


def largest_exact_two_to_three() -> tuple[int, int]:
    """Largest exact 2:3 portrait inside the verified edge and pixel caps."""

    best: tuple[int, int] | None = None
    width = 32
    while width <= MAX_EDGE_PX:
        height = width * 3 // 2
        if (
            width % 32 == 0
            and height <= MAX_EDGE_PX
            and not api_dimension_problems(width, height)
        ):
            best = (width, height)
        width += 32
    if best is None:
        raise SpecError("no legal 2:3 size fits the verified caps")
    return best


def nearest_bleed_size() -> tuple[int, int]:
    """Legal size nearest to the 6×9 trim plus 3 mm bleed, in pixels."""

    geometry = cover_geometry()
    width = _nearest_multiple(geometry.full_width_px)
    height = _nearest_multiple(geometry.full_height_px)
    return width, height


def _nearest_multiple(value: int) -> int:
    multiple = DIMENSION_MULTIPLE
    lower = (value // multiple) * multiple
    upper = lower + multiple
    if abs(value - lower) <= abs(upper - value):
        return lower
    return upper


def candidate_sizes() -> list[dict[str, Any]]:
    geometry = cover_geometry()
    higher = (1536, 2304)
    four_k = (2160, 3840)
    largest = largest_exact_two_to_three()
    bleed = nearest_bleed_size()
    rows = [
        _candidate(SELECTED_WIDTH, SELECTED_HEIGHT, "recommended_portrait", selected=True),
        _candidate(higher[0], higher[1], "higher_exact_two_to_three_under_experimental_pixel_count"),
        _candidate(four_k[0], four_k[1], "documented_4k_portrait"),
        _candidate(largest[0], largest[1], "largest_exact_two_to_three_inside_caps"),
        _candidate(bleed[0], bleed[1], "nearest_legal_size_to_bleed_canvas"),
        _candidate(1024, 1024, "recommended_square"),
        _candidate(1536, 1024, "recommended_landscape"),
    ]
    for row in rows:
        row["bleed_canvas_px"] = [geometry.full_width_px, geometry.full_height_px]
    return rows


def _candidate(width: int, height: int, role: str, *, selected: bool = False) -> dict[str, Any]:
    pixels = width * height
    return {
        "role": role,
        "selected": selected,
        "width": width,
        "height": height,
        "size": size_label(width, height),
        "pixels": pixels,
        "ratio": _ratio_text(width, height),
        "exact_two_to_three": height * 2 == width * 3,
        "api_problems": api_dimension_problems(width, height),
        "accepted_by_verified_constraints": not api_dimension_problems(width, height),
        "experimental": is_experimental(width, height),
        "published_image_output_estimates_usd": {
            quality: published_image_output_estimate_usd(width, height, quality)
            for quality in ACCEPTED_QUALITIES
        },
        "print": _print_placement(width, height),
    }


def print_resolution_plan() -> dict[str, Any]:
    geometry = cover_geometry()
    selected = _print_placement(SELECTED_WIDTH, SELECTED_HEIGHT)
    return {
        "trim_in": [geometry.width_in, geometry.height_in],
        "dpi_target": geometry.dpi,
        "bleed_mm": geometry.bleed_mm,
        "trim_px": [geometry.trim_width_px, geometry.trim_height_px],
        "bleed_canvas_px": [geometry.full_width_px, geometry.full_height_px],
        "trim_aspect": geometry.aspect_ratio,
        "selected_size": size_label(SELECTED_WIDTH, SELECTED_HEIGHT),
        "selected_quality": REQUESTED_QUALITY,
        "selected_output_format": REQUESTED_OUTPUT_FORMAT,
        "selected_background": REQUESTED_BACKGROUND,
        "placement": selected,
        "professional_print_quality_guaranteed": False,
        "sharpness_requires_visual_inspection": True,
        "interior_format_modified": False,
        "flux_limits_reused": False,
    }


def submission_body(request: Any) -> dict[str, Any]:
    """JSON object for one text-only Images API generation. No reference images."""

    problems = request_problems(request)
    if problems:
        raise SpecError(",".join(problems))
    quality = str(request.metadata["quality"])
    output_format = str(request.metadata["output_format"])
    background = str(request.metadata["background"])
    return {
        "model": OFFICIAL_MODEL_ID,
        "prompt": request.prompt,
        "n": 1,
        "size": size_label(request.width_px, request.height_px),
        "quality": quality,
        "output_format": output_format,
        "background": background,
    }


def request_problems(request: Any) -> list[str]:
    problems = cover_dimension_problems(int(request.width_px), int(request.height_px))
    metadata = getattr(request, "metadata", None) or {}
    quality = metadata.get("quality")
    output_format = metadata.get("output_format")
    background = metadata.get("background")
    if request.model_name != OFFICIAL_MODEL_ID:
        problems.append("model_not_authorized")
    if quality not in ACCEPTED_QUALITIES:
        problems.append("quality_not_accepted")
    if output_format not in OUTPUT_FORMATS:
        problems.append("output_format_not_accepted")
    if output_format != REQUESTED_OUTPUT_FORMAT:
        problems.append("output_format_not_png")
    if background != REQUESTED_BACKGROUND:
        problems.append("background_not_opaque")
    if metadata.get("reference_images"):
        problems.append("reference_images_not_allowed")
    if metadata.get("stream") or metadata.get("partial_images"):
        problems.append("streaming_not_allowed")
    prompt = str(getattr(request, "prompt", "") or "")
    if len(prompt) > PROMPT_MAX_CHARS:
        problems.append("prompt_above_32000_characters")
    if int(getattr(request, "image_count", 0) or 0) != 1:
        problems.append("endpoint_sends_one_image")
    return problems


def _print_placement(width: int, height: int) -> dict[str, Any]:
    geometry = cover_geometry()
    trim_scale = _div(geometry.trim_width_px, width)
    trim_ppi = _div(width, geometry.width_in)
    bleed_scale_w = Decimal(geometry.full_width_px) / Decimal(width)
    bleed_scale_h = Decimal(geometry.full_height_px) / Decimal(height)
    cover_scale = max(bleed_scale_w, bleed_scale_h)
    return {
        "trim_effective_ppi": _money(trim_ppi, "0.01"),
        "upscale_factor_to_trim": _money(trim_scale, "0.0001"),
        "below_300_ppi_on_trim": trim_ppi < Decimal(geometry.dpi),
        "bleed_cover_scale": _money(cover_scale, "0.0001"),
        "bleed_effective_ppi": _money(Decimal(geometry.dpi) / cover_scale, "0.01"),
        "crop": "uniform cover-crop onto the bleed canvas; the 2:3 frame is slightly taller than the bleed rectangle",
        "pixels": width * height,
    }


def _div(numerator: int | float, denominator: int | float) -> Decimal:
    return Decimal(str(numerator)) / Decimal(str(denominator))


def _money(value: Decimal, places: str) -> str:
    return format(value.quantize(Decimal(places), rounding=ROUND_HALF_UP), "f")


def _ratio_text(width: int, height: int) -> str:
    if height * 2 == width * 3:
        return "2:3"
    return _money(Decimal(width) / Decimal(height), "0.000001")


__all__ = [
    "ACCEPTED_QUALITIES",
    "API_HOST",
    "AUTH_SCHEME",
    "DIMENSION_MULTIPLE",
    "DOC_GUIDE",
    "DOC_MODEL",
    "DOC_PRICING",
    "DOC_PROMPTING",
    "DOC_REFERENCE",
    "DOC_SERVICE_TERMS",
    "DOC_SERVICES",
    "ENV_API_KEY",
    "EXPERIMENTAL_PIXELS",
    "GENERATION_URL",
    "MAX_EDGE_PX",
    "MAX_IMAGE_BYTES",
    "MAX_IMAGES_PER_REQUEST",
    "MAX_PIXELS",
    "MIN_PIXELS",
    "OFFICIAL_MODEL_ID",
    "OUTPUT_FORMATS",
    "PARTIAL_IMAGE_EXTRA_OUTPUT_TOKENS",
    "PROMPT_MAX_CHARS",
    "PROVIDER_ID",
    "PUBLISHED_IMAGE_OUTPUT_ESTIMATES_USD",
    "REQUESTED_BACKGROUND",
    "REQUESTED_OUTPUT_FORMAT",
    "REQUESTED_QUALITY",
    "SELECTED_HEIGHT",
    "SELECTED_WIDTH",
    "SNAPSHOT_MODEL_ID",
    "SpecError",
    "VERIFIED_ON",
    "api_dimension_problems",
    "candidate_sizes",
    "cover_dimension_problems",
    "is_experimental",
    "largest_exact_two_to_three",
    "nearest_bleed_size",
    "print_resolution_plan",
    "published_image_output_estimate_usd",
    "request_problems",
    "size_label",
    "submission_body",
]
