"""Promotion WIN003 avec provenance A.28→A.30. Pas de nouvelle génération."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_kind_specific_limits.constants import (
    CURRENT_GRANULARITY_POLICY,
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    SELECTED_POLICY,
    SIGNATURE_DECISION,
    WIN003_PROMOTION_LABEL,
    WIN003_SIGNATURE,
    WINDOW_ID,
)
from app.source_analysis_v31_remaining_windows.paths import (
    candidate_cache_dir,
    candidate_window_dir,
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
        "analysis_signature": WIN003_SIGNATURE,
        "candidate_only": True,
        "production_analyzer_must_not_consume": True,
        "transport": "semantic-transport-v3.1-local-lite",
        "prompt": "window-analysis-1.4.0",
        "thinking_mode": "disabled",
        "architecture": "GLOBALIZE_IDEA_SUBTYPE",
        "technical_ok": promoted,
        "semantic_quality": semantic_quality,
        "provenance": {
            "original_provider_phase": "A.28",
            "revalidation_phase": "A.30",
            "provider_call_during_a30": False,
            "new_provider_generation": False,
            "policy": SELECTED_POLICY,
            "granularity_policy_version": CURRENT_GRANULARITY_POLICY,
            "label": WIN003_PROMOTION_LABEL,
            "signature_decision": SIGNATURE_DECISION,
        },
    }


def persist_win003_candidate(
    project_name: str,
    transport: Mapping[str, Any],
    *,
    semantic_quality: str | None,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    isolated = candidate_window_dir(project_name, WINDOW_ID, sortie_dir=sortie_dir)
    cache = candidate_cache_dir(
        project_name, WIN003_SIGNATURE, WINDOW_ID, sortie_dir=sortie_dir
    )
    metadata = candidate_metadata(promoted=True, semantic_quality=semantic_quality)
    written: dict[str, str] = {}
    for root, label in ((isolated, "isolated"), (cache, "cache")):
        write_bytes_atomic(root / "transport.json", dict(transport))
        write_bytes_atomic(root / "metadata.json", metadata)
        written[label] = str(root)
    return written


def build_provenance(
    *,
    promoted: bool,
    stored: Mapping[str, str],
    semantic_quality: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "window_id": WINDOW_ID,
        "analysis_signature": WIN003_SIGNATURE,
        "promoted": promoted,
        "label": WIN003_PROMOTION_LABEL if promoted else None,
        "original_provider_phase": "A.28",
        "revalidation_phase": "A.30",
        "provider_call_during_a30": False,
        "new_provider_generation": False,
        "policy": SELECTED_POLICY,
        "granularity_policy_version": CURRENT_GRANULARITY_POLICY,
        "signature_decision": SIGNATURE_DECISION,
        "a28_historical_status": "FAIL",
        "semantic_quality": semantic_quality,
        "candidate_storage": dict(stored),
        "project_name": PROJECT_NAME,
    }


__all__ = [
    "build_provenance",
    "candidate_metadata",
    "persist_win003_candidate",
]
