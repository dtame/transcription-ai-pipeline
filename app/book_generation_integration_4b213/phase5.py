"""Phase 5 Book Validator interface only. Not implemented. Not executed."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation_integration_4b213.constants import (
    PHASE,
    PHASE5_INTERFACE_VERSION,
    PRODUCTION_CACHE_ACCEPTANCE,
)


def phase5_payload(chapter_result: Mapping[str, Any]) -> dict[str, Any]:
    chapter = dict(chapter_result.get("chapter") or {})
    return {
        "interface_version": PHASE5_INTERFACE_VERSION,
        "executed": False,
        "independent": True,
        "must_not_accept_semantic_gate_verdict_alone": True,
        "chapter_id": chapter.get("chapter_id"),
        "title": chapter.get("title"),
        "text": [
            {
                "paragraph_id": para.get("paragraph_id"),
                "section_id": para.get("section_id"),
                "text": para.get("text"),
                "kind": para.get("kind"),
            }
            for para in chapter_result.get("paragraph_results") or []
        ],
        "structure": chapter_result.get("structure"),
        "sources": [
            handle
            for para in chapter_result.get("paragraph_results") or []
            for handle in para.get("source_refs") or []
        ],
        "evidence_handles": [
            handle
            for para in chapter_result.get("paragraph_results") or []
            for handle in para.get("evidence_handles") or []
        ],
        "semantic_gate_results": {
            "decision": chapter_result.get("decision"),
            "paragraph_decisions": [
                {
                    "paragraph_id": para.get("paragraph_id"),
                    "decision": para.get("decision"),
                    "validation_ok": (para.get("validation") or {}).get("ok"),
                    "verdicts": (para.get("validation") or {}).get("verdicts"),
                }
                for para in chapter_result.get("paragraph_results") or []
            ],
        },
        "versions": (chapter_result.get("cache_record") or {}).get("versions"),
        "hashes": {
            "generated_text_sha256": (chapter_result.get("cache_record") or {}).get(
                "generated_text_sha256"
            ),
            "validation_key": chapter_result.get("key"),
            "source_map_sha256": chapter.get("source_map_sha256"),
            "editorial_plan_sha256": chapter.get("editorial_plan_sha256"),
        },
        "decisions": {
            "chapter": chapter_result.get("decision"),
            "isolated_acceptance_candidate": chapter_result.get("isolated_acceptance_candidate"),
        },
        "anomalies": (chapter_result.get("chapter_policy") or {}).get("reasons") or [],
        "traceability": [
            {
                "chapter_id": para.get("chapter_id"),
                "section_id": para.get("section_id"),
                "paragraph_id": para.get("paragraph_id"),
                "unit_ids": [
                    unit.get("unit_id")
                    for unit in (para.get("prepared") or {}).get("units") or []
                ],
                "evidence_handles": para.get("evidence_handles"),
            }
            for para in chapter_result.get("paragraph_results") or []
        ],
        "production_cache_acceptance": PRODUCTION_CACHE_ACCEPTANCE,
        "phase5_not_started": True,
        "secrets_included": False,
    }


def phase5_interface(chapter_result: Mapping[str, Any] | None = None) -> dict[str, Any]:
    sample = phase5_payload(chapter_result or {})
    return {
        "phase": PHASE,
        "version": PHASE5_INTERFACE_VERSION,
        "implemented": False,
        "executed": False,
        "independent": True,
        "semantic_gate_does_not_replace_phase5": True,
        "required_inputs": [
            "chapter",
            "text",
            "structure",
            "sources",
            "evidence_handles",
            "semantic_gate_results",
            "versions",
            "hashes",
            "decisions",
            "anomalies",
            "traceability",
        ],
        "sample": sample,
        "secrets_included": False,
    }


__all__ = ["phase5_interface", "phase5_payload"]
