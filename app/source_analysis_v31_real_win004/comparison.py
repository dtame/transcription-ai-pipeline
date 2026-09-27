"""Comparaison descriptive OFFLINE A.27 vs A.22/A.24. Pas de causalité stochastique."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v3_real_win001.metrics import record_metrics
from app.source_analysis_v31_real_win004.constants import (
    A19_RESULT,
    A21_RESULT,
    A22_COVERAGE_PCT,
    A22_DISTINCT_SRC,
    A22_EXAMPLE,
    A22_FINISH,
    A22_HTTP,
    A22_IDEA,
    A22_LOCAL_INPUT,
    A22_OUTPUT,
    A22_OWNED,
    A22_PROMPT,
    A22_PROVIDER_INPUT,
    A22_QUALITY_REASON_REPORTED,
    A22_QUALITY_REPORTED,
    A22_READY,
    A22_RECORDS,
    A22_REFERENCE,
    A22_RELATION,
    A22_REQUEST_ID,
    A22_RESULT,
    A22_SRC_RANGE,
    A22_STRUCTURED_PARSE,
    A22_TARGET,
    A22_THINKING,
    A22_THINKING_TOKENS,
    A22_TOPIC,
    A22_TOTAL_SRC_OCCURRENCES,
    A22_UNCERTAINTY,
    A22_VALID_SRC_OCCURRENCES,
    A22_V3_SIGNATURE,
    A22_WORDS,
    A23_RESULT,
    A24_COVERAGE_PCT,
    A24_EXAMPLE,
    A24_FINISH,
    A24_HTTP,
    A24_IDEA,
    A24_LOCAL_INPUT,
    A24_OUTPUT,
    A24_PROMPT,
    A24_PROVIDER_INPUT,
    A24_RECORDS,
    A24_REFERENCE,
    A24_RELATION,
    A24_REQUEST_ID,
    A24_RESULT,
    A24_SRC_RANGE,
    A24_STRUCTURED_PARSE,
    A24_THINKING,
    A24_THINKING_TOKENS,
    A24_TOPIC,
    A24_TOTAL_SRC_OCCURRENCES,
    A24_VALID_SRC_OCCURRENCES,
    A24_V3_SIGNATURE,
    A25_RESULT,
    A26_RESULT,
    A261_RESULT,
    SUBTYPE_FAILURE_CLASS_IF_PASS,
    V3_HANDLE_ARCHITECTURE,
)


def classify_subtype_failure(
    *,
    leakage: int,
    old_v3: int,
    invalid_importance: int,
    structured: str | None,
    technical_ok: bool,
) -> str:
    if leakage > 0 or old_v3 > 0:
        return "PERSISTS"
    if structured != "PASS" or not technical_ok or invalid_importance > 0:
        return "DIFFERENT_FAILURE"
    return SUBTYPE_FAILURE_CLASS_IF_PASS


def compare_with_a22_a24(
    *,
    execution: Mapping[str, Any],
    transport: Mapping[str, Any] | None,
    review: Mapping[str, Any],
    src_forensic: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    a27_counts = record_metrics(transport)
    src = src_forensic or execution.get("src_forensic") or {}
    coverage = review.get("coverage") or {}
    metadata = review.get("metadata") or execution.get("metadata") or {}
    leakage = int(metadata.get("idea_subtype_leakage") or 0)
    old_v3 = int(metadata.get("old_v3_idea_shape") or 0)
    invalid_importance = int(metadata.get("invalid_importance") or 0)
    defect = classify_subtype_failure(
        leakage=leakage,
        old_v3=old_v3,
        invalid_importance=invalid_importance,
        structured=execution.get("structured_parse"),
        technical_ok=bool(execution.get("technical_ok")),
    )
    quality = review.get("semantic_quality")
    technical = bool(execution.get("technical_ok"))
    two_windows = (
        A21_RESULT == "PASS"
        and technical
        and quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
        and defect == SUBTYPE_FAILURE_CLASS_IF_PASS
    )
    return {
        "a19": {"result": A19_RESULT, "unchanged": True, "gold_truth": False},
        "a21": {"result": A21_RESULT, "unchanged": True},
        "a23": {"result": A23_RESULT, "unchanged": True},
        "a25": {"result": A25_RESULT, "unchanged": True},
        "a26": {"result": A26_RESULT, "unchanged": True},
        "a261": {"result": A261_RESULT, "unchanged": True},
        "a22": {
            "valid_transport": False,
            "gold_truth": False,
            "ready_candidate": False,
            "result": A22_RESULT,
            "signature": A22_V3_SIGNATURE,
            "prompt": A22_PROMPT,
            "transport": "semantic-transport-v3",
            "window_id": A22_TARGET,
            "src_range": A22_SRC_RANGE,
            "owned_src_count": A22_OWNED,
            "word_count": A22_WORDS,
            "http": A22_HTTP,
            "thinking": A22_THINKING,
            "thinking_tokens": A22_THINKING_TOKENS,
            "finish_reason": A22_FINISH,
            "structured_parse": A22_STRUCTURED_PARSE,
            "request_id": A22_REQUEST_ID,
            "local_input_estimate": A22_LOCAL_INPUT,
            "input_tokens": A22_PROVIDER_INPUT,
            "output_tokens": A22_OUTPUT,
            "records": A22_RECORDS,
            "kinds": {
                "TOPIC": A22_TOPIC,
                "IDEA": A22_IDEA,
                "RELATION": A22_RELATION,
                "EXAMPLE": A22_EXAMPLE,
                "REFERENCE": A22_REFERENCE,
                "UNCERTAINTY": A22_UNCERTAINTY,
            },
            "total_src_occurrences": A22_TOTAL_SRC_OCCURRENCES,
            "valid_src_occurrences": A22_VALID_SRC_OCCURRENCES,
            "distinct_src_refs": A22_DISTINCT_SRC,
            "semantic_src_coverage_pct": A22_COVERAGE_PCT,
            "semantic_quality": A22_QUALITY_REPORTED,
            "semantic_quality_reason": A22_QUALITY_REASON_REPORTED,
            "idea_subtype_required": True,
            "ready": A22_READY,
        },
        "a24": {
            "valid_transport": False,
            "gold_truth": False,
            "ready_candidate": False,
            "result": A24_RESULT,
            "signature": A24_V3_SIGNATURE,
            "prompt": A24_PROMPT,
            "transport": "semantic-transport-v3",
            "src_range": A24_SRC_RANGE,
            "http": A24_HTTP,
            "thinking": A24_THINKING,
            "thinking_tokens": A24_THINKING_TOKENS,
            "finish_reason": A24_FINISH,
            "structured_parse": A24_STRUCTURED_PARSE,
            "request_id": A24_REQUEST_ID,
            "local_input_estimate": A24_LOCAL_INPUT,
            "input_tokens": A24_PROVIDER_INPUT,
            "output_tokens": A24_OUTPUT,
            "records": A24_RECORDS,
            "kinds": {
                "TOPIC": A24_TOPIC,
                "IDEA": A24_IDEA,
                "RELATION": A24_RELATION,
                "EXAMPLE": A24_EXAMPLE,
                "REFERENCE": A24_REFERENCE,
            },
            "total_src_occurrences": A24_TOTAL_SRC_OCCURRENCES,
            "valid_src_occurrences": A24_VALID_SRC_OCCURRENCES,
            "semantic_src_coverage_pct": A24_COVERAGE_PCT,
            "idea_kind_example": 1,
        },
        "a27": {
            "input_tokens": execution.get("input_tokens"),
            "output_tokens": execution.get("output_tokens"),
            "thinking_tokens": execution.get("thinking_tokens"),
            "finish_reason": execution.get("finish_reason"),
            "local_input_estimate": execution.get("local_input_estimate"),
            "input_ratio": execution.get("input_ratio"),
            "cost": (execution.get("cost") or {}).get("display"),
            "elapsed_ms": execution.get("provider_elapsed_ms"),
            "kinds": a27_counts,
            "structured_parse": execution.get("structured_parse"),
            "v31_decoder": execution.get("v31_decoder"),
            "src_forensic": src,
            "semantic_src_coverage_pct": coverage.get("verified_semantic_src_coverage_pct")
            or coverage.get("semantic_src_coverage_pct"),
            "semantic_quality": quality,
            "idea_subtype_leakage": leakage,
            "old_v3_idea_shape": old_v3,
            "invalid_importance": invalid_importance,
            "four_patterns": review.get("four_patterns"),
        },
        "experimental_variable": (
            "local IDEA subtype removed; prompt 1.4.0 + v3.1-local-lite"
        ),
        "same_clean_ownership": True,
        "same_transport_wire_schema": True,
        "same_thinking_disabled": True,
        "counts_need_not_match": True,
        "causality_claimed": False,
        "a22_a24_subtype_failure_class": defect,
        "thinking_disabled_two_distinct_windows": two_windows,
        "v3_handle_architecture": V3_HANDLE_ARCHITECTURE,
        "notes": (
            "A.19 remains FAIL. A.21 remains PASS. A.22 remains FAIL. "
            "A.23 remains PASS. A.24 remains FAIL. A.25 remains PARTIAL. "
            "A.26 remains PASS. A.26.1 remains PASS. A.22/A.24 generations "
            "are invalid historical evidence and are not READY candidates. "
            "If A.27 passes, the local IDEA subtype failure class is "
            "ELIMINATED_BY_ARCHITECTURE, not merely prompt-fixed."
        ),
    }


__all__ = ["classify_subtype_failure", "compare_with_a22_a24"]
