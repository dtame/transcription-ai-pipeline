"""Réutilise la revue sémantique A.29 du même raw WIN003. Pas de second LLM."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v31_kind_specific_limits.constants import (
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    WIN003_RAW_SHA256,
    WIN003_REQUEST_ID,
    WIN003_SIGNATURE,
)
from app.source_analysis_v31_length_ceiling.constants import (
    COUNTERFACTUAL_ARTIFACT,
)
from app.source_analysis_v31_length_ceiling.evidence import read_json


def load_a29_semantic_evidence(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    path = audit_dir(project_name, sortie_dir=sortie_dir) / COUNTERFACTUAL_ARTIFACT
    payload = read_json(path)
    summary = payload.get("semantic_review_summary") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "source_artifact": COUNTERFACTUAL_ARTIFACT,
        "a29_phase": payload.get("phase"),
        "summary": summary,
        "semantic_quality": summary.get("semantic_quality"),
        "unsupported_count": summary.get("unsupported_count"),
        "material_omissions": summary.get("material_omissions"),
        "relation_quality_summary": summary.get("relation_quality_summary"),
        "transport_valid": summary.get("transport_valid"),
        "performed": summary.get("performed"),
    }


def confirm_semantic_identity(
    identity: Mapping[str, Any],
    a29: Mapping[str, Any],
    live_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    same_response = bool(identity.get("same_paid_response"))
    a29_ok = a29.get("semantic_quality") == "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
    live_quality = None
    live_ok = None
    if isinstance(live_review, Mapping):
        live_quality = live_review.get("semantic_quality")
        live_ok = live_quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
    reusable = same_response and a29_ok
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "same_saved_win003_response": same_response,
        "request_id": WIN003_REQUEST_ID,
        "raw_sha256": WIN003_RAW_SHA256,
        "analysis_signature": WIN003_SIGNATURE,
        "a29_semantic_quality": a29.get("semantic_quality"),
        "a29_unsupported_count": a29.get("unsupported_count"),
        "a29_material_omissions": a29.get("material_omissions"),
        "a29_relations": a29.get("relation_quality_summary"),
        "live_semantic_quality": live_quality,
        "live_matches_a29": live_ok is True and a29_ok,
        "reusable_as_semantic_evidence": reusable,
        "second_llm": False,
        "accepted_standard": "ACCEPTABLE_FOR_LOCAL_EXTRACTION",
    }


__all__ = ["confirm_semantic_identity", "load_a29_semantic_evidence"]
