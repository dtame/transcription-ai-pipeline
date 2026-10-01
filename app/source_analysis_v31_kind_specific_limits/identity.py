"""Identité de la réponse WIN003 A.28 sauvegardée. Lecture seule."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v31_kind_specific_limits.constants import (
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    WIN003_FORENSIC_RELATIVE,
    WIN003_OWNED_SRC_COUNT,
    WIN003_RAW_SHA256,
    WIN003_RAW_SIZE,
    WIN003_REQUEST_ID,
    WIN003_SIGNATURE,
    WIN003_SRC_RANGE,
    WIN003_WORD_COUNT,
    WINDOW_ID,
)
from app.source_analysis_v31_length_ceiling.evidence import (
    read_json,
    read_win003_raw_bytes,
    win003_envelope_path,
    win003_raw_path,
)


def verify_saved_win003_identity(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    raw = read_win003_raw_bytes(project_name, sortie_dir=sortie_dir)
    raw_path = win003_raw_path(project_name, sortie_dir=sortie_dir)
    envelope_path = win003_envelope_path(project_name, sortie_dir=sortie_dir)
    envelope = read_json(envelope_path)
    file_hash = sha256_of_file(raw_path)
    same_paid = (
        envelope.get("request_id") == WIN003_REQUEST_ID
        and envelope.get("raw_sha256") == WIN003_RAW_SHA256
        and envelope.get("analysis_signature") == WIN003_SIGNATURE
        and envelope.get("window_id") == WINDOW_ID
        and file_hash == WIN003_RAW_SHA256
        and len(raw) == WIN003_RAW_SIZE
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "window_id": WINDOW_ID,
        "response_source": "SAVED_A28_RESPONSE",
        "new_provider_call": False,
        "raw_bytes": len(raw),
        "raw_sha256": file_hash,
        "expected_raw_sha256": WIN003_RAW_SHA256,
        "expected_raw_size": WIN003_RAW_SIZE,
        "request_id": envelope.get("request_id"),
        "expected_request_id": WIN003_REQUEST_ID,
        "analysis_signature": envelope.get("analysis_signature"),
        "expected_analysis_signature": WIN003_SIGNATURE,
        "forensic_relative": WIN003_FORENSIC_RELATIVE,
        "window_ownership": envelope.get("window_id"),
        "src_range": WIN003_SRC_RANGE,
        "owned_src_count": WIN003_OWNED_SRC_COUNT,
        "word_count": WIN003_WORD_COUNT,
        "envelope_raw_sha256": envelope.get("raw_sha256"),
        "raw_unmodified": file_hash == WIN003_RAW_SHA256 and len(raw) == WIN003_RAW_SIZE,
        "same_paid_response": same_paid,
    }


__all__ = ["verify_saved_win003_identity"]
