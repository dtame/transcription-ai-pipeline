"""Production cost estimate from Sonnet 5 verified pricing. No calls."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Sequence

from app.ai.pricing import build_default_catalog
from app.book_generation.constants import MODEL, PROVIDER, STAGE_BOOK_GENERATION


def _money(value: Decimal) -> str:
    return f"${value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}"


def estimate_production_cost(
    chapter_budgets: Sequence[dict[str, Any]],
    *,
    provider: str = PROVIDER,
    model: str = MODEL,
) -> dict[str, Any]:
    catalog = build_default_catalog()
    pricing = catalog.get(provider, model)
    if pricing is None:
        return {
            "status": "unknown",
            "reason": f"no verified pricing for {provider}/{model}",
            "input_cost_usd": None,
            "output_cost_usd": None,
            "total_cost_usd": None,
            "estimated_production_calls": len(chapter_budgets),
        }
    input_tokens = 0
    output_tokens = 0
    for row in chapter_budgets:
        request = dict(row.get("request") or {})
        output = dict(row.get("output") or {})
        input_tokens += int(request.get("provider_adjusted_pessimistic") or 0)
        output_tokens += int(output.get("conservative_output_tokens") or 0)
    million = Decimal("1000000")
    input_cost = (Decimal(input_tokens) / million) * pricing.input_cost_per_1m_tokens
    output_cost = (Decimal(output_tokens) / million) * pricing.output_cost_per_1m_tokens
    total = input_cost + output_cost
    return {
        "status": "estimated",
        "provider": provider,
        "model": model,
        "stage": STAGE_BOOK_GENERATION,
        "pricing_verified": bool(pricing.verified),
        "pricing_effective_date": pricing.effective_date,
        "input_tokens_pessimistic": input_tokens,
        "output_tokens_conservative": output_tokens,
        "input_cost_per_1m_tokens": float(pricing.input_cost_per_1m_tokens),
        "output_cost_per_1m_tokens": float(pricing.output_cost_per_1m_tokens),
        "input_cost_usd": float(input_cost),
        "output_cost_usd": float(output_cost),
        "total_cost_usd": float(total),
        "total_cost_display": _money(total),
        "estimated_production_calls": len(chapter_budgets),
        "unknown_or_incomplete": False,
        "note": (
            "Estimate uses pessimistic input tokens and conservative manuscript "
            "output. Actual cost is unknown until real usage is reported."
        ),
    }
