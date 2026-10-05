"""Cost estimates from documented tariffs and historical measurements. No spend."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.book_generation_integration_4b213.constants import (
    HISTORICAL_4B211_COMPLETION_TOKENS,
    HISTORICAL_4B211_COST_USD,
    HISTORICAL_4B211_INPUT_TOKENS,
    HISTORICAL_4B211_REASONING_TOKENS,
    PHASE,
)
from app.book_generation_integration_4b213.paths import repo_root


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _band(central: Decimal | None, *, low_factor: str, high_factor: str) -> dict[str, Any]:
    if central is None:
        return {
            "low_usd": None,
            "central_usd": None,
            "high_usd": None,
            "status": "UNKNOWN",
            "counted_as_zero": False,
        }
    low = (central * Decimal(low_factor)).quantize(Decimal("0.000001"))
    high = (central * Decimal(high_factor)).quantize(Decimal("0.000001"))
    return {
        "low_usd": float(low),
        "central_usd": float(central),
        "high_usd": float(high),
        "low_factor": low_factor,
        "high_factor": high_factor,
        "factors_are_assumptions_not_measured": True,
        "counted_as_zero": False,
    }


def cost_estimates(*, root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    generator = _load(base / "audit" / "book_generator_4b1" / "book_generator_4b1_cost_estimate.json")
    semantic = _load(
        base / "audit" / "book_semantic_gate_4b23" / "book_semantic_gate_4b23_cost_estimate.json"
    )
    gen_central = (
        Decimal(str(generator["total_cost_usd"]))
        if generator.get("total_cost_usd") is not None
        else None
    )
    sem_central = (
        Decimal(str(semantic["total_cost_usd"]))
        if semantic.get("total_cost_usd") is not None
        else None
    )
    generator_band = {
        **_band(gen_central, low_factor="0.6", high_factor="2.0"),
        "status": generator.get("status") or "estimated",
        "source": "audit/book_generator_4b1/book_generator_4b1_cost_estimate.json",
        "provider": generator.get("provider"),
        "model": generator.get("model"),
        "pricing_verified": generator.get("pricing_verified"),
        "pricing_effective_date": generator.get("pricing_effective_date"),
        "input_tokens_pessimistic": generator.get("input_tokens_pessimistic"),
        "output_tokens_conservative": generator.get("output_tokens_conservative"),
        "estimated_production_calls": generator.get("estimated_production_calls"),
        "low_assumption": "If actual tokens are about 60% of the 4B.1 pessimistic/conservative envelope. NOT MEASURED.",
        "high_assumption": "If section fallback effectively doubles generation work. NOT MEASURED. Retries remain 0.",
        "unknown_or_incomplete": bool(generator.get("unknown_or_incomplete")),
    }
    semantic_band = {
        **_band(sem_central, low_factor="0.6", high_factor="2.0"),
        "status": semantic.get("status") or "UNKNOWN",
        "source": "audit/book_semantic_gate_4b23/book_semantic_gate_4b23_cost_estimate.json",
        "provider": semantic.get("provider"),
        "model": semantic.get("model"),
        "pricing_verified": semantic.get("pricing_verified"),
        "granularity": "one_call_per_chapter_as_documented_in_4b23",
        "unmodeled_regimes": semantic.get("unmodeled_regimes"),
        "unknown_or_incomplete": True,
        "low_assumption": "If actual chapter-call tokens are about 60% of the 4B.2.3 envelope. NOT MEASURED.",
        "high_assumption": "If output/thinking exceeds the conservative envelope. NOT MEASURED. Long-context regime remains unmodeled.",
        "per_paragraph_scale": "UNKNOWN",
        "h01_canary_limit": {
            "historical_4b211_cost": HISTORICAL_4B211_COST_USD,
            "input_tokens": HISTORICAL_4B211_INPUT_TOKENS,
            "completion_tokens": HISTORICAL_4B211_COMPLETION_TOKENS,
            "reasoning_tokens": HISTORICAL_4B211_REASONING_TOKENS,
            "scope": "one paragraph / five units / one Terra call",
            "not_a_19_chapter_estimate": True,
            "do_not_extrapolate_without_paragraph_count": True,
        },
    }
    phase5 = {
        "status": "UNKNOWN",
        "low_usd": None,
        "central_usd": None,
        "high_usd": None,
        "counted_as_zero": False,
        "reason": "Phase 5 Book Validator is not implemented. No measured token use.",
    }
    resumption = {
        "status": "UNKNOWN",
        "low_usd": None,
        "central_usd": None,
        "high_usd": None,
        "counted_as_zero": False,
        "reason": "Resume cost depends on interrupted chapters. No real resume was executed.",
    }
    unknown_items = ["phase5", "resumption", "per_paragraph_semantic_gate_scale"]
    partial_central = None
    if gen_central is not None and sem_central is not None:
        partial_central = gen_central + sem_central
    return {
        "phase": PHASE,
        "spent": False,
        "provider_calls": 0,
        "book_generator": generator_band,
        "semantic_gate": semantic_band,
        "phase5": phase5,
        "resumption": resumption,
        "unknown_items": unknown_items,
        "unknown_not_treated_as_zero": True,
        "partial_sum_generator_plus_chapter_gate": {
            "low_usd": (
                float((Decimal(str(generator_band["low_usd"])) + Decimal(str(semantic_band["low_usd"]))).quantize(Decimal("0.000001")))
                if generator_band.get("low_usd") is not None and semantic_band.get("low_usd") is not None
                else None
            ),
            "central_usd": float(partial_central) if partial_central is not None else None,
            "high_usd": (
                float((Decimal(str(generator_band["high_usd"])) + Decimal(str(semantic_band["high_usd"]))).quantize(Decimal("0.000001")))
                if generator_band.get("high_usd") is not None and semantic_band.get("high_usd") is not None
                else None
            ),
            "excludes": unknown_items,
            "complete_total": "UNKNOWN",
            "counted_as_zero": False,
        },
        "total_complete_usd": None,
        "total_complete_status": "UNKNOWN",
        "risks_of_overrun": [
            "Section fallback on Book Generator.",
            "Per-paragraph Semantic Gate instead of one call per chapter.",
            "Unmodeled Terra long-context pricing.",
            "Human-review loops that authorize extra bounded rewrites.",
            "Phase 5 cost unknown.",
        ],
        "secrets_included": False,
    }


__all__ = ["cost_estimates"]
