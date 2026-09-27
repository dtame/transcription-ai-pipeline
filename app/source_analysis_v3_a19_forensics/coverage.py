"""Couverture SRC sémantique A.19 — bandes et trous. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v2_a15_forensics.coverage import build_coverage_analysis as a15_coverage
from app.source_analysis_v2_real_win001.metrics import src_metrics
from app.source_analysis_v3_a19_forensics.constants import (
    A19_COVERAGE_PCT_REPORTED,
    A19_DISTINCT_SRC_REPORTED,
    A19_OWNED,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)
from app.source_analysis_local_v3.source_refs import is_canonical_src


def build_a19_coverage(
    transport: Mapping[str, Any],
    window: WindowInput,
    transcript: TranscriptInput,
    src_audit: Mapping[str, Any],
) -> dict[str, Any]:
    base = a15_coverage(transport, window, transcript)
    src = src_metrics(transport, window)
    records = [
        item
        for item in (transport.get("records") or [])
        if isinstance(item, Mapping)
    ]
    raw_tokens: list[str] = []
    for item in records:
        for ref in item.get("s") or []:
            if isinstance(ref, str):
                raw_tokens.append(ref)
    canonical_owned = {
        token
        for token in raw_tokens
        if is_canonical_src(token) and token in set(window.owned_src_refs)
    }
    malformed = [token for token in raw_tokens if not is_canonical_src(token)]
    verified_distinct_raw = len(set(raw_tokens))
    verified_coverage_count = len(canonical_owned)
    verified_pct = round(100.0 * verified_coverage_count / A19_OWNED, 2)
    bands = base.get("bands") or []
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "owned_src_count": window.owned_src_count,
        "reported_distinct_src_refs": A19_DISTINCT_SRC_REPORTED,
        "reported_semantic_src_coverage_pct": A19_COVERAGE_PCT_REPORTED,
        "verified_distinct_src_refs_raw": verified_distinct_raw,
        "verified_distinct_canonical_owned": verified_coverage_count,
        "verified_semantic_src_coverage_pct": verified_pct,
        "src_metrics_legacy_strip_count": src,
        "legacy_325_includes_malformed_token": verified_distinct_raw
        == A19_DISTINCT_SRC_REPORTED,
        "malformed_tokens_excluded_from_coverage": malformed,
        "coverage_count_explains_27_11": verified_coverage_count == 324
        and verified_pct == A19_COVERAGE_PCT_REPORTED,
        "more_coverage_is_not_automatically_better": True,
        "a15_coverage_pct": 19.92,
        "quality_not_percentage": (
            "A.19 cites more SRC (324 owned vs A.15 238) but quality is judged "
            "by grounding, idea grouping, relation targets, and example association."
        ),
        "bands": bands,
        "thin_bands": base.get("thin_bands"),
        "gap_count": base.get("gap_count"),
        "largest_gaps": base.get("largest_gaps"),
        "largest_substantive_gap": base.get("largest_substantive_gap"),
        "beginning": bool(bands and bands[0].get("semantic_records_grounded")),
        "middle": bool(bands and bands[len(bands) // 2].get("semantic_records_grounded")),
        "end": bool(bands and bands[-1].get("semantic_records_grounded")),
        "src_audit_distinct_canonical_owned": src_audit.get(
            "distinct_canonical_owned_src_refs"
        ),
        "output_completeness": {
            "actual_output_tokens": 10897,
            "max_output_tokens": 32000,
            "capacity_signal": "absent",
            "covers_beginning": bool(bands and bands[0].get("semantic_records_grounded")),
            "covers_middle": bool(
                bands and bands[len(bands) // 2].get("semantic_records_grounded")
            ),
            "covers_end": bool(bands and bands[-1].get("semantic_records_grounded")),
        },
    }


__all__ = ["build_a19_coverage"]
