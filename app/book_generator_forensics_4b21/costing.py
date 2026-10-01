"""Future CH016 and optional Terra semantic-gate cost estimates. Not spent."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

from app.ai.pricing import build_default_catalog
from app.book_generator_forensics_4b21.constants import (
    EXPECTED_MAX_OUTPUT,
    FUTURE_MODEL,
)


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)} USD"


def future_cost_estimate(
    future_request: Mapping[str, Any],
    *,
    historical_input_tokens: int = 6063,
    historical_output_tokens: int = 1754,
    historical_cost_usd: float = 0.029666,
) -> dict[str, Any]:
    catalog = build_default_catalog()
    sonnet = catalog.get("anthropic", "claude-sonnet-5")
    terra = catalog.get("openai", "gpt-5.6-terra")
    historical_system = 3238
    historical_user = 9944
    future_system = int(future_request.get("system_prompt_chars") or 0)
    future_user = int(future_request.get("user_prompt_chars") or 0)
    char_ratio = (future_system + future_user) / max(1, historical_system + historical_user)
    estimated_input = int(round(historical_input_tokens * char_ratio))
    estimated_output = historical_output_tokens
    million = Decimal("1000000")
    input_cost = (Decimal(estimated_input) / million) * sonnet.input_cost_per_1m_tokens
    output_cost = (Decimal(estimated_output) / million) * sonnet.output_cost_per_1m_tokens
    total = input_cost + output_cost
    terra_in = estimated_input + estimated_output
    terra_out = 1500
    terra_input_cost = (Decimal(terra_in) / million) * terra.input_cost_per_1m_tokens
    terra_output_cost = (Decimal(terra_out) / million) * terra.output_cost_per_1m_tokens
    terra_one = terra_input_cost + terra_output_cost
    terra_nineteen = terra_one * Decimal(19)
    return {
        "spent": False,
        "counted_as_spent": False,
        "future_model": FUTURE_MODEL,
        "future_max_output": EXPECTED_MAX_OUTPUT,
        "calibration": {
            "historical_input_tokens": historical_input_tokens,
            "historical_output_tokens": historical_output_tokens,
            "historical_cost_usd": historical_cost_usd,
            "historical_system_chars": historical_system,
            "historical_user_chars": historical_user,
            "future_system_chars": future_system,
            "future_user_chars": future_user,
            "input_char_ratio": round(char_ratio, 6),
        },
        "hardened_ch016": {
            "estimated_input_tokens": estimated_input,
            "estimated_output_tokens": estimated_output,
            "input_cost_usd": float(input_cost),
            "output_cost_usd": float(output_cost),
            "total_cost_usd": float(total),
            "total_cost_display": _money(total),
            "pricing_verified": bool(sonnet.verified),
            "not_executed": True,
        },
        "future_terra_chapter_semantic_gate": {
            "model": "openai / gpt-5.6-terra",
            "independence_from_generator": True,
            "estimated_calls_if_per_chapter": 19,
            "estimated_input_tokens_per_call": terra_in,
            "estimated_output_tokens_per_call": terra_out,
            "estimated_cost_usd_per_call": float(terra_one),
            "estimated_cost_usd_19_chapters": float(terra_nineteen),
            "cost_status": "base_estimate",
            "unmodeled_regimes": terra.unmodeled_regimes,
            "not_executed": True,
        },
        "note": (
            "Estimates only. Hardened CH016 is not spent. Terra semantic-gate "
            "cost is architecture analysis only."
        ),
    }
