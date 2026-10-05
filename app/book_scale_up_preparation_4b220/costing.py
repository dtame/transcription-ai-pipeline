"""
Offline cost envelope. Unknown is never zero. Central is not a safety cap.

Authorized spend for this phase is 0 USD. No provider call.
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

from app.ai.estimation import estimate_tokens
from app.ai.pricing import build_default_catalog
from app.book_generation.budget import estimate_manuscript_output
from app.book_generation.constants import HARD_MAX_OUTPUT_TOKENS, MIN_MAX_OUTPUT_TOKENS
from app.book_generation.coverage import assigned_idea_ids_for_chapter, chapter_by_id
from app.book_generation.evidence import build_chapter_evidence, render_evidence_json
from app.book_scale_up_preparation_4b220.constants import (
    ACCEPTED_CHAPTER,
    AUTHORIZED_SPEND_USD,
    CH012_ACTUAL_COST_USD,
    CH012_ACTUAL_INPUT_TOKENS,
    CH012_ACTUAL_OUTPUT_TOKENS,
    H01_ANALOG_USD,
    HISTORICAL_CHAPTER_CENTRAL_USD,
    MODEL,
    PESSIMISTIC_CHARS_PER_TOKEN,
    PHASE,
    PRICING_EFFECTIVE_DATE,
    PROVIDER,
    SONNET_INPUT_COST_PER_1M,
    SONNET_OUTPUT_COST_PER_1M,
)
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus
from app.book_scale_up_preparation_4b220.prompt_select import inspect_prompt_1_1

MILLION = Decimal("1000000")


def _money(value: Decimal | None) -> float | str | None:
    if value is None:
        return None
    return float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def tokens_to_usd(*, input_tokens: int, output_tokens: int) -> dict[str, Any]:
    input_cost = (Decimal(input_tokens) / MILLION) * SONNET_INPUT_COST_PER_1M
    output_cost = (Decimal(output_tokens) / MILLION) * SONNET_OUTPUT_COST_PER_1M
    total = input_cost + output_cost
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": _money(input_cost),
        "output_cost_usd": _money(output_cost),
        "total_cost_usd": _money(total),
        "decimal_total": total,
        "counted_as_zero": False,
    }


def pricing_context() -> dict[str, Any]:
    catalog = build_default_catalog()
    pricing = catalog.get(PROVIDER, MODEL)
    if pricing is None:
        return {
            "verified": False,
            "status": "UNKNOWN",
            "input_cost_per_1m_tokens": None,
            "output_cost_per_1m_tokens": None,
            "unmodeled_regimes": ["missing_catalog_entry"],
            "counted_as_zero": False,
        }
    regimes = getattr(pricing, "unmodeled_regimes", None) or ()
    return {
        "verified": bool(pricing.verified),
        "status": "known" if pricing.verified and not regimes else "base_estimate",
        "input_cost_per_1m_tokens": float(pricing.input_cost_per_1m_tokens),
        "output_cost_per_1m_tokens": float(pricing.output_cost_per_1m_tokens),
        "effective_date": pricing.effective_date,
        "source": pricing.source,
        "unmodeled_regimes": list(regimes) if regimes else [],
        "counted_as_zero": False,
    }


def chosen_max_output(idea_count: int, section_count: int) -> dict[str, Any]:
    output = estimate_manuscript_output(idea_count, section_count)
    raw = max(
        int(output["expected_output_tokens"]) * 3,
        int(output["conservative_output_tokens"]) * 2,
        MIN_MAX_OUTPUT_TOKENS,
    )
    chosen = min(HARD_MAX_OUTPUT_TOKENS, raw)
    return {
        "expected_output_tokens": output["expected_output_tokens"],
        "conservative_output_tokens": output["conservative_output_tokens"],
        "formula_raw_max_output_tokens": raw,
        "chosen_max_output_tokens": chosen,
        "central_is_not_the_safety_cap": True,
    }


def estimate_chapter_request_tokens(
    evidence: Mapping[str, Any],
    *,
    prompt: Mapping[str, Any],
) -> dict[str, Any]:
    system = str(prompt.get("system") or "")
    instructions = str(prompt.get("instructions") or "")
    bundle = render_evidence_json(dict(evidence))
    user = instructions + "\nEVIDENCE_BUNDLE_JSON\n" + bundle + "\n"
    joined = system + "\n" + user
    local = estimate_tokens(joined, model=MODEL)
    pessimistic = int(
        math.ceil(Decimal(max(len(joined), 1)) / PESSIMISTIC_CHARS_PER_TOKEN)
    )
    chosen = max(int(local.tokens or 0), pessimistic)
    return {
        "method_primary": local.method,
        "primary_tokens": int(local.tokens or 0),
        "pessimistic_tokens": pessimistic,
        "chosen_tokens": chosen,
        "request_chars": len(joined),
        "system_chars": len(system),
        "user_chars": len(user),
        "unknown_is_not_zero": True,
    }


def estimate_chapter_cost(
    chapter,
    *,
    corpus: CanonicalCorpus,
    prompt: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = build_chapter_evidence(
        corpus.plan,
        corpus.source_map,
        chapter,
        language=corpus.language,
        hydrate=True,
        transcript_index=corpus.transcript,
    )
    idea_count = len(assigned_idea_ids_for_chapter(chapter))
    section_count = len(chapter.sections)
    output = chosen_max_output(idea_count, section_count)
    tokens = estimate_chapter_request_tokens(evidence, prompt=prompt)
    input_tokens = int(tokens["chosen_tokens"])
    primary_tokens = int(tokens["primary_tokens"] or 0) or input_tokens
    expected = tokens_to_usd(
        input_tokens=input_tokens,
        output_tokens=int(output["expected_output_tokens"]),
    )
    high = tokens_to_usd(
        input_tokens=input_tokens,
        output_tokens=int(output["chosen_max_output_tokens"]),
    )
    low_primary = tokens_to_usd(
        input_tokens=min(primary_tokens, input_tokens),
        output_tokens=int(output["expected_output_tokens"]),
    )
    analog = (
        CH012_ACTUAL_COST_USD
        * Decimal(max(idea_count, 1))
        / Decimal("11")
    )
    low_scale = min(analog, low_primary["decimal_total"], expected["decimal_total"])
    long_context = input_tokens + int(output["chosen_max_output_tokens"]) >= 200_000
    return {
        "chapter_id": chapter.chapter_id,
        "working_title": chapter.working_title,
        "idea_count": idea_count,
        "section_count": section_count,
        "input_estimate": tokens,
        "output_plan": output,
        "expected_cost_usd": expected["total_cost_usd"],
        "low_ch012_analog_usd": _money(low_scale),
        "calculable_maximum_usd": high["total_cost_usd"],
        "authorized_budget_usd": _money(AUTHORIZED_SPEND_USD),
        "long_context_regime": "UNKNOWN" if long_context else "NOT APPLICABLE",
        "thinking_tokens": "disabled_for_configured_sonnet_call",
        "thinking_cost": "UNKNOWN_if_enabled_later",
        "counted_as_zero": False,
        "central_is_not_a_safety_cap": True,
        "this_estimate_is_not_an_authorization": True,
    }


def scale_up_cost_envelope(
    *,
    first_chapter_id: str,
    remaining_ids: list[str],
    corpus: CanonicalCorpus | None = None,
) -> dict[str, Any]:
    corpus = corpus or load_canonical_corpus()
    prompt = inspect_prompt_1_1()
    pricing = pricing_context()
    rows = []
    for chapter_id in remaining_ids:
        chapter = chapter_by_id(corpus.plan, chapter_id)
        rows.append(estimate_chapter_cost(chapter, corpus=corpus, prompt=prompt))
    expected_sum = sum(Decimal(str(row["expected_cost_usd"])) for row in rows)
    low_sum = sum(Decimal(str(row["low_ch012_analog_usd"])) for row in rows)
    high_sum = sum(Decimal(str(row["calculable_maximum_usd"])) for row in rows)
    first = next(row for row in rows if row["chapter_id"] == first_chapter_id)
    paragraph_proxy = sum(max(row["idea_count"], row["section_count"]) for row in rows)
    validation_analog = H01_ANALOG_USD * Decimal(paragraph_proxy)
    unknown_items = [
        "reasoning_token_billing_if_thinking_enabled",
        "long_context_pricing_if_200k_tokens",
        "provider_invoice_adjustments",
        "semantic_gate_complete_cost",
        "phase5_whole_book_validation",
    ]
    return {
        "phase": PHASE,
        "provider": PROVIDER,
        "model": MODEL,
        "pricing": pricing,
        "pricing_effective_date": PRICING_EFFECTIVE_DATE,
        "pricing_are_configured_project_rates": True,
        "not_live_provider_prices": True,
        "accepted_chapter_excluded": ACCEPTED_CHAPTER,
        "per_chapter": rows,
        "generation_18_chapters": {
            "low_usd": _money(low_sum),
            "central_usd": _money(expected_sum),
            "high_calculable_maximum_usd": _money(high_sum),
            "complete_cost": "UNKNOWN",
            "counted_as_zero": False,
        },
        "first_chapter": {
            "chapter_id": first["chapter_id"],
            "expected_cost_usd": first["expected_cost_usd"],
            "low_ch012_analog_usd": first["low_ch012_analog_usd"],
            "calculable_maximum_usd": first["calculable_maximum_usd"],
            "authorized_budget_usd": _money(AUTHORIZED_SPEND_USD),
            "recommended_future_cap_rule": (
                "Use the calculable theoretical maximum plus an explicit human "
                "margin. Do not use the central estimate as the safety cap."
            ),
        },
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
        "ch012_actual_reference": {
            "cost_usd": float(CH012_ACTUAL_COST_USD),
            "input_tokens": CH012_ACTUAL_INPUT_TOKENS,
            "output_tokens": CH012_ACTUAL_OUTPUT_TOKENS,
            "historical_central_usd": str(HISTORICAL_CHAPTER_CENTRAL_USD),
        },
        "authorized_spend_usd": _money(AUTHORIZED_SPEND_USD),
        "this_phase_spend_usd": 0.0,
        "this_estimate_is_not_an_authorization": True,
        "future_real_execution_requires": [
            "explicit user authorization",
            "authorized model",
            "authorized chapter",
            "cost cap above the calculable maximum, not the central estimate",
            "pre-call verification",
            "stop on unknown cost",
            "stop if cap exceeded",
            "no automatic paid retry",
            "actual-spend logging",
        ],
        "secrets_included": False,
    }


__all__ = [
    "estimate_chapter_cost",
    "pricing_context",
    "scale_up_cost_envelope",
    "tokens_to_usd",
]
