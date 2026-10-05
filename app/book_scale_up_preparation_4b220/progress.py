"""Preparation progress manifest. No fake AUTHORIZED or GENERATED states."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_scale_up_preparation_4b220.constants import (
    ACCEPTED_CHAPTER,
    EXPECTED_ACCEPTED_JSON_SHA256,
    EXPECTED_ACCEPTED_MD_SHA256,
    PHASE,
    PROGRESS_MANIFEST_VERSION,
    STATUS_ACCEPTED,
    STATUS_AUTHORIZED,
    STATUS_PENDING,
    STATUS_READY,
)
from app.book_scale_up_preparation_4b220.paths import accepted_editorial_manifest_path


def scale_up_progress_manifest(
    *,
    inventory: Mapping[str, Any],
    selection: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    first_id = str(selection.get("selected_chapter_id") or "")
    first_ready = bool(context.get("ready")) and not context.get("generation_blocked")
    chapters = []
    chapters.append(
        {
            "chapter_id": ACCEPTED_CHAPTER,
            "status": STATUS_ACCEPTED,
            "generation_status": STATUS_ACCEPTED,
            "validation_status": "EDITORIAL_ACCEPTED_NOT_SEMANTICALLY_CERTIFIED",
            "content_duplicated": False,
            "accepted_manifest": str(accepted_editorial_manifest_path()).replace("\\", "/"),
            "accepted_md_sha256": EXPECTED_ACCEPTED_MD_SHA256,
            "accepted_json_sha256": EXPECTED_ACCEPTED_JSON_SHA256,
            "attempt": None,
        }
    )
    for row in inventory.get("chapters") or []:
        chapter_id = row["chapter_id"]
        if chapter_id == first_id and first_ready:
            status = STATUS_READY
        else:
            status = STATUS_PENDING
        chapters.append(
            {
                "chapter_id": chapter_id,
                "working_title": row.get("working_title"),
                "book_order": row.get("book_order"),
                "status": status,
                "generation_status": status,
                "validation_status": "NOT_STARTED",
                "authorized": False,
                "attempt": None,
                "required_attempt_fields_when_generated": [
                    "attempt_id",
                    "model",
                    "prompt_version",
                    "context_sha256",
                    "response_sha256",
                    "actual_cost_usd",
                    "errors",
                ],
            }
        )
    statuses = {row["chapter_id"]: row["status"] for row in chapters}
    if statuses.get(ACCEPTED_CHAPTER) != STATUS_ACCEPTED:
        raise RuntimeError("CH012 must remain ACCEPTED in the progress manifest.")
    if STATUS_AUTHORIZED in statuses.values():
        raise RuntimeError("No chapter may be marked AUTHORIZED in this phase.")
    if any(
        row["status"] == "GENERATED" and row.get("attempt") is None for row in chapters
    ):
        raise RuntimeError("GENERATED requires a verifiable artifact.")
    return {
        "phase": PHASE,
        "manifest_version": PROGRESS_MANIFEST_VERSION,
        "kind": "preparation_manifest",
        "authorized_spend_usd": 0.0,
        "any_authorized_false": True,
        "chapters": chapters,
        "resume_policy": {
            "identify_attempts_by_unique_id": True,
            "keep_model_and_prompt": True,
            "keep_context_hash": True,
            "keep_response_hash": True,
            "keep_actual_cost": True,
            "keep_errors": True,
            "no_paid_repeat_after_ambiguous_interruption": True,
            "human_decision_required_if_attempt_uncertain": True,
        },
        "ch012_content_not_duplicated": True,
        "book_json_published": False,
        "secrets_included": False,
    }


__all__ = ["scale_up_progress_manifest"]
