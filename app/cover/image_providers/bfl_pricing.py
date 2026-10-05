"""Cost estimate for FLUX.2 [pro].

The public pages state a floor and a round-up rule. They do not publish a
maximum dollar amount for a chosen resolution. A floor is not used as an
estimate. Unknown maximum cost blocks a paid call. A user-chosen budget cap
is not treated as a promise that the provider will stop at that amount.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from app.cover.image_providers.bfl_spec import (
    CREDIT_USD,
    DOC_COSTS,
    DOC_PRICING,
    MAX_PIXELS,
    PUBLISHED_EDITING_FLOOR_USD,
    PUBLISHED_TEXT_TO_IMAGE_FLOOR_USD,
    TERMS_FEE_URL_UNVERIFIED,
    largest_portrait_generation_size,
)


class UnverifiedFluxPricing:
    """Production pricing. The dollar maximum stays unknown."""

    source = "unverified_resolution_schedule"

    def estimate(self, request: Any) -> dict[str, Any]:
        estimate = _unknown_estimate()
        width = getattr(request, "width_px", None)
        height = getattr(request, "height_px", None)
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            estimate.update(megapixel_breakdown(width, height))
        estimate["max_cost_usd"] = None
        estimate["user_budget_is_a_provider_cap"] = False
        return estimate


class FixturePricing:
    """Test double. Not an official price and not used by the phase runner."""

    source = "test_fixture"

    def __init__(self, usd: float) -> None:
        if usd < 0:
            raise ValueError("a fixture price cannot be negative")
        self.usd = float(usd)

    def estimate(self, request: Any) -> dict[str, Any]:
        del request
        return {
            "known": True,
            "estimated_cost_usd": self.usd,
            "actual_cost_usd": None,
            "currency": "USD",
            "credit_usd": CREDIT_USD,
            "published_text_to_image_floor_usd": PUBLISHED_TEXT_TO_IMAGE_FLOOR_USD,
            "floor_used_as_estimate": False,
            "resolution_schedule": "TEST_FIXTURE",
            "source": self.source,
            "blocks_paid_call": False,
        }


def decimal_megapixels(width_px: int, height_px: int) -> Decimal:
    """Pixels divided by 1,000,000. Matches the published 2.07MP example."""

    if width_px <= 0 or height_px <= 0:
        raise ValueError("dimensions must be positive")
    return Decimal(width_px * height_px) / Decimal(1_000_000)


def billed_megapixels(width_px: int, height_px: int) -> int:
    """Ceiling to the next whole decimal megapixel.

    The help center says 1920×1080 = 2.07MP is charged as 3MP. Truncation
    would bill that example as 2MP and is not used.
    """

    pixels = width_px * height_px
    if pixels <= 0:
        raise ValueError("dimensions must be positive")
    return (pixels + 1_000_000 - 1) // 1_000_000


def megapixel_breakdown(width_px: int, height_px: int) -> dict[str, Any]:
    decimal_mp = decimal_megapixels(width_px, height_px)
    binary_mp = Decimal(width_px * height_px) / Decimal(1024 * 1024)
    return {
        "width_px": width_px,
        "height_px": height_px,
        "pixels": width_px * height_px,
        "decimal_megapixels": format(decimal_mp, "f"),
        "billed_megapixels_ceiling": billed_megapixels(width_px, height_px),
        "binary_megapixels_1024_squared": format(binary_mp, "f"),
        "rounding": "ceiling_to_next_decimal_megapixel",
        "rounding_source": DOC_COSTS,
    }


def maximum_cost_usd(
    width_px: int,
    height_px: int,
    schedule: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a dollar maximum only for a schedule marked as a verified maximum."""

    breakdown = megapixel_breakdown(width_px, height_px)
    active = dict(schedule or official_pro_text_to_image_schedule())
    billed = int(breakdown["billed_megapixels_ceiling"])
    if active.get("status") != "VERIFIED_MAXIMUM":
        return {
            **breakdown,
            "known": False,
            "max_cost_usd": None,
            "estimated_cost_usd": None,
            "blocks_paid_call": True,
            "reason": "published_floor_is_not_a_maximum",
            "schedule_status": active.get("status"),
        }
    first = Decimal(str(active["first_megapixel_usd"]))
    additional = Decimal(str(active["additional_megapixel_usd"]))
    if first < 0 or additional < 0:
        raise ValueError("a verified price cannot be negative")
    total = first if billed == 1 else first + (additional * (billed - 1))
    return {
        **breakdown,
        "known": True,
        "max_cost_usd": format(total, "f"),
        "estimated_cost_usd": format(total, "f"),
        "blocks_paid_call": False,
        "reason": "verified_schedule",
        "schedule_status": "VERIFIED_MAXIMUM",
    }


def official_pro_text_to_image_schedule() -> dict[str, Any]:
    width, height = largest_portrait_generation_size()
    return {
        "model_id": "flux-2-pro",
        "operation": "text_to_image",
        "status": "UNVERIFIED_MAXIMUM",
        "published_floor_usd": str(PUBLISHED_TEXT_TO_IMAGE_FLOOR_USD),
        "published_floor_label": "from $0.03/MP",
        "floor_is_a_maximum": False,
        "first_megapixel_usd": None,
        "additional_megapixel_usd": None,
        "selected_pixels": width * height,
        "selected_billed_megapixels": billed_megapixels(width, height),
        "pixel_cap": MAX_PIXELS,
        "dynamic_pricing_possible": True,
        "terms_fee_url": TERMS_FEE_URL_UNVERIFIED,
        "terms_fee_url_status": "HTTP_404_ON_2026_10_04",
        "sources": [DOC_PRICING, DOC_COSTS],
    }


def cost_estimation_examples() -> dict[str, Any]:
    """Worked examples. The official Pro schedule stays an unknown maximum."""

    width, height = largest_portrait_generation_size()
    verified_for_test_only = {
        "status": "VERIFIED_MAXIMUM",
        "first_megapixel_usd": "0.030",
        "additional_megapixel_usd": "0.015",
    }
    return {
        "official_pro_text_to_image": maximum_cost_usd(width, height),
        "official_rounding_example_1920x1080": megapixel_breakdown(1920, 1080),
        "selected_image": megapixel_breakdown(width, height),
        "square_label_1024": megapixel_breakdown(1024, 1024),
        "square_label_conflict": (
            "The help center calls 1024×1024 one megapixel. Decimal ceiling "
            "of 1.048576 is 2. The ceiling is kept because the 2.07MP example "
            "is charged as 3MP, and truncation would under-count that example."
        ),
        "test_only_schedule_is_not_official": maximum_cost_usd(
            width,
            height,
            verified_for_test_only,
        ),
        "floor_times_billed_megapixels_not_used": {
            "expression": "0.03 * 4",
            "value_usd": "0.12",
            "used_as_maximum": False,
        },
        "user_budget_is_a_provider_cap": False,
    }


def credits_to_usd(cost: Any) -> float | None:
    """Convert a provider cost only when the response actually includes one."""

    if isinstance(cost, bool) or cost is None:
        return None
    if isinstance(cost, (int, float)):
        return round(float(cost) * CREDIT_USD, 6)
    return None


def _unknown_estimate() -> dict[str, Any]:
    return {
        "known": False,
        "estimated_cost_usd": None,
        "actual_cost_usd": None,
        "currency": "USD",
        "credit_usd": CREDIT_USD,
        "published_text_to_image_floor_usd": PUBLISHED_TEXT_TO_IMAGE_FLOOR_USD,
        "published_editing_floor_usd": PUBLISHED_EDITING_FLOOR_USD,
        "floor_used_as_estimate": False,
        "resolution_schedule": "UNVERIFIED",
        "terms_fee_url": TERMS_FEE_URL_UNVERIFIED,
        "terms_fee_url_status": "HTTP_404_ON_VERIFICATION_DATE",
        "source": DOC_PRICING,
        "blocks_paid_call": True,
    }


def pricing_verification() -> dict[str, Any]:
    estimate = _unknown_estimate()
    estimate["status"] = "PARTIAL"
    estimate["verified"] = [
        "1 credit = 0.01 USD",
        "FLUX.2 [pro] text-to-image is listed from 0.03 USD",
        "FLUX.2 [pro] image editing is listed from 0.045 USD",
        "price varies with output resolution",
        "submit response may include cost in credits, and the field may be null",
    ]
    estimate["unverified"] = [
        "exact maximum USD for the selected legal image",
        "the additional-megapixel rate for FLUX.2 [pro]; only the floor is published",
        "the pricing calculator result for that image",
        "https://bfl.ai/pricing/api/ returned 404 on the verification date",
    ]
    return estimate


__all__ = [
    "FixturePricing",
    "UnverifiedFluxPricing",
    "billed_megapixels",
    "cost_estimation_examples",
    "credits_to_usd",
    "decimal_megapixels",
    "maximum_cost_usd",
    "megapixel_breakdown",
    "official_pro_text_to_image_schedule",
    "pricing_verification",
]
