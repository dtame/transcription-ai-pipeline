"""Scénarios de coût — pas des prédictions provider."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

from app.source_analysis_window_output_bounding.size_study import run_size_study
from app.source_analysis_post_canary_architecture.constants import (
    CALL1_COST_USD,
    CALL2_COST,
    HISTORICAL_RATIO,
    HISTORICAL_RATIO_LABEL,
    INPUT_COST_PER_1M,
    OUTPUT_COST_PER_1M,
    PHASE,
    SCHEMA_VERSION,
    TOKENS_PER_MILLION,
)

_MONEY = Decimal("0.000001")


def money(value: Decimal) -> str:
    quantized = value.quantize(_MONEY, rounding=ROUND_HALF_UP)
    return f"{quantized:.6f}"


def tokens_cost(tokens: int, per_million: Decimal) -> Decimal:
    return (Decimal(int(tokens)) / TOKENS_PER_MILLION) * per_million


def _output_tokens_for_window(
    *,
    mean_words: float,
    baseline_words: float,
    size_local: int,
    floor: int,
    cap: int,
) -> int:
    if baseline_words <= 0:
        scale = 1.0
    else:
        scale = min(1.0, max(0.25, float(mean_words) / float(baseline_words)))
    estimated = int(round(size_local * scale))
    return max(floor, min(cap, estimated))


def plan_cost_scenarios(
    plan: Mapping[str, Any],
    *,
    size_study: Mapping[str, Any],
    baseline_words: float,
    consolidation_calls_direct: int,
    consolidation_calls_hierarchical: int,
) -> dict[str, Any]:
    windows = list(plan.get("windows") or [])
    local_inputs = [
        int(window.get("local_estimated_request_1_1") or 0) for window in windows
    ]
    window_count = int(plan.get("window_count") or 0)
    mean_words = float((plan.get("words") or {}).get("mean") or 0.0)
    scenarios = (size_study.get("scenarios") or {})
    small = int((scenarios.get("SMALL") or {}).get("local_estimated_tokens") or 1500)
    medium = int((scenarios.get("MEDIUM") or {}).get("local_estimated_tokens") or 4000)
    large = int((scenarios.get("LARGE") or {}).get("local_estimated_tokens") or 8000)
    stress = int((scenarios.get("STRESS") or {}).get("local_estimated_tokens") or 11000)

    output_low = _output_tokens_for_window(
        mean_words=mean_words,
        baseline_words=baseline_words,
        size_local=small,
        floor=800,
        cap=6000,
    )
    output_medium = _output_tokens_for_window(
        mean_words=mean_words,
        baseline_words=baseline_words,
        size_local=medium,
        floor=1500,
        cap=12000,
    )
    output_stress = _output_tokens_for_window(
        mean_words=mean_words,
        baseline_words=baseline_words,
        size_local=max(large, stress),
        floor=3000,
        cap=16000,
    )

    local_input_total = sum(local_inputs)
    historical_input_total = int(
        (Decimal(local_input_total) * HISTORICAL_RATIO).to_integral_value(
            rounding=ROUND_HALF_UP
        )
    )
    local_input_cost = tokens_cost(local_input_total, INPUT_COST_PER_1M)
    historical_input_cost = tokens_cost(historical_input_total, INPUT_COST_PER_1M)

    def _output_block(per_window: int) -> dict[str, Any]:
        total = per_window * window_count
        cost = tokens_cost(total, OUTPUT_COST_PER_1M)
        return {
            "per_window_output_tokens": per_window,
            "total_output_tokens": total,
            "output_cost_usd": money(cost),
            "assumption": "SCENARIO, NOT PREDICTION",
        }

    outputs = {
        "LOW": _output_block(output_low),
        "MEDIUM": _output_block(output_medium),
        "POLICY_STRESS": _output_block(output_stress),
    }

    def _total(input_cost: Decimal, output_key: str) -> str:
        out = Decimal(outputs[output_key]["output_cost_usd"])
        return money(input_cost + out)

    consolidation_unmeasured = {
        "status": "NOT_YET_MEASURED",
        "direct_extra_calls": consolidation_calls_direct,
        "hierarchical_extra_calls_if_triggered": consolidation_calls_hierarchical,
        "cost": "UNKNOWN",
        "counted_as_zero": False,
        "note": (
            "Consolidation provider spend is additional. It is not hidden "
            "and is not treated as zero."
        ),
    }
    return {
        "label": plan.get("label"),
        "window_count": window_count,
        "provider_window_calls": window_count,
        "local_input_total_tokens": local_input_total,
        "historical_ratio_input_total_tokens": historical_input_total,
        "input_scenarios": {
            "LOCAL_ESTIMATE": {
                "kind": "SCENARIO, NOT PREDICTION",
                "tokens": local_input_total,
                "cost_usd": money(local_input_cost),
            },
            "HISTORICAL_RATIO": {
                "kind": "SCENARIO, NOT PREDICTION",
                "formula": HISTORICAL_RATIO_LABEL,
                "ratio": str(HISTORICAL_RATIO),
                "tokens": historical_input_total,
                "cost_usd": money(historical_input_cost),
            },
        },
        "output_scenarios": outputs,
        "window_analysis_only_totals": {
            "LOCAL_ESTIMATE_LOW": _total(local_input_cost, "LOW"),
            "LOCAL_ESTIMATE_MEDIUM": _total(local_input_cost, "MEDIUM"),
            "LOCAL_ESTIMATE_POLICY_STRESS": _total(local_input_cost, "POLICY_STRESS"),
            "HISTORICAL_RATIO_LOW": _total(historical_input_cost, "LOW"),
            "HISTORICAL_RATIO_MEDIUM": _total(historical_input_cost, "MEDIUM"),
            "HISTORICAL_RATIO_POLICY_STRESS": _total(
                historical_input_cost, "POLICY_STRESS"
            ),
        },
        "corpus_range_window_analysis_only": {
            "low_usd": _total(local_input_cost, "LOW"),
            "high_usd": _total(historical_input_cost, "POLICY_STRESS"),
            "kind": "SCENARIO RANGE, NOT PREDICTION",
        },
        "consolidation": consolidation_unmeasured,
        "repeat_one_failed_window": {
            "local_input_cost_usd": money(
                tokens_cost(int(plan.get("local_estimated_request", {}).get("max") or 0), INPUT_COST_PER_1M)
            ),
            "historical_ratio_input_cost_usd": money(
                tokens_cost(
                    int(
                        (
                            Decimal(
                                int(
                                    (plan.get("local_estimated_request") or {}).get("max")
                                    or 0
                                )
                            )
                            * HISTORICAL_RATIO
                        ).to_integral_value(rounding=ROUND_HALF_UP)
                    ),
                    INPUT_COST_PER_1M,
                )
            ),
            "output_unknown": True,
            "kind": "SCENARIO, NOT PREDICTION",
        },
        "not_provider_billing_prediction": True,
    }


def build_cost_artifact(
    simulations: Mapping[str, Any],
    *,
    consolidation_by_label: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    size_study = run_size_study()
    current = simulations["current_three_window"]
    baseline_words = float((current.get("words") or {}).get("mean") or 12745)
    rows = [current, *list(simulations.get("candidates") or [])]
    plans: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("feasible", True):
            plans.append(
                {
                    "label": row.get("label"),
                    "feasible": False,
                    "infeasible_reason": row.get("infeasible_reason"),
                }
            )
            continue
        label = str(row.get("label"))
        scaling = (consolidation_by_label or {}).get(label) or {}
        window_count = int(row.get("window_count") or 0)
        regional_groups = int(
            (scaling.get("hierarchy") or {}).get("regional_group_count") or 0
        )
        plans.append(
            plan_cost_scenarios(
                row,
                size_study=size_study,
                baseline_words=baseline_words,
                consolidation_calls_direct=1,
                consolidation_calls_hierarchical=regional_groups + 1,
            )
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "OFFLINE_COST_SCENARIOS",
        "real_provider_calls": 0,
        "kind": "SCENARIO, NOT PREDICTION",
        "pricing": {
            "input_usd_per_1m": str(INPUT_COST_PER_1M),
            "output_usd_per_1m": str(OUTPUT_COST_PER_1M),
            "source": "configured base catalog, no web research",
        },
        "historical_spend": {
            "call_1_usd": str(CALL1_COST_USD),
            "call_1_status": "KNOWN",
            "call_2_usd": CALL2_COST,
            "call_2_status": "UNKNOWN",
            "call_2_counted_as_zero": False,
            "known_minimum_usd": str(CALL1_COST_USD),
            "total_actual_usd": "UNKNOWN",
            "unknown_is_not_zero": True,
        },
        "size_study_output_anchors": {
            name: int(spec.get("local_estimated_tokens") or 0)
            for name, spec in (size_study.get("scenarios") or {}).items()
        },
        "plans": plans,
    }
