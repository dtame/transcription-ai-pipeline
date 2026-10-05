"""Human editorial acceptance record for CH018. Not a cryptographic signature."""

from __future__ import annotations

from typing import Any

from app.book_batch_preparation_4b222.constants import (
    ACCEPTANCE_RECORD_VERSION,
    ACCEPTANCE_SCOPE,
    ACCEPTED_CH018_ID,
    ACCEPTED_CH018_TITLE,
    DECISION_SOURCE,
    PHASE,
    RECORDING_DATE,
)
from app.book_batch_preparation_4b222.paths import ch018_json_path, ch018_md_path


def editorial_acceptance_record(
    *,
    accepted_md_sha256: str,
    accepted_json_sha256: str,
) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "record_version": ACCEPTANCE_RECORD_VERSION,
        "chapter_id": ACCEPTED_CH018_ID,
        "chapter_title": ACCEPTED_CH018_TITLE,
        "accepted_artifact_paths": {
            "markdown": str(ch018_md_path()).replace("\\", "/"),
            "json": str(ch018_json_path()).replace("\\", "/"),
        },
        "accepted_markdown_sha256": accepted_md_sha256,
        "accepted_json_sha256": accepted_json_sha256,
        "recording_date": RECORDING_DATE,
        "decision_source": DECISION_SOURCE,
        "decision_source_detail": (
            "The user explicitly approved CH018 at "
            "audit/real/book_generation_4b221_ch018/chapter_candidate.md, "
            "including general reading quality, chapter structure, authorial "
            "narrative voice, testimony restatement, the formulations flagged "
            "in the 4B.2.21 report, and the editorial content as a whole."
        ),
        "scope": ACCEPTANCE_SCOPE,
        "narrative_voice": "accepted",
        "testimonies": "accepted",
        "previously_flagged_formulations": "accepted",
        "semantic_certification": "not_performed",
        "automated_source_coverage_certification": "not_performed",
        "publication_authorization": "not_granted",
        "not_a_digital_signature": True,
        "not_a_legal_or_cryptographic_user_approval": True,
        "not_a_semantic_certificate": True,
        "chapter_must_not_be_regenerated": True,
        "chapter_prose_must_not_be_modified": True,
        "secrets_included": False,
    }


__all__ = ["editorial_acceptance_record"]
