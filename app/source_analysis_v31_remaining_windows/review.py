"""Revue sémantique OFFLINE vs CLEAN fenêtre. Politique A.25/A.26. 0 LLM."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v2_a15_forensics.coverage import build_coverage_analysis
from app.source_analysis_v3_second_window.review import review_transport as review_generic
from app.source_analysis_v31_real_win004.comparison import classify_subtype_failure
from app.source_analysis_v31_real_win004.metadata import (
    audit_idea_example_duplication,
    audit_local_lite_idea_metadata,
)
from app.source_analysis_v31_remaining_windows.constants import (
    SEMANTIC_REVIEW_INVALID,
    SEMANTIC_REVIEW_STATUS,
    SUBTYPE_FAILURE_CLASS_IF_PASS,
)


def _relation_distribution(relations: Mapping[str, Any] | None) -> dict[str, int]:
    counts = {
        "well-supported": 0,
        "plausible-loose": 0,
        "incorrect": 0,
        "unverifiable": 0,
    }
    if not isinstance(relations, Mapping):
        return counts
    for row in relations.get("rows") or []:
        quality = str(row.get("quality") or "")
        grounding = str(row.get("grounding") or "")
        if grounding == "UNSUPPORTED":
            counts["incorrect"] += 1
        elif quality in {"plausible", "loose", "plausible-loose"}:
            counts["plausible-loose"] += 1
        elif quality in {"well-supported", "well_supported"}:
            counts["well-supported"] += 1
        else:
            counts["unverifiable"] += 1
    return counts


def _major_idea_checklist(
    transport: Mapping[str, Any] | None,
    window: WindowInput,
    transcript: TranscriptInput,
) -> dict[str, Any]:
    coverage = build_coverage_analysis(transport or {}, window, transcript)
    bands = coverage.get("bands") or []
    rows: list[dict[str, Any]] = []
    represented = partial = missing = 0
    for index, band in enumerate(bands):
        grounded = bool(band.get("semantic_records_grounded"))
        words = int(band.get("word_count") or band.get("owned_words") or 0)
        label = str(band.get("label") or band.get("sample") or f"band_{index + 1}")
        if grounded:
            status = "represented"
            represented += 1
        elif words >= 40:
            status = "missing"
            missing += 1
        else:
            status = "partial"
            partial += 1
        rows.append(
            {
                "band": index + 1,
                "label": label[:160],
                "status": status,
                "material": words >= 80 and status == "missing",
                "source_grounded": True,
            }
        )
    material_omissions = [row for row in rows if row["material"]]
    return {
        "rows": rows,
        "represented": represented,
        "partial": partial,
        "missing": missing,
        "material_omissions": len(material_omissions),
        "material_omission_rows": material_omissions,
        "largest_substantive_gap": coverage.get("largest_substantive_gap"),
        "bands": bands,
        "identical_counts_not_required": True,
    }


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
    base = review_generic(
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
    outline = _major_idea_checklist(transport, window, transcript)
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
    relations = base.get("relations") or {}
    distribution = _relation_distribution(relations)
    if distribution["incorrect"]:
        quality = "INADEQUATE"
        reasons.append("incorrect or materially misleading relations")
    transport_valid = bool(technical_ok and metadata["local_lite_metadata_pass"])
    status = SEMANTIC_REVIEW_STATUS if transport_valid else SEMANTIC_REVIEW_INVALID
    coverage = dict(base.get("coverage") or {})
    coverage.update(
        {
            "major_ideas_represented": outline["represented"],
            "major_ideas_partial": outline["partial"],
            "major_ideas_missing": outline["missing"],
            "material_omissions": outline["material_omissions"],
            "outline_mapping": outline["rows"],
            "largest_substantive_gap": outline["largest_substantive_gap"],
        }
    )
    defect = classify_subtype_failure(
        leakage=int(metadata.get("idea_subtype_leakage") or 0),
        old_v3=int(metadata.get("old_v3_idea_shape") or 0),
        invalid_importance=int(metadata.get("invalid_importance") or 0),
        structured="PASS" if technical_ok else "FAIL",
        technical_ok=technical_ok,
    )
    merged = dict(base)
    merged.update(
        {
            "status": status,
            "label": status,
            "transport_valid": transport_valid,
            "semantic_quality": quality,
            "reasons": reasons,
            "metadata": metadata,
            "duplication": duplication,
            "coverage": coverage,
            "major_idea_checklist": outline,
            "material_omissions": outline["material_omissions"],
            "relation_quality_summary": distribution,
            "a22_a24_subtype_failure_class": defect
            if not (metadata["idea_subtype_leakage"] or metadata["old_v3_idea_shape"])
            else defect,
            "subtype_failure_class": defect or SUBTYPE_FAILURE_CLASS_IF_PASS,
            "do_not_generalize": True,
            "policy": "A.25/A.26 stable semantic acceptance",
            "src_audit_present": src_audit is not None,
        }
    )
    return merged


__all__ = ["review_transport"]
