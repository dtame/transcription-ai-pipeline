"""Écriture atomique des artefacts A.41 — nouveaux fichiers seulement."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_drop_domain.constants import (
    BUDGET_ARTIFACT,
    COUNTERFACTUAL_ARTIFACT,
    ESTIMATOR_ARTIFACT,
    FORENSICS_ARTIFACT,
    HANG_ARTIFACT,
    HARDENING_ARTIFACT,
    NEXT_FIXTURE_ARTIFACT,
    PHASE,
    POLICY_ARTIFACT,
    READINESS_ARTIFACT,
    REPORT_NAME,
    SCHEMA_VERSION,
    TEST_DELTA_ARTIFACT,
)
from app.source_analysis_v31_global_drop_domain.paths import artifact_path
from app.source_analysis_v31_global_drop_domain.report import render_report


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
    tests: str = "offline A.41",
) -> dict[str, Path]:
    written = {
        "forensics": write_bytes_atomic(
            artifact_path(project_name, FORENSICS_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("forensics")),
        ),
        "counterfactual": write_bytes_atomic(
            artifact_path(project_name, COUNTERFACTUAL_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("counterfactual")),
        ),
        "policy": write_bytes_atomic(
            artifact_path(project_name, POLICY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("policy")),
        ),
        "hardening": write_bytes_atomic(
            artifact_path(project_name, HARDENING_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("hardening")),
        ),
        "estimator": write_bytes_atomic(
            artifact_path(project_name, ESTIMATOR_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("estimator")),
        ),
        "budget": write_bytes_atomic(
            artifact_path(project_name, BUDGET_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("budget")),
        ),
        "hang": write_bytes_atomic(
            artifact_path(project_name, HANG_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("hang")),
        ),
        "next_fixture": write_bytes_atomic(
            artifact_path(project_name, NEXT_FIXTURE_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("next_fixture")),
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
