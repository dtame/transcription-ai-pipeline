"""Comparaison descriptive OFFLINE A.21 vs A.19. Pas de causalité stochastique."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v3_hardened_win001.constants import (
    A15_COVERAGE_PCT,
    A15_DISTINCT_SRC,
    A19_COST_DISPLAY,
    A19_COVERAGE_PCT_REPORTED,
    A19_DECODER,
    A19_DISTINCT_SRC_REPORTED,
    A19_ELAPSED_MS,
    A19_EXAMPLE,
    A19_FINISH_REASON,
    A19_HTTP_STATUS,
    A19_IDEA,
    A19_INPUT_RATIO,
    A19_INPUT_TOKENS,
    A19_LOCAL_INPUT,
    A19_MALFORMED_TOKEN,
    A19_OUTPUT_TOKENS,
    A19_PARSE,
    A19_PROMPT,
    A19_RECORDS,
    A19_REFERENCE,
    A19_RELATION,
    A19_RESULT,
    A19_THINKING_TOKENS,
    A19_TOPIC,
    A19_TOTAL_SRC_OCCURRENCES,
    A19_UNCERTAINTY,
    A19_VALID_CANONICAL_OCCURRENCES,
    A19_V3_SIGNATURE,
    V3_HANDLE_ARCHITECTURE,
)
from app.source_analysis_v3_real_win001.metrics import record_metrics


def compare_with_a19(
    *,
    execution: Mapping[str, Any],
    transport: Mapping[str, Any] | None,
    review: Mapping[str, Any],
    src_forensic: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    a21_counts = record_metrics(transport)
    handle_gate = execution.get("handle_gate") or {}
    src = src_forensic or execution.get("src_forensic") or {}
    input_tokens = execution.get("input_tokens")
    output_tokens = execution.get("output_tokens")
    thinking_tokens = execution.get("thinking_tokens")
    local_est = execution.get("local_input_estimate")
    ratio = None
    if input_tokens and local_est:
        ratio = round(float(input_tokens) / float(local_est), 6)
    a15_defect = "ELIMINATED" if handle_gate.get("handle_gate_pass") else "NOT COMPARABLE"
    if int(handle_gate.get("wrong_kind_handles") or 0) > 0:
        a15_defect = "PERSISTS"
    malformed_eliminated = src.get("a19_src_typo_class")
    return {
        "a19": {
            "valid_transport": False,
            "gold_truth": False,
            "result": A19_RESULT,
            "signature": A19_V3_SIGNATURE,
            "prompt": A19_PROMPT,
            "transport": "semantic-transport-v3",
            "http": A19_HTTP_STATUS,
            "thinking_tokens": A19_THINKING_TOKENS,
            "finish_reason": A19_FINISH_REASON,
            "structured_parse": A19_PARSE,
            "v3_decoder": A19_DECODER,
            "malformed_src": A19_MALFORMED_TOKEN,
            "valid_canonical_occurrences": A19_VALID_CANONICAL_OCCURRENCES,
            "total_src_occurrences": A19_TOTAL_SRC_OCCURRENCES,
            "local_input_estimate": A19_LOCAL_INPUT,
            "input_tokens": A19_INPUT_TOKENS,
            "output_tokens": A19_OUTPUT_TOKENS,
            "input_ratio": A19_INPUT_RATIO,
            "elapsed_ms": A19_ELAPSED_MS,
            "cost": A19_COST_DISPLAY,
            "records": A19_RECORDS,
            "kinds": {
                "TOPIC": A19_TOPIC,
                "IDEA": A19_IDEA,
                "RELATION": A19_RELATION,
                "EXAMPLE": A19_EXAMPLE,
                "REFERENCE": A19_REFERENCE,
                "UNCERTAINTY": A19_UNCERTAINTY,
            },
            "distinct_src_refs": A19_DISTINCT_SRC_REPORTED,
            "semantic_src_coverage_pct": A19_COVERAGE_PCT_REPORTED,
        },
        "a15_reference": {
            "distinct_src_refs": A15_DISTINCT_SRC,
            "semantic_src_coverage_pct": A15_COVERAGE_PCT,
        },
        "a21": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "thinking_tokens": thinking_tokens,
            "finish_reason": execution.get("finish_reason"),
            "local_input_estimate": local_est,
            "input_ratio": ratio,
            "cost": (execution.get("cost") or {}).get("display"),
            "elapsed_ms": execution.get("provider_elapsed_ms"),
            "kinds": a21_counts,
            "structured_parse": execution.get("structured_parse"),
            "v3_decoder": execution.get("v3_decoder"),
            "src_forensic": src,
        },
        "counts_need_not_match": True,
        "experimental_variable": "SRC-reference prompt hardening 1.3 → 1.3.1",
        "causality_claimed": False,
        "a19_src_typo_class": malformed_eliminated,
        "a15_target_kind_defect": a15_defect,
        "v3_handle_architecture": V3_HANDLE_ARCHITECTURE,
        "malformed_src_copying_eliminated": malformed_eliminated == "ELIMINATED",
        "coverage_vs_a19": {
            "a15_pct": A15_COVERAGE_PCT,
            "a19_pct": A19_COVERAGE_PCT_REPORTED,
            "a21_pct": (review.get("coverage") or {}).get("semantic_src_coverage_pct")
            or src.get("semantic_src_coverage_pct"),
        },
        "descriptive": {
            "thinking_tokens_a19": A19_THINKING_TOKENS,
            "thinking_tokens_a21": thinking_tokens,
            "finish_a19": A19_FINISH_REASON,
            "finish_a21": execution.get("finish_reason"),
            "output_a19": A19_OUTPUT_TOKENS,
            "output_a21": output_tokens,
            "input_a19": A19_INPUT_TOKENS,
            "input_a21": input_tokens,
            "cost_a19": A19_COST_DISPLAY,
            "cost_a21": (execution.get("cost") or {}).get("display"),
            "elapsed_a19": A19_ELAPSED_MS,
            "elapsed_a21": execution.get("provider_elapsed_ms"),
            "records_a19": A19_RECORDS,
            "records_a21": a21_counts.get("total_records"),
            "causality_claimed": False,
            "one_window_analyzed_again": True,
        },
        "notes": (
            "A.19 remains FAIL evidence of an isolated SRC copy typo. "
            "Compare descriptively. Do not infer causality from stochastic "
            "output differences. Do not require identical counts."
        ),
    }


__all__ = ["compare_with_a19"]
