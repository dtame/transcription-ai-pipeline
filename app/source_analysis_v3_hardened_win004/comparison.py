"""Comparaison descriptive OFFLINE A.24 vs A.22. Pas de causalité stochastique."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v3_real_win001.metrics import record_metrics
from app.source_analysis_v3_hardened_win004.constants import (
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
    V3_HANDLE_ARCHITECTURE,
)


def classify_type_contract(
    *,
    idea_example: int,
    other_metadata: int,
    structured: str | None,
    technical_ok: bool,
) -> str:
    if idea_example > 0:
        return "PERSISTS"
    if structured != "PASS" or not technical_ok or other_metadata > 0:
        return "DIFFERENT_FAILURE"
    return "ELIMINATED"


def compare_with_a22(
    *,
    execution: Mapping[str, Any],
    transport: Mapping[str, Any] | None,
    review: Mapping[str, Any],
    src_forensic: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    a24_counts = record_metrics(transport)
    src = src_forensic or execution.get("src_forensic") or {}
    coverage = review.get("coverage") or {}
    metadata = review.get("metadata") or execution.get("metadata") or {}
    idea_example = int(metadata.get("idea_kind_example") or 0)
    other_metadata = int(metadata.get("other_metadata_violation_count") or 0)
    defect = classify_type_contract(
        idea_example=idea_example,
        other_metadata=other_metadata,
        structured=execution.get("structured_parse"),
        technical_ok=bool(execution.get("technical_ok")),
    )
    quality = review.get("semantic_quality")
    technical = bool(execution.get("technical_ok"))
    two_windows = (
        A21_RESULT == "PASS"
        and technical
        and quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
        and defect == "ELIMINATED"
    )
    return {
        "a19": {"result": A19_RESULT, "unchanged": True, "gold_truth": False},
        "a21": {"result": A21_RESULT, "unchanged": True},
        "a23": {"result": A23_RESULT, "unchanged": True},
        "a22": {
            "valid_transport": False,
            "gold_truth": False,
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
            "idea_kind_example": 4,
            "ready": A22_READY,
        },
        "a24": {
            "input_tokens": execution.get("input_tokens"),
            "output_tokens": execution.get("output_tokens"),
            "thinking_tokens": execution.get("thinking_tokens"),
            "finish_reason": execution.get("finish_reason"),
            "local_input_estimate": execution.get("local_input_estimate"),
            "input_ratio": execution.get("input_ratio"),
            "cost": (execution.get("cost") or {}).get("display"),
            "elapsed_ms": execution.get("provider_elapsed_ms"),
            "kinds": a24_counts,
            "structured_parse": execution.get("structured_parse"),
            "v3_decoder": execution.get("v3_decoder"),
            "src_forensic": src,
            "semantic_src_coverage_pct": coverage.get("verified_semantic_src_coverage_pct")
            or coverage.get("semantic_src_coverage_pct"),
            "semantic_quality": quality,
            "idea_kind_example": idea_example,
            "other_metadata_violations": other_metadata,
            "four_patterns": review.get("four_patterns"),
        },
        "experimental_variable": "IDEA/EXAMPLE type-contract prompt 1.3.1 → 1.3.2",
        "same_clean_ownership": True,
        "same_transport_schema": True,
        "same_thinking_disabled": True,
        "counts_need_not_match": True,
        "causality_claimed": False,
        "a22_type_contract_defect": defect,
        "thinking_disabled_two_distinct_windows": two_windows,
        "v3_two_distinct_windows": two_windows,
        "v3_handle_architecture": V3_HANDLE_ARCHITECTURE,
        "notes": (
            "A.19 remains FAIL. A.21 remains PASS. A.22 remains FAIL. "
            "A.23 remains PASS. A.24 tests whether prompt 1.3.2 eliminates "
            "the IDEA/EXAMPLE vocabulary defect on the same CLEAN WIN004. "
            "Do not infer causality from stochastic count differences."
        ),
    }


__all__ = ["classify_type_contract", "compare_with_a22"]
