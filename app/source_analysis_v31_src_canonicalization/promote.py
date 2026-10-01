"""Promotion WIN007 dérivée A.31→A.33. Pas de nouvelle génération. Cache distinct."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_final_three.paths import (
    candidate_cache_dir,
    candidate_window_dir,
)
from app.source_analysis_v31_src_canonicalization.constants import (
    CORRECTION_REASON_CODE,
    EXPECTED_CANONICAL,
    GRANULARITY_POLICY,
    MALFORMED_TOKEN,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    SIGNATURE_DECISION,
    SRC_POLICY_NEW,
    SRC_POLICY_OLD,
    WIN007_PROMOTION_LABEL,
    WIN007_REQUEST_ID,
    WIN007_SIGNATURE,
    WINDOW_ID,
)


def derived_cache_dir(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return (
        candidate_cache_dir(
            project_name, WIN007_SIGNATURE, WINDOW_ID, sortie_dir=sortie_dir
        ).parent
        / SRC_POLICY_NEW
        / WINDOW_ID
    )


def candidate_metadata(
    *,
    promoted: bool,
    semantic_quality: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "window_id": WINDOW_ID,
        "analysis_signature": WIN007_SIGNATURE,
        "candidate_only": True,
        "production_analyzer_must_not_consume": True,
        "transport": "semantic-transport-v3.1-local-lite",
        "prompt": "window-analysis-1.4.0",
        "granularity": GRANULARITY_POLICY,
        "thinking_mode": "disabled",
        "architecture": "GLOBALIZE_IDEA_SUBTYPE",
        "technical_ok": promoted,
        "semantic_quality": semantic_quality,
        "src_reference_policy_version": SRC_POLICY_NEW,
        "historical_src_reference_policy_version": SRC_POLICY_OLD,
        "derived_representation": True,
        "raw_provider_evidence_mutated": False,
        "provenance": {
            "provider_generation_phase": "A.31",
            "provider_request_id": WIN007_REQUEST_ID,
            "provider_call_during_a33": False,
            "strict_raw_status": "FAIL",
            "derived_canonical_status": "PASS" if promoted else "FAIL",
            "canonicalization_policy": SRC_POLICY_NEW,
            "canonicalizations": 1 if promoted else 0,
            "raw_token": MALFORMED_TOKEN,
            "canonical_token": EXPECTED_CANONICAL,
            "correction_reason": CORRECTION_REASON_CODE,
            "revalidation_phase": "A.33",
            "label": WIN007_PROMOTION_LABEL,
            "signature_decision": SIGNATURE_DECISION,
        },
    }


def persist_win007_derived_candidate(
    project_name: str,
    transport: Mapping[str, Any],
    *,
    semantic_quality: str | None,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    isolated = candidate_window_dir(project_name, WINDOW_ID, sortie_dir=sortie_dir)
    cache = derived_cache_dir(project_name, sortie_dir=sortie_dir)
    historical_cache = candidate_cache_dir(
        project_name, WIN007_SIGNATURE, WINDOW_ID, sortie_dir=sortie_dir
    )
    metadata = candidate_metadata(promoted=True, semantic_quality=semantic_quality)
    written: dict[str, str] = {}
    for root, label in ((isolated, "isolated"), (cache, "derived_cache")):
        write_bytes_atomic(root / "transport.json", dict(transport))
        write_bytes_atomic(root / "metadata.json", metadata)
        written[label] = str(root)
    written["historical_strict_cache_untouched"] = str(historical_cache)
    written["historical_strict_cache_existed"] = str(historical_cache.is_dir())
    return written


def build_provenance(
    *,
    promoted: bool,
    stored: Mapping[str, str],
    semantic_quality: str | None,
    derived_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    audit = dict(derived_audit or {})
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "window_id": WINDOW_ID,
        "analysis_signature": WIN007_SIGNATURE,
        "promoted": promoted,
        "label": WIN007_PROMOTION_LABEL if promoted else None,
        "provider_generation_phase": "A.31",
        "provider_request_id": WIN007_REQUEST_ID,
        "provider_call_during_a33": False,
        "strict_raw_status": "FAIL",
        "derived_canonical_status": "PASS" if promoted else "FAIL",
        "canonicalization_policy": SRC_POLICY_NEW,
        "historical_strict_policy": SRC_POLICY_OLD,
        "canonicalizations": audit.get("canonicalized_src_count"),
        "raw_token": MALFORMED_TOKEN,
        "canonical_token": EXPECTED_CANONICAL,
        "correction_reason": CORRECTION_REASON_CODE,
        "revalidation_phase": "A.33",
        "signature_decision": SIGNATURE_DECISION,
        "a31_historical_status": "FAIL",
        "semantic_quality": semantic_quality,
        "candidate_storage": dict(stored),
        "project_name": PROJECT_NAME,
        "raw_malformed_src_count": audit.get("raw_malformed_src_count"),
        "canonicalized_src_count": audit.get("canonicalized_src_count"),
        "rejected_malformed_src_count": audit.get("rejected_malformed_src_count"),
    }


__all__ = [
    "build_provenance",
    "candidate_metadata",
    "derived_cache_dir",
    "persist_win007_derived_candidate",
]
