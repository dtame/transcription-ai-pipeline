"""Durable progress manifest. No fake GENERATED or AUTHORIZED states."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_batch_preparation_4b222.constants import (
    ACCEPTED_CH012_ID,
    ACCEPTED_CH018_ID,
    EXPECTED_ACCEPTED_JSON_SHA256,
    EXPECTED_ACCEPTED_MD_SHA256,
    EXPECTED_CH018_JSON_SHA256,
    EXPECTED_CH018_MD_SHA256,
    FAITHFUL_PROMPT_1_1,
    PHASE,
    PROGRESS_MANIFEST_VERSION,
    STATUS_ACCEPTED,
    STATUS_AUTHORIZED,
    STATUS_GENERATED,
    STATUS_PENDING,
)
from app.book_batch_preparation_4b222.guard import BookBatchPreparation4222Error
from app.book_batch_preparation_4b222.paths import (
    accepted_editorial_manifest_path,
    phase_audit_dir,
)


def _accepted_row(
    chapter_id: str,
    *,
    manifest_path: str,
    md_sha256: str,
    json_sha256: str,
    book_order: int,
    title: str,
) -> dict[str, Any]:
    return {
        "chapter_id": chapter_id,
        "working_title": title,
        "book_order": book_order,
        "status": STATUS_ACCEPTED,
        "generation_status": STATUS_ACCEPTED,
        "validation_status": "EDITORIAL_ACCEPTED_NOT_SEMANTICALLY_CERTIFIED",
        "editorial_review": "HUMAN_ACCEPTED",
        "content_duplicated": False,
        "accepted_manifest": manifest_path,
        "accepted_md_sha256": md_sha256,
        "accepted_json_sha256": json_sha256,
        "attempt": None,
        "model": None,
        "prompt": None,
        "prompt_hash": None,
        "context_hash": None,
        "date": None,
        "forecast_cost_usd": None,
        "actual_cost_usd": None,
        "structural_validation": None,
        "artifact_paths": None,
        "artifact_hashes": {
            "markdown_sha256": md_sha256,
            "json_sha256": json_sha256,
        },
        "error": None,
    }


def batch_progress_manifest(
    *,
    inventory: Mapping[str, Any],
    cost: Mapping[str, Any],
    ch018_manifest_path: str,
) -> dict[str, Any]:
    costs = {row["chapter_id"]: row for row in cost.get("per_chapter") or []}
    chapters = [
        _accepted_row(
            ACCEPTED_CH012_ID,
            manifest_path=str(accepted_editorial_manifest_path()).replace("\\", "/"),
            md_sha256=EXPECTED_ACCEPTED_MD_SHA256,
            json_sha256=EXPECTED_ACCEPTED_JSON_SHA256,
            book_order=12,
            title="Prayer Corrected",
        ),
        _accepted_row(
            ACCEPTED_CH018_ID,
            manifest_path=ch018_manifest_path,
            md_sha256=EXPECTED_CH018_MD_SHA256,
            json_sha256=EXPECTED_CH018_JSON_SHA256,
            book_order=18,
            title="Testimonies of Resurrection",
        ),
    ]
    for row in inventory.get("chapters") or []:
        chapter_cost = costs.get(row["chapter_id"]) or {}
        chapters.append(
            {
                "chapter_id": row["chapter_id"],
                "working_title": row.get("working_title"),
                "book_order": row.get("book_order"),
                "status": STATUS_PENDING,
                "generation_status": STATUS_PENDING,
                "validation_status": "NOT_STARTED",
                "editorial_review": "NOT_STARTED",
                "authorized": False,
                "attempt": None,
                "model": None,
                "prompt": FAITHFUL_PROMPT_1_1,
                "prompt_hash": None,
                "context_hash": None,
                "date": None,
                "forecast_cost_usd": chapter_cost.get("expected_cost_usd"),
                "actual_cost_usd": None,
                "structural_validation": None,
                "artifact_paths": None,
                "artifact_hashes": None,
                "error": None,
                "required_attempt_fields_when_generated": [
                    "attempt_id",
                    "model",
                    "prompt_version",
                    "prompt_hash",
                    "context_sha256",
                    "response_sha256",
                    "actual_cost_usd",
                    "errors",
                ],
            }
        )
    statuses = {row["chapter_id"]: row["status"] for row in chapters}
    if statuses.get(ACCEPTED_CH012_ID) != STATUS_ACCEPTED:
        raise BookBatchPreparation4222Error("CH012 must remain ACCEPTED.")
    if statuses.get(ACCEPTED_CH018_ID) != STATUS_ACCEPTED:
        raise BookBatchPreparation4222Error("CH018 must remain ACCEPTED.")
    if STATUS_AUTHORIZED in statuses.values():
        raise BookBatchPreparation4222Error("No chapter may be marked AUTHORIZED in this phase.")
    if any(row["status"] == STATUS_GENERATED and row.get("attempt") is None for row in chapters):
        raise BookBatchPreparation4222Error("GENERATED requires a verifiable artifact.")
    return {
        "phase": PHASE,
        "manifest_version": PROGRESS_MANIFEST_VERSION,
        "kind": "preparation_manifest",
        "authorized_spend_usd": 0.0,
        "any_authorized_false": True,
        "chapters": chapters,
        "resume_policy": {
            "skip_accepted_chapters": True,
            "skip_generated_chapters_when_no_new_call_required": True,
            "never_automatically_repeat_uncertain_call": True,
            "never_reuse_consumed_authorization": True,
            "preserve_partial_batch_results": True,
            "resume_only_after_remaining_authorization_check": True,
            "identify_attempts_by_unique_id": True,
            "keep_model_and_prompt": True,
            "keep_context_hash": True,
            "keep_response_hash": True,
            "keep_actual_cost": True,
            "keep_errors": True,
            "human_decision_required_if_attempt_uncertain": True,
        },
        "accepted_content_not_duplicated": True,
        "audit_directory": str(phase_audit_dir()).replace("\\", "/"),
        "book_json_published": False,
        "secrets_included": False,
    }


__all__ = ["batch_progress_manifest"]
