"""Cost notes for gpt-image-2.

The pricing page bills tokens. The image guide publishes rounded image-output
estimates for three sizes. Those figures exclude text tokens and are not a
ceiling. No Images API parameter was found that makes the provider stop at a
dollar amount. A local budget is not that ceiling.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.cover.image_providers.openai_spec import (
    ACCEPTED_QUALITIES,
    DOC_GUIDE,
    DOC_PRICING,
    OFFICIAL_MODEL_ID,
    SELECTED_HEIGHT,
    SELECTED_WIDTH,
    published_image_output_estimate_usd,
    size_label,
)

# Rates printed beside gpt-image-2 on the pricing page, per 1M tokens.
# The same page also prints a higher gpt-image-2.5 schedule. The image guide
# states those higher 2.5 rates and says the models share an output-token
# price. The two statements are not reconciled here.
TEXT_INPUT_USD_PER_MILLION = Decimal("2.50")
CACHED_TEXT_INPUT_USD_PER_MILLION = Decimal("0.625")
IMAGE_INPUT_USD_PER_MILLION = Decimal("4.00")
CACHED_IMAGE_INPUT_USD_PER_MILLION = Decimal("1.00")
IMAGE_OUTPUT_USD_PER_MILLION = Decimal("15.00")
HIGHER_SCHEDULE_OUTPUT_USD_PER_MILLION = Decimal("30.00")


class TokenBillingPricing:
    """Production pricing. The full request has no verified dollar maximum."""

    source = "published_token_rates_without_a_pre_request_ceiling"

    def estimate(self, request: Any) -> dict[str, Any]:
        quality = str((getattr(request, "metadata", None) or {}).get("quality") or "")
        width = int(getattr(request, "width_px", 0) or 0)
        height = int(getattr(request, "height_px", 0) or 0)
        image_output = None
        if quality in ACCEPTED_QUALITIES and width > 0 and height > 0:
            image_output = published_image_output_estimate_usd(width, height, quality)
        return {
            "known": False,
            "estimated_cost_usd": None,
            "published_image_output_estimate_usd": image_output,
            "published_image_output_estimate_excludes_text_tokens": True,
            "estimate_is_a_billing_guarantee": False,
            "verified_maximum_cost_usd": None,
            "local_budget_is_a_provider_cap": False,
            "blocks_paid_call": True,
            "reason": "token_maximum_not_guaranteed_before_request",
            "currency": "USD",
            "model_id": OFFICIAL_MODEL_ID,
            "source": self.source,
            "text_input_usd_per_million": format(TEXT_INPUT_USD_PER_MILLION, "f"),
            "image_input_usd_per_million": format(IMAGE_INPUT_USD_PER_MILLION, "f"),
            "image_output_usd_per_million": format(IMAGE_OUTPUT_USD_PER_MILLION, "f"),
            "cached_input_applies_to_direct_images_api": False,
            "reference_images": False,
            "actual_cost_usd": None,
        }


class FixtureImagePricing:
    """Test double. Not an official price and not used by the phase runner."""

    source = "test_fixture"

    def __init__(self, usd: float | None, *, verified_maximum_usd: float | None = None) -> None:
        if usd is not None and usd < 0:
            raise ValueError("a fixture price cannot be negative")
        if verified_maximum_usd is not None and verified_maximum_usd < 0:
            raise ValueError("a fixture ceiling cannot be negative")
        self.usd = None if usd is None else float(usd)
        self.verified_maximum_usd = (
            None if verified_maximum_usd is None else float(verified_maximum_usd)
        )

    def estimate(self, request: Any) -> dict[str, Any]:
        del request
        return {
            "known": self.usd is not None and self.verified_maximum_usd is not None,
            "estimated_cost_usd": self.usd,
            "published_image_output_estimate_usd": None,
            "estimate_is_a_billing_guarantee": self.verified_maximum_usd is not None,
            "verified_maximum_cost_usd": self.verified_maximum_usd,
            "local_budget_is_a_provider_cap": False,
            "blocks_paid_call": self.usd is None or self.verified_maximum_usd is None,
            "reason": "test_fixture",
            "currency": "USD",
            "source": self.source,
            "actual_cost_usd": None,
        }


def quality_cost_comparison() -> dict[str, Any]:
    """Published image-output estimates. Missing cells stay null."""

    sizes = [
        (1024, 1024),
        (SELECTED_WIDTH, SELECTED_HEIGHT),
        (1536, 1024),
        (1536, 2304),
        (2160, 3840),
    ]
    rows = []
    for width, height in sizes:
        estimates = {
            quality: published_image_output_estimate_usd(width, height, quality)
            for quality in ACCEPTED_QUALITIES
        }
        rows.append(
            {
                "size": size_label(width, height),
                "width": width,
                "height": height,
                "image_output_estimate_usd": estimates,
                "full_request_estimate_usd": None,
                "verified_maximum_cost_usd": None,
                "estimate_is_a_billing_guarantee": False,
            }
        )
    return {
        "model_id": OFFICIAL_MODEL_ID,
        "billing_unit": "tokens",
        "rates_per_million_tokens_beside_gpt_image_2": {
            "text_input": format(TEXT_INPUT_USD_PER_MILLION, "f"),
            "cached_text_input": format(CACHED_TEXT_INPUT_USD_PER_MILLION, "f"),
            "image_input": format(IMAGE_INPUT_USD_PER_MILLION, "f"),
            "cached_image_input": format(CACHED_IMAGE_INPUT_USD_PER_MILLION, "f"),
            "image_output": format(IMAGE_OUTPUT_USD_PER_MILLION, "f"),
        },
        "conflicting_higher_output_rate_stated_for_gpt_image_2_5": format(
            HIGHER_SCHEDULE_OUTPUT_USD_PER_MILLION, "f"
        ),
        "rate_conflict_blocks_a_guaranteed_ceiling": True,
        "cached_rates_apply_to_direct_images_api": False,
        "partial_image_extra_output_tokens_if_streaming": 100,
        "streaming_used": False,
        "reference_images_used": False,
        "rows": rows,
        "sources": [DOC_PRICING, DOC_GUIDE],
    }


def pricing_facts() -> dict[str, Any]:
    selected = published_image_output_estimate_usd(SELECTED_WIDTH, SELECTED_HEIGHT, "medium")
    return {
        "selected_size": size_label(SELECTED_WIDTH, SELECTED_HEIGHT),
        "selected_quality": "medium",
        "published_image_output_estimate_usd": selected,
        "full_request_estimate_usd": None,
        "verified_maximum_cost_usd": None,
        "blocks_paid_call": True,
        "comparison": quality_cost_comparison(),
    }


__all__ = [
    "CACHED_IMAGE_INPUT_USD_PER_MILLION",
    "CACHED_TEXT_INPUT_USD_PER_MILLION",
    "FixtureImagePricing",
    "HIGHER_SCHEDULE_OUTPUT_USD_PER_MILLION",
    "IMAGE_INPUT_USD_PER_MILLION",
    "IMAGE_OUTPUT_USD_PER_MILLION",
    "TEXT_INPUT_USD_PER_MILLION",
    "TokenBillingPricing",
    "pricing_facts",
    "quality_cost_comparison",
]
