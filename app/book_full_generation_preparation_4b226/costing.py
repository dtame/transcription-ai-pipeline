"""
Offline 13-chapter budget forecast. No provider call.

Unknown is never zero. Central is not a safety cap.
Observed accepted-chapter costs are calibration, not remaining-chapter prices.
Authorized spend for this phase is 0 USD.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.book_full_generation_preparation_4b226.constants import (
    ACCEPTED_CHAPTER_IDS,
    AUTHORIZED_SPEND_USD,
    CH001_ACTUAL_COST_USD,
    CH002_ACTUAL_COST_USD,
    CH003_ACTUAL_COST_USD,
    CH004_ACTUAL_COST_USD,
    CH012_ACTUAL_COST_USD,
    CH018_ACTUAL_COST_USD,
    MODEL,
    OBSERVED_IDEA_SCALE,
    PHASE,
    PRICING_EFFECTIVE_DATE,
    PROPOSED_CAP_MARGIN,
    PROVIDER,
    REMAINING_CHAPTER_IDS,
)
from app.book_generation.coverage import chapter_by_id
from app.book_scale_up_preparation_4b220.context import build_chapter_source_context
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus
from app.book_scale_up_preparation_4b220.costing import (
    estimate_chapter_cost,
    pricing_context,
)
from app.book_scale_up_preparation_4b220.prompt_select import inspect_prompt_1_1


def _money(value: Decimal | None) -> float | str | None:
    if value is None:
        return None
    return float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _analog(actual: Decimal, idea_count: int) -> Decimal:
    return actual * Decimal(max(idea_count, 1)) / OBSERVED_IDEA_SCALE


def remaining_chapters_budget_forecast(
    *,
    corpus: CanonicalCorpus | None = None,
) -> dict[str, Any]:
    corpus = corpus or load_canonical_corpus()
    prompt = inspect_prompt_1_1()
    pricing = pricing_context()
    observed = {
        "CH001": CH001_ACTUAL_COST_USD,
        "CH002": CH002_ACTUAL_COST_USD,
        "CH003": CH003_ACTUAL_COST_USD,
        "CH004": CH004_ACTUAL_COST_USD,
        "CH012": CH012_ACTUAL_COST_USD,
        "CH018": CH018_ACTUAL_COST_USD,
    }
    blended_observed = sum(observed.values()) / Decimal(len(observed))
    rows: list[dict[str, Any]] = []
    unknown_components: list[str] = []
    blocked = False
    block_reason = None
    if pricing.get("status") == "UNKNOWN" or pricing.get("verified") is not True:
        blocked = True
        block_reason = "COST_MAXIMUM_UNKNOWN"
        unknown_components.append("applicable_tariff")
    if pricing.get("unmodeled_regimes"):
        blocked = True
        block_reason = block_reason or "UNMODELED_PRICING_REGIME"
        unknown_components.extend(list(pricing.get("unmodeled_regimes") or []))

    for chapter_id in REMAINING_CHAPTER_IDS:
        chapter = chapter_by_id(corpus.plan, chapter_id)
        raw = estimate_chapter_cost(chapter, corpus=corpus, prompt=prompt)
        built = build_chapter_source_context(chapter_id, corpus=corpus)
        idea_count = int(raw["idea_count"])
        section_count = int(raw["section_count"])
        expected = Decimal(str(raw["expected_cost_usd"]))
        maximum = Decimal(str(raw["calculable_maximum_usd"]))
        analogs = [_analog(value, idea_count) for value in observed.values()]
        analog_blend = sum(analogs) / Decimal(len(analogs))
        input_est = dict(raw.get("input_estimate") or {})
        output_plan = dict(raw.get("output_plan") or {})
        context = dict(built.get("context_size") or {})
        long_context = raw.get("long_context_regime") == "UNKNOWN"
        chapter_unknown: list[str] = []
        if long_context:
            chapter_unknown.append("long_context_pricing")
        if raw.get("calculable_maximum_usd") in {None, "UNKNOWN"}:
            chapter_unknown.append("preflight_max")
            blocked = True
            block_reason = block_reason or "COST_MAXIMUM_UNKNOWN"
        truncation_risks = list(built.get("potentially_truncated") or [])
        if int(output_plan.get("chosen_max_output_tokens") or 0) >= 30000:
            truncation_risks.append("output_near_hard_max")
        if built.get("context_truncated"):
            truncation_risks.append("source_context_truncated")
            blocked = True
            block_reason = block_reason or "SOURCE_CONTEXT_TRUNCATED"
        src_count = len((built.get("expected_sources") or {}).get("src_ids") or [])
        row = {
            "chapter_id": chapter_id,
            "working_title": chapter.working_title,
            "section_count": section_count,
            "idea_count": idea_count,
            "src_count": src_count,
            "estimated_context_size": {
                "hydrated_src_count": (built.get("resolved_sources") or {}).get(
                    "hydrated_count"
                ),
                "hydrated_src_words": built.get("hydrated_src_words"),
                "metrics": context,
                "hydratable": built.get("ready") is True
                and not built.get("missing_sources"),
                "context_truncated": bool(built.get("context_truncated")),
            },
            "estimated_input_tokens": input_est.get("chosen_tokens"),
            "estimated_output_tokens_central": output_plan.get("expected_output_tokens"),
            "estimated_output_tokens_max": output_plan.get("chosen_max_output_tokens"),
            "historical_observed_cost_usd": "UNKNOWN",
            "historical_observed_is_not_zero": True,
            "central_estimate_usd": _money(expected),
            "preflight_max_cost_usd": _money(maximum),
            "blended_accepted_analog_usd": _money(analog_blend),
            "accepted_chapter_analogs_are_not_remaining_prices": True,
            "pricing_status": pricing.get("status"),
            "tariff_knowledge_status": (
                "known_configured_sonnet_standard_rates"
                if pricing.get("verified") and not chapter_unknown
                else "UNKNOWN"
            ),
            "truncation_risks": truncation_risks,
            "unknown_components": chapter_unknown,
            "counted_as_zero": False,
            "central_is_not_a_safety_cap": True,
            "this_estimate_is_not_an_authorization": True,
        }
        rows.append(row)
        unknown_components.extend(
            f"{chapter_id}:{item}" for item in chapter_unknown
        )

    central_sum = sum(Decimal(str(row["central_estimate_usd"])) for row in rows)
    max_sum = sum(Decimal(str(row["preflight_max_cost_usd"])) for row in rows)
    recommended = (max_sum * (Decimal("1") + PROPOSED_CAP_MARGIN)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    unknown_items = [
        "historical_observed_cost_of_ungenerated_remaining_chapters",
        "reasoning_token_billing_if_thinking_enabled",
        "long_context_pricing_if_200k_tokens",
        "provider_invoice_adjustments",
        "semantic_gate_complete_cost",
        "phase5_whole_book_validation",
        "human_review_time",
    ]
    unknown_items.extend(unknown_components)
    if blocked:
        recommended_display: float | str = "BLOCKED"
    else:
        recommended_display = _money(recommended)  # type: ignore[assignment]
    return {
        "phase": PHASE,
        "provider": PROVIDER,
        "model": MODEL,
        "pricing": pricing,
        "pricing_effective_date": PRICING_EFFECTIVE_DATE,
        "pricing_are_configured_project_rates": True,
        "not_live_provider_prices": True,
        "accepted_chapters_excluded": list(ACCEPTED_CHAPTER_IDS),
        "observed_calibration": {
            "ch001_actual_cost_usd": float(CH001_ACTUAL_COST_USD),
            "ch002_actual_cost_usd": float(CH002_ACTUAL_COST_USD),
            "ch003_actual_cost_usd": float(CH003_ACTUAL_COST_USD),
            "ch004_actual_cost_usd": float(CH004_ACTUAL_COST_USD),
            "ch012_actual_cost_usd": float(CH012_ACTUAL_COST_USD),
            "ch018_actual_cost_usd": float(CH018_ACTUAL_COST_USD),
            "blended_accepted_usd": _money(blended_observed),
            "not_used_as_fixed_remaining_chapter_price": True,
        },
        "per_chapter": rows,
        "GLOBAL_ESTIMATED_COST": _money(central_sum),
        "GLOBAL_PREFLIGHT_MAX_COST": _money(max_sum),
        "RECOMMENDED_AUTHORIZATION_CAP": recommended_display,
        "proposed_cap_margin": float(PROPOSED_CAP_MARGIN),
        "authorized_spend_usd": _money(AUTHORIZED_SPEND_USD),
        "this_phase_spend_usd": 0.0,
        "blocked": blocked,
        "block_reason": block_reason,
        "unknown_cost_components": sorted(set(unknown_items)),
        "unknown_replaced_by_zero": False,
        "distinctions": {
            "historical_observed": "actual spend of already generated accepted chapters; remaining 13 are UNKNOWN",
            "central_estimate": "token-based expected cost from hydrated evidence and configured rates",
            "preflight_max": "pre-call theoretical maximum from chosen max_tokens",
            "recommended_cap": "sum of calculable maxima plus documented 15 percent margin",
            "authorized_cap": "currently 0 USD; future scope is not activated",
        },
        "this_estimate_is_not_an_authorization": True,
        "future_authorization_not_activated": True,
        "secrets_included": False,
    }


__all__ = ["remaining_chapters_budget_forecast"]

