"""Budget contexte/sortie/coût. Estimations. 0 appel réel."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Mapping

from app.ai.estimation import estimate_tokens
from app.source_analysis_v31_global_preflight.constants import (
    CONTEXT_WINDOW_TOKENS,
    FUTURE_COMPARISON_MODEL,
    GLOBAL_PROMPT_VERSION,
    GLOBAL_TRANSPORT_VERSION,
    HISTORICAL_GLOBAL_TIMEOUTS,
    INPUT_COST_PER_1M,
    MODE,
    MODEL,
    MODEL_MAX_OUTPUT_TOKENS,
    OPUS_INPUT_COST_PER_1M,
    OPUS_OUTPUT_COST_PER_1M,
    OUTPUT_COST_PER_1M,
    PHASE,
    PROPOSED_ARCHITECTURE,
    PROPOSED_MAX_OUTPUT,
    PROPOSED_THINKING_POLICY,
    PROVIDER,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_global_preflight.prompt import prompt_bundle
from app.source_analysis_v31_global_preflight.transport import measure_global_schema


def _money(tokens: int, per_million: float) -> str:
    amount = (Decimal(tokens) / Decimal(1_000_000)) * Decimal(str(per_million))
    return f"{amount.quantize(Decimal('0.000001'))} USD"


def _window_cost_summary(inventory: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    total_in = 0
    total_out = 0
    total_cost = Decimal("0")
    cost_known = True
    for window_id, row in (inventory.get("windows") or {}).items():
        cost = row.get("cost") or {}
        inp = int(row.get("provider_input_tokens") or 0)
        out = int(row.get("provider_output_tokens") or 0)
        total_in += inp
        total_out += out
        amount = cost.get("total_cost")
        if amount is None:
            cost_known = False
        else:
            total_cost += Decimal(str(amount))
        local = int(row.get("local_input_estimate") or 0)
        rows.append(
            {
                "window_id": window_id,
                "request_id": row.get("request_id"),
                "provider_input_tokens": row.get("provider_input_tokens"),
                "provider_output_tokens": row.get("provider_output_tokens"),
                "local_input_estimate": local,
                "input_ratio": (inp / local) if local else None,
                "elapsed_ms": row.get("elapsed_ms"),
                "cost": cost,
            }
        )
    ratios = [item["input_ratio"] for item in rows if item["input_ratio"]]
    return {
        "windows": rows,
        "real_calls_to_reach_seven_ready": len(rows),
        "total_provider_input_tokens": total_in,
        "total_provider_output_tokens": total_out,
        "total_cost_usd": str(total_cost.quantize(Decimal("0.000001"))) if cost_known else "UNKNOWN",
        "mean_provider_input_over_local": (sum(ratios) / len(ratios)) if ratios else None,
        "cost_tracker_mutated": False,
        "notes": "Summarized from saved execution artifacts only.",
    }


def build_context_budget(
    normalized: Mapping[str, Any],
    inventory: Mapping[str, Any],
    schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prompt = prompt_bundle()
    measured = schema or measure_global_schema()
    compact = json.dumps(normalized.get("compact") or {}, ensure_ascii=False, separators=(",", ":"))
    schema_json = json.dumps(measured.get("schema") or {}, ensure_ascii=False, separators=(",", ":"))
    request_text = "\n".join(
        [
            prompt["system"],
            prompt["instructions"],
            schema_json,
            compact,
        ]
    )
    local_est = estimate_tokens(request_text, model=MODEL)
    prompt_est = estimate_tokens(prompt["system"] + prompt["instructions"], model=MODEL)
    data_est = estimate_tokens(compact, model=MODEL)
    schema_est = estimate_tokens(schema_json, model=MODEL)
    mean_ratio = (inventory.get("totals") or {}).get(
        "observed_window_provider_input_over_local_mean"
    )
    if not isinstance(mean_ratio, (int, float)):
        mean_ratio = 2.15
    upper_bound = int(local_est.tokens * float(mean_ratio))
    json_adjusted = int(local_est.tokens * 1.5)
    planning = int(max(json_adjusted, local_est.tokens) * 1.2)
    idea_chars = sum(
        len(str(item.get("value") or ""))
        for item in normalized.get("all_records") or []
        if item.get("kind") == "IDEA"
    )
    other_chars = sum(
        len(str(item.get("value") or ""))
        for item in normalized.get("all_records") or []
        if item.get("kind") != "IDEA"
    )
    disp_chars = len(normalized.get("idea_input_ids") or []) * 48
    worst_output_chars = int((idea_chars + other_chars + disp_chars) * 1.35) + 2500
    worst_output_tokens = (worst_output_chars + 3) // 4
    output_ok = worst_output_tokens <= PROPOSED_MAX_OUTPUT
    one_call_input_ok = planning < (CONTEXT_WINDOW_TOKENS - PROPOSED_MAX_OUTPUT)
    thinking = {
        "local_extraction_contract": "THINKING_DISABLED",
        "consolidation_is_more_reasoning_heavy": True,
        "adaptive_previously_consumed_output_budget": True,
        "observed_call_c_thinking_tokens": 21911,
        "options": {
            "disabled": "protects 32000 output budget; proven on local-lite",
            "adaptive_low": "possible if max_output raised; still shares output budget",
            "adaptive_high": "rejected for first call; historically starved JSON",
        },
        "selected": PROPOSED_THINKING_POLICY,
        "reason": (
            "Worst-case compact output is close to 32000. Adaptive thinking "
            "previously consumed 21911 tokens of a 32000 cap. First authorized "
            "consolidation call should keep thinking disabled. Revisit only "
            "if max_output is raised using the model's 128000 ceiling."
        ),
    }
    architectures = {
        "A": {
            "name": "one global consolidation call",
            "fits_input": one_call_input_ok,
            "selected": True,
            "reason": "Normalized seven-window input is compact semantic extraction, not the ~38k-word transcript.",
        },
        "B": {
            "name": "hierarchical consolidation",
            "selected": False,
            "reason": "No evidence that input exceeds a safe one-call budget.",
        },
        "C": {
            "name": "deterministic pre-clustering + one global call",
            "selected": False,
            "reason": "Useful later as a hint generator; not required to fit context.",
        },
        "D": {
            "name": "multiple thematic calls + final merge",
            "selected": False,
            "reason": "Adds provider calls and merge-loss risk without budget need.",
        },
    }
    cost_out = min(max(worst_output_tokens, 8000), PROPOSED_MAX_OUTPUT)
    in_cost = (Decimal(planning) / Decimal(1_000_000)) * Decimal(str(INPUT_COST_PER_1M))
    out_cost = (Decimal(cost_out) / Decimal(1_000_000)) * Decimal(str(OUTPUT_COST_PER_1M))
    total_cost = (in_cost + out_cost).quantize(Decimal("0.000001"))
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "model": MODEL,
        "provider": PROVIDER,
        "model_unchanged": True,
        "context_window_tokens": CONTEXT_WINDOW_TOKENS,
        "model_max_output_tokens": MODEL_MAX_OUTPUT_TOKENS,
        "proposed_max_output": PROPOSED_MAX_OUTPUT,
        "prompt_version": GLOBAL_PROMPT_VERSION,
        "transport_version": GLOBAL_TRANSPORT_VERSION,
        "components": {
            "system_chars": prompt["system_chars"],
            "instructions_chars": prompt["instructions_chars"],
            "schema_raw_bytes": measured.get("raw_bytes"),
            "schema_adapted_bytes": measured.get("adapted_bytes"),
            "normalized_compact_chars": len(compact),
            "output_reserve": PROPOSED_MAX_OUTPUT,
        },
        "local_estimate": {
            "tokens": local_est.tokens,
            "method": local_est.method,
            "estimated": True,
            "prompt_tokens": prompt_est.tokens,
            "schema_tokens": schema_est.tokens,
            "data_tokens": data_est.tokens,
        },
        "provider_adjusted_estimate": {
            "json_factor_1_5": json_adjusted,
            "window_ratio_upper_bound": upper_bound,
            "window_ratio_mean": mean_ratio,
            "window_ratio_includes_transcript": True,
            "planning_tokens_with_20pct_margin": planning,
            "note": "Local estimate is not provider usage. Window ratios overstate JSON-only consolidation input.",
        },
        "output_budget": {
            "idea_text_chars": idea_chars,
            "other_text_chars": other_chars,
            "disposition_overhead_chars": disp_chars,
            "worst_case_chars": worst_output_chars,
            "worst_case_tokens_chars_div_4": worst_output_tokens,
            "max_output_32000_sufficient": output_ok,
            "sufficiency": "MARGINAL" if worst_output_tokens > 24000 else "YES",
            "if_truncated": "raise max_output without changing model; model allows 128000",
        },
        "thinking_policy": thinking,
        "call_architecture": {
            "selected": PROPOSED_ARCHITECTURE,
            "options": architectures,
            "minimize_provider_calls": True,
            "historical_full_transcript_timeouts_seconds": list(HISTORICAL_GLOBAL_TIMEOUTS),
            "do_not_repeat_that_architecture": True,
            "difference": "input is compact semantic extraction, not full transcript",
        },
        "failure_strategy": {
            "one_authorized_call": True,
            "no_automatic_retry": True,
            "persist_provider_evidence_before_decode": True,
            "offline_forensic_analysis_on_failure": True,
        },
        "one_call_realistically_bounded": one_call_input_ok and True,
        "cost_estimate_one_call": {
            "marked": "ESTIMATE",
            "input_tokens_planning": planning,
            "output_tokens_planning": cost_out,
            "input_cost": f"{in_cost.quantize(Decimal('0.000001'))} USD",
            "output_cost": f"{out_cost.quantize(Decimal('0.000001'))} USD",
            "total": f"{total_cost} USD",
            "pricing": f"{PROVIDER} {MODEL} ${INPUT_COST_PER_1M}/1M in ${OUTPUT_COST_PER_1M}/1M out",
            "opus_comparison_only": {
                "model": FUTURE_COMPARISON_MODEL,
                "input_cost": _money(planning, OPUS_INPUT_COST_PER_1M),
                "output_cost": _money(cost_out, OPUS_OUTPUT_COST_PER_1M),
                "not_selected": True,
            },
        },
        "time_estimate": {
            "not_guaranteed_latency": True,
            "historical_ready_window_elapsed_ms": [
                {
                    "window_id": window_id,
                    "elapsed_ms": (row or {}).get("elapsed_ms"),
                    "output_tokens": (row or {}).get("provider_output_tokens"),
                }
                for window_id, row in (inventory.get("windows") or {}).items()
            ],
            "likely_same_order_as_largest_window_plus_reasoning": True,
            "do_not_use_7200s_timeout": True,
            "proposed_read_timeout_seconds": 1800,
        },
        "local_extraction_cost_summary": _window_cost_summary(inventory),
        "future_model_comparison": {
            "configured_model_unchanged": MODEL,
            "compare_later_with": FUTURE_COMPARISON_MODEL,
            "reason": "consolidation is reasoning-heavy; Sonnet 5 remains first authorized model",
        },
    }


def finalize_cost_total(budget: dict[str, Any]) -> dict[str, Any]:
    planning = int((budget.get("cost_estimate_one_call") or {}).get("input_tokens_planning") or 0)
    cost_out = int((budget.get("cost_estimate_one_call") or {}).get("output_tokens_planning") or 0)
    in_cost = (Decimal(planning) / Decimal(1_000_000)) * Decimal(str(INPUT_COST_PER_1M))
    out_cost = (Decimal(cost_out) / Decimal(1_000_000)) * Decimal(str(OUTPUT_COST_PER_1M))
    total = (in_cost + out_cost).quantize(Decimal("0.000001"))
    budget["cost_estimate_one_call"]["input_cost"] = f"{in_cost.quantize(Decimal('0.000001'))} USD"
    budget["cost_estimate_one_call"]["output_cost"] = f"{out_cost.quantize(Decimal('0.000001'))} USD"
    budget["cost_estimate_one_call"]["total"] = f"{total} USD"
    return budget


__all__ = ["build_context_budget", "finalize_cost_total"]
