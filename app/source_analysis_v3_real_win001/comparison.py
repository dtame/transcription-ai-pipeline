"""Comparaison descriptive OFFLINE A.19 vs A.15. A.15 n'est pas vérité or."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v3_real_win001.constants import (
    A15_COST_DISPLAY,
    A15_COVERAGE_PCT,
    A15_DISTINCT_SRC,
    A15_EXAMPLE,
    A15_FINISH,
    A15_IDEA,
    A15_INPUT_RATIO,
    A15_INVALID_LINKS,
    A15_INVALID_RECORDS,
    A15_LOCAL_INPUT,
    A15_OUTPUT_TOKENS,
    A15_PROVIDER_INPUT,
    A15_RECORDS,
    A15_REFERENCE,
    A15_RELATION,
    A15_SEMANTIC_CONTENT,
    A15_THINKING_TOKENS,
    A15_TOPIC,
    A15_UNCERTAINTY,
    A15_V2_SIGNATURE,
)
from app.source_analysis_v3_real_win001.metrics import record_metrics


def _defect_status(review: Mapping[str, Any], handle_gate: Mapping[str, Any]) -> str:
    if not handle_gate.get("handle_gate_pass"):
        if int(handle_gate.get("wrong_kind_handles") or 0) > 0:
            return "PERSISTS"
        return "NOT COMPARABLE"
    probes = list(review.get("example_probes") or [])
    topic_hits = [probe for probe in probes if probe.get("topic_associated")]
    present = [probe for probe in probes if probe.get("present")]
    if topic_hits:
        return "PERSISTS"
    if present and all(probe.get("idea_associated") for probe in present):
        return "ELIMINATED"
    if handle_gate.get("wrong_kind_handles") == 0:
        return "ELIMINATED"
    return "NOT COMPARABLE"


def compare_with_a15(
    *,
    execution: Mapping[str, Any],
    transport: Mapping[str, Any] | None,
    review: Mapping[str, Any],
) -> dict[str, Any]:
    a19_counts = record_metrics(transport)
    handle_gate = execution.get("handle_gate") or {}
    defect = _defect_status(review, handle_gate)
    input_tokens = execution.get("input_tokens")
    output_tokens = execution.get("output_tokens")
    thinking_tokens = execution.get("thinking_tokens")
    local_est = execution.get("local_input_estimate")
    ratio = None
    if input_tokens and local_est:
        ratio = round(float(input_tokens) / float(local_est), 6)
    return {
        "a15": {
            "valid_transport": False,
            "gold_truth": False,
            "signature": A15_V2_SIGNATURE,
            "prompt": "window-analysis-1.2.1",
            "transport": "semantic-transport-v2",
            "thinking_tokens": A15_THINKING_TOKENS,
            "finish_reason": A15_FINISH,
            "local_input_estimate": A15_LOCAL_INPUT,
            "input_tokens": A15_PROVIDER_INPUT,
            "output_tokens": A15_OUTPUT_TOKENS,
            "input_ratio": A15_INPUT_RATIO,
            "cost": A15_COST_DISPLAY,
            "records": A15_RECORDS,
            "kinds": {
                "TOPIC": A15_TOPIC,
                "IDEA": A15_IDEA,
                "RELATION": A15_RELATION,
                "EXAMPLE": A15_EXAMPLE,
                "REFERENCE": A15_REFERENCE,
                "UNCERTAINTY": A15_UNCERTAINTY,
            },
            "invalid_records": A15_INVALID_RECORDS,
            "invalid_links": A15_INVALID_LINKS,
            "distinct_src_refs": A15_DISTINCT_SRC,
            "semantic_src_coverage_pct": A15_COVERAGE_PCT,
            "semantic_content": A15_SEMANTIC_CONTENT,
        },
        "a19": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "thinking_tokens": thinking_tokens,
            "finish_reason": execution.get("finish_reason"),
            "local_input_estimate": local_est,
            "input_ratio": ratio,
            "cost": (execution.get("cost") or {}).get("display"),
            "kinds": a19_counts,
            "structured_parse": execution.get("structured_parse"),
            "elapsed_ms": execution.get("provider_elapsed_ms"),
        },
        "counts_need_not_match": True,
        "experimental_variable": "V2 numeric links → V3 symbolic handles (prompt 1.2.1 → 1.3)",
        "a15_invalid_link_defect": defect,
        "example_probes": review.get("example_probes"),
        "relation_quality_vs_a16": (review.get("relations") or {}).get("overall_vs_a16"),
        "coverage_vs_a15": {
            "a15_pct": A15_COVERAGE_PCT,
            "a19_pct": (review.get("coverage") or {}).get("semantic_src_coverage_pct")
            or (execution.get("src") or {}).get("semantic_src_coverage_pct"),
        },
        "descriptive": {
            "thinking_tokens_a15": A15_THINKING_TOKENS,
            "thinking_tokens_a19": thinking_tokens,
            "finish_a15": A15_FINISH,
            "finish_a19": execution.get("finish_reason"),
            "output_a15": A15_OUTPUT_TOKENS,
            "output_a19": output_tokens,
            "input_a15": A15_PROVIDER_INPUT,
            "input_a19": input_tokens,
            "cost_a15": A15_COST_DISPLAY,
            "cost_a19": (execution.get("cost") or {}).get("display"),
            "causality_claimed": False,
            "one_window_analyzed_twice": True,
        },
        "notes": (
            "A.15 remains an invalid-link transport with acceptable semantic "
            "content. Compare descriptively. Do not require identical counts."
        ),
    }


__all__ = ["compare_with_a15"]
