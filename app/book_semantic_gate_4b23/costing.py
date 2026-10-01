"""Terra semantic-gate cost estimate. Unknown != zero. No spend."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Sequence

from app.ai.pricing import (
    COST_STATUS_BASE_ESTIMATE,
    REGIME_LONG_CONTEXT,
    build_default_catalog,
)
from app.book_semantic_gate_4b23.constants import (
    PREVIOUS_19_CHAPTER_COST_USD,
    SEMANTIC_GATE_MODEL,
    SEMANTIC_GATE_PROVIDER,
)


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.000001'))} USD"


def estimate_from_budgets(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    catalog = build_default_catalog()
    pricing = catalog.get(SEMANTIC_GATE_PROVIDER, SEMANTIC_GATE_MODEL)
    if pricing is None:
        return {
            "status": "unknown",
            "reason": "no verified Terra pricing",
            "total_cost_usd": None,
            "unknown_or_incomplete": True,
            "counted_as_zero": False,
            "spent": False,
        }
    input_tokens = 0
    output_tokens = 0
    chapter_costs = []
    for row in rows:
        request = dict(row.get("request") or {})
        output = dict(row.get("output") or {})
        inp = int(request.get("provider_adjusted_pessimistic") or 0)
        out = int(output.get("conservative_output_tokens") or 0)
        input_tokens += inp
        output_tokens += out
        breakdown = catalog.estimate_cost(
            SEMANTIC_GATE_PROVIDER, SEMANTIC_GATE_MODEL, inp, out
        )
        chapter_costs.append(
            {
                "chapter_id": row.get("chapter_id"),
                "input_tokens": inp,
                "output_tokens": out,
                "cost_usd": (
                    float(breakdown.total_cost)
                    if breakdown.total_cost is not None
                    else None
                ),
                "status": breakdown.status,
            }
        )
    total = catalog.estimate_cost(
        SEMANTIC_GATE_PROVIDER, SEMANTIC_GATE_MODEL, input_tokens, output_tokens
    )
    amount = total.total_cost
    max_input = max(
        (int((row.get("request") or {}).get("provider_adjusted_pessimistic") or 0) for row in rows),
        default=0,
    )
    return {
        "spent": False,
        "counted_as_spent": False,
        "counted_as_zero": False,
        "provider": SEMANTIC_GATE_PROVIDER,
        "model": SEMANTIC_GATE_MODEL,
        "pricing_verified": bool(pricing.verified),
        "pricing_effective_date": pricing.effective_date,
        "input_cost_per_1m_tokens": float(pricing.input_cost_per_1m_tokens),
        "output_cost_per_1m_tokens": float(pricing.output_cost_per_1m_tokens),
        "input_tokens_pessimistic": input_tokens,
        "output_tokens_conservative": output_tokens,
        "input_cost_usd": float(total.input_cost) if total.input_cost is not None else None,
        "output_cost_usd": float(total.output_cost) if total.output_cost is not None else None,
        "total_cost_usd": float(amount) if amount is not None else None,
        "total_cost_display": _money(amount) if amount is not None else "unknown",
        "status": total.status,
        "unknown_or_incomplete": total.status != "known",
        "unmodeled_regimes": total.unmodeled_regimes or REGIME_LONG_CONTEXT,
        "estimated_production_calls": len(rows),
        "previous_rough_estimate_usd": PREVIOUS_19_CHAPTER_COST_USD,
        "previous_estimate_frozen": False,
        "chapter_costs": chapter_costs,
        "long_context": {
            "regime": REGIME_LONG_CONTEXT,
            "exact_threshold_modeled": False,
            "assumed_applied": False,
            "largest_request_input_tokens": max_input,
            "context_window": 1_050_000,
            "note": (
                "Phase 2B does not model Terra long-context pricing thresholds. "
                "Current chapter estimates are a small fraction of the verified "
                "1,050,000-token context window, so the long-context regime is "
                "not assumed to apply. Because the threshold is unknown, cost "
                "remains base_estimate, not known. Unknown != zero."
            ),
        },
        "note": (
            "Estimate uses pessimistic input tokens and conservative audit "
            "output. Actual cost is unknown until real Terra usage is reported."
        ),
        "cost_status_is_not_known": total.status == COST_STATUS_BASE_ESTIMATE,
    }


__all__ = ["estimate_from_budgets"]
