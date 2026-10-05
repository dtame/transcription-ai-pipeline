"""Verified Black Forest Labs facts used by the sealed FLUX.2 [pro] adapter.

Values here were read from official documentation. Anything the docs do not
state is left unset and marked UNVERIFIED by the caller. This module does
not open a socket.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from app.cover.renderer.geometry import cover_geometry

PROVIDER_ID = "black_forest_labs"
OFFICIAL_MODEL_ID = "flux-2-pro"
PREVIEW_MODEL_ID_NOT_SELECTED = "flux-2-pro-preview"
ENV_API_KEY = "BFL_API_KEY"
AUTH_HEADER = "x-key"

API_HOST = "api.bfl.ai"
POLL_HOSTS = frozenset({API_HOST, "api.eu.bfl.ai", "api.us.bfl.ai"})
SUBMIT_URL = "https://api.bfl.ai/v1/flux-2-pro"
OUTPUT_FORMATS = ("jpeg", "png", "webp")
REQUESTED_OUTPUT_FORMAT = "png"

MIN_EDGE_PX = 64
DIMENSION_MULTIPLE = 16
# Help center: maximum 4 megapixels. The billing example treats 1920×1080 as
# 2.07MP, which is pixels / 1_000_000. The same pages also give 2048×2048 as
# an example of that maximum. That square is 4,194,304 pixels. A request is
# refused above the stricter decimal ceiling so 1664×2496 cannot be sent.
MAX_PIXELS = 4_000_000
DOCUMENTED_SQUARE_EXAMPLE = (2048, 2048)
REJECTED_PRIOR_GENERATION_SIZE = (1664, 2496)

PENDING_STATUSES = frozenset({"Pending", "Reasoning", "Generating"})
READY_STATUS = "Ready"
# "Failed" appears in the quick-start guide and is absent from the OpenAPI
# StatusResponse enum. It is treated as terminal so it cannot be retried.
TERMINAL_FAILURE_STATUSES = frozenset(
    {
        "Error",
        "Failed",
        "Request Moderated",
        "Content Moderated",
        "Task not found",
    }
)

CREDIT_USD = 0.01
PUBLISHED_TEXT_TO_IMAGE_FLOOR_USD = 0.03
PUBLISHED_EDITING_FLOOR_USD = 0.045
SIGNED_URL_MINUTES = 10
ACTIVE_TASK_LIMIT = 24
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024

DELIVERY_HOST = re.compile(r"^delivery\.[a-z0-9-]+\.bfl\.ai$")

DOC_SUBMIT = "https://docs.bfl.ai/api-reference/models/generate-or-edit-an-image-with-flux2-%5Bpro%5D"
DOC_TEXT_TO_IMAGE = "https://docs.bfl.ai/flux_2/flux2_text_to_image"
DOC_GUIDE = "https://docs.bfl.ai/api_integration/integration_guidelines"
DOC_ERRORS = "https://docs.bfl.ai/api_integration/errors"
DOC_GET_RESULT = "https://docs.bfl.ai/api-reference/utility/get-result"
DOC_PRICING = "https://docs.bfl.ai/quick_start/pricing"
DOC_SPECS = "https://help.bfl.ai/articles/6944273991-what-are-the-flux-2-technical-specifications"
DOC_DIMENSIONS = "https://help.bfl.ai/articles/8916739058-what-aspect-ratios-and-output-dimensions-are-supported"
DOC_COSTS = "https://help.bfl.ai/articles/7986977817-what-are-the-costs-associated-with-using-your-models"
DOC_COMMERCIAL = "https://help.bfl.ai/articles/4375863104-can-i-use-the-api-for-a-commercial-application"
DOC_USAGE_POLICY = "https://bfl.ai/legal/usage-policy"
DOC_EU_DEVELOPER_TERMS = "https://bfl.ai/legal/eu-developer-terms-of-service"
DOC_EU_API_TERMS = "https://bfl.ai/legal/eu-api-service-terms"
DOC_OVERVIEW = "https://docs.bfl.ai/flux_2/flux2_overview"
DOC_DEVELOPER_TERMS = "https://bfl.ai/legal/developer-terms-of-service"
DOC_API_TERMS = "https://bfl.ai/legal/flux-api-service-terms"
TERMS_FEE_URL_UNVERIFIED = "https://bfl.ai/pricing/api/"
VERIFIED_ON = "2026-10-04"


class SpecError(ValueError):
    """A cover request does not match the verified API limits."""


def largest_portrait_generation_size() -> tuple[int, int]:
    """Largest 2:3 image whose edges are legal and whose area is within the cap."""

    best: tuple[int, int] | None = None
    width = MIN_EDGE_PX
    while width <= 2048:
        if width % 32 == 0:
            height = width * 3 // 2
            if (
                height % DIMENSION_MULTIPLE == 0
                and height >= MIN_EDGE_PX
                and width * height <= MAX_PIXELS
            ):
                best = (width, height)
        width += DIMENSION_MULTIPLE
    if best is None:
        raise SpecError("no legal 2:3 generation size fits the verified pixel cap")
    return best


def dimension_problems(width_px: int, height_px: int) -> list[str]:
    problems: list[str] = []
    if width_px < MIN_EDGE_PX or height_px < MIN_EDGE_PX:
        problems.append("below_minimum_edge")
    if width_px % DIMENSION_MULTIPLE or height_px % DIMENSION_MULTIPLE:
        problems.append("not_multiple_of_16")
    if width_px * height_px > MAX_PIXELS:
        problems.append("above_4_000_000_pixel_cap")
    if height_px <= width_px:
        problems.append("not_portrait")
    return problems


def dimension_problem(width_px: int, height_px: int) -> str | None:
    problems = dimension_problems(width_px, height_px)
    return problems[0] if problems else None


def submission_body(request: Any) -> dict[str, Any]:
    """Build the verified JSON object. Negative prompts are not a field."""

    problem = dimension_problem(request.width_px, request.height_px)
    if problem:
        raise SpecError(problem)
    body: dict[str, Any] = {
        "prompt": request.prompt,
        "width": request.width_px,
        "height": request.height_px,
        "output_format": REQUESTED_OUTPUT_FORMAT,
        "disable_pup": True,
    }
    if request.seed is not None:
        body["seed"] = request.seed
    return body


def validate_polling_url(url: str) -> str:
    parts = urlsplit(str(url or "").strip())
    if parts.scheme != "https" or parts.hostname not in POLL_HOSTS:
        raise SpecError("polling_url_host_not_allowed")
    if parts.path != "/v1/get_result" or "id=" not in (parts.query or ""):
        raise SpecError("polling_url_path_not_allowed")
    if parts.username or parts.password:
        raise SpecError("polling_url_credentials_not_allowed")
    return url


def validate_delivery_url(url: str) -> str:
    parts = urlsplit(str(url or "").strip())
    host = parts.hostname or ""
    if parts.scheme != "https" or not DELIVERY_HOST.match(host):
        raise SpecError("delivery_url_not_allowed")
    if parts.username or parts.password:
        raise SpecError("delivery_url_credentials_not_allowed")
    return url


def print_resolution_plan() -> dict[str, Any]:
    geometry = cover_geometry()
    generation = largest_portrait_generation_size()
    scaling = print_scaling_analysis()
    trim_problem = dimension_problems(geometry.trim_width_px, geometry.trim_height_px)
    bleed_problem = dimension_problems(geometry.full_width_px, geometry.full_height_px)
    return {
        "trim_in": [geometry.width_in, geometry.height_in],
        "dpi": geometry.dpi,
        "bleed_mm": geometry.bleed_mm,
        "trim_px": [geometry.trim_width_px, geometry.trim_height_px],
        "bleed_canvas_px": [geometry.full_width_px, geometry.full_height_px],
        "aspect_ratio": geometry.aspect_ratio,
        "api_generation_px": list(generation),
        "api_generation_pixels": generation[0] * generation[1],
        "pixel_cap": MAX_PIXELS,
        "trim_rejected_because": trim_problem,
        "bleed_canvas_rejected_because": bleed_problem,
        "uniform_cover_scale": scaling["uniform_cover_scale"],
        "upscale_is_not_quality_proof": True,
        "sharpness_inspection_required": True,
        "professional_print_quality_guaranteed": False,
        "interior_format_modified": False,
        "strategy": (
            "Request the largest exact 2:3 PNG that stays at or under "
            "4,000,000 pixels. Place it on the bleed canvas with a uniform "
            "cover-crop. Do not stretch it to the bleed ratio. Inspect "
            "sharpness before any print file is approved."
        ),
    }


def selected_generation_record() -> dict[str, Any]:
    width, height = largest_portrait_generation_size()
    pixels = width * height
    prior_w, prior_h = REJECTED_PRIOR_GENERATION_SIZE
    square_w, square_h = DOCUMENTED_SQUARE_EXAMPLE
    return {
        "model_id": OFFICIAL_MODEL_ID,
        "width": width,
        "height": height,
        "pixels": pixels,
        "width_times_height": f"{width} × {height} = {pixels}",
        "width_over_height": _ratio_text(width, height),
        "aspect_ratio": "2:3",
        "exact_two_to_three": height * 2 == width * 3,
        "multiple_of": DIMENSION_MULTIPLE,
        "pixel_cap": MAX_PIXELS,
        "within_cap": pixels <= MAX_PIXELS,
        "orientation": "portrait",
        "output_format": REQUESTED_OUTPUT_FORMAT,
        "rejected_prior_size": {
            "width": prior_w,
            "height": prior_h,
            "pixels": prior_w * prior_h,
            "problems": dimension_problems(prior_w, prior_h),
        },
        "documented_square_example": {
            "width": square_w,
            "height": square_h,
            "pixels": square_w * square_h,
            "above_strict_cap": square_w * square_h > MAX_PIXELS,
            "requested": False,
        },
    }


def resolution_constraints() -> dict[str, Any]:
    return {
        "consulted_on": VERIFIED_ON,
        "sources": [DOC_SPECS, DOC_DIMENSIONS, DOC_SUBMIT],
        "minimum_edge_px": MIN_EDGE_PX,
        "minimum_image": [MIN_EDGE_PX, MIN_EDGE_PX],
        "dimension_multiple": DIMENSION_MULTIPLE,
        "maximum_pixels_enforced": MAX_PIXELS,
        "documented_wording": "4 megapixels (e.g., 2048×2048)",
        "documented_square_example_pixels": 2048 * 2048,
        "aspect_ratio": "any, including portrait; no separate portrait limit",
        "default_size": [1024, 1024],
        "recommended_by_vendor_for_quality_and_speed": "at or below 2 megapixels",
        "over_cap_behavior": (
            "The help center says images over 4MP are automatically resized. "
            "It does not promise a rejection. This adapter refuses the request "
            "before any call so a silent resize cannot change the billed size."
        ),
        "below_minimum_behavior": (
            "OpenAPI sets width and height minimum to 64. A schema failure is "
            "an HTTP 422 validation error."
        ),
        "non_multiple_behavior": (
            "The help center requires multiples of 16. The published OpenAPI "
            "schema does not repeat that rule. This adapter rejects a "
            "non-multiple before any call. The pages read do not name the "
            "HTTP status the API would return for that case."
        ),
        "selected": selected_generation_record(),
    }


def print_scaling_analysis() -> dict[str, Any]:
    """How the selected PNG would cover a 6×9 page with 3 mm bleed."""

    from decimal import Decimal, ROUND_HALF_UP

    geometry = cover_geometry()
    width, height = largest_portrait_generation_size()
    full_w = geometry.full_width_px
    full_h = geometry.full_height_px
    scale_w = Decimal(full_w) / Decimal(width)
    scale_h = Decimal(full_h) / Decimal(height)
    scale = max(scale_w, scale_h)
    used_w = Decimal(full_w) / scale
    used_h = Decimal(full_h) / scale
    bleed_in = Decimal(str(geometry.bleed_mm)) / Decimal("25.4")
    physical_w = Decimal(str(geometry.width_in)) + (bleed_in * 2)
    physical_h = Decimal(str(geometry.height_in)) + (bleed_in * 2)
    four = Decimal("0.0001")
    two = Decimal("0.01")

    def q(value: Decimal, places: Decimal) -> str:
        return format(value.quantize(places, rounding=ROUND_HALF_UP), "f")

    return {
        "generation_px": [width, height],
        "generation_pixels": width * height,
        "source_ratio_width_over_height": q(Decimal(width) / Decimal(height), four),
        "trim_ratio_width_over_height": q(
            Decimal(geometry.trim_width_px) / Decimal(geometry.trim_height_px),
            four,
        ),
        "bleed_canvas_px": [full_w, full_h],
        "bleed_ratio_width_over_height": q(Decimal(full_w) / Decimal(full_h), four),
        "uniform_cover_scale": float(round(float(scale), 4)),
        "uniform_cover_scale_exact": q(scale, four),
        "scale_driven_by": "width" if scale_w >= scale_h else "height",
        "source_pixels_used": [q(used_w, two), q(used_h, two)],
        "source_pixels_cropped": [q(Decimal(width) - used_w, two), q(Decimal(height) - used_h, two)],
        "crop": (
            "Uniform scale covers the bleed canvas. The source is exact 2:3 and "
            "the bleed canvas is slightly wider, so a thin strip is cropped from "
            "the top and bottom. The image is not stretched."
        ),
        "physical_bleed_inches": [q(physical_w, four), q(physical_h, four)],
        "effective_ppi_across_width": q(Decimal(width) / physical_w, two),
        "target_canvas_ppi": geometry.dpi,
        "effective_ppi_below_target": True,
        "vendor_recommends_at_or_below_2mp": True,
        "selected_size_is_near_4mp": True,
        "professional_print_quality_guaranteed": False,
        "sharpness_inspection_required": True,
        "risks": [
            "The placed image samples the physical cover at about 262 ppi, below the 300 ppi canvas.",
            "The enlargement is about 1.15×. It is not evidence of print sharpness.",
            "Black Forest Labs recommends staying at or below 2MP for quality and speed. This request is the largest legal 2:3 size, near 4MP.",
            "A real image has not been inspected.",
        ],
    }


def _ratio_text(width: int, height: int) -> str:
    from decimal import Decimal, ROUND_HALF_UP

    quantized = (Decimal(width) / Decimal(height)).quantize(
        Decimal("0.000001"),
        rounding=ROUND_HALF_UP,
    )
    return format(quantized, "f")


__all__ = [
    "ACTIVE_TASK_LIMIT",
    "API_HOST",
    "AUTH_HEADER",
    "CREDIT_USD",
    "DELIVERY_HOST",
    "DOC_API_TERMS",
    "DOC_COMMERCIAL",
    "DOC_COSTS",
    "DOC_DEVELOPER_TERMS",
    "DOC_DIMENSIONS",
    "DOC_EU_API_TERMS",
    "DOC_EU_DEVELOPER_TERMS",
    "DOC_OVERVIEW",
    "DOC_USAGE_POLICY",
    "DOC_ERRORS",
    "DOC_GET_RESULT",
    "DOC_GUIDE",
    "DOC_PRICING",
    "DOC_SPECS",
    "DOC_SUBMIT",
    "DOC_TEXT_TO_IMAGE",
    "ENV_API_KEY",
    "DOCUMENTED_SQUARE_EXAMPLE",
    "MAX_DOWNLOAD_BYTES",
    "MAX_PIXELS",
    "REJECTED_PRIOR_GENERATION_SIZE",
    "OFFICIAL_MODEL_ID",
    "OUTPUT_FORMATS",
    "PENDING_STATUSES",
    "POLL_HOSTS",
    "PREVIEW_MODEL_ID_NOT_SELECTED",
    "PROVIDER_ID",
    "PUBLISHED_EDITING_FLOOR_USD",
    "PUBLISHED_TEXT_TO_IMAGE_FLOOR_USD",
    "READY_STATUS",
    "REQUESTED_OUTPUT_FORMAT",
    "SIGNED_URL_MINUTES",
    "SUBMIT_URL",
    "SpecError",
    "TERMS_FEE_URL_UNVERIFIED",
    "TERMINAL_FAILURE_STATUSES",
    "VERIFIED_ON",
    "dimension_problem",
    "largest_portrait_generation_size",
    "print_resolution_plan",
    "print_scaling_analysis",
    "resolution_constraints",
    "selected_generation_record",
    "submission_body",
    "validate_delivery_url",
    "validate_polling_url",
]
