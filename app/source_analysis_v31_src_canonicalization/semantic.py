"""Réutilise la revue sémantique A.32 du même raw WIN007. Pas de second LLM."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v31_src_canonicalization.constants import (
    A32_SEMANTIC_ARTIFACT,
    EXPECTED_CANONICAL,
    MALFORMED_TOKEN,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    WIN007_RAW_SHA256,
    WIN007_REQUEST_ID,
    WIN007_SIGNATURE,
)
from app.source_analysis_v31_src_typo_forensics.evidence import read_json


def load_a32_semantic_evidence(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    path = audit_dir(project_name, sortie_dir=sortie_dir) / A32_SEMANTIC_ARTIFACT
    payload = read_json(path) if path.is_file() else {}
    coverage = payload.get("coverage") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "source_artifact": A32_SEMANTIC_ARTIFACT,
        "present": path.is_file(),
        "a32_phase": payload.get("phase"),
        "semantic_quality": payload.get("semantic_quality"),
        "unsupported_content": payload.get("unsupported_content"),
        "unsupported_count": payload.get("unsupported_count"),
        "material_omissions": payload.get("material_omissions"),
        "relation_quality_summary": payload.get("relation_quality_summary"),
        "transport_valid": payload.get("transport_valid"),
        "beginning": coverage.get("beginning"),
        "middle": coverage.get("middle"),
        "end": coverage.get("end"),
        "second_llm": payload.get("second_llm"),
        "payload": payload,
    }


def confirm_semantic_identity(
    identity: Mapping[str, Any],
    a32: Mapping[str, Any],
    live_review: Mapping[str, Any] | None,
    *,
    raw_token: str | None,
    canonical_token: str | None,
) -> dict[str, Any]:
    same_response = bool(identity.get("same_paid_response"))
    a32_ok = a32.get("semantic_quality") == "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
    live_quality = None
    live_ok = None
    live_unsupported = None
    live_omissions = None
    if isinstance(live_review, Mapping):
        live_quality = live_review.get("semantic_quality")
        live_ok = live_quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
        live_unsupported = live_review.get("unsupported_count")
        if live_unsupported is None:
            live_unsupported = live_review.get("unsupported_content")
        live_omissions = live_review.get("material_omissions")
    mapping_ok = raw_token == MALFORMED_TOKEN and canonical_token == EXPECTED_CANONICAL
    reusable = same_response and a32_ok and mapping_ok and a32.get("present") is True
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "same_saved_win007_response": same_response,
        "request_id": WIN007_REQUEST_ID,
        "raw_sha256": WIN007_RAW_SHA256,
        "analysis_signature": WIN007_SIGNATURE,
        "refers_to_exact_saved_response": same_response,
        "refers_to_exact_single_derived_correction": mapping_ok,
        "raw_token": raw_token,
        "canonical_token": canonical_token,
        "a32_semantic_quality": a32.get("semantic_quality"),
        "a32_unsupported_count": a32.get("unsupported_count")
        if a32.get("unsupported_count") is not None
        else a32.get("unsupported_content"),
        "a32_material_omissions": a32.get("material_omissions"),
        "a32_beginning": a32.get("beginning"),
        "a32_middle": a32.get("middle"),
        "a32_end": a32.get("end"),
        "a32_relations": a32.get("relation_quality_summary"),
        "live_semantic_quality": live_quality,
        "live_unsupported": live_unsupported,
        "live_omissions": live_omissions,
        "live_matches_a32": live_ok is True and a32_ok,
        "reusable_as_semantic_evidence": reusable,
        "second_llm": False,
        "accepted_standard": "ACCEPTABLE_FOR_LOCAL_EXTRACTION",
    }


__all__ = ["confirm_semantic_identity", "load_a32_semantic_evidence"]
