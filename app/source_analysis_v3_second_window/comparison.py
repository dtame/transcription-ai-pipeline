"""Comparaison descriptive OFFLINE A.21 WIN001 vs A.22 second window."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v3_real_win001.metrics import record_metrics
from app.source_analysis_v3_second_window.constants import (
    A19_RESULT,
    A21_COVERAGE_PCT,
    A21_COST_DISPLAY,
    A21_ELAPSED_MS,
    A21_EXAMPLE,
    A21_FINISH,
    A21_HTTP,
    A21_IDEA,
    A21_INPUT_TOKENS,
    A21_LOCAL,
    A21_OUTPUT_TOKENS,
    A21_OWNED,
    A21_PROMPT,
    A21_QUALITY,
    A21_READY,
    A21_RECORDS,
    A21_REFERENCE,
    A21_RELATION,
    A21_RESULT,
    A21_SRC_RANGE,
    A21_THINKING_TOKENS,
    A21_TOPIC,
    A21_TOTAL_SRC_OCCURRENCES,
    A21_UNCERTAINTY,
    A21_V3_SIGNATURE,
    A21_WINDOW_ID,
    A21_WORDS,
    V3_HANDLE_ARCHITECTURE,
)


def compare_with_win001(
    *,
    execution: Mapping[str, Any],
    transport: Mapping[str, Any] | None,
    review: Mapping[str, Any],
    window: Mapping[str, Any] | None = None,
    src_forensic: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    a22_counts = record_metrics(transport)
    window = window or {}
    src = src_forensic or execution.get("src_forensic") or {}
    coverage = review.get("coverage") or {}
    selected = execution.get("authorized_target") or window.get("window_id")
    disjoint = selected not in {None, A21_WINDOW_ID}
    src_range = window.get("src_range")
    independent = bool(
        disjoint
        and src_range
        and src_range != A21_SRC_RANGE
        and int(window.get("owned_src_count") or 0) != A21_OWNED
    )
    a22_density = None
    owned = window.get("owned_src_count")
    words = window.get("word_count")
    if owned and words:
        a22_density = round(float(words) / float(owned), 6)
    a21_density = round(float(A21_WORDS) / float(A21_OWNED), 6)
    quality = review.get("semantic_quality")
    technical = bool(execution.get("technical_ok"))
    independence_value = (
        "MEANINGFUL_INDEPENDENT_EVIDENCE"
        if independent and technical and quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
        else "INSUFFICIENT"
        if not independent
        else "TECHNICAL_OR_SEMANTIC_INCOMPLETE"
    )
    two_windows = (
        A21_RESULT == "PASS"
        and technical
        and quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
        and independent
    )
    return {
        "a19": {
            "result": A19_RESULT,
            "unchanged": True,
            "gold_truth": False,
        },
        "a21_win001": {
            "result": A21_RESULT,
            "window_id": A21_WINDOW_ID,
            "src_range": A21_SRC_RANGE,
            "owned_src_count": A21_OWNED,
            "word_count": A21_WORDS,
            "local_input_estimate": A21_LOCAL,
            "input_tokens": A21_INPUT_TOKENS,
            "output_tokens": A21_OUTPUT_TOKENS,
            "thinking_tokens": A21_THINKING_TOKENS,
            "http": A21_HTTP,
            "finish_reason": A21_FINISH,
            "records": A21_RECORDS,
            "kinds": {
                "TOPIC": A21_TOPIC,
                "IDEA": A21_IDEA,
                "RELATION": A21_RELATION,
                "EXAMPLE": A21_EXAMPLE,
                "REFERENCE": A21_REFERENCE,
                "UNCERTAINTY": A21_UNCERTAINTY,
            },
            "total_src_occurrences": A21_TOTAL_SRC_OCCURRENCES,
            "semantic_src_coverage_pct": A21_COVERAGE_PCT,
            "semantic_quality": A21_QUALITY,
            "signature": A21_V3_SIGNATURE,
            "prompt": A21_PROMPT,
            "cost": A21_COST_DISPLAY,
            "elapsed_ms": A21_ELAPSED_MS,
            "ready": A21_READY,
            "source_density_words_per_src": a21_density,
        },
        "a22_second_window": {
            "window_id": selected,
            "src_range": src_range,
            "owned_src_count": owned,
            "word_count": words,
            "local_input_estimate": execution.get("local_input_estimate"),
            "input_tokens": execution.get("input_tokens"),
            "output_tokens": execution.get("output_tokens"),
            "thinking_tokens": execution.get("thinking_tokens"),
            "finish_reason": execution.get("finish_reason"),
            "kinds": a22_counts,
            "src_forensic": src,
            "semantic_src_coverage_pct": coverage.get("semantic_src_coverage_pct"),
            "semantic_quality": quality,
            "source_density_words_per_src": a22_density,
            "language": (review.get("language") or {}).get("primary"),
        },
        "differences": {
            "source_position": f"{A21_WINDOW_ID} beginning vs {selected} independent region",
            "semantic_material": "different owned SRC region — subject difference expected",
            "record_distribution": {
                "a21": A21_RECORDS,
                "a22": a22_counts.get("total_records"),
            },
            "src_density": {
                "a21_words_per_src": a21_density,
                "a22_words_per_src": a22_density,
            },
            "language": {
                "a21_primary": "en",
                "a22_primary": (review.get("language") or {}).get("primary"),
                "french_required": False,
            },
        },
        "independent_of_win001": independent,
        "independence_value": independence_value,
        "thinking_disabled_two_distinct_windows": two_windows,
        "v3_two_distinct_windows": two_windows,
        "src_hardening_two_distinct_windows": two_windows,
        "counts_need_not_match": True,
        "causality_claimed": False,
        "v3_handle_architecture": V3_HANDLE_ARCHITECTURE,
        "do_not_generalize_beyond_this_project": True,
        "notes": (
            "A.19 remains FAIL. A.21 remains PASS / READY 1/7. "
            "A.22 tests whether the same architecture works on an independent "
            "source region. Do not infer causality from stochastic count differences."
        ),
    }


__all__ = ["compare_with_win001"]
