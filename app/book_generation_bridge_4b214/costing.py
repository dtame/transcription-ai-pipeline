"""Cost assumptions and estimates. Local configured tariffs only. No network."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from app.book_generation_bridge_4b214.constants import (
    CANDIDATE_GRANULARITY,
    COST_UNKNOWN,
    GENERATOR_MODEL,
    GENERATOR_PROVIDER,
    HISTORICAL_4B211_COMPLETION_TOKENS,
    HISTORICAL_4B211_COST_USD,
    HISTORICAL_4B211_INPUT_TOKENS,
    HISTORICAL_4B211_REASONING_TOKENS,
    PHASE,
    PRICING_EFFECTIVE_DATE,
    SEMANTIC_GATE_MODEL,
    SEMANTIC_GATE_PROVIDER,
    SONNET_INPUT_COST_PER_1M,
    SONNET_OUTPUT_COST_PER_1M,
    TERRA_INPUT_COST_PER_1M,
    TERRA_OUTPUT_COST_PER_1M,
)
from app.book_generation_bridge_4b214.paths import repo_root
from app.book_generation_bridge_4b214.scenarios import request_volume_scenarios


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _usd(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(Decimal("0.000001")))


def _band(central: Decimal | None, *, low_factor: str, high_factor: str) -> dict[str, Any]:
    if central is None:
        return {
            "low_usd": None,
            "central_usd": None,
            "high_usd": None,
            "status": COST_UNKNOWN,
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


def cost_assumptions() -> dict[str, Any]:
    h01_in = Decimal(HISTORICAL_4B211_INPUT_TOKENS)
    h01_out = Decimal(HISTORICAL_4B211_COMPLETION_TOKENS)
    implied = (h01_in / Decimal("1000000")) * Decimal(str(TERRA_INPUT_COST_PER_1M)) + (
        h01_out / Decimal("1000000")
    ) * Decimal(str(TERRA_OUTPUT_COST_PER_1M))
    return {
        "phase": PHASE,
        "pricing_source": "app.config.AI_PRICING_ENTRIES",
        "pricing_effective_date": PRICING_EFFECTIVE_DATE,
        "tariffs_are_not_necessarily_current": True,
        "no_network_rate_lookup": True,
        "terra": {
            "provider": SEMANTIC_GATE_PROVIDER,
            "model": SEMANTIC_GATE_MODEL,
            "input_cost_per_1m_tokens": TERRA_INPUT_COST_PER_1M,
            "output_cost_per_1m_tokens": TERRA_OUTPUT_COST_PER_1M,
            "unmodeled_regimes": "long_context_not_modeled",
            "status": "base_estimate",
        },
        "sonnet": {
            "provider": GENERATOR_PROVIDER,
            "model": GENERATOR_MODEL,
            "input_cost_per_1m_tokens": SONNET_INPUT_COST_PER_1M,
            "output_cost_per_1m_tokens": SONNET_OUTPUT_COST_PER_1M,
            "status": "estimated",
        },
        "h01_canary_measured_once": {
            "input_tokens": HISTORICAL_4B211_INPUT_TOKENS,
            "completion_tokens": HISTORICAL_4B211_COMPLETION_TOKENS,
            "reasoning_tokens": HISTORICAL_4B211_REASONING_TOKENS,
            "recorded_cost_usd": HISTORICAL_4B211_COST_USD,
            "implied_input_plus_completion_usd": _usd(implied),
            "reasoning_separately_billed": COST_UNKNOWN,
            "scope": "one paragraph / five units / one Terra call",
            "not_a_19_chapter_estimate": True,
            "not_a_generated_book_paragraph": True,
        },
        "future_paragraphs": {
            "average_paragraphs_per_section": "ASSUMPTION 2 / 4 / 7",
            "average_units_per_paragraph": "ASSUMPTION 2 / 4 / 8; h01 had 5",
            "average_tokens_per_paragraph": "UNKNOWN; h01 used as a small analog only",
            "average_evidence_tokens_per_paragraph": "UNKNOWN",
            "output_tokens_per_unit": "UNKNOWN",
            "reasoning_tokens": "UNKNOWN",
            "counted_as_zero": False,
        },
        "old_4b23_chapter_call_envelope": {
            "reused_as_primary_semantic_gate_estimate": False,
            "reason": "That envelope assumed one call per chapter. Current validator requires one paragraph per response.",
        },
        "secrets_included": False,
    }


def cost_estimates(
    *,
    root: Path | None = None,
    volumes: Mapping[str, Any] | None = None,
    scenarios: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base = root or repo_root()
    generator = _load(base / "audit" / "book_generator_4b1" / "book_generator_4b1_cost_estimate.json")
    old_semantic = _load(
        base / "audit" / "book_semantic_gate_4b23" / "book_semantic_gate_4b23_cost_estimate.json"
    )
    gen_central = (
        Decimal(str(generator["total_cost_usd"]))
        if generator.get("total_cost_usd") is not None
        else None
    )
    generator_band = {
        **_band(gen_central, low_factor="0.6", high_factor="2.0"),
        "status": generator.get("status") or "estimated",
        "source": "audit/book_generator_4b1/book_generator_4b1_cost_estimate.json",
        "provider": generator.get("provider") or GENERATOR_PROVIDER,
        "model": generator.get("model") or GENERATOR_MODEL,
        "pricing_verified": generator.get("pricing_verified"),
        "pricing_effective_date": generator.get("pricing_effective_date") or PRICING_EFFECTIVE_DATE,
        "estimated_production_calls": generator.get("estimated_production_calls"),
        "unknown_or_incomplete": bool(generator.get("unknown_or_incomplete")),
        "note": "4B.1 documented 19-chapter envelope. Bands 0.6x/2.0x are assumptions, not measured 19-chapter spend.",
    }
    scenario_doc = scenarios or request_volume_scenarios(volumes)
    strategy_a = dict(scenario_doc.get("strategy_a") or {})
    per_call = Decimal("0.006286")
    a_low = Decimal(str(strategy_a.get("requests_low") or 0)) * per_call
    a_central = Decimal(str(strategy_a.get("requests_central") or 0)) * per_call
    a_high = Decimal(str(strategy_a.get("requests_high") or 0)) * per_call
    semantic = {
        "status": "hypothesis",
        "granularity": CANDIDATE_GRANULARITY,
        "source": "h01 analog * assumed paragraph counts under strategy A",
        "provider": SEMANTIC_GATE_PROVIDER,
        "model": SEMANTIC_GATE_MODEL,
        "pricing_effective_date": PRICING_EFFECTIVE_DATE,
        "per_call_usd_h01_analog": float(per_call),
        "requests_low": strategy_a.get("requests_low"),
        "requests_central": strategy_a.get("requests_central"),
        "requests_high": strategy_a.get("requests_high"),
        "low_usd": _usd(a_low),
        "central_usd": _usd(a_central),
        "high_usd": _usd(a_high),
        "limited_resume_central_usd": _usd(a_central * Decimal("1.10")),
        "significant_resume_high_usd": _usd(a_high * Decimal("1.50")),
        "counted_as_zero": False,
        "unknown_or_incomplete": True,
        "not_measured_on_generated_book_paragraphs": True,
        "h01_not_extrapolated_as_fact": True,
        "old_4b23_chapter_call_envelope_not_reused_as_primary": {
            "central_usd": old_semantic.get("total_cost_usd"),
            "status": old_semantic.get("status"),
            "reused": False,
        },
        "reasoning_token_billing": COST_UNKNOWN,
        "long_context_pricing": COST_UNKNOWN,
    }
    phase5 = {
        "status": COST_UNKNOWN,
        "low_usd": None,
        "central_usd": None,
        "high_usd": None,
        "counted_as_zero": False,
        "reason": "Independent Book Validator is not implemented. No measured token use.",
    }
    resumption = {
        "status": COST_UNKNOWN,
        "low_usd": None,
        "central_usd": None,
        "high_usd": None,
        "counted_as_zero": False,
        "modeled_sensitivity_only": {
            "limited_plus_10_percent_on_gate_central": semantic["limited_resume_central_usd"],
            "significant_plus_50_percent_on_gate_high": semantic["significant_resume_high_usd"],
        },
    }
    unknown_items = [
        "phase5",
        "generated_paragraph_count",
        "generated_unit_count",
        "actual_tokens_per_generated_paragraph",
        "terra_reasoning_billing",
        "terra_long_context_pricing",
        "real_resume_cost",
    ]
    partial = None
    if gen_central is not None and semantic.get("central_usd") is not None:
        partial = gen_central + Decimal(str(semantic["central_usd"]))
    return {
        "phase": PHASE,
        "spent": False,
        "provider_calls": 0,
        "book_generator": generator_band,
        "semantic_gate": semantic,
        "phase5": phase5,
        "resumption": resumption,
        "unknown_items": unknown_items,
        "unknown_not_treated_as_zero": True,
        "partial_sum_generator_plus_strategy_a_gate": {
            "low_usd": _usd(
                Decimal(str(generator_band["low_usd"])) + Decimal(str(semantic["low_usd"]))
            )
            if generator_band.get("low_usd") is not None and semantic.get("low_usd") is not None
            else None,
            "central_usd": _usd(partial) if partial is not None else None,
            "high_usd": _usd(
                Decimal(str(generator_band["high_usd"])) + Decimal(str(semantic["high_usd"]))
            )
            if generator_band.get("high_usd") is not None and semantic.get("high_usd") is not None
            else None,
            "excludes": unknown_items,
            "complete_total": COST_UNKNOWN,
            "counted_as_zero": False,
        },
        "total_complete_usd": None,
        "total_complete_status": COST_UNKNOWN,
        "candidate_granularity": CANDIDATE_GRANULARITY,
        "secrets_included": False,
    }


__all__ = ["cost_assumptions", "cost_estimates"]
