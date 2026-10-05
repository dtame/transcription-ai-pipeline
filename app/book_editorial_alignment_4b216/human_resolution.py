"""
Lightweight human-resolution protocol.

The original Terra response stays immutable.
A human decision does not authorize publication.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.book_editorial_alignment_4b216.constants import (
    HISTORICAL_H11_STATUS,
    HISTORICAL_SEMANTIC_CONTRACT,
    HUMAN_RESOLUTION_VERSION,
    PHASE,
)
from app.book_editorial_alignment_4b216.guard import BookEditorialAlignment4216Error
from app.book_semantic_gate_4b28.constants import H11_HUMAN_LABEL

DECISION_CONFIRM_INVENTION = "CONFIRM_INVENTION_AND_REQUEST_CORRECTION"
DECISION_CONFIRM_FALSE_REJECTION = "CONFIRM_FALSE_REJECTION"
DECISION_MAINTAIN_BLOCK = "MAINTAIN_BLOCK"
DECISIONS = (
    DECISION_CONFIRM_INVENTION,
    DECISION_CONFIRM_FALSE_REJECTION,
    DECISION_MAINTAIN_BLOCK,
)

REQUIRED_FIELDS = (
    "exact_text",
    "unit_id",
    "terra_verdict",
    "reasons",
    "evidence",
    "sources",
    "contract_version",
    "hashes",
    "human_decision",
    "justification",
)


def protocol_document() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "version": HUMAN_RESOLUTION_VERSION,
        "graphical_interface_built": False,
        "terra_response_immutable": True,
        "human_decision_authorizes_publication": False,
        "independent_validation_still_required": True,
        "does_not_rewrite_historical_labels": True,
        "historical_h11_status": HISTORICAL_H11_STATUS,
        "historical_h11_human_label": H11_HUMAN_LABEL,
        "historical_h11_human_label_unmodified": True,
        "automatic_unsupported_to_supported": False,
        "automatic_block_to_pass": False,
        "required_fields": list(REQUIRED_FIELDS),
        "decisions": [
            {
                "id": DECISION_CONFIRM_INVENTION,
                "label": "Confirm the invention and request a correction.",
            },
            {
                "id": DECISION_CONFIRM_FALSE_REJECTION,
                "label": "Confirm a false rejection with a justification grounded in the sources.",
            },
            {
                "id": DECISION_MAINTAIN_BLOCK,
                "label": "Maintain the block when the case remains uncertain.",
            },
        ],
        "contract_version_expected": HISTORICAL_SEMANTIC_CONTRACT,
        "secrets_included": False,
    }


def build_resolution(record: Mapping[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if not record.get(field)]
    if missing:
        raise BookEditorialAlignment4216Error(
            "human resolution is missing: " + ", ".join(missing)
        )
    decision = str(record.get("human_decision") or "")
    if decision not in DECISIONS:
        raise BookEditorialAlignment4216Error(f"unknown human decision: {decision}")
    if record.get("publication_authorized") is True:
        raise BookEditorialAlignment4216Error(
            "human resolution cannot authorize publication"
        )
    terra_verdict = str(record.get("terra_verdict") or "")
    if record.get("rewritten_terra_verdict") not in (None, "", terra_verdict):
        raise BookEditorialAlignment4216Error("the Terra verdict cannot be rewritten")
    return {
        "phase": PHASE,
        "protocol": HUMAN_RESOLUTION_VERSION,
        "exact_text": record.get("exact_text"),
        "unit_id": record.get("unit_id"),
        "terra_verdict": terra_verdict,
        "terra_verdict_immutable": True,
        "reasons": list(record.get("reasons") or []),
        "evidence": list(record.get("evidence") or []),
        "sources": list(record.get("sources") or []),
        "contract_version": record.get("contract_version"),
        "hashes": dict(record.get("hashes") or {}),
        "human_decision": decision,
        "justification": record.get("justification"),
        "publication_authorized": False,
        "independent_validation_still_required": True,
        "not_a_terra_call": True,
        "secrets_included": False,
    }


__all__ = [
    "DECISION_CONFIRM_FALSE_REJECTION",
    "DECISION_CONFIRM_INVENTION",
    "DECISION_MAINTAIN_BLOCK",
    "build_resolution",
    "protocol_document",
]
