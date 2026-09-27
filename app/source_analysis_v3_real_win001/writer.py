"""Écriture atomique des artefacts A.19 — isolés, jamais production."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v3_real_win001.constants import (
    COMPARISON_ARTIFACT,
    EXECUTION_ARTIFACT,
    HANDLE_ARTIFACT,
    PHASE,
    PREFLIGHT_ARTIFACT,
    REPORT_NAME,
    REVIEW_ARTIFACT,
    SCHEMA_VERSION,
    WINDOW_ID,
)
from app.source_analysis_v3_real_win001.paths import candidate_cache_dir, candidate_window_dir
from app.source_analysis_v3_real_win001.report import render_report
from app.source_analysis_v3_real_win001.runner import RealV3Win001Result


def artifact_path(project_name: str, name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / name


def write_preflight_artifact(
    project_name: str,
    preflight: Mapping[str, Any],
    *,
    sortie_dir: Path | None = None,
) -> Path:
    payload = dict(preflight)
    payload.pop("request", None)
    payload.pop("window_obj", None)
    payload.pop("transcript_obj", None)
    payload["schema_version"] = SCHEMA_VERSION
    payload["phase"] = PHASE
    payload["secrets_included"] = False
    return write_bytes_atomic(
        artifact_path(project_name, PREFLIGHT_ARTIFACT, sortie_dir=sortie_dir),
        payload,
    )


def _persist_candidate(
    project_name: str,
    result: RealV3Win001Result,
    transport: Mapping[str, Any] | None,
    *,
    sortie_dir: Path | None,
) -> dict[str, str]:
    if not isinstance(transport, Mapping):
        return {}
    execution = result.execution or {}
    technical = bool(execution.get("technical_ok"))
    quality = (result.review or {}).get("semantic_quality")
    if not technical or quality != "ACCEPTABLE_FOR_LOCAL_EXTRACTION":
        return {}
    if execution.get("v3_validator") != "PASS":
        return {}
    signature = execution.get("analysis_signature") or (
        result.preflight or {}
    ).get("analysis_signature")
    if not signature:
        return {}
    isolated = candidate_window_dir(project_name, sortie_dir=sortie_dir)
    cache = candidate_cache_dir(project_name, str(signature), sortie_dir=sortie_dir)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "window_id": WINDOW_ID,
        "analysis_signature": signature,
        "candidate_only": True,
        "production_analyzer_must_not_consume": True,
        "transport": "semantic-transport-v3",
        "prompt": "window-analysis-1.3",
        "thinking_mode": "disabled",
        "architecture": "LOCAL_SYMBOLIC_HANDLES",
        "technical_ok": technical,
        "semantic_quality": quality,
    }
    written: dict[str, str] = {}
    for root, label in ((isolated, "isolated"), (cache, "cache")):
        write_bytes_atomic(root / "transport.json", dict(transport))
        write_bytes_atomic(root / "metadata.json", metadata)
        written[label] = str(root)
    return written


def write_execution_artifacts(
    project_name: str,
    result: RealV3Win001Result,
    *,
    transport: Mapping[str, Any] | None = None,
    sortie_dir: Path | None = None,
    tests: str | None = None,
) -> dict[str, Path]:
    stored = _persist_candidate(
        project_name, result, transport, sortie_dir=sortie_dir
    )
    execution = dict(result.execution)
    execution["candidate_storage"] = stored
    written = {
        "execution": write_bytes_atomic(
            artifact_path(project_name, EXECUTION_ARTIFACT, sortie_dir=sortie_dir),
            {
                "schema_version": SCHEMA_VERSION,
                "phase": PHASE,
                "mode": result.mode,
                "authorization_scope": result.authorization_scope,
                "engine_generate_attempts": result.engine_generate_attempts,
                "anthropic_post_attempts": result.anthropic_post_attempts,
                "error": result.error,
                "execution": execution,
            },
        )
    }
    if result.handles:
        written["handles"] = write_bytes_atomic(
            artifact_path(project_name, HANDLE_ARTIFACT, sortie_dir=sortie_dir),
            result.handles,
        )
    if result.review.get("performed"):
        written["review"] = write_bytes_atomic(
            artifact_path(project_name, REVIEW_ARTIFACT, sortie_dir=sortie_dir),
            result.review,
        )
    if result.comparison:
        written["comparison"] = write_bytes_atomic(
            artifact_path(project_name, COMPARISON_ARTIFACT, sortie_dir=sortie_dir),
            result.comparison,
        )
    written["report"] = write_bytes_atomic(
        artifact_path(project_name, REPORT_NAME, sortie_dir=sortie_dir),
        render_report(result, tests=tests),
    )
    return written


__all__ = [
    "artifact_path",
    "write_execution_artifacts",
    "write_preflight_artifact",
]
