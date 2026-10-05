"""Phase 5 Book Validator boundary. Not executed. Independent of Semantic Gate."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation_bridge_4b214.constants import (
    COST_UNKNOWN,
    PHASE,
    PHASE5_EXECUTED,
    PHASE5_INTERFACE_VERSION,
    PRODUCTION_CACHE_ACCEPTANCE,
)
from app.book_generation_integration_4b213.phase5 import phase5_payload


def phase5_boundary(chapter_result: Mapping[str, Any] | None = None) -> dict[str, Any]:
    sample = phase5_payload(chapter_result or {})
    return {
        "phase": PHASE,
        "version": PHASE5_INTERFACE_VERSION,
        "implemented": False,
        "executed": PHASE5_EXECUTED,
        "independent": True,
        "semantic_gate_pass_does_not_make_book_publishable": True,
        "semantic_gate_does_not_replace_phase5": True,
        "required_inputs": [
            "chapter",
            "text",
            "structure",
            "sources",
            "evidence_handles",
            "semantic_gate_results",
            "human_review",
            "versions",
            "hashes",
            "decisions",
            "anomalies",
            "traceability",
            "budget_unknowns",
        ],
        "contracts": {
            "book_schema": "1.0",
            "semantic_contract": "book-semantic-validator-2.0.2-candidate",
            "independent_validator": "not_implemented",
        },
        "hashes_required": [
            "source_map_sha256",
            "editorial_plan_sha256",
            "transcript_sha256",
            "generated_text_sha256",
            "evidence_bundle_sha256",
        ],
        "human_review_elements": [
            "machine_decision",
            "human_action",
            "human_decision",
            "original_raw_preserved",
        ],
        "cost": {
            "status": COST_UNKNOWN,
            "counted_as_zero": False,
        },
        "trigger_conditions": [
            "All intended chapters have isolated Semantic Gate decisions.",
            "Human review of REVIEW/BLOCK is complete.",
            "Independent Book Validator implementation exists.",
            "Explicit human authorization for Phase 5 is issued.",
            "Phase 5 budget is no longer UNKNOWN or is explicitly accepted as unknown-with-cap.",
        ],
        "sample": sample,
        "production_cache_acceptance": PRODUCTION_CACHE_ACCEPTANCE,
        "word_pdf": "not_authorized",
        "secrets_included": False,
    }


__all__ = ["phase5_boundary"]
