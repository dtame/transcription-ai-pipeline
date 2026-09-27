"""Revue sémantique forensique du transport V3 invalide. Pas un candidat validé."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.source_refs import is_canonical_src
from app.source_analysis_v2_a15_forensics.semantic import classify_record
from app.source_analysis_v3_a19_forensics.constants import (
    A19_HYPOTHETICAL_INTENDED_SRC,
    A19_MALFORMED_SRC,
    MODE,
    PHASE,
    SCHEMA_VERSION,
    SEMANTIC_REVIEW_STATUS,
    V3_HANDLE_ARCHITECTURE,
)
from app.source_analysis_v3_real_win001.handles import example_target_kinds
from app.source_analysis_v3_real_win001.review import (
    _AUDIT_OUTLINE,
    _EXAMPLE_PROBES,
    _INTERPRETER,
    _OUTLINE_NEEDLES,
    _blob,
    _match_needles,
    _probe_examples,
    _relation_quality,
    _src_index,
)
from app.source_analysis_v3_real_win001.metrics import record_metrics, src_metrics


def _records(transport: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(transport, Mapping):
        return []
    return [item for item in (transport.get("records") or []) if isinstance(item, Mapping)]


def build_forensic_semantic_review(
    transport: Mapping[str, Any] | None,
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    coverage: Mapping[str, Any],
) -> dict[str, Any]:
    records = _records(transport)
    src_index = _src_index(transcript, window)
    owned_text = " ".join(src_index.get(ref, "") for ref in window.owned_src_refs)
    reviewed: list[dict[str, Any]] = []
    for index, item in enumerate(records):
        raw_refs = [
            str(ref) for ref in (item.get("s") or []) if isinstance(ref, str)
        ]
        invalid_refs = [ref for ref in raw_refs if not is_canonical_src(ref)]
        cited_valid = " ".join(
            src_index.get(ref, "") for ref in raw_refs if ref in src_index
        )
        row = classify_record(index, item, cited_valid, owned_text)
        row["s"] = raw_refs
        if invalid_refs:
            row["status"] = "INVALID_SRC_REFERENCE"
            row["invalid_src_refs"] = invalid_refs
            row["note"] = (
                "Record contains malformed SRC token(s). Transport not repaired. "
                + str(row.get("note") or "")
            )
        if index == 50:
            hypo_text = src_index.get(A19_HYPOTHETICAL_INTENDED_SRC, "")
            hypo = classify_record(index, item, hypo_text, owned_text)
            row["hypothetical_intended_ref_for_forensic_inspection"] = {
                "label": "HYPOTHETICAL_INTENDED_REF_FOR_FORENSIC_INSPECTION",
                "token": A19_HYPOTHETICAL_INTENDED_SRC,
                "observed_token": A19_MALFORMED_SRC,
                "repaired_evidence": False,
                "status_if_canonical_token_were_used": hypo.get("status"),
                "cited_excerpt": hypo_text[:240],
            }
        reviewed.append(row)

    for row, item in zip(reviewed, records):
        if str(item.get("k") or "") != "RELATION":
            continue
        if row.get("status") not in {
            "UNDETERMINABLE_FROM_CITED_SRC",
            "INVALID_SRC_REFERENCE",
        }:
            continue
        links = [raw for raw in (item.get("l") or []) if isinstance(raw, str)]
        idea_hits = 0
        for raw in links:
            target_index = next(
                (
                    idx
                    for idx, other in enumerate(records)
                    if str(other.get("h") or "") == raw
                    and str(other.get("k") or "") == "IDEA"
                ),
                None,
            )
            if target_index is None:
                continue
            target_review = reviewed[target_index]
            if target_review.get("status") in {"SUPPORTED", "PARTIALLY_SUPPORTED"}:
                idea_hits += 1
        if idea_hits:
            row["status"] = "PARTIALLY_SUPPORTED"
            row["note"] = (
                "RELATION s[] empty by contract; IDEA targets are source-grounded. "
                "Diagnostic handle-graph inspection only. Official pipeline FAIL."
            )

    counts = {
        "SUPPORTED": 0,
        "PARTIALLY_SUPPORTED": 0,
        "UNSUPPORTED": 0,
        "UNDETERMINABLE_FROM_CITED_SRC": 0,
        "INVALID_SRC_REFERENCE": 0,
    }
    for row in reviewed:
        status = str(row.get("status") or "UNDETERMINABLE_FROM_CITED_SRC")
        counts[status] = counts.get(status, 0) + 1

    blob = _blob(records)
    interpreter = [marker for marker in _INTERPRETER if marker in blob]
    french_kept = bool(
        re.search(
            r"(néanti|nanti|c'est pourquoi|timothée|évangile|assemblée)",
            blob,
            re.IGNORECASE,
        )
    )
    rec = record_metrics(transport)
    src = src_metrics(transport, window)
    bands = coverage.get("bands") or []
    beginning = bool(bands and bands[0].get("semantic_records_grounded"))
    middle = bool(bands and bands[len(bands) // 2].get("semantic_records_grounded"))
    end = bool(bands and bands[-1].get("semantic_records_grounded"))
    outline_hits = []
    for index, needles in enumerate(_OUTLINE_NEEDLES, start=1):
        outline_hits.append(
            {
                "outline_item": index,
                "needles": list(needles),
                "represented": all(token in blob for token in needles)
                or any(token in blob for token in needles),
            }
        )
    example_probes = _probe_examples(records)
    example_rows = example_target_kinds(transport)
    topic_examples = [row for row in example_rows if row.get("links_to_topic")]
    relations = _relation_quality(records, reviewed)
    outline_represented = sum(1 for row in outline_hits if row["represented"])
    unsupported = counts["UNSUPPORTED"]
    quality = "ACCEPTABLE_FOR_LOCAL_EXTRACTION_FORENSIC_ONLY"
    thinking = (
        "SUPPORTED_FOR_THIS_SAME_SOURCE_WINDOW_BY_TWO_FORENSIC_OBSERVATIONS "
        "(A.15 invalid V2 + A.19 invalid V3 lexical transport). "
        "Not a validated V3 candidate. Do not generalize to other windows."
    )
    reasons: list[str] = []
    if rec["IDEA"] < 3:
        quality = "INADEQUATE"
        thinking = "NOT_SUPPORTED"
        reasons.append("too few ideas")
    if unsupported:
        quality = "INADEQUATE"
        thinking = "NOT_SUPPORTED"
        reasons.append("material unsupported content")
    if topic_examples:
        quality = "REVIEW_REQUIRED"
        thinking = "REVIEW_REQUIRED"
        reasons.append("EXAMPLE still targets TOPIC")
    if not (beginning and middle and end):
        if quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION_FORENSIC_ONLY":
            quality = "REVIEW_REQUIRED"
        reasons.append("beginning/middle/end incomplete")
    a15_target_kind = "ELIMINATED" if not topic_examples else "PRESENT"
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "status": SEMANTIC_REVIEW_STATUS,
        "validated_candidate": False,
        "official_pipeline": "FAIL",
        "response_repaired": False,
        "source_refs_substituted": False,
        "external_fact_check": False,
        "second_llm": False,
        "semantic_quality": quality,
        "thinking_disabled_local_extraction": thinking,
        "unsupported_content": unsupported,
        "unsupported_count": unsupported,
        "grounding_counts": counts,
        "records_reviewed": len(reviewed),
        "records": reviewed,
        "record_metrics": rec,
        "src_metrics": src,
        "coverage": {
            "distinct_src_refs": src.get("distinct_srcs_referenced"),
            "semantic_src_coverage_pct": src.get("semantic_src_coverage_pct"),
            "bands": bands,
            "largest_substantive_gap": coverage.get("largest_substantive_gap"),
            "beginning": beginning,
            "middle": middle,
            "end": end,
        },
        "major_idea_coverage": {
            "outline_status": "DIAGNOSTIC_ONLY",
            "never_consume_as_canonical": True,
            "outline": list(_AUDIT_OUTLINE),
            "hits": outline_hits,
            "represented_count": outline_represented,
        },
        "example_probes": example_probes,
        "example_targets": example_rows,
        "a15_target_kind_defect": a15_target_kind,
        "relations": relations,
        "language": {
            "primary": transcript.primary_language,
            "french_markers_in_values": french_kept,
            "interpreter_markers_in_values": interpreter,
        },
        "v3_handle_architecture": V3_HANDLE_ARCHITECTURE,
        "do_not_generalize": True,
        "reasons": reasons,
        "notes": (
            "FORENSIC_SEMANTIC_REVIEW_OF_INVALID_V3_TRANSPORT. "
            "Handle graph inspected diagnostically. Official status remains FAIL."
        ),
    }


__all__ = ["build_forensic_semantic_review"]
