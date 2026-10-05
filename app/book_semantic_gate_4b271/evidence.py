"""Canonical h01 evidence extraction. Read-only. No provider calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.book_generation.hydrate import load_clean_transcript_index
from app.book_semantic_gate_4b23.identity import load_json, verify_canonical_inputs
from app.book_semantic_gate_4b23.paths import production_map_path, production_plan_path
from app.book_semantic_gate_4b261.complexity import extract_gate_input
from app.book_semantic_gate_4b262.request import freeze_single_case_request
from app.book_semantic_gate_4b27.request import paragraph_context
from app.book_semantic_gate_4b271.constants import (
    EXPECTED_EVIDENCE_HANDLES,
    PHASE,
    PROJECT_NAME,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
)
from app.editorial_planning.models import EditorialPlan
from app.source_analysis.models import SourceMap

NEIGHBOR_WINDOW = 3
SRC_IDS = (
    "SRC006149",
    "SRC006180",
    "SRC006182",
    "SRC006183",
    "SRC006187",
)
CONTEXT_SRC_IDS = (
    "SRC006181",
    "SRC006184",
    "SRC006185",
    "SRC006186",
    "SRC006188",
    "SRC006189",
)


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
                "in_gate_request": item.src_id in SRC_IDS or item.src_id == "IDEA224",
            }
        )
    return rows


def _gate_supplied_texts(payload: dict[str, Any]) -> dict[str, str]:
    gate = extract_gate_input(payload)
    out: dict[str, str] = {}
    for row in gate.get("src_text") or []:
        handle = str(row.get("id") or "")
        if handle:
            out[handle] = str(row.get("t") or row.get("text") or "")
    for row in gate.get("ideas") or []:
        handle = str(row.get("id") or "")
        if handle:
            out[handle] = str(row.get("sum") or row.get("t") or row.get("text") or "")
    return out


def build_canonical_evidence_inventory(*, root: Path | None = None) -> dict[str, Any]:
    identities = verify_canonical_inputs(root=root)
    context = paragraph_context(root=root)
    frozen = freeze_single_case_request(root=root)
    payload = dict(frozen.get("payload") or {})
    paragraph = str((context.get("paragraph_texts") or {}).get(SELECTED_CASE_HANDLE) or "")
    supplied = _gate_supplied_texts(payload)
    source_map = SourceMap.from_dict(load_json(production_map_path()))
    plan = EditorialPlan.from_dict(load_json(production_plan_path()))
    idea = next(item for item in source_map.ideas if item.idea_id == "IDEA224")
    topic = next((item for item in source_map.topics if item.topic_id == "TOP054"), None)
    index = load_clean_transcript_index(PROJECT_NAME)
    segments = list(index.segments)
    lookup = index.by_src()
    plan_section = None
    for chapter in plan.chapters:
        for section in chapter.sections:
            if "IDEA224" in section.idea_refs:
                plan_section = {
                    "chapter_id": chapter.chapter_id,
                    "section_id": section.section_id,
                    "purpose": section.purpose,
                    "idea_refs": list(section.idea_refs),
                }
                break
    src_rows = []
    for src_id in SRC_IDS:
        segment = lookup[src_id]
        gate_text = supplied.get(src_id)
        src_rows.append(
            {
                "id": src_id,
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
                "relation_with_IDEA224": (
                    "Listed in IDEA224.source_refs. Hydrated SRC wording is "
                    "primary wording evidence; the IDEA summary is a compact "
                    "canonical restatement, not a substitute for SRC text."
                ),
                "relation_with_disputed_clause": _src_clause_relation(src_id, segment.text),
            }
        )
    neighboring_not_sent = []
    for src_id in CONTEXT_SRC_IDS:
        segment = lookup[src_id]
        neighboring_not_sent.append(
            {
                **_segment_payload(segment),
                "in_gate_request": False,
                "not_used_as_additional_terra_evidence": True,
                "why_recorded": (
                    "Local canonical context around assigned SRC IDs. "
                    "Not supplied to Terra. Not used to complete missing "
                    "support from outside the gate request."
                ),
            }
        )
    return {
        "phase": PHASE,
        "handle": SELECTED_CASE_HANDLE,
        "case_id_audit_only": SELECTED_CASE_ID,
        "paragraph": {
            "handle": SELECTED_CASE_HANDLE,
            "exact_text": paragraph,
            "chars": len(paragraph),
            "unicode_codepoints": len(paragraph),
            "utf8_bytes": len(paragraph.encode("utf-8")),
            "source": "frozen 4B.2.2 candidate / compact 4B.2.7 request",
        },
        "ideas": [
            {
                "id": "IDEA224",
                "exact_text": idea.summary,
                "kind": idea.kind,
                "importance": idea.importance,
                "topic_refs": list(idea.topic_refs),
                "relations": [item.to_dict() for item in idea.relations],
                "source_refs": list(idea.source_refs),
                "gate_request_text": supplied.get("IDEA224"),
                "gate_text_matches_canonical": supplied.get("IDEA224") == idea.summary,
                "provenance": {
                    "artifact": "analysis/source_map.json",
                    "field": "ideas[].summary",
                    "note": (
                        "SourceMap idea records contain a summary, not a "
                        "longer body. No additional IDEA224 prose exists."
                    ),
                },
                "editorial_assignment": plan_section,
                "relation_with_disputed_clause": (
                    "The summary attests that believers should not fear death "
                    "because there is no set time. It does not contain the "
                    "verbs calculate or bargain."
                ),
            }
        ],
        "src": src_rows,
        "topic": topic.to_dict() if topic is not None else None,
        "neighboring_canonical_src_not_in_gate_request": neighboring_not_sent,
        "allowed_handles_in_request": list(EXPECTED_EVIDENCE_HANDLES),
        "external_religious_knowledge_used": False,
        "summaries_not_substituted_for_src": True,
        "canonical_hashes": {
            "source_map": identities["source_map"]["sha256"],
            "editorial_plan": identities["editorial_plan"]["sha256"],
            "clean_transcript": identities["clean_transcript"]["sha256"],
        },
        "secrets_included": False,
    }


def _src_clause_relation(src_id: str, text: str) -> str:
    mapping = {
        "SRC006149": (
            "Supports the opening prohibition of fear of death. No calculate "
            "or bargain wording."
        ),
        "SRC006180": (
            "Attests that fear is observable. No calculate or bargain wording. "
            "Does not itself support or refute the no-set-time claim."
        ),
        "SRC006182": (
            "Attests that the observed fear is not normal. No calculate or "
            "bargain wording."
        ),
        "SRC006183": (
            "Supports 'It should be our joy.' No calculate or bargain wording."
        ),
        "SRC006187": (
            "Supports the 'if somebody has gone to heaven' opening. No "
            "calculate or bargain wording."
        ),
    }
    return mapping.get(src_id, text)


def load_saved_terra_payload(*, root: Path | None = None) -> dict[str, Any]:
    from app.book_semantic_gate_4b271.paths import historical_4b27_dir

    path = historical_4b27_dir(root=root) / "book_semantic_gate_4b27_raw_structured_response.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    parsed = payload.get("parsed")
    if not isinstance(parsed, dict):
        raise ValueError("Saved Terra JSON is missing parsed object.")
    return parsed


__all__ = [
    "CONTEXT_SRC_IDS",
    "SRC_IDS",
    "build_canonical_evidence_inventory",
    "load_saved_terra_payload",
]
