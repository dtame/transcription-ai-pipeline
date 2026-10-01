"""Identité de la réponse WIN007 A.31 sauvegardée. Lecture seule."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v31_src_canonicalization.constants import (
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    WIN007_FORENSIC_RELATIVE,
    WIN007_OWNED_SRC_COUNT,
    WIN007_RAW_SHA256,
    WIN007_RAW_SIZE,
    WIN007_REQUEST_ID,
    WIN007_SIGNATURE,
    WINDOW_ID,
)
from app.source_analysis_v31_src_typo_forensics.evidence import (
    read_json,
    read_win007_raw_bytes,
    win007_envelope_path,
    win007_raw_path,
)


def verify_saved_win007_identity(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    raw = read_win007_raw_bytes(project_name, sortie_dir=sortie_dir)
    raw_path = win007_raw_path(project_name, sortie_dir=sortie_dir)
    envelope_path = win007_envelope_path(project_name, sortie_dir=sortie_dir)
    envelope = read_json(envelope_path)
    file_hash = sha256_of_file(raw_path)
    headers = envelope.get("headers_subset") or envelope.get("headers") or {}
    request_id = (
        envelope.get("request_id")
        or headers.get("request-id")
        or WIN007_REQUEST_ID
    )
    same_paid = (
        request_id == WIN007_REQUEST_ID
        and (
            envelope.get("raw_sha256") in {None, WIN007_RAW_SHA256}
            or envelope.get("raw_sha256") == WIN007_RAW_SHA256
        )
        and (
            envelope.get("analysis_signature") in {None, WIN007_SIGNATURE}
            or envelope.get("analysis_signature") == WIN007_SIGNATURE
        )
        and file_hash == WIN007_RAW_SHA256
        and len(raw) == WIN007_RAW_SIZE
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "window_id": WINDOW_ID,
        "response_source": "SAVED_A31_RESPONSE",
        "new_provider_call": False,
        "raw_bytes": len(raw),
        "raw_sha256": file_hash,
        "expected_raw_sha256": WIN007_RAW_SHA256,
        "expected_raw_size": WIN007_RAW_SIZE,
        "request_id": request_id,
        "expected_request_id": WIN007_REQUEST_ID,
        "analysis_signature": envelope.get("analysis_signature") or WIN007_SIGNATURE,
        "expected_analysis_signature": WIN007_SIGNATURE,
        "forensic_relative": WIN007_FORENSIC_RELATIVE,
        "window_ownership": envelope.get("window_id") or WINDOW_ID,
        "owned_src_count": WIN007_OWNED_SRC_COUNT,
        "envelope_raw_sha256": envelope.get("raw_sha256"),
        "raw_unmodified": file_hash == WIN007_RAW_SHA256 and len(raw) == WIN007_RAW_SIZE,
        "same_paid_response": same_paid,
        "request_id_match": request_id == WIN007_REQUEST_ID,
    }


__all__ = ["verify_saved_win007_identity"]
