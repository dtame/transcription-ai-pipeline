"""Écriture atomique des artefacts A.43 — nouveaux fichiers seulement."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_reuse_output.constants import (
    BREAKDOWN_ARTIFACT,
    BUDGET_ARTIFACT,
    CONTRACT_ARTIFACT,
    COST_ARTIFACT,
    OPTIONS_ARTIFACT,
    PHASE,
    QUALITY_ARTIFACT,
    READINESS_ARTIFACT,
    REPORT_NAME,
    REUSE_ANALYSIS_ARTIFACT,
    SCHEMA_ARTIFACT,
    SCHEMA_VERSION,
    SELECTED_ARTIFACT,
    STRESS_ARTIFACT,
    TEST_DELTA_ARTIFACT,
)
from app.source_analysis_v31_global_reuse_output.paths import artifact_path
from app.source_analysis_v31_global_reuse_output.report import render_report


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
    tests: str = "offline A.43",
) -> dict[str, Path]:
    written = {
        "reuse_analysis": write_bytes_atomic(
            artifact_path(project_name, REUSE_ANALYSIS_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("reuse_analysis")),
        ),
        "quality": write_bytes_atomic(
            artifact_path(project_name, QUALITY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("quality")),
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
        "contract": write_bytes_atomic(
            artifact_path(project_name, CONTRACT_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(
                {
                    "prompt": bundle.get("prompt"),
                    "schema": {
                        key: value
                        for key, value in (bundle.get("schema") or {}).items()
                        if key not in {"schema", "adapted_schema"}
                    },
                    "next_fixture": bundle.get("next_fixture"),
                    "selected": bundle.get("selected"),
                }
            ),
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
            artifact_path(project_name, SCHEMA_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("schema")),
        ),
        "cost": write_bytes_atomic(
            artifact_path(project_name, COST_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("cost")),
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
