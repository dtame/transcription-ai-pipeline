"""Minimal canonical semantic-gate input. Targeted evidence only."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.book_generation.evidence import render_evidence_json
from app.book_semantic_gate_4b23.constants import (
    EVIDENCE_SCOPE,
    SEMANTIC_GATE_VALIDATOR_VERSION,
)
from app.file_utils import content_hash


def compact_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    sections = []
    for section in candidate.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        paragraphs = []
        for para in section.get("paragraphs") or []:
            if not isinstance(para, Mapping):
                continue
            paragraphs.append(
                {
                    "h": str(para.get("provider_handle") or para.get("h") or ""),
                    "k": str(para.get("kind") or para.get("k") or ""),
                    "t": str(para.get("text") or para.get("t") or ""),
                    "e": list(
                        para.get("evidence_handles")
                        or para.get("e")
                        or []
                    ),
                    "idea": list(para.get("idea_refs") or []),
                    "ex": list(para.get("example_refs") or []),
                    "ref": list(para.get("reference_refs") or []),
                    "unc": list(para.get("uncertainty_refs") or []),
                    "src": list(para.get("source_refs") or []),
                }
            )
        sections.append(
            {
                "sid": str(section.get("section_id") or section.get("sid") or ""),
                "title": str(section.get("title") or ""),
                "paras": paragraphs,
            }
        )
    return {
        "chapter_id": str(candidate.get("chapter_id") or ""),
        "title": str(candidate.get("title") or ""),
        "sections": sections,
    }


def required_paragraph_handles(candidate: Mapping[str, Any]) -> list[str]:
    handles: list[str] = []
    compact = compact_candidate(candidate)
    for section in compact.get("sections") or []:
        for para in section.get("paras") or []:
            handle = str(para.get("h") or "")
            if handle:
                handles.append(handle)
    return handles


def build_gate_input(
    *,
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Any],
    language: str,
    approved_reuse: list[str] | None = None,
) -> dict[str, Any]:
    compact = compact_candidate(candidate)
    return {
        "v": SEMANTIC_GATE_VALIDATOR_VERSION,
        "chapter_handle": compact.get("chapter_id")
        or (evidence.get("chapter") or {}).get("id"),
        "canonical_document_language": language,
        "chapter": {
            "id": (evidence.get("chapter") or {}).get("id"),
            "t": (evidence.get("chapter") or {}).get("t"),
            "p": (evidence.get("chapter") or {}).get("p"),
        },
        "sections": list(evidence.get("sections") or []),
        "candidate": compact,
        "ideas": list(evidence.get("ideas") or []),
        "examples": list(evidence.get("examples") or []),
        "references": list(evidence.get("references") or []),
        "uncertainties": list(evidence.get("uncertainties") or []),
        "src_text": list(evidence.get("src_text") or []),
        "allowed_handles": list(evidence.get("allowed") or []),
        "approved_reuse": list(approved_reuse or []),
        "scope": EVIDENCE_SCOPE,
        "rules": {
            "judge_only_supplied_evidence": True,
            "no_external_knowledge": True,
            "declared_handles_are_hints_only": True,
            "partial_ref_permits_only_supplied_content": True,
            "no_rescue_from_other_chapters": True,
            "paraphrase_allowed": True,
            "synthesis_within_combined_support_allowed": True,
            "provider_kind_not_authoritative": True,
            "no_manuscript_rewrite": True,
        },
    }


def render_gate_input_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def gate_input_identity(payload: Mapping[str, Any]) -> str:
    return content_hash(render_gate_input_json(payload))


def evidence_contract_payload() -> dict[str, Any]:
    return {
        "minimal_chapter_input": [
            "generated chapter candidate",
            "canonical chapter/section structure",
            "assigned IDEA evidence",
            "EX evidence",
            "REF evidence",
            "UNC evidence",
            "hydrated SRC text",
            "canonical language",
            "traceability handles",
        ],
        "no_whole_book": True,
        "no_whole_transcript": True,
        "evidence_scope": EVIDENCE_SCOPE,
        "declared_handles": "hints, never proof",
        "verification_scope": "bounded canonical section evidence",
        "do_not_rescue_with_other_chapters": True,
        "approved_reuse_only_when_editorial_plan_authorizes": True,
        "hydrated_src_is_primary_wording_evidence": True,
        "source_map_provides_organization_and_traceability": True,
        "partial_reference_rule": (
            "A partial REF permits only what the supplied REF/SRC evidence "
            "actually contains."
        ),
        "not_bible_specific": True,
        "bundle_version": SEMANTIC_GATE_VALIDATOR_VERSION,
        "note": (
            "Gate input is derived from the existing chapter evidence bundle "
            "plus the generated candidate. Full SourceMap and full transcript "
            "are never sent."
        ),
    }


def production_evidence_sha256(evidence: Mapping[str, Any]) -> str:
    return content_hash(render_evidence_json(dict(evidence)))


__all__ = [
    "build_gate_input",
    "compact_candidate",
    "evidence_contract_payload",
    "gate_input_identity",
    "production_evidence_sha256",
    "render_gate_input_json",
    "required_paragraph_handles",
]
