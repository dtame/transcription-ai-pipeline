"""Human editorial acceptance record. Not a cryptographic or legal signature."""

from __future__ import annotations

from typing import Any

from app.book_editorial_acceptance_4b219.constants import (
    ACCEPTANCE_RECORD_VERSION,
    ACCEPTANCE_SCOPE,
    ACCEPTED_CHAPTER_VERSION,
    CHAPTER_ID,
    DECISION_SOURCE,
    P000001_STATUS,
    PHASE,
    RECORDING_DATE,
)
from app.book_editorial_acceptance_4b219.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
)


def editorial_acceptance_record(
    *,
    accepted_md_sha256: str,
    accepted_json_sha256: str,
) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "record_version": ACCEPTANCE_RECORD_VERSION,
        "chapter_id": CHAPTER_ID,
        "accepted_artifact_paths": {
            "markdown": str(accepted_chapter_md_path()).replace("\\", "/"),
            "json": str(accepted_chapter_json_path()).replace("\\", "/"),
        },
        "accepted_markdown_sha256": accepted_md_sha256,
        "accepted_json_sha256": accepted_json_sha256,
        "accepted_version": ACCEPTED_CHAPTER_VERSION,
        "recording_date": RECORDING_DATE,
        "decision_source": DECISION_SOURCE,
        "decision_source_detail": (
            "The user reread and explicitly approved the corrected CH012 "
            "chapter at audit/book_authorial_voice_4b218/"
            "chapter_candidate_authorial_v2.md, including reading quality, "
            "the four-section organization, faithful restatement style, "
            "authorial narrative voice, the 4B.2.18 corrections, and the "
            "current P000001 wording without further change."
        ),
        "scope": ACCEPTANCE_SCOPE,
        "narrative_voice": "accepted",
        "p000001": P000001_STATUS,
        "p000001_further_correction_requested": False,
        "semantic_certification": "not_performed",
        "automated_source_coverage_certification": "not_performed",
        "publication_authorization": "not_granted",
        "not_a_digital_signature": True,
        "not_a_legal_or_cryptographic_user_approval": True,
        "not_a_semantic_certificate": True,
        "not_proof_of_exhaustive_source_coverage": True,
        "secrets_included": False,
    }


__all__ = ["editorial_acceptance_record"]
