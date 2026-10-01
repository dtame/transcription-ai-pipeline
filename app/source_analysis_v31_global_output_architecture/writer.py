"""Écriture atomique des artefacts A.39 — nouveaux fichiers seulement."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_output_architecture.constants import (
    BREAKDOWN_ARTIFACT,
    BUDGET_ARTIFACT,
    FORENSICS_ARTIFACT,
    MEMBERSHIP_ARTIFACT,
    NEXT_SCHEMA_ARTIFACT,
    OPTIONS_ARTIFACT,
    PHASE,
    READINESS_ARTIFACT,
    RELATION_DECISION_ARTIFACT,
    REPORT_NAME,
    SCHEMA_VERSION,
    SELECTED_ARTIFACT,
    STRESS_ARTIFACT,
    TEST_DELTA_ARTIFACT,
)
from app.source_analysis_v31_global_output_architecture.paths import artifact_path
from app.source_analysis_v31_global_output_architecture.report import render_report


def _with_header(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("phase", PHASE)
    return data


def write_audit_bundle(
    project_name: str,
    bundle: Mapping[str, Any],
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.39",
) -> dict[str, Path]:
    written = {
        "forensics": write_bytes_atomic(
            artifact_path(project_name, FORENSICS_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("forensics")),
        ),
        "breakdown": write_bytes_atomic(
            artifact_path(project_name, BREAKDOWN_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("breakdown")),
        ),
        "options": write_bytes_atomic(
            artifact_path(project_name, OPTIONS_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("options")),
        ),
        "selected": write_bytes_atomic(
            artifact_path(project_name, SELECTED_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("selected")),
        ),
        "membership": write_bytes_atomic(
            artifact_path(project_name, MEMBERSHIP_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("membership")),
        ),
        "relation": write_bytes_atomic(
            artifact_path(project_name, RELATION_DECISION_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("relation")),
        ),
        "budget": write_bytes_atomic(
            artifact_path(project_name, BUDGET_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("budget")),
        ),
        "stress": write_bytes_atomic(
            artifact_path(project_name, STRESS_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("stress")),
        ),
        "schema": write_bytes_atomic(
            artifact_path(project_name, NEXT_SCHEMA_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("schema")),
        ),
        "readiness": write_bytes_atomic(
            artifact_path(project_name, READINESS_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("readiness")),
        ),
        "report": write_bytes_atomic(
            artifact_path(project_name, REPORT_NAME, sortie_dir=sortie_dir),
            render_report(bundle, tests=tests),
        ),
    }
    if bundle.get("test_delta"):
        written["test_delta"] = write_bytes_atomic(
            artifact_path(project_name, TEST_DELTA_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("test_delta")),
        )
    return written


__all__ = ["write_audit_bundle"]
