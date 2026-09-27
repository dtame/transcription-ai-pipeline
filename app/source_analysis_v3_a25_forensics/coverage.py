"""Couverture SRC A.24. Réutilise l'outline diagnostique A.23. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.source_refs import is_canonical_src
from app.source_analysis_v2_a15_forensics.coverage import build_coverage_analysis as a15_coverage
from app.source_analysis_v2_real_win001.metrics import src_metrics
from app.source_analysis_v3_a22_forensics.coverage import _AUDIT_OUTLINE, _blob
from app.source_analysis_v3_a25_forensics.constants import (
    A24_COVERAGE_PCT,
    A24_DISTINCT_SRC,
    A24_OWNED,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)


def build_a24_coverage(
    transport: Mapping[str, Any],
    window: WindowInput,
    transcript: TranscriptInput,
    src_audit: Mapping[str, Any],
) -> dict[str, Any]:
    base = a15_coverage(transport, window, transcript)
    src = src_metrics(transport, window)
    records = [
        item for item in (transport.get("records") or []) if isinstance(item, Mapping)
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
    verified_distinct_raw = len(set(raw_tokens))
    verified_coverage_count = len(canonical_owned)
    verified_pct = round(100.0 * verified_coverage_count / A24_OWNED, 2)
    bands = base.get("bands") or []
    blob = _blob(records)
    outline_rows = []
    for index, (label, needles, expected) in enumerate(_AUDIT_OUTLINE, start=1):
        hits = [needle for needle in needles if needle in blob]
        if len(hits) == len(needles) or len(hits) >= 2:
            status = "represented"
        elif hits:
            status = "partial"
        else:
            status = "missing"
        outline_rows.append(
            {
                "outline_item": index,
                "label": label,
                "needles": list(needles),
                "hits": hits,
                "status": status,
                "expected_from_clean_read": expected,
            }
        )
    represented = [row for row in outline_rows if row["status"] == "represented"]
    partial = [row for row in outline_rows if row["status"] == "partial"]
    missing = [row for row in outline_rows if row["status"] == "missing"]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "owned_src_count": window.owned_src_count,
        "reported_distinct_src_refs": A24_DISTINCT_SRC,
        "reported_semantic_src_coverage_pct": A24_COVERAGE_PCT,
        "verified_distinct_src_refs_raw": verified_distinct_raw,
        "verified_distinct_canonical_owned": verified_coverage_count,
        "verified_semantic_src_coverage_pct": verified_pct,
        "src_metrics_legacy": src,
        "more_coverage_is_not_automatically_better": True,
        "quality_not_percentage": (
            "23.05% (272/1180) is not a quality threshold. Judgment is by "
            "major-idea representation, grounding, and relation/example quality."
        ),
        "bands": bands,
        "thin_bands": base.get("thin_bands"),
        "gap_count": base.get("gap_count"),
        "largest_gaps": base.get("largest_gaps"),
        "largest_substantive_gap": base.get("largest_substantive_gap"),
        "beginning": bool(bands and bands[0].get("semantic_records_grounded")),
        "middle": bool(
            bands and bands[len(bands) // 2].get("semantic_records_grounded")
        ),
        "end": bool(bands and bands[-1].get("semantic_records_grounded")),
        "src_audit_distinct_canonical_owned": src_audit.get(
            "distinct_canonical_owned_src_refs"
        ),
        "diagnostic_outline": [row["label"] for row in outline_rows],
        "outline_mapping": outline_rows,
        "major_ideas_represented": len(represented),
        "major_ideas_partial": len(partial),
        "major_ideas_missing": len(missing),
        "major_ideas_distorted": 0,
        "major_ideas_over_fragmented": 0,
        "missing_rows": missing,
        "partial_rows": partial,
        "editorial_planning": False,
    }


__all__ = ["build_a24_coverage"]
