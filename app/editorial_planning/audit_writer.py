"""Écriture des artefacts d'audit Phase 4A. Jamais editorial_plan.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.editorial_planning.constants import (
    AUDIT_CONTRACT,
    AUDIT_COVERAGE_POLICY,
    AUDIT_FAKEAI,
    AUDIT_INPUT_BUDGET,
    AUDIT_OUTPUT_BUDGET,
    AUDIT_PREFLIGHT,
    AUDIT_READINESS,
    AUDIT_REPORT,
    AUDIT_SCHEMA_IDENTITY,
    AUDIT_VALIDATOR,
    PHASE,
    EDITORIAL_PLAN_SCHEMA_VERSION,
)
from app.editorial_planning.report import render_report
from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def artifact_path(project_name: str, name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / name


def _with_header(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    data.setdefault("schema_version", EDITORIAL_PLAN_SCHEMA_VERSION)
    data.setdefault("phase", PHASE)
    return data


def write_audit_bundle(
    project_name: str,
    bundle: Mapping[str, Any],
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline Phase 4A",
) -> dict[str, Path]:
    written = {
        "input_budget": write_bytes_atomic(
            artifact_path(project_name, AUDIT_INPUT_BUDGET, sortie_dir=sortie_dir),
            _with_header(bundle.get("input_budget")),
        ),
        "output_budget": write_bytes_atomic(
            artifact_path(project_name, AUDIT_OUTPUT_BUDGET, sortie_dir=sortie_dir),
            _with_header(bundle.get("output_budget")),
        ),
        "contract": write_bytes_atomic(
            artifact_path(project_name, AUDIT_CONTRACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("contract")),
        ),
        "schema_identity": write_bytes_atomic(
            artifact_path(project_name, AUDIT_SCHEMA_IDENTITY, sortie_dir=sortie_dir),
            _with_header(bundle.get("schema_identity")),
        ),
        "coverage_policy": write_bytes_atomic(
            artifact_path(project_name, AUDIT_COVERAGE_POLICY, sortie_dir=sortie_dir),
            _with_header(bundle.get("coverage_policy")),
        ),
        "validator": write_bytes_atomic(
            artifact_path(project_name, AUDIT_VALIDATOR, sortie_dir=sortie_dir),
            _with_header(bundle.get("validator_contract")),
        ),
        "fakeai": write_bytes_atomic(
            artifact_path(project_name, AUDIT_FAKEAI, sortie_dir=sortie_dir),
            _with_header(bundle.get("fakeai")),
        ),
        "preflight": write_bytes_atomic(
            artifact_path(project_name, AUDIT_PREFLIGHT, sortie_dir=sortie_dir),
            _with_header(bundle.get("preflight")),
        ),
        "readiness": write_bytes_atomic(
            artifact_path(project_name, AUDIT_READINESS, sortie_dir=sortie_dir),
            _with_header(bundle.get("readiness")),
        ),
        "report": write_bytes_atomic(
            artifact_path(project_name, AUDIT_REPORT, sortie_dir=sortie_dir),
            render_report(bundle, tests=tests),
        ),
    }
    return written
