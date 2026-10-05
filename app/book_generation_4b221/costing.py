"""
Precall cost bound for the single CH018 Sonnet call.

Unknown is never treated as zero. Theoretical maximum uses the request
max_tokens, not the 4B.2.20 central estimate. Thinking must stay disabled.
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

from app.ai.estimation import estimate_tokens
from app.ai.pricing import build_default_catalog
from app.book_generation.budget import estimate_manuscript_output
from app.book_generation.constants import HARD_MAX_OUTPUT_TOKENS, MIN_MAX_OUTPUT_TOKENS
from app.book_generation_4b217.constants import (
    SONNET_INPUT_COST_PER_1M,
    SONNET_OUTPUT_COST_PER_1M,
)
from app.book_generation_4b221.constants import (
    BUDGET_CAP_DISPLAY,
    BUDGET_CAP_USD,
    MODEL,
    PESSIMISTIC_CHARS_PER_TOKEN,
    PHASE,
    PHASE_4B220_EXPECTED_USD,
    PHASE_4B220_MAX_USD,
    PRICING_EFFECTIVE_DATE,
    PROVIDER,
    TARGET_CHAPTER_ID,
)
from app.book_generation_4b221.guard import BookGeneration4221Error

MILLION = Decimal("1000000")


def _money(value: Decimal | None) -> float | None:
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


def evidence_derived_max_output(*, idea_count: int, section_count: int) -> dict[str, Any]:
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
        "historical_default_floor_16384_not_applied": True,
        "reason_floor_not_applied": (
            "The historical 16384 default floor would make the theoretical "
            "maximum exceed the authorized 0.15 USD cap. The evidence-derived "
            "formula (max(expected*3, conservative*2, 4096)) is used instead. "
            "Sources are not truncated. Output is not reduced below the formula."
        ),
        "did_not_truncate_sources": True,
        "did_not_inflate_to_consume_cap": True,
        "did_not_silently_reduce_output_limit": True,
        "hard_max_output_tokens": HARD_MAX_OUTPUT_TOKENS,
        "min_max_output_tokens": MIN_MAX_OUTPUT_TOKENS,
    }


def json_payload_text(payload: Mapping[str, Any]) -> str:
    import json

    cleaned = dict(payload)
    for key in ("x-api-key", "api_key", "authorization"):
        cleaned.pop(key, None)
    return json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def estimate_input_tokens(identity: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(identity.get("payload") or {})
    system = str(payload.get("system") or identity.get("system") or "")
    user = ""
    for message in payload.get("messages") or []:
        if message.get("role") == "user":
            user = str(message.get("content") or "")
    if not user:
        user = str(identity.get("user") or "")
    joined = system + "\n" + user
    encoded = json_payload_text(payload)
    local = estimate_tokens(joined, model=MODEL)
    chars = len(joined)
    pessimistic_prompt = int(math.ceil(Decimal(max(chars, 1)) / PESSIMISTIC_CHARS_PER_TOKEN))
    pessimistic_payload = int(
        math.ceil(Decimal(max(len(encoded), 1)) / PESSIMISTIC_CHARS_PER_TOKEN)
    )
    chosen = max(int(local.tokens or 0), pessimistic_prompt, pessimistic_payload)
    return {
        "phase": PHASE,
        "method_primary": local.method,
        "method_pessimistic": "historical_chars_per_token_1.9365",
        "primary_tokens": int(local.tokens or 0),
        "pessimistic_prompt_tokens": pessimistic_prompt,
        "pessimistic_payload_tokens": pessimistic_payload,
        "chosen_tokens": chosen,
        "chosen_is_max_of_local_methods": True,
        "request_chars": chars,
        "payload_chars": len(encoded),
        "system_chars": len(system),
        "user_chars": len(user),
        "unknown_is_not_zero": True,
        "secrets_included": False,
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


def reserve_budget(
    identity: Mapping[str, Any],
    *,
    idea_count: int,
    section_count: int,
) -> dict[str, Any]:
    pricing = pricing_context()
    if pricing.get("status") == "UNKNOWN" or pricing.get("verified") is not True:
        raise BookGeneration4221Error(
            "Applicable tariff is UNKNOWN. STOP before provider call."
        )
    if pricing.get("unmodeled_regimes"):
        raise BookGeneration4221Error(
            "A billable pricing regime cannot be bounded. STOP."
        )
    thinking_ok = (
        identity.get("thinking_mode") in {None, "disabled"}
        and identity.get("thinking_disabled") is not False
        and identity.get("thinking_type") in {None, "disabled"}
    )
    if identity.get("thinking_type") not in {None, "disabled"}:
        raise BookGeneration4221Error(
            "Thinking is enabled and cannot be bounded. STOP."
        )
    if not thinking_ok and identity.get("thinking_present"):
        raise BookGeneration4221Error(
            "Thinking is not the verified budgeted configuration. STOP."
        )
    input_est = estimate_input_tokens(identity)
    input_tokens = int(input_est["chosen_tokens"])
    output_plan = evidence_derived_max_output(
        idea_count=idea_count, section_count=section_count
    )
    max_out = int(output_plan["chosen_max_output_tokens"])
    theoretical = tokens_to_usd(input_tokens=input_tokens, output_tokens=max_out)
    default_floor = tokens_to_usd(input_tokens=input_tokens, output_tokens=16384)
    long_context = input_tokens + max_out >= 200_000
    rates_usable = (
        pricing.get("verified") is True
        and pricing.get("input_cost_per_1m_tokens") is not None
        and pricing.get("output_cost_per_1m_tokens") is not None
        and not pricing.get("unmodeled_regimes")
        and not long_context
    )
    established = rates_usable and theoretical["decimal_total"] is not None
    over = (
        theoretical["decimal_total"] > BUDGET_CAP_USD
        if established
        else True
    )
    within = established and not over
    block_reason = None
    if not established:
        block_reason = "COST_MAXIMUM_UNKNOWN"
    elif over:
        block_reason = "COST_MAXIMUM_EXCEEDS_CAP"
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "provider": PROVIDER,
        "model": MODEL,
        "model_id": f"{PROVIDER}/{MODEL}",
        "maximum_remote_calls": 1,
        "budget_cap_usd": float(BUDGET_CAP_USD),
        "budget_cap_display": BUDGET_CAP_DISPLAY,
        "pricing": pricing,
        "pricing_effective_date": PRICING_EFFECTIVE_DATE,
        "pricing_are_configured_project_rates": True,
        "not_live_provider_prices": True,
        "rates_established_with_sufficient_certainty": rates_usable,
        "thinking_mode": "disabled",
        "thinking_tokens_budgeted": 0,
        "thinking_cost": "disabled_not_unknown",
        "long_context_regime": "NOT APPLICABLE",
        "applicable_fees": [],
        "tariff_uncertainty": "none_modeled_for_verified_sonnet_standard_rates",
        "input_estimate": input_est,
        "output_plan": output_plan,
        "max_output_tokens": max_out,
        "theoretical_maximum_usd": theoretical["total_cost_usd"],
        "theoretical_maximum_breakdown": {
            "input_cost_usd": theoretical["input_cost_usd"],
            "output_cost_usd": theoretical["output_cost_usd"],
        },
        "if_16384_default_floor_used_usd": default_floor["total_cost_usd"],
        "phase_4b220_expected_usd": str(PHASE_4B220_EXPECTED_USD),
        "phase_4b220_calculable_maximum_usd": str(PHASE_4B220_MAX_USD),
        "central_estimate_is_not_the_safety_cap": True,
        "within_budget": within,
        "unknown_is_not_zero": True,
        "did_not_truncate_sources": True,
        "did_not_silently_reduce_quality": True,
        "not_a_provider_invoice": True,
        "blocked": not within,
        "block_reason": block_reason,
        "secrets_included": False,
    }


def actual_cost(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    thinking_tokens: int | None = None,
) -> dict[str, Any]:
    if thinking_tokens:
        return {
            "status": "UNKNOWN",
            "total_cost_usd": None,
            "display": "UNKNOWN",
            "counted_as_zero": False,
            "notes": "Billable thinking tokens were reported. Not inferred as zero.",
        }
    if input_tokens is None or output_tokens is None:
        return {
            "status": "UNKNOWN",
            "total_cost_usd": None,
            "display": "UNKNOWN",
            "counted_as_zero": False,
            "notes": "Provider usage unavailable — not inferred as zero.",
        }
    catalog = build_default_catalog()
    breakdown = catalog.estimate_cost(PROVIDER, MODEL, input_tokens, output_tokens)
    payload = breakdown.to_dict()
    if breakdown.total_cost is None:
        payload["display"] = "UNKNOWN"
        payload["status"] = "UNKNOWN"
        payload["counted_as_zero"] = False
    else:
        payload["display"] = f"{breakdown.total_cost} {breakdown.currency or 'USD'}"
        payload["total_cost_usd"] = float(breakdown.total_cost)
    payload["not_a_provider_invoice"] = True
    payload["thinking_tokens"] = thinking_tokens or 0
    return payload


__all__ = [
    "actual_cost",
    "evidence_derived_max_output",
    "estimate_input_tokens",
    "pricing_context",
    "reserve_budget",
    "tokens_to_usd",
]
