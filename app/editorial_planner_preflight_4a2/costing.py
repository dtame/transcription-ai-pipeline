"""Estimated production cost. ESTIMATED, not actual. 0 provider calls."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.ai.pricing import COST_STATUS_UNKNOWN, REGIME_LONG_CONTEXT, build_default_catalog
from app.editorial_planner_preflight_4a2.constants import (
    A1_COST_USD,
    A1_INPUT_TOKENS,
    A1_OUTPUT_TOKENS,
    A1_THINKING_TOKENS,
    MODEL,
    PROVIDER,
    THINKING_HEADROOM_TOKENS,
)


def _as_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def estimate_pair(*, input_tokens: int, output_tokens: int) -> dict[str, Any]:
    catalog = build_default_catalog()
    breakdown = catalog.estimate_cost(PROVIDER, MODEL, input_tokens, output_tokens)
    payload = breakdown.to_dict()
    payload["status"] = breakdown.status
    payload["display"] = (
        f"{breakdown.total_cost} {breakdown.currency or 'USD'}"
        if breakdown.total_cost is not None
        else "UNKNOWN"
    )
    payload["cost_status_mark"] = "ESTIMATED"
    payload["input_tokens"] = input_tokens
    payload["output_tokens"] = output_tokens
    return payload


def long_context_status(input_tokens: int) -> dict[str, Any]:
    catalog = build_default_catalog()
    pricing = catalog.get(PROVIDER, MODEL)
    gpt_has_regime = False
    opus_regime = ""
    if pricing is not None:
        opus_regime = pricing.unmodeled_regimes or ""
    terra = catalog.get("openai", "gpt-5.6-terra")
    if terra is not None:
        gpt_has_regime = REGIME_LONG_CONTEXT in (terra.unmodeled_regimes or "")
    return {
        "provider": PROVIDER,
        "model": MODEL,
        "estimated_input_tokens": input_tokens,
        "opus_unmodeled_regimes": opus_regime or None,
        "opus_long_context_regime_declared": bool(opus_regime),
        "gpt_terra_has_unmodeled_long_context": gpt_has_regime,
        "phase2b_pricing_completeness": (
            "Opus 5 has verified base input/output rates and no declared "
            "long_context unmodeled regime in AI_PRICING_ENTRIES. GPT-5.6 Terra "
            "is the only Phase 2B production model marked long_context_not_modeled."
        ),
        "crosses_declared_long_context_threshold": False,
        "threshold_modeled_for_opus": False,
        "status": "BASE_PRICING_APPLIES_NO_OPUS_LONG_CONTEXT_REGIME",
        "web_research": False,
    }


def production_cost_estimate(
    *,
    input_tokens: int,
    expected_output: int,
    conservative_output: int,
    hard_output: int,
) -> dict[str, Any]:
    thinking = THINKING_HEADROOM_TOKENS
    expected = estimate_pair(
        input_tokens=input_tokens,
        output_tokens=expected_output + thinking,
    )
    conservative = estimate_pair(
        input_tokens=input_tokens,
        output_tokens=conservative_output + thinking,
    )
    hard = estimate_pair(
        input_tokens=input_tokens,
        output_tokens=hard_output + thinking,
    )
    return {
        "cost_status_mark": "ESTIMATED",
        "not_actual": True,
        "a1_actual_not_extrapolated": {
            "cost_usd": A1_COST_USD,
            "input_tokens": A1_INPUT_TOKENS,
            "output_tokens": A1_OUTPUT_TOKENS,
            "thinking_tokens": A1_THINKING_TOKENS,
            "note": "A.1 actual cost is historical. Production cost is estimated separately.",
        },
        "thinking_treatment": (
            "A.1 reported thinking_tokens inside usage.output_tokens_details. "
            "Engine records output_tokens without subtracting thinking. "
            "Estimates add documented thinking headroom to visible output and "
            "price the sum at the Opus output rate (conservative)."
        ),
        "pricing": {
            "provider": PROVIDER,
            "model": MODEL,
            "input_cost_per_1m": 5.00,
            "output_cost_per_1m": 25.00,
            "effective_date": "2026-09-18",
            "source": "Anthropic official pricing/model documentation (Phase 2B catalog)",
        },
        "long_context": long_context_status(input_tokens),
        "expected": expected,
        "conservative": conservative,
        "hard": hard,
        "expected_cost": expected.get("display"),
        "conservative_cost": conservative.get("display"),
        "hard_cost": hard.get("display"),
    }


__all__ = ["long_context_status", "production_cost_estimate"]
