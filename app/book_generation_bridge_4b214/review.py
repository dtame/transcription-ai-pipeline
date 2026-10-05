"""Human review protocol for REVIEW and BLOCK. Original model output is preserved."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation_bridge_4b214.constants import (
    DECISION_BLOCK,
    DECISION_PASS,
    DECISION_REVIEW,
    PHASE,
    REVIEW_CONFIRM_SUPPORTED,
    REVIEW_MAINTAIN_BLOCK,
    REVIEW_PROTOCOL_VERSION,
    REVIEW_REQUEST_CORRECTION,
)
from app.book_generation_bridge_4b214.guard import BookGenerationBridge214Error
from app.file_utils import content_hash


def apply_human_review(
    chapter_result: Mapping[str, Any],
    *,
    action: str,
    reviewer: str,
    note: str,
) -> dict[str, Any]:
    if action not in {
        REVIEW_CONFIRM_SUPPORTED,
        REVIEW_REQUEST_CORRECTION,
        REVIEW_MAINTAIN_BLOCK,
    }:
        raise BookGenerationBridge214Error(f"unknown review action {action!r}")
    decision = str(chapter_result.get("decision") or "")
    raw_preserved = []
    for para in chapter_result.get("paragraph_results") or []:
        raw_preserved.append(
            {
                "paragraph_id": para.get("paragraph_id"),
                "raw": para.get("raw"),
                "raw_hash": content_hash(repr(para.get("raw"))),
                "text": para.get("text"),
                "evidence_handles": list(para.get("evidence_handles") or []),
                "decision": para.get("decision"),
            }
        )
    human_decision = decision
    requires_new_text_version = False
    production_cache_write = False
    isolated_acceptance_candidate = bool(
        chapter_result.get("isolated_acceptance_candidate")
    )
    if decision == DECISION_BLOCK:
        if action == REVIEW_CONFIRM_SUPPORTED:
            human_decision = DECISION_BLOCK
            note_extra = "BLOCK cannot become PASS automatically."
        elif action == REVIEW_REQUEST_CORRECTION:
            human_decision = DECISION_BLOCK
            requires_new_text_version = True
            isolated_acceptance_candidate = False
            note_extra = "Correction must produce a new text version; previous validation is invalid."
        else:
            human_decision = DECISION_BLOCK
            isolated_acceptance_candidate = False
            note_extra = "BLOCK maintained."
    elif decision == DECISION_REVIEW:
        if action == REVIEW_CONFIRM_SUPPORTED:
            human_decision = DECISION_REVIEW
            isolated_acceptance_candidate = False
            note_extra = (
                "Human confirmed the proposition appears supported. "
                "This does not rewrite the model response and does not write production cache."
            )
        elif action == REVIEW_REQUEST_CORRECTION:
            human_decision = DECISION_REVIEW
            requires_new_text_version = True
            isolated_acceptance_candidate = False
            note_extra = "Human requested correction. New text version required."
        else:
            human_decision = DECISION_BLOCK
            isolated_acceptance_candidate = False
            note_extra = "Human maintained a block from REVIEW."
    elif decision == DECISION_PASS:
        human_decision = DECISION_PASS
        note_extra = "PASS is unchanged by this protocol. Production cache still refused."
    else:
        human_decision = DECISION_BLOCK
        note_extra = "Unknown machine decision remains blocked."
    return {
        "phase": PHASE,
        "protocol_version": REVIEW_PROTOCOL_VERSION,
        "machine_decision": decision,
        "human_action": action,
        "human_decision": human_decision,
        "reviewer": reviewer,
        "note": f"{note} {note_extra}".strip(),
        "raw_preserved": raw_preserved,
        "original_response_mutated": False,
        "requires_new_text_version": requires_new_text_version,
        "previous_validation_invalidated": requires_new_text_version,
        "block_cannot_become_pass_automatically": True,
        "production_cache_write": production_cache_write,
        "isolated_acceptance_candidate": isolated_acceptance_candidate,
        "audited": True,
        "secrets_included": False,
    }


def human_review_protocol() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "version": REVIEW_PROTOCOL_VERSION,
        "review_keeps": [
            "proposal",
            "text",
            "evidence",
            "reason",
            "identifiers",
            "versions",
            "hashes",
        ],
        "review_actions": [
            REVIEW_CONFIRM_SUPPORTED,
            REVIEW_REQUEST_CORRECTION,
            REVIEW_MAINTAIN_BLOCK,
        ],
        "block_cannot_become_pass_automatically": True,
        "correction_requires_new_text_version": True,
        "substantial_text_change_invalidates_previous_validation": True,
        "no_automatic_production_cache_acceptance": True,
        "original_model_response_not_silently_modified": True,
        "human_decision_is_audited": True,
        "secrets_included": False,
    }


__all__ = ["apply_human_review", "human_review_protocol"]
