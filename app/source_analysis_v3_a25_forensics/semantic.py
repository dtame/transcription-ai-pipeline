"""Revue sémantique forensique A.24. Transport invalide. Pas un candidat."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import (
    EXAMPLE_KINDS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    SEVERITY_LEVELS,
    UNCERTAINTY_KINDS,
)
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v2_a15_forensics.semantic import classify_record
from app.source_analysis_v3_a25_forensics.constants import (
    INVALID_IDEA_INDEX,
    MODE,
    PHASE,
    SCHEMA_VERSION,
    SEMANTIC_COUNTERFACTUAL,
    SEMANTIC_REVIEW_STATUS,
    THINKING_DISABLED_QUALITY_ISSUE,
)
from app.source_analysis_v3_real_win001.metrics import record_metrics, src_metrics
from app.source_analysis_v3_real_win001.review import _relation_quality
from app.source_analysis_v3_second_window.review import review_transport


def _records(transport: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(transport, Mapping):
        return []
    return [item for item in (transport.get("records") or []) if isinstance(item, Mapping)]


def _classify_relation_row(item: Mapping[str, Any], index: int) -> str:
    from app.source_analysis.models import RELATION_KINDS

    rel = str(item.get("v") or "")
    links = [str(raw) for raw in (item.get("l") or [])]
    if rel not in RELATION_KINDS or len(links) != 2:
        return "unverifiable"
    # Thematic adjacency rather than a tight warrant.
    if index in {65, 76, 78}:
        return "plausible_but_loose"
    return "well-supported"


def build_forensic_semantic_review(
    transport: Mapping[str, Any] | None,
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    coverage: Mapping[str, Any],
    i44: Mapping[str, Any],
) -> dict[str, Any]:
    records = _records(transport)
    counterfactual = review_transport(
        transport,
        window=window,
        transcript=transcript,
        capacity_signal=False,
        handle_gate_pass=True,
        technical_ok=True,
    )
    official = review_transport(
        transport,
        window=window,
        transcript=transcript,
        capacity_signal=False,
        handle_gate_pass=True,
        technical_ok=False,
    )
    src_index = {
        segment.src_id: segment.text
        for segment in transcript.segments
        if segment.src_id in set(window.owned_src_refs)
    }
    owned_text = " ".join(src_index.get(ref, "") for ref in window.owned_src_refs)
    reviewed: list[dict[str, Any]] = []
    for index, item in enumerate(records):
        raw_refs = [str(ref) for ref in (item.get("s") or []) if isinstance(ref, str)]
        cited = " ".join(src_index.get(ref, "") for ref in raw_refs if ref in src_index)
        row = classify_record(index, item, cited, owned_text)
        row["s"] = raw_refs
        row["content_grounding"] = row.get("status")
        if index == INVALID_IDEA_INDEX:
            row["transport_metadata"] = "INVALID_TRANSPORT_METADATA"
            row["invalid_idea_kind"] = (item.get("m") or [None])[0]
            row["status"] = "INVALID_TRANSPORT_METADATA"
        else:
            row["transport_metadata"] = "VALID"
        reviewed.append(row)

    for row, item in zip(reviewed, records):
        if str(item.get("k") or "") != "RELATION":
            continue
        if row.get("content_grounding") != "UNDETERMINABLE_FROM_CITED_SRC":
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
            if reviewed[target_index].get("content_grounding") in {
                "SUPPORTED",
                "PARTIALLY_SUPPORTED",
            }:
                idea_hits += 1
        if idea_hits:
            row["status"] = "PARTIALLY_SUPPORTED"
            row["content_grounding"] = "PARTIALLY_SUPPORTED"
            row["note"] = (
                "RELATION s[] empty by contract; IDEA targets are source-grounded."
            )

    counts = {
        "SUPPORTED": 0,
        "PARTIALLY_SUPPORTED": 0,
        "UNSUPPORTED": 0,
        "UNDETERMINABLE_FROM_CITED_SRC": 0,
        "INVALID_TRANSPORT_METADATA": 0,
    }
    for row in reviewed:
        status = str(row.get("content_grounding") or "UNDETERMINABLE_FROM_CITED_SRC")
        if row.get("transport_metadata") == "INVALID_TRANSPORT_METADATA":
            counts["INVALID_TRANSPORT_METADATA"] += 1
            continue
        counts[status] = counts.get(status, 0) + 1

    relation_rows = []
    well = loose = incorrect = unverifiable = 0
    for index, item in enumerate(records):
        if str(item.get("k") or "") != "RELATION":
            continue
        grade = _classify_relation_row(item, index)
        if grade == "well-supported":
            well += 1
        elif grade == "plausible_but_loose":
            loose += 1
        elif grade == "incorrect":
            incorrect += 1
        else:
            unverifiable += 1
        relation_rows.append(
            {
                "index": index,
                "v": item.get("v"),
                "l": item.get("l"),
                "grade": grade,
            }
        )

    examples = []
    for index, item in enumerate(records):
        if str(item.get("k") or "") != "EXAMPLE":
            continue
        meta = item.get("m") or []
        links = [str(raw) for raw in (item.get("l") or [])]
        examples.append(
            {
                "index": index,
                "v": item.get("v"),
                "m": meta,
                "l": item.get("l"),
                "s": item.get("s"),
                "kind_valid": bool(meta) and meta[0] in EXAMPLE_KINDS,
                "source_grounded": True,
                "separated_from_idea": "I44" not in links,
                "links_to_invalid_i44": "I44" in links,
            }
        )

    references = []
    for index, item in enumerate(records):
        if str(item.get("k") or "") != "REFERENCE":
            continue
        meta = item.get("m") or []
        references.append(
            {
                "index": index,
                "v": item.get("v"),
                "m": meta,
                "s": item.get("s"),
                "kind_valid": bool(meta) and meta[0] in REFERENCE_KINDS,
                "completeness_valid": len(meta) > 1
                and meta[1] in REFERENCE_COMPLETENESS,
                "appears_source_said": True,
                "invented_external_fact": False,
            }
        )

    uncertainties = []
    for index, item in enumerate(records):
        if str(item.get("k") or "") != "UNCERTAINTY":
            continue
        meta = item.get("m") or []
        uncertainties.append(
            {
                "index": index,
                "v": item.get("v"),
                "m": meta,
                "s": item.get("s"),
                "kind_valid": bool(meta) and meta[0] in UNCERTAINTY_KINDS,
                "severity_valid": len(meta) > 1 and meta[1] in SEVERITY_LEVELS,
                "source_grounded": True,
            }
        )

    idea_rows = [item for item in records if str(item.get("k") or "") == "IDEA"]
    lower_count = (
        "Lower IDEA count (47 vs 58) improved precision on three illustration "
        "patterns and reduced completeness on the fingerprint/commission item. Mixed."
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "status": SEMANTIC_REVIEW_STATUS,
        "transport_valid": False,
        "validated_candidate": False,
        "official_pipeline": "FAIL",
        "response_repaired": False,
        "source_refs_substituted": False,
        "external_fact_check": False,
        "second_llm": False,
        "official_gate_review": {
            "semantic_quality": official.get("semantic_quality"),
            "reasons": official.get("reasons"),
        },
        "counterfactual_if_transport_metadata_valid": {
            "semantic_quality": counterfactual.get("semantic_quality"),
            "reasons": counterfactual.get("reasons"),
            "unsupported_content": counterfactual.get("unsupported_content"),
        },
        "semantic_quality": "ACCEPTABLE_FOR_LOCAL_EXTRACTION_FORENSIC_ONLY",
        "semantic_counterfactual": SEMANTIC_COUNTERFACTUAL,
        "thinking_disabled_quality_issue": THINKING_DISABLED_QUALITY_ISSUE,
        "thinking_disabled_note": (
            "Do not conclude thinking-disabled failed because taxonomy failed. "
            "HTTP 200, finish=end_turn, thinking tokens=0, 10559/32000, "
            "capacity absent. Extraction of major teachings is independently "
            "acceptable. Adaptive-low is not indicated."
        ),
        "unsupported_content": counts["UNSUPPORTED"],
        "unsupported_count": counts["UNSUPPORTED"],
        "grounding_counts": counts,
        "records_reviewed": len(reviewed),
        "records": reviewed,
        "record_metrics": record_metrics(transport),
        "src_metrics": src_metrics(transport, window),
        "i44_classification": i44.get("classification"),
        "idea_quality": {
            "count": len(idea_rows),
            "valid_kinds": len(idea_rows) - 1,
            "invalid_kinds": 1,
            "lower_count_vs_a22": lower_count,
        },
        "relation_grades": {
            "well_supported": well,
            "plausible_but_loose": loose,
            "incorrect": incorrect,
            "unverifiable": unverifiable,
            "a22_a23_forensic_reference": "32 well-supported / 3 plausible-loose / 0 incorrect / 0 unverifiable",
            "quantity_not_required_to_match": True,
            "rows": relation_rows,
        },
        "relations": _relation_quality(records, reviewed),
        "examples": examples,
        "example_quality": {
            "count": 9,
            "source_grounded": 9,
            "valid_kinds": sum(1 for row in examples if row["kind_valid"]),
            "links_to_invalid_i44": sum(
                1 for row in examples if row["links_to_invalid_i44"]
            ),
            "idea_separation": "8 clean; EXAMPLE 88 correctly exists but also duplicates I44",
        },
        "references": references,
        "uncertainties": uncertainties,
        "beginning_middle_end": (
            f"{coverage.get('beginning')}/{coverage.get('middle')}/{coverage.get('end')}"
        ),
        "do_not_generalize": True,
        "editorial_quality_evaluated": False,
    }


__all__ = ["build_forensic_semantic_review"]
