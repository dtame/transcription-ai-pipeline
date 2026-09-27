"""Revue sémantique OFFLINE du transport V3 vs CLEAN fenêtre sélectionnée. 0 LLM."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v2_a15_forensics.coverage import build_coverage_analysis
from app.source_analysis_v2_a15_forensics.semantic import classify_record
from app.source_analysis_v3_real_win001.handles import example_target_kinds
from app.source_analysis_v3_real_win001.metrics import record_metrics, src_metrics
from app.source_analysis_v3_real_win001.review import (
    _INTERPRETER,
    _blob,
    _relation_quality,
)
from app.source_analysis_v3_second_window.constants import (
    SEMANTIC_REVIEW_INVALID,
    SEMANTIC_REVIEW_STATUS,
)

_FRENCH_CONTENT = re.compile(
    r"(néanti|nanti|c'est pourquoi|timothée|évangile|assemblée|parce que|"
    r"aujourd'hui|seigneur)",
    re.IGNORECASE,
)


def _records(transport: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(transport, Mapping):
        return []
    return [item for item in (transport.get("records") or []) if isinstance(item, Mapping)]


def _src_index(transcript: TranscriptInput, window: WindowInput) -> dict[str, str]:
    wanted = set(window.owned_src_refs)
    return {
        segment.src_id: segment.text
        for segment in transcript.segments
        if segment.src_id in wanted
    }


def _window_has_french(owned_text: str) -> bool:
    return bool(_FRENCH_CONTENT.search(owned_text))


def review_transport(
    transport: Mapping[str, Any] | None,
    *,
    window: WindowInput,
    transcript: TranscriptInput,
    capacity_signal: bool,
    handle_gate_pass: bool,
    technical_ok: bool,
) -> dict[str, Any]:
    if not isinstance(transport, Mapping):
        return {
            "performed": False,
            "status": SEMANTIC_REVIEW_INVALID,
            "semantic_quality": "INADEQUATE",
            "thinking_disabled_local_extraction": "NOT_SUPPORTED",
            "unsupported_content": "not reviewed — no valid transport",
            "transport_valid": False,
            "reason": "technical validation did not produce a transport",
        }
    records = _records(transport)
    src_index = _src_index(transcript, window)
    owned_text = " ".join(src_index.get(ref, "") for ref in window.owned_src_refs)
    reviewed = [
        classify_record(
            index,
            item,
            " ".join(
                src_index.get(ref, "")
                for ref in (
                    [
                        str(raw).strip()
                        for raw in (item.get("s") or [])
                        if isinstance(raw, str) and str(raw).strip()
                    ]
                )
            ),
            owned_text,
        )
        for index, item in enumerate(records)
    ]
    for row, item in zip(reviewed, records):
        if str(item.get("k") or "") != "RELATION":
            continue
        if row.get("status") != "UNDETERMINABLE_FROM_CITED_SRC":
            continue
        links = [raw for raw in (item.get("l") or []) if isinstance(raw, str)]
        idea_hits = 0
        for raw in links:
            target = next(
                (
                    other
                    for other in records
                    if str(other.get("h") or "") == raw
                    and str(other.get("k") or "") == "IDEA"
                ),
                None,
            )
            if target is None:
                continue
            target_index = next(
                (idx for idx, rec in enumerate(records) if rec is target),
                None,
            )
            target_review = next(
                (other for other in reviewed if other.get("index") == target_index),
                None,
            )
            if target_review and target_review.get("status") in {
                "SUPPORTED",
                "PARTIALLY_SUPPORTED",
            }:
                idea_hits += 1
        if idea_hits == 2:
            row["status"] = "PARTIALLY_SUPPORTED"
            row["note"] = (
                "RELATION s[] empty by contract; both IDEA targets are "
                "source-grounded. Not auto-unsupported."
            )
        elif idea_hits == 1:
            row["status"] = "PARTIALLY_SUPPORTED"
            row["note"] = (
                "RELATION s[] empty by contract; one IDEA target is grounded."
            )
    counts = {
        "SUPPORTED": 0,
        "PARTIALLY_SUPPORTED": 0,
        "UNSUPPORTED": 0,
        "UNDETERMINABLE_FROM_CITED_SRC": 0,
    }
    for row in reviewed:
        status = str(row.get("status") or "UNDETERMINABLE_FROM_CITED_SRC")
        counts[status] = counts.get(status, 0) + 1
    blob = _blob(records)
    interpreter = [marker for marker in _INTERPRETER if marker in blob]
    french_in_window = _window_has_french(owned_text)
    french_in_values = bool(_FRENCH_CONTENT.search(blob))
    rec = record_metrics(transport)
    src = src_metrics(transport, window)
    coverage = build_coverage_analysis(transport, window, transcript)
    bands = coverage.get("bands") or []
    beginning = bool(bands and bands[0].get("semantic_records_grounded"))
    middle = bool(bands and bands[len(bands) // 2].get("semantic_records_grounded"))
    end = bool(bands and bands[-1].get("semantic_records_grounded"))
    example_rows = example_target_kinds(transport)
    relations = _relation_quality(records, reviewed)
    material_unsupported = counts["UNSUPPORTED"]
    quality = "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
    reasons: list[str] = []
    if not technical_ok or capacity_signal or not handle_gate_pass:
        quality = "INADEQUATE"
        reasons.append("technical V3 gate failed")
    if rec["IDEA"] < 3:
        quality = "INADEQUATE"
        reasons.append("too few ideas for a normal window")
    if material_unsupported:
        quality = "INADEQUATE"
        reasons.append("material unsupported content")
    if not (beginning and middle and end):
        if quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
            quality = "REVIEW_REQUIRED"
        reasons.append("beginning/middle/end coverage incomplete")
    if interpreter:
        if quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
            quality = "REVIEW_REQUIRED"
        reasons.append("possible interpreter material")
    transport_valid = bool(technical_ok)
    status = SEMANTIC_REVIEW_STATUS if transport_valid else SEMANTIC_REVIEW_INVALID
    thinking = None
    if technical_ok and quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
        thinking = "SUPPORTED_ON_TWO_DISTINCT_REAL_WINDOWS"
    elif quality == "REVIEW_REQUIRED":
        thinking = "REVIEW_REQUIRED"
    else:
        thinking = "NOT_SUPPORTED"
    return {
        "performed": True,
        "status": status,
        "transport_valid": transport_valid,
        "validated_result": technical_ok and quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION",
        "response_repaired": False,
        "source_refs_substituted": False,
        "external_fact_check": False,
        "second_llm": False,
        "semantic_quality": quality,
        "thinking_disabled_local_extraction": thinking,
        "unsupported_content": material_unsupported,
        "unsupported_count": material_unsupported,
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
            "appears_spatially_complete": beginning and middle and end,
        },
        "example_targets": example_rows,
        "relations": relations,
        "language": {
            "primary": transcript.primary_language,
            "window_contains_legitimate_french": french_in_window,
            "french_required": False,
            "french_markers_in_values": french_in_values,
            "interpreter_markers_in_values": interpreter,
            "assessed_against_actual_window_content": True,
        },
        "do_not_generalize": True,
        "generalization_forbidden": (
            "remaining windows, other transcripts, other languages, other domains"
        ),
        "editorial_quality_evaluated": False,
        "reasons": reasons,
        "notes": (
            f"Deterministic forensic review against exact CLEAN {window.window_id}. "
            "RELATION s[] empty is contractual. Empty EXAMPLE l[] is not "
            "automatically invalid. Not a second model call."
        ),
    }


__all__ = ["review_transport"]
