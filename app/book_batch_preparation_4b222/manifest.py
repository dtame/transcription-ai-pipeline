"""Immutable-by-hash CH018 accepted-chapter manifest. Does not copy the chapter."""

from __future__ import annotations

from typing import Any

from app.book_batch_preparation_4b222.constants import (
    ACCEPTANCE_SCOPE,
    ACCEPTED_CH018_ID,
    ACCEPTED_CH018_TITLE,
    DECISION_SOURCE,
    EDITORIAL_POLICY,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    EXPECTED_TRANSCRIPT,
    MANIFEST_VERSION,
    NARRATIVE_VOICE_CONTRACT,
    PHASE,
    RECORDING_DATE,
)
from app.book_batch_preparation_4b222.paths import (
    ch018_json_path,
    ch018_lock_path,
    ch018_md_path,
    production_map_path,
    production_plan_path,
    production_transcript_path,
)


def accepted_editorial_manifest(
    *,
    accepted_md_sha256: str,
    accepted_json_sha256: str,
    lock_sha256: str,
    freeze_allowed: bool,
) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "manifest_version": MANIFEST_VERSION,
        "chapter_id": ACCEPTED_CH018_ID,
        "chapter_title": ACCEPTED_CH018_TITLE,
        "immutable_by_hash": True,
        "historical_files_copied": False,
        "historical_files_moved": False,
        "historical_files_overwritten": False,
        "freeze_allowed": freeze_allowed,
        "freeze_status": "FROZEN" if freeze_allowed else "BLOCKED",
        "accepted_artifacts": {
            "markdown_path": str(ch018_md_path()).replace("\\", "/"),
            "markdown_sha256": accepted_md_sha256,
            "json_path": str(ch018_json_path()).replace("\\", "/"),
            "json_sha256": accepted_json_sha256,
            "provider_lock_path": str(ch018_lock_path()).replace("\\", "/"),
            "provider_lock_sha256": lock_sha256,
        },
        "canonical_dependencies": {
            "source_map_path": str(production_map_path()).replace("\\", "/"),
            "source_map_sha256": EXPECTED_SOURCE_MAP,
            "editorial_plan_path": str(production_plan_path()).replace("\\", "/"),
            "editorial_plan_sha256": EXPECTED_EDITORIAL_PLAN,
            "clean_transcript_path": str(production_transcript_path()).replace("\\", "/"),
            "clean_transcript_sha256": EXPECTED_TRANSCRIPT,
        },
        "applicable_editorial_policy": EDITORIAL_POLICY,
        "applicable_narrative_voice_contract": NARRATIVE_VOICE_CONTRACT,
        "human_acceptance": {
            "status": "accepted" if freeze_allowed else "blocked",
            "scope": ACCEPTANCE_SCOPE,
            "decision_source": DECISION_SOURCE,
            "recording_date": RECORDING_DATE,
            "narrative_voice": "accepted",
            "testimonies": "accepted",
            "previously_flagged_formulations": "accepted",
            "not_a_digital_signature": True,
            "not_a_legal_or_cryptographic_user_approval": True,
        },
        "future_controls_must_reference_this_manifest": True,
        "semantic_certification": "not_performed",
        "publication_authorization": "not_granted",
        "accepted_chapter_must_not_be_altered": True,
        "content_must_not_be_duplicated": True,
        "secrets_included": False,
    }


__all__ = ["accepted_editorial_manifest"]
