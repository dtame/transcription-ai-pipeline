"""Comparaison descriptive OFFLINE A.15 vs CALL C. CALL C n'est pas vérité."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_output_ceiling_review.facts import forensic_paths
from app.source_analysis_output_ceiling_review.raw_parser import extract_root_prefix
from app.source_analysis_v2_real_win001.constants import (
    CALL_C_COST,
    CALL_C_FINISH,
    CALL_C_LOCAL,
    CALL_C_OUTPUT,
    CALL_C_PROVIDER_INPUT,
    CALL_C_THINKING_TOKENS,
    PROJECT_NAME,
    SMALL_SIGNATURE,
)
from app.source_analysis_v2_real_win001.metrics import record_metrics


def _kind_counts(records: list[Any]) -> dict[str, int]:
    counts = {
        "TOPIC": 0,
        "IDEA": 0,
        "RELATION": 0,
        "EXAMPLE": 0,
        "REFERENCE": 0,
        "UNCERTAINTY": 0,
    }
    for item in records:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("k") or "")
        if kind in counts:
            counts[kind] += 1
    return counts


def compare_with_call_c(
    *,
    execution: Mapping[str, Any],
    transport: Mapping[str, Any] | None,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    paths = forensic_paths(project_name, sortie_dir=sortie_dir)
    raw_path = paths.get("structured_raw")
    text = raw_path.read_text(encoding="utf-8") if raw_path and raw_path.is_file() else ""
    prefix = extract_root_prefix(text) if text else {}
    complete = list(prefix.get("complete_records") or [])
    call_c_counts = _kind_counts(complete)
    a15_counts = record_metrics(transport)
    input_tokens = execution.get("input_tokens")
    output_tokens = execution.get("output_tokens")
    thinking_tokens = execution.get("thinking_tokens")
    local_est = execution.get("local_input_estimate")
    ratio = None
    if input_tokens and local_est:
        ratio = round(float(input_tokens) / float(local_est), 6)
    return {
        "call_c": {
            "valid": False,
            "truncated": True,
            "gold_truth": False,
            "signature": SMALL_SIGNATURE,
            "input_tokens": CALL_C_PROVIDER_INPUT,
            "output_tokens": CALL_C_OUTPUT,
            "thinking_tokens": CALL_C_THINKING_TOKENS,
            "finish_reason": CALL_C_FINISH,
            "local_input_estimate": CALL_C_LOCAL,
            "cost": CALL_C_COST,
            "complete_prefix_records": len(complete),
            "complete_prefix_kinds": call_c_counts,
            "structured_parse": "FAIL",
        },
        "a15": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "thinking_tokens": thinking_tokens,
            "finish_reason": execution.get("finish_reason"),
            "local_input_estimate": local_est,
            "input_ratio": ratio,
            "kinds": a15_counts,
            "structured_parse": execution.get("structured_parse"),
        },
        "descriptive": {
            "thinking_tokens_call_c": CALL_C_THINKING_TOKENS,
            "thinking_tokens_a15": thinking_tokens,
            "finish_call_c": CALL_C_FINISH,
            "finish_a15": execution.get("finish_reason"),
            "output_call_c": CALL_C_OUTPUT,
            "output_a15": output_tokens,
            "shared_budget_failure_eliminated_on_this_window": (
                execution.get("finish_reason") not in {None, "max_tokens", "length"}
                and execution.get("structured_parse") == "PASS"
                and (thinking_tokens in {0, None})
            ),
            "causality_claimed": False,
            "one_window_only": True,
        },
        "notes": (
            "CALL C remains invalid/truncated. Compare only record distribution "
            "and usage. Do not treat CALL C as gold truth."
        ),
    }


__all__ = ["compare_with_call_c"]
