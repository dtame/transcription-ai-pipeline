"""
Offline 17-chapter cost envelope.

Unknown is never zero. Central is not a safety cap.
Observed CH012 and CH018 costs are calibration, not fixed chapter prices.
Authorized spend for this phase is 0 USD.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.book_batch_preparation_4b222.constants import (
    ACCEPTED_CH012_ID,
    ACCEPTED_CH018_ID,
    AUTHORIZED_SPEND_USD,
    BATCH_CHAPTERS,
    BATCH_IDS,
    CH012_ACTUAL_COST_USD,
    CH012_ACTUAL_INPUT_TOKENS,
    CH012_ACTUAL_OUTPUT_TOKENS,
    CH018_ACTUAL_COST_USD,
    CH018_ACTUAL_INPUT_TOKENS,
    CH018_ACTUAL_OUTPUT_TOKENS,
    H01_ANALOG_USD,
    HISTORICAL_CHAPTER_CENTRAL_USD,
    MODEL,
    OBSERVED_IDEA_SCALE,
    PHASE,
    PRICING_EFFECTIVE_DATE,
    PROPOSED_CAP_MARGIN,
    PROVIDER,
)
from app.book_generation.coverage import chapter_by_id
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus
from app.book_scale_up_preparation_4b220.costing import (
    estimate_chapter_cost,
    pricing_context,
    tokens_to_usd,
)
from app.book_scale_up_preparation_4b220.prompt_select import inspect_prompt_1_1


def _money(value: Decimal | None) -> float | str | None:
    if value is None:
        return None
    return float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _analog(actual: Decimal, idea_count: int) -> Decimal:
    return actual * Decimal(max(idea_count, 1)) / OBSERVED_IDEA_SCALE


def enrich_chapter_cost(row: dict[str, Any]) -> dict[str, Any]:
    idea_count = int(row["idea_count"])
    ch012_analog = _analog(CH012_ACTUAL_COST_USD, idea_count)
    ch018_analog = _analog(CH018_ACTUAL_COST_USD, idea_count)
    blended = (ch012_analog + ch018_analog) / Decimal("2")
    expected = Decimal(str(row["expected_cost_usd"]))
    maximum = Decimal(str(row["calculable_maximum_usd"]))
    inherited_low = Decimal(str(row["low_ch012_analog_usd"]))
    low = min(inherited_low, ch012_analog, ch018_analog, expected)
    proposed = (maximum * (Decimal("1") + PROPOSED_CAP_MARGIN)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    enriched = dict(row)
    enriched.update(
        {
            "low_ch012_analog_usd": _money(ch012_analog),
            "low_ch018_analog_usd": _money(ch018_analog),
            "low_blended_observed_analog_usd": _money(blended),
            "low_usd": _money(low),
            "expected_cost_usd": _money(expected),
            "calculable_maximum_usd": _money(maximum),
            "proposed_cap_usd": _money(proposed),
            "authorized_cap_usd": _money(AUTHORIZED_SPEND_USD),
            "observed_costs_are_not_fixed_prices": True,
            "central_is_not_a_safety_cap": True,
            "this_estimate_is_not_an_authorization": True,
            "counted_as_zero": False,
        }
    )
    return enriched


def batch_cost_envelope(
    remaining_ids: list[str],
    *,
    corpus: CanonicalCorpus | None = None,
) -> dict[str, Any]:
    corpus = corpus or load_canonical_corpus()
    prompt = inspect_prompt_1_1()
    pricing = pricing_context()
    rows = []
    for chapter_id in remaining_ids:
        chapter = chapter_by_id(corpus.plan, chapter_id)
        raw = estimate_chapter_cost(chapter, corpus=corpus, prompt=prompt)
        rows.append(enrich_chapter_cost(raw))
    expected_sum = sum(Decimal(str(row["expected_cost_usd"])) for row in rows)
    low_sum = sum(Decimal(str(row["low_usd"])) for row in rows)
    high_sum = sum(Decimal(str(row["calculable_maximum_usd"])) for row in rows)
    proposed_sum = sum(Decimal(str(row["proposed_cap_usd"])) for row in rows)
    batches = []
    for batch_id in BATCH_IDS:
        chapter_ids = list(BATCH_CHAPTERS[batch_id])
        selected = [row for row in rows if row["chapter_id"] in chapter_ids]
        batch_expected = sum(Decimal(str(row["expected_cost_usd"])) for row in selected)
        batch_low = sum(Decimal(str(row["low_usd"])) for row in selected)
        batch_max = sum(Decimal(str(row["calculable_maximum_usd"])) for row in selected)
        batch_proposed = sum(Decimal(str(row["proposed_cap_usd"])) for row in selected)
        batches.append(
            {
                "batch_id": batch_id,
                "chapter_ids": chapter_ids,
                "low_usd": _money(batch_low),
                "expected_cost_usd": _money(batch_expected),
                "calculable_maximum_usd": _money(batch_max),
                "proposed_cap_usd": _money(batch_proposed),
                "authorized_cap_usd": _money(AUTHORIZED_SPEND_USD),
            }
        )
    paragraph_proxy = sum(max(row["idea_count"], row["section_count"]) for row in rows)
    validation_analog = H01_ANALOG_USD * Decimal(paragraph_proxy)
    unknown_items = [
        "reasoning_token_billing_if_thinking_enabled",
        "long_context_pricing_if_200k_tokens",
        "provider_invoice_adjustments",
        "semantic_gate_complete_cost",
        "phase5_whole_book_validation",
        "human_review_time",
    ]
    return {
        "phase": PHASE,
        "provider": PROVIDER,
        "model": MODEL,
        "pricing": pricing,
        "pricing_effective_date": PRICING_EFFECTIVE_DATE,
        "pricing_are_configured_project_rates": True,
        "not_live_provider_prices": True,
        "accepted_chapters_excluded": [ACCEPTED_CH012_ID, ACCEPTED_CH018_ID],
        "observed_calibration": {
            "ch012_actual_cost_usd": float(CH012_ACTUAL_COST_USD),
            "ch012_input_tokens": CH012_ACTUAL_INPUT_TOKENS,
            "ch012_output_tokens": CH012_ACTUAL_OUTPUT_TOKENS,
            "ch018_actual_cost_usd": float(CH018_ACTUAL_COST_USD),
            "ch018_input_tokens": CH018_ACTUAL_INPUT_TOKENS,
            "ch018_output_tokens": CH018_ACTUAL_OUTPUT_TOKENS,
            "not_used_as_fixed_chapter_price": True,
            "historical_central_usd": str(HISTORICAL_CHAPTER_CENTRAL_USD),
        },
        "per_chapter": rows,
        "generation_17_chapters": {
            "low_usd": _money(low_sum),
            "central_usd": _money(expected_sum),
            "high_calculable_maximum_usd": _money(high_sum),
            "proposed_cap_usd": _money(proposed_sum),
            "authorized_cap_usd": _money(AUTHORIZED_SPEND_USD),
            "complete_cost": "UNKNOWN",
            "counted_as_zero": False,
        },
        "batches": batches,
        "validation_cost": {
            "semantic_gate_complete_cost": "UNKNOWN",
            "terra_h01_analog_using_idea_or_section_proxy_usd": _money(validation_analog),
            "proxy_units": paragraph_proxy,
            "reasoning_token_billing": "UNKNOWN",
            "long_context_pricing": "UNKNOWN",
            "counted_as_zero": False,
            "separated_from_generation": True,
        },
        "unknown_items": unknown_items,
        "unknown_replaced_by_zero": False,
        "distinctions": {
            "expected_cost": "token-based central estimate",
            "calculable_maximum": "pre-call theoretical maximum from chosen max_tokens",
            "proposed_cap": "calculable maximum plus documented 15 percent margin",
            "authorized_cap": "currently 0 USD",
        },
        "proposed_cap_margin": float(PROPOSED_CAP_MARGIN),
        "authorized_spend_usd": _money(AUTHORIZED_SPEND_USD),
        "this_phase_spend_usd": 0.0,
        "this_estimate_is_not_an_authorization": True,
        "secrets_included": False,
    }


__all__ = ["batch_cost_envelope", "enrich_chapter_cost", "tokens_to_usd"]
