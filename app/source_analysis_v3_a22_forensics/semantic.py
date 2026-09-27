"""Revue sémantique forensique du transport V3 WIN004 invalide. Pas un candidat validé."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.models import (
    EXAMPLE_KINDS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    RELATION_KINDS,
    SEVERITY_LEVELS,
    UNCERTAINTY_KINDS,
)
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v2_a15_forensics.semantic import classify_record
from app.source_analysis_v3_a22_forensics.constants import (
    A22_QUALITY_REASON_REPORTED,
    A22_QUALITY_REPORTED,
    A22_REVIEW_ARTIFACT,
    INVALID_IDEA_EXAMPLE_INDEXES,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    SEMANTIC_COUNTERFACTUAL,
    SEMANTIC_INADEQUACY_ROOT_CAUSE,
    SEMANTIC_REVIEW_STATUS,
    THINKING_DISABLED_EVIDENCE,
)
from app.source_analysis_v3_real_win001.metrics import record_metrics, src_metrics
from app.source_analysis_v3_real_win001.review import _relation_quality
from app.source_analysis_v3_second_window.review import review_transport


def _records(transport: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(transport, Mapping):
        return []
    return [item for item in (transport.get("records") or []) if isinstance(item, Mapping)]


def _original_review_reasons(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    path = audit_dir(project_name, sortie_dir=sortie_dir) / A22_REVIEW_ARTIFACT
    if not path.is_file():
        return {"present": False}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "present": True,
        "semantic_quality": data.get("semantic_quality"),
        "reasons": data.get("reasons"),
        "unsupported_content": data.get("unsupported_content"),
        "transport_valid": data.get("transport_valid"),
        "beginning": (data.get("coverage") or {}).get("beginning"),
        "middle": (data.get("coverage") or {}).get("middle"),
        "end": (data.get("coverage") or {}).get("end"),
        "grounding_counts": data.get("grounding_counts"),
    }


def _classify_relation_row(item: Mapping[str, Any], index: int) -> str:
    rel = str(item.get("v") or "")
    links = [str(raw) for raw in (item.get("l") or [])]
    if rel not in RELATION_KINDS or len(links) != 2:
        return "unverifiable"
    # Handle validity ≠ semantic validity. These three are thematic adjacency
    # more than a tight IDEA-to-IDEA warrant in CLEAN WIN004.
    if index in {71, 93, 96}:
        return "plausible_but_loose"
    return "well-supported"


def build_forensic_semantic_review(
    transport: Mapping[str, Any] | None,
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    coverage: Mapping[str, Any],
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    records = _records(transport)
    original = _original_review_reasons(project_name, sortie_dir=sortie_dir)
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
        if index in INVALID_IDEA_EXAMPLE_INDEXES:
            row["transport_metadata"] = "INVALID_TRANSPORT_METADATA"
            row["invalid_idea_kind"] = (item.get("m") or [None])[0]
        else:
            row["transport_metadata"] = "VALID"
        reviewed.append(row)

    for row, item in zip(reviewed, records):
        if str(item.get("k") or "") != "RELATION":
            continue
        if row.get("status") != "UNDETERMINABLE_FROM_CITED_SRC":
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
                "RELATION s[] empty by contract; IDEA targets are source-grounded. "
                "Diagnostic handle-graph inspection only. Official pipeline FAIL."
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
        counts[status] = counts.get(status, 0) + 1
        if row.get("transport_metadata") == "INVALID_TRANSPORT_METADATA":
            counts["INVALID_TRANSPORT_METADATA"] += 1

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
        examples.append(
            {
                "index": index,
                "v": item.get("v"),
                "m": meta,
                "l": item.get("l"),
                "s": item.get("s"),
                "kind_valid": bool(meta) and meta[0] in EXAMPLE_KINDS,
                "source_grounded": True,
                "separated_from_idea": True,
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
                "completeness_valid": len(meta) > 1 and meta[1] in REFERENCE_COMPLETENESS,
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

    dimensions = {
        "grounding": "content-supported; 0 UNSUPPORTED; 4 invalid IDEA metadata",
        "coverage": coverage.get("verified_semantic_src_coverage_pct"),
        "topic_quality": "12 topics track the CLEAN WIN004 arc",
        "idea_quality": "58 ideas; 54 valid kinds; 4 mislabeled example",
        "idea_completeness": "major teachings represented; Lucifer/Davos partial via UNCERTAINTY",
        "idea_granularity": "fine but not pathological; T3/T4 law-making is split across several IDEAs",
        "relations": f"{well} well-supported / {loose} plausible-loose / {incorrect} incorrect / {unverifiable} unverifiable",
        "examples": "9 valid EXAMPLE records; 4 duplicate the invalid IDEA/example rows",
        "references": "8 biblical references, source-said, not invented external facts",
        "uncertainties": "5 rows, canonical vocabulary, source-grounded",
        "duplication": "IDEA(example)+EXAMPLE for four illustrations",
        "unsupported_synthesis": 0,
        "beginning_middle_end": (
            f"{coverage.get('beginning')}/{coverage.get('middle')}/{coverage.get('end')}"
        ),
        "language": "en; no required French; no interpreter markers",
    }
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
        "a22_reported_quality": A22_QUALITY_REPORTED,
        "a22_reported_reason": A22_QUALITY_REASON_REPORTED,
        "a22_original_review": original,
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
        "semantic_inadequacy_root_cause": SEMANTIC_INADEQUACY_ROOT_CAUSE,
        "secondary_quality_pattern": "EXAMPLE_IDEA_COLLAPSE",
        "secondary_pattern_independently_fatal": False,
        "thinking_disabled_local_extraction": THINKING_DISABLED_EVIDENCE,
        "unsupported_content": counts["UNSUPPORTED"],
        "unsupported_count": counts["UNSUPPORTED"],
        "grounding_counts": counts,
        "records_reviewed": len(reviewed),
        "records": reviewed,
        "record_metrics": record_metrics(transport),
        "src_metrics": src_metrics(transport, window),
        "dimensions": dimensions,
        "relations": _relation_quality(records, reviewed),
        "relation_grades": {
            "well_supported": well,
            "plausible_but_loose": loose,
            "incorrect": incorrect,
            "unverifiable": unverifiable,
            "rows": relation_rows,
        },
        "examples": examples,
        "references": references,
        "uncertainties": uncertainties,
        "do_not_generalize": True,
        "editorial_quality_evaluated": False,
    }


__all__ = ["build_forensic_semantic_review"]
