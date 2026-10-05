"""
Pre-call budget reservation for the single 4B.2.15 Terra operation.

Unknown is never treated as zero. Theoretical maximum includes the full
output cap, which is the only place billed reasoning tokens can appear
under the historical Terra usage model.
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

from app.ai.estimation import estimate_tokens
from app.book_semantic_gate_4b215.constants import (
    BUDGET_CAP_DISPLAY,
    BUDGET_CAP_USD,
    HISTORICAL_CONSERVATIVE_OUTPUT,
    MIN_USABLE_OUTPUT_TOKENS,
    MODEL,
    PHASE,
    PRICING_EFFECTIVE_DATE,
    PROVIDER,
    TERRA_INPUT_COST_PER_1M,
    TERRA_OUTPUT_COST_PER_1M,
)
from app.book_semantic_gate_4b261.costing import estimate_cost, pricing_context

PESSIMISTIC_CHARS_PER_TOKEN = Decimal("1.9365384615384615")
MILLION = Decimal("1000000")


def _money(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _user_and_system(payload: Mapping[str, Any]) -> tuple[str, str]:
    system = ""
    user = ""
    for message in payload.get("messages") or []:
        if message.get("role") == "system":
            system = str(message.get("content") or "")
        elif message.get("role") == "user":
            user = str(message.get("content") or "")
    return system, user


def estimate_input_tokens(payload: Mapping[str, Any]) -> dict[str, Any]:
    system, user = _user_and_system(payload)
    joined = system + "\n" + user
    local = estimate_tokens(joined, model=MODEL)
    chars = len(joined)
    pessimistic = int(math.ceil(Decimal(chars) / PESSIMISTIC_CHARS_PER_TOKEN))
    chosen = max(int(local.tokens or 0), pessimistic)
    return {
        "phase": PHASE,
        "method_primary": local.method,
        "method_pessimistic": "historical_4b24_chars_per_token_1.9365",
        "documented_local_methods": [local.method, "historical_4b24_chars_per_token_1.9365"],
        "estimated": True,
        "primary_tokens": int(local.tokens or 0),
        "pessimistic_tokens": pessimistic,
        "chosen_tokens": chosen,
        "chosen_is_max_of_local_methods": True,
        "request_chars": chars,
        "system_chars": len(system),
        "user_chars": len(user),
        "unknown_is_not_zero": True,
        "secrets_included": False,
    }


def tokens_to_usd(*, input_tokens: int, output_tokens: int) -> dict[str, Any]:
    input_cost = (Decimal(input_tokens) / MILLION) * TERRA_INPUT_COST_PER_1M
    output_cost = (Decimal(output_tokens) / MILLION) * TERRA_OUTPUT_COST_PER_1M
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


def choose_output_cap(input_tokens: int) -> dict[str, Any]:
    priced_input = (Decimal(input_tokens) / MILLION) * TERRA_INPUT_COST_PER_1M
    remaining = BUDGET_CAP_USD - priced_input
    if remaining <= 0:
        return {
            "ok": False,
            "reason": "input_alone_exceeds_budget",
            "max_completion_tokens": None,
            "theoretical_max_usd": _money(priced_input),
            "usable": False,
        }
    max_out = int(remaining / TERRA_OUTPUT_COST_PER_1M * MILLION)
    chosen = min(max_out, int(HISTORICAL_CONSERVATIVE_OUTPUT))
    usable = chosen >= MIN_USABLE_OUTPUT_TOKENS
    theoretical = tokens_to_usd(input_tokens=input_tokens, output_tokens=chosen)
    over = theoretical["decimal_total"] > BUDGET_CAP_USD
    return {
        "ok": usable and not over,
        "reason": (
            None
            if usable and not over
            else ("theoretical_max_exceeds_budget" if over else "usable_output_exceeds_budget")
        ),
        "max_completion_tokens": chosen,
        "max_affordable_output_tokens": max_out,
        "min_usable_output_tokens": MIN_USABLE_OUTPUT_TOKENS,
        "historical_conservative_output": HISTORICAL_CONSERVATIVE_OUTPUT,
        "theoretical_max_usd": theoretical["total_cost_usd"],
        "usable": usable,
        "over_budget": over,
        "did_not_arbitrarily_squeeze_below_usable": chosen >= MIN_USABLE_OUTPUT_TOKENS or not usable,
        "reasoning_included_in_completion_cap": True,
        "8192_exceeds_budget": True,
    }


def reserve_budget(payload: Mapping[str, Any]) -> dict[str, Any]:
    pricing = pricing_context()
    input_est = estimate_input_tokens(payload)
    input_tokens = int(input_est["chosen_tokens"])
    cap = choose_output_cap(input_tokens)
    max_out = cap.get("max_completion_tokens")
    catalog = None
    if max_out is not None:
        catalog = estimate_cost(input_tokens, int(max_out))
    full_8192 = estimate_cost(input_tokens, int(HISTORICAL_CONSERVATIVE_OUTPUT))
    long_context_applicable = input_tokens + int(max_out or 0) >= 200_000
    rates_usable = (
        pricing.get("verified") is True
        and pricing.get("input_cost_per_1m_tokens") is not None
        and pricing.get("output_cost_per_1m_tokens") is not None
        and not long_context_applicable
    )
    theoretical = cap.get("theoretical_max_usd")
    within = (
        theoretical is not None
        and Decimal(str(theoretical)) <= BUDGET_CAP_USD
        and bool(cap.get("ok"))
        and rates_usable
    )
    return {
        "phase": PHASE,
        "provider": PROVIDER,
        "model": MODEL,
        "maximum_remote_calls": 1,
        "budget_cap_usd": float(BUDGET_CAP_USD),
        "budget_cap_display": BUDGET_CAP_DISPLAY,
        "pricing": pricing,
        "pricing_effective_date": PRICING_EFFECTIVE_DATE,
        "pricing_are_configured_project_rates": True,
        "not_live_provider_prices": True,
        "historical_rates_are_not_a_current_invoice_guarantee": True,
        "rates_established_with_sufficient_certainty": rates_usable,
        "long_context_regime": "NOT APPLICABLE" if not long_context_applicable else "UNKNOWN",
        "input_estimate": input_est,
        "output_cap": cap,
        "max_completion_tokens": max_out,
        "catalog_estimate": catalog,
        "if_8192_exhausted": full_8192,
        "theoretical_maximum_usd": theoretical,
        "within_budget": within,
        "unknown_is_not_zero": True,
        "reasoning_tokens": "UNKNOWN_INCLUDED_IN_COMPLETION_CAP",
        "reasoning_not_double_counted": True,
        "not_a_provider_invoice": True,
        "reservation_is_not_an_invoice": True,
        "blocked": not within,
        "block_reason": (
            None
            if within
            else (
                "pricing_insufficient_certainty"
                if not rates_usable
                else cap.get("reason") or "budget_cap"
            )
        ),
        "secrets_included": False,
    }


__all__ = [
    "choose_output_cap",
    "estimate_input_tokens",
    "reserve_budget",
    "tokens_to_usd",
]
