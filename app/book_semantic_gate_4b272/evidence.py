"""Canonical P3 evidence extraction. Read-only. No h01 evidence. No provider calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_generation.hydrate import load_clean_transcript_index
from app.book_semantic_gate_4b23.identity import load_json, verify_canonical_inputs
from app.book_semantic_gate_4b23.paths import production_map_path, production_plan_path
from app.book_semantic_gate_4b261.complexity import extract_gate_input
from app.book_semantic_gate_4b261.evidence import load_4b26_bundle
from app.book_semantic_gate_4b261.strategies import _slice_gate_input
from app.book_semantic_gate_4b272.constants import (
    DISPUTED_CAUSAL_CLAUSE,
    H01_EVIDENCE_HANDLES,
    P3_CONTEXT_SRC_IDS,
    P3_EVIDENCE_HANDLES,
    P3_SRC_IDS,
    PHASE,
    PROJECT_NAME,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
)
from app.book_semantic_gate_4b272.identity import load_p3_benchmark_case, load_p3_gate_paragraph
from app.editorial_planning.models import EditorialPlan
from app.source_analysis.models import SourceMap

NEIGHBOR_WINDOW = 3


def _segment_payload(segment: Any) -> dict[str, Any]:
    return {
        "id": segment.src_id,
        "text": segment.text,
        "provenance": {
            "artifact": "transcripts/clean/transcript_data.json",
            "source_id": segment.source_id,
            "source_order": segment.source_order,
        },
        "temporal_position": {
            "start_seconds": segment.start,
            "end_seconds": segment.end,
        },
        "chars": len(segment.text),
    }


def _neighbors(segments: list[Any], src_id: str) -> list[dict[str, Any]]:
    by_id = {item.src_id: index for index, item in enumerate(segments)}
    index = by_id.get(src_id)
    if index is None:
        return []
    lo = max(0, index - NEIGHBOR_WINDOW)
    hi = min(len(segments), index + NEIGHBOR_WINDOW + 1)
    rows = []
    for cursor in range(lo, hi):
        item = segments[cursor]
        rows.append(
            {
                "id": item.src_id,
                "text": item.text,
                "start_seconds": item.start,
                "end_seconds": item.end,
                "is_target": item.src_id == src_id,
                "in_authorized_p3_handles": item.src_id in P3_EVIDENCE_HANDLES,
            }
        )
    return rows


def _gate_supplied_texts(gate: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in gate.get("src_text") or []:
        handle = str(row.get("id") or "")
        if handle:
            out[handle] = str(row.get("t") or row.get("text") or "")
    for row in gate.get("ideas") or []:
        handle = str(row.get("id") or "")
        if handle:
            out[handle] = str(row.get("sum") or row.get("t") or row.get("text") or "")
    for row in gate.get("references") or []:
        handle = str(row.get("id") or "")
        if handle:
            out[handle] = str(row.get("t") or row.get("text") or row.get("sum") or "")
    return out


def _src_clause_relation(src_id: str, text: str) -> dict[str, Any]:
    lowered = text.lower()
    mapping = {
        "SRC006152": (
            "Supports 'Fear of death is an abuse'. Does not state why a "
            "strategy continues to operate."
        ),
        "SRC006154": (
            "Supports 'an abuse to your very person'. No causal 'because' "
            "and no resistance-by-truth condition."
        ),
        "SRC006155": (
            "Names the devil as the agent of the abuse. No effectiveness or "
            "truth-resistance claim."
        ),
        "SRC006156": (
            "Attests that the devil has used the abuse since. Continuity of "
            "use is not a because-clause about present efficacy wherever "
            "truth does not resist."
        ),
        "SRC006157": (
            "Attests that the devil has not changed his style. Unchanged "
            "style is not the same as 'it still works wherever it is not "
            "resisted by truth'."
        ),
    }
    return {
        "relation_with_paragraph": mapping.get(src_id, "Assigned P3 SRC wording."),
        "relation_with_causal_clause": (
            "Does not explicitly affirm or entail the disputed because-clause."
        ),
        "contains_exact_clause": DISPUTED_CAUSAL_CLAUSE.lower() in lowered,
        "contains_because": "because" in lowered,
        "contains_still_works": "still works" in lowered,
        "contains_resisted_by_truth": "resisted by truth" in lowered,
        "sufficient_to_justify_causality": False,
    }


def build_canonical_evidence_inventory(*, root: Path | None = None) -> dict[str, Any]:
    identities = verify_canonical_inputs(root=root)
    historical = load_p3_benchmark_case(root=root)
    paragraph = load_p3_gate_paragraph(root=root)
    bundle = load_4b26_bundle(root=root)
    gate = extract_gate_input(dict(bundle.get("payload") or {}))
    sliced = _slice_gate_input(gate, [SELECTED_CASE_HANDLE])
    supplied = _gate_supplied_texts(sliced)
    source_map = SourceMap.from_dict(load_json(production_map_path()))
    plan = EditorialPlan.from_dict(load_json(production_plan_path()))
    idea = next(item for item in source_map.ideas if item.idea_id == "IDEA225")
    index = load_clean_transcript_index(PROJECT_NAME)
    segments = list(index.segments)
    lookup = index.by_src()
    plan_section = None
    for chapter in plan.chapters:
        for section in chapter.sections:
            if "IDEA225" in section.idea_refs:
                plan_section = {
                    "chapter_id": chapter.chapter_id,
                    "section_id": section.section_id,
                    "purpose": section.purpose,
                    "idea_refs": list(section.idea_refs),
                }
                break
        if plan_section:
            break
    src_rows = []
    for src_id in P3_SRC_IDS:
        segment = lookup[src_id]
        gate_text = supplied.get(src_id)
        relation = _src_clause_relation(src_id, segment.text)
        src_rows.append(
            {
                "id": src_id,
                "canonical_id": src_id,
                "exact_text": segment.text,
                "gate_request_text": gate_text,
                "gate_text_matches_canonical": gate_text == segment.text,
                "provenance": {
                    "artifact": "transcripts/clean/transcript_data.json",
                    "source_id": segment.source_id,
                    "source_order": segment.source_order,
                    "source_map_ref_via_idea": src_id in idea.source_refs,
                },
                "temporal_position": {
                    "start_seconds": segment.start,
                    "end_seconds": segment.end,
                },
                "local_context": _neighbors(segments, src_id),
                "relation_with_paragraph": relation["relation_with_paragraph"],
                "relation_with_causal_clause": relation["relation_with_causal_clause"],
                "sufficiency_for_causality": "insufficient",
                "contains_exact_clause": relation["contains_exact_clause"],
                "contains_because": relation["contains_because"],
                "sufficient_to_justify_causality": relation[
                    "sufficient_to_justify_causality"
                ],
            }
        )
    neighboring_not_sent = []
    for src_id in P3_CONTEXT_SRC_IDS:
        segment = lookup[src_id]
        neighboring_not_sent.append(
            {
                **_segment_payload(segment),
                "in_gate_request": False,
                "not_used_as_additional_terra_evidence": True,
                "not_used_to_complete_p3": True,
                "why_recorded": (
                    "Local canonical context around assigned SRC IDs. "
                    "Not supplied to the provider. Not used to complete "
                    "missing support from outside the historical case."
                ),
            }
        )
    idea_text = idea.summary
    idea_lowered = idea_text.lower()
    present_ids = sorted(
        {str(item.get("id") or "") for item in (sliced.get("src_text") or []) if item.get("id")}
        | {str(item.get("id") or "") for item in (sliced.get("ideas") or []) if item.get("id")}
        | {str(item.get("id") or "") for item in (sliced.get("references") or []) if item.get("id")}
    )
    missing = [handle for handle in P3_EVIDENCE_HANDLES if handle not in present_ids]
    h01_injected = [handle for handle in H01_EVIDENCE_HANDLES if handle in present_ids]
    return {
        "phase": PHASE,
        "handle": SELECTED_CASE_HANDLE,
        "case_id_audit_only": SELECTED_CASE_ID,
        "paragraph": {
            "handle": SELECTED_CASE_HANDLE,
            "exact_text": str(historical.get("text") or paragraph.get("text") or ""),
            "chars": len(str(historical.get("text") or "")),
            "unicode_codepoints": len(str(historical.get("text") or "")),
            "utf8_bytes": len(str(historical.get("text") or "").encode("utf-8")),
            "source": "frozen 4B.2.3 benchmark / 4B.2.6 gate slice h02",
        },
        "ideas": [
            {
                "id": "IDEA225",
                "canonical_id": "IDEA225",
                "exact_text": idea_text,
                "kind": idea.kind,
                "importance": idea.importance,
                "topic_refs": list(idea.topic_refs),
                "relations": [item.to_dict() for item in idea.relations],
                "source_refs": list(idea.source_refs),
                "gate_request_text": supplied.get("IDEA225"),
                "gate_text_matches_canonical": supplied.get("IDEA225") == idea_text,
                "provenance": {
                    "artifact": "analysis/source_map.json",
                    "field": "ideas[].summary",
                    "note": (
                        "SourceMap idea records contain a summary, not a "
                        "longer body. No additional IDEA225 prose exists."
                    ),
                },
                "editorial_assignment": plan_section,
                "relation_with_paragraph": (
                    "Canonical restatement that living is abused when death "
                    "is feared, and that fear of death is the devil's old "
                    "strategy."
                ),
                "relation_with_causal_clause": (
                    "Names an old strategy. Does not say the strategy still "
                    "works wherever it is not resisted by truth."
                ),
                "contains_exact_clause": DISPUTED_CAUSAL_CLAUSE.lower() in idea_lowered,
                "contains_because": "because" in idea_lowered,
                "sufficient_to_justify_causality": False,
                "sufficiency_for_causality": "insufficient",
            }
        ],
        "src": src_rows,
        "references": [],
        "neighboring_canonical_src_not_in_gate_request": neighboring_not_sent,
        "allowed_handles_in_request": list(P3_EVIDENCE_HANDLES),
        "present_ids": present_ids,
        "missing_required_handles": missing,
        "h01_handles_injected": h01_injected,
        "complete": not missing and not h01_injected and bool(present_ids),
        "other_cases_excluded": not h01_injected,
        "h01_evidence_not_used": not h01_injected,
        "external_religious_knowledge_used": False,
        "summaries_not_substituted_for_src": True,
        "canonical_hashes": {
            "source_map": identities["source_map"]["sha256"],
            "editorial_plan": identities["editorial_plan"]["sha256"],
            "clean_transcript": identities["clean_transcript"]["sha256"],
        },
        "secrets_included": False,
    }


__all__ = ["P3_CONTEXT_SRC_IDS", "P3_SRC_IDS", "build_canonical_evidence_inventory"]
