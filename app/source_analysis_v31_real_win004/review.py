"""Revue sémantique OFFLINE du transport v3.1-local-lite vs CLEAN WIN004. 0 LLM."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v3_a22_forensics.coverage import build_a22_coverage
from app.source_analysis_v3_second_window.review import review_transport as review_a22_transport
from app.source_analysis_v31_real_win004.constants import (
    SEMANTIC_REVIEW_INVALID,
    SEMANTIC_REVIEW_STATUS,
)
from app.source_analysis_v31_real_win004.metadata import (
    audit_idea_example_duplication,
    audit_local_lite_idea_metadata,
    probe_historical_patterns,
)


def review_transport(
    transport: Mapping[str, Any] | None,
    *,
    window: WindowInput,
    transcript: TranscriptInput,
    capacity_signal: bool,
    handle_gate_pass: bool,
    technical_ok: bool,
    src_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base = review_a22_transport(
        transport,
        window=window,
        transcript=transcript,
        capacity_signal=capacity_signal,
        handle_gate_pass=handle_gate_pass,
        technical_ok=technical_ok,
    )
    metadata = audit_local_lite_idea_metadata(
        transport if isinstance(transport, dict) else None
    )
    duplication = audit_idea_example_duplication(
        transport if isinstance(transport, dict) else None
    )
    four = probe_historical_patterns(transport if isinstance(transport, dict) else None)
    outline = {}
    if isinstance(transport, Mapping):
        outline = build_a22_coverage(
            transport,
            window,
            transcript,
            src_audit or {},
        )
    quality = base.get("semantic_quality")
    reasons = list(base.get("reasons") or [])
    if metadata["idea_subtype_leakage"] or metadata["old_v3_idea_shape"]:
        quality = "INADEQUATE"
        reasons.append("local-lite IDEA subtype leakage or old V3 shape")
    elif metadata["invalid_importance"]:
        quality = "INADEQUATE"
        reasons.append("invalid IDEA importance vocabulary")
    elif not metadata["local_lite_metadata_pass"]:
        quality = "INADEQUATE"
        reasons.append("other invalid local-lite metadata")
    represented = int(outline.get("major_ideas_represented") or 0)
    missing = int(outline.get("major_ideas_missing") or 0)
    if missing > 2 and quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
        quality = "REVIEW_REQUIRED"
        reasons.append("major-idea outline has more than two missing items")
    if represented < 10 and quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
        quality = "REVIEW_REQUIRED"
        reasons.append("major-idea outline under-represented vs A.23 diagnostic")
    fall_note = (
        "A.24 automated needle reported The Fall missing; forensic review found "
        "it present as T9 / I28–I31. Verify semantically, do not repeat the "
        "counting error."
    )
    transport_valid = bool(technical_ok and metadata["local_lite_metadata_pass"])
    if technical_ok and quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
        thinking = "SUPPORTED_ON_TWO_DISTINCT_REAL_WINDOWS"
        thinking_note = (
            "This project, this local-window architecture, WIN001 + WIN004 "
            "evidence. Do not generalize further."
        )
        local_lite_evidence = (
            "v3.1-local-lite receives its first real-provider validation on WIN004."
        )
        status = SEMANTIC_REVIEW_STATUS
    else:
        thinking = (
            "NOT_SUPPORTED"
            if quality == "INADEQUATE"
            else base.get("thinking_disabled_local_extraction")
        )
        thinking_note = (
            "Thinking-disabled two-window evidence is not confirmed because "
            "the A.27 technical or semantic gate did not fully pass."
        )
        local_lite_evidence = (
            "v3.1-local-lite has not yet received a fully validated real WIN004."
        )
        status = SEMANTIC_REVIEW_STATUS if transport_valid else SEMANTIC_REVIEW_INVALID
    merged = dict(base)
    coverage = dict(merged.get("coverage") or {})
    coverage.update(
        {
            "major_ideas_represented": outline.get("major_ideas_represented"),
            "major_ideas_partial": outline.get("major_ideas_partial"),
            "major_ideas_missing": outline.get("major_ideas_missing"),
            "outline_mapping": outline.get("outline_mapping"),
            "a23_reference": "15 represented / 1 partial / 0 missing",
            "verified_distinct_canonical_owned": outline.get(
                "verified_distinct_canonical_owned"
            ),
            "verified_semantic_src_coverage_pct": outline.get(
                "verified_semantic_src_coverage_pct"
            ),
            "fall_false_negative_warning": fall_note,
        }
    )
    i44 = four.get("i44_like") or {}
    merged.update(
        {
            "status": status,
            "label": status,
            "transport_valid": transport_valid,
            "semantic_quality": quality,
            "reasons": reasons,
            "metadata": metadata,
            "duplication": duplication,
            "four_patterns": four,
            "i44_like": i44,
            "coverage": coverage,
            "major_idea_benchmark": {
                "a23_represented": 15,
                "a23_partial": 1,
                "a23_missing": 0,
                "a27_represented": outline.get("major_ideas_represented"),
                "a27_partial": outline.get("major_ideas_partial"),
                "a27_missing": outline.get("major_ideas_missing"),
                "identical_counts_not_required": True,
            },
            "thinking_disabled_local_extraction": thinking,
            "thinking_disabled_limitation": thinking_note,
            "thinking_disabled_two_distinct_windows": thinking
            == "SUPPORTED_ON_TWO_DISTINCT_REAL_WINDOWS",
            "local_lite_evidence": local_lite_evidence,
            "do_not_generalize": True,
            "generalization_forbidden": (
                "remaining windows, other transcripts, other languages, other domains"
            ),
        }
    )
    return merged


__all__ = ["review_transport"]
