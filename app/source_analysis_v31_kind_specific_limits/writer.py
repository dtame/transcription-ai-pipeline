"""Écriture atomique des artefacts A.30 — nouveaux fichiers seulement."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_kind_specific_limits.constants import (
    PHASE,
    POLICY_ARTIFACT,
    PREFLIGHT_ARTIFACT,
    PROVENANCE_ARTIFACT,
    READY_ARTIFACT,
    REPORT_NAME,
    REVALIDATION_ARTIFACT,
    SCHEMA_ARTIFACT,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_kind_specific_limits.report import render_report


def artifact_path(project_name: str, name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / name


def _with_header(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("phase", PHASE)
    return data


def write_audit_bundle(
    project_name: str,
    bundle: Mapping[str, Any],
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.30",
) -> dict[str, Path]:
    written = {
        "policy": write_bytes_atomic(
            artifact_path(project_name, POLICY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle["policy"]),
        ),
        "schema": write_bytes_atomic(
            artifact_path(project_name, SCHEMA_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle["schema"]),
        ),
        "revalidation": write_bytes_atomic(
            artifact_path(project_name, REVALIDATION_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle["replay_public"]),
        ),
        "provenance": write_bytes_atomic(
            artifact_path(project_name, PROVENANCE_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle["provenance"]),
        ),
        "ready": write_bytes_atomic(
            artifact_path(project_name, READY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle["ready"]),
        ),
        "preflight": write_bytes_atomic(
            artifact_path(project_name, PREFLIGHT_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle["preflight"]),
        ),
        "report": write_bytes_atomic(
            artifact_path(project_name, REPORT_NAME, sortie_dir=sortie_dir),
            render_report(bundle, tests=tests),
        ),
    }
    return written


__all__ = ["artifact_path", "write_audit_bundle"]
