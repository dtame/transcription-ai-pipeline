"""Scénarios de coût / risque. Aucune prédiction. 0 appel provider."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any

from app.ai.capabilities import resolve_capabilities
from app.ai.pricing import build_default_catalog
from app.ai.settings import resolve_stage_settings
from app.source_analysis.window_granularity import MAX_OUTPUT_TOKENS_FROZEN
from app.source_analysis.window_models import STAGE_WINDOW
from app.source_analysis_bounded_win001_retry_readiness.constants import (
    HARD_MAX_LOCAL_ESTIMATE,
    HISTORICAL_LOCAL_ESTIMATE,
    HISTORICAL_PROVIDER_INPUT,
    HISTORICAL_SPEND_USD,
    LONG_CONTEXT_THRESHOLD,
)
from app.source_analysis_hybrid_readiness.constants import TARGET_MODEL, TARGET_PROVIDER
from app.source_analysis_window_output_bounding.size_study import run_size_study

OUTPUT_SCENARIOS = (8000, 13023, 16000, 20000, 32000)
STRESS_RATIO = Decimal("2.5")


def _money(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _cost(tokens: int, per_million: Decimal) -> Decimal:
    return (Decimal(tokens) * per_million) / Decimal(1_000_000)


def build_cost_risk(
    *,
    local_estimated_input: int,
    size_study: dict[str, Any] | None = None,
) -> dict[str, Any]:
    study = size_study or run_size_study()
    catalog = build_default_catalog()
    pricing = catalog.get(TARGET_PROVIDER, TARGET_MODEL)
    input_rate = pricing.input_cost_per_1m_tokens if pricing else Decimal("2")
    output_rate = pricing.output_cost_per_1m_tokens if pricing else Decimal("10")
    settings = resolve_stage_settings(STAGE_WINDOW)
    capabilities = resolve_capabilities(TARGET_PROVIDER, TARGET_MODEL)
    usable = capabilities.usable_context(settings.context_safety_ratio)
    exact_ratio = Decimal(HISTORICAL_PROVIDER_INPUT) / Decimal(HISTORICAL_LOCAL_ESTIMATE)
    ratio_input = int(
        (Decimal(local_estimated_input) * exact_ratio).to_integral_value(
            rounding=ROUND_HALF_EVEN
        )
    )
    stress_input = int(
        (Decimal(local_estimated_input) * STRESS_RATIO).to_integral_value(
            rounding=ROUND_HALF_EVEN
        )
    )
    max_valid = int(study["max_policy_valid_local_tokens"])
    input_scenarios = {
        "LOCAL_ESTIMATE": {
            "kind": "SCENARIO",
            "not_prediction": True,
            "tokens": local_estimated_input,
            "label": "local estimator units",
        },
        "HISTORICAL_RATIO": {
            "kind": "SCENARIO",
            "not_prediction": True,
            "tokens": ratio_input,
            "ratio": format(exact_ratio, "f"),
            "ratio_display": "2.155975",
            "formula": f"{local_estimated_input} × ({HISTORICAL_PROVIDER_INPUT}/{HISTORICAL_LOCAL_ESTIMATE})",
            "observation_only": True,
        },
        "STRESS_2_5X": {
            "kind": "SCENARIO",
            "not_prediction": True,
            "tokens": stress_input,
            "ratio": "2.5",
            "justification": (
                "modest stress above the single 3B.7.7A observation; "
                "not a calibrated tokenizer"
            ),
        },
    }
    input_costs = {
        name: {
            "kind": "SCENARIO",
            "not_prediction": True,
            "tokens": row["tokens"],
            "usd": _money(_cost(int(row["tokens"]), input_rate)),
            "rate_per_1m": _money(input_rate),
        }
        for name, row in input_scenarios.items()
    }
    output_costs = {
        str(tokens): {
            "kind": "SCENARIO",
            "not_prediction": True,
            "tokens": tokens,
            "usd": _money(_cost(tokens, output_rate)),
            "rate_per_1m": _money(output_rate),
        }
        for tokens in OUTPUT_SCENARIOS
    }
    matrix: dict[str, dict[str, dict[str, Any]]] = {}
    for in_name, in_row in input_scenarios.items():
        matrix[in_name] = {}
        for out_tokens in OUTPUT_SCENARIOS:
            total = _cost(int(in_row["tokens"]), input_rate) + _cost(
                out_tokens, output_rate
            )
            matrix[in_name][str(out_tokens)] = {
                "kind": "SCENARIO",
                "not_prediction": True,
                "usd": _money(total),
            }
    ratio_tokens = int(input_scenarios["HISTORICAL_RATIO"]["tokens"])
    return {
        "kind": "RISK_REVIEW",
        "not_prediction": True,
        "historical_spend_usd": HISTORICAL_SPEND_USD,
        "historical_spend_separated": True,
        "potential_new_spend": "SCENARIO_RANGE_NOT_PREDICTION",
        "application_hard_dollar_cap": False,
        "call_budget_is_primary_spend_control": True,
        "max_new_calls": 1,
        "local_estimated_input": local_estimated_input,
        "hard_max_local_planner_units": HARD_MAX_LOCAL_ESTIMATE,
        "hard_max_is_not_provider_billing_ceiling": True,
        "within_hard_max": local_estimated_input <= HARD_MAX_LOCAL_ESTIMATE,
        "historical_ratio": {
            "observation": f"{HISTORICAL_PROVIDER_INPUT}/{HISTORICAL_LOCAL_ESTIMATE}",
            "value": format(exact_ratio, "f"),
            "display": "2.155975",
            "calibrated_tokenizer": False,
            "prediction": False,
        },
        "input_scenarios": input_scenarios,
        "context": {
            "provider": TARGET_PROVIDER,
            "model": TARGET_MODEL,
            "context_window": capabilities.context_window,
            "usable_context": usable,
            "safety_ratio": float(settings.context_safety_ratio),
            "historical_ratio_fits_usable": ratio_tokens <= usable,
            "historical_ratio_plus_32000_fits_usable": (
                ratio_tokens + MAX_OUTPUT_TOKENS_FROZEN
            )
            <= usable,
            "margin_vs_usable_historical_ratio": usable - ratio_tokens,
            "primary_retry_risk_is_not_input_context_overflow": True,
        },
        "long_context": {
            "threshold_protocol": LONG_CONTEXT_THRESHOLD,
            "threshold_encoded_in_repo": False,
            "historical_ratio_crosses_threshold": ratio_tokens
            > LONG_CONTEXT_THRESHOLD,
            "stress_2_5x_crosses_threshold": stress_input > LONG_CONTEXT_THRESHOLD,
        },
        "input_cost_scenarios": input_costs,
        "output_policy": {
            "max_output": MAX_OUTPUT_TOKENS_FROZEN,
            "max_policy_valid_local_tokens": max_valid,
            "percent_of_32000": study["percent_of_32000"],
            "safety_margin_tokens": study["safety_margin_tokens"],
            "why_keep_32000": (
                "semantic policy constrains expected output; local validator "
                "enforces hard limits; overflow signals capacity; 32k remains "
                "transport headroom; do not truncate solely because an "
                "operational cap was lowered prematurely"
            ),
        },
        "output_cost_scenarios": output_costs,
        "total_cost_matrix": matrix,
        "pricing": {
            "input_usd_per_1m": _money(input_rate),
            "output_usd_per_1m": _money(output_rate),
            "source": pricing.source if pricing else None,
            "effective_date": pricing.effective_date if pricing else None,
        },
    }
