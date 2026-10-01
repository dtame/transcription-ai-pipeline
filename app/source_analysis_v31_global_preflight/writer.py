"""Écriture atomique des artefacts A.34 — nouveaux fichiers seulement."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_preflight.constants import (
    BOUNDARY_ARTIFACT,
    BUDGET_ARTIFACT,
    CONTRACT_ARTIFACT,
    DUPLICATE_ARTIFACT,
    FREEZE_ARTIFACT,
    INVENTORY_ARTIFACT,
    NORMALIZED_ARTIFACT,
    PHASE,
    READINESS_ARTIFACT,
    RELATION_POLICY_ARTIFACT,
    REPORT_NAME,
    REVIEW_PLAN_ARTIFACT,
    SCHEMA_VERSION,
    TEST_DELTA_ARTIFACT,
    TRANSPORT_SCHEMA_ARTIFACT,
    VALIDATOR_ARTIFACT,
)
from app.source_analysis_v31_global_preflight.report import render_report


def artifact_path(project_name: str, name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / name


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
    tests: str = "offline A.34",
) -> dict[str, Path]:
    schema_public = dict(bundle.get("schema") or {})
    written = {
        "normalized": write_bytes_atomic(
            artifact_path(project_name, NORMALIZED_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("normalized")),
        ),
        "inventory": write_bytes_atomic(
            artifact_path(project_name, INVENTORY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("inventory")),
        ),
        "boundary": write_bytes_atomic(
            artifact_path(project_name, BOUNDARY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("boundary")),
        ),
        "duplicates": write_bytes_atomic(
            artifact_path(project_name, DUPLICATE_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("duplicates")),
        ),
        "relation_policy": write_bytes_atomic(
            artifact_path(project_name, RELATION_POLICY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("relation_policy")),
        ),
        "contract": write_bytes_atomic(
            artifact_path(project_name, CONTRACT_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("contract")),
        ),
        "schema": write_bytes_atomic(
            artifact_path(project_name, TRANSPORT_SCHEMA_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(schema_public),
        ),
        "budget": write_bytes_atomic(
            artifact_path(project_name, BUDGET_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("budget")),
        ),
        "validator": write_bytes_atomic(
            artifact_path(project_name, VALIDATOR_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("validator")),
        ),
        "review": write_bytes_atomic(
            artifact_path(project_name, REVIEW_PLAN_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("review")),
        ),
        "freeze": write_bytes_atomic(
            artifact_path(project_name, FREEZE_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("freeze")),
        ),
        "readiness": write_bytes_atomic(
            artifact_path(project_name, READINESS_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("readiness")),
        ),
        "test_delta": write_bytes_atomic(
            artifact_path(project_name, TEST_DELTA_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("test_delta")),
        ),
        "report": write_bytes_atomic(
            artifact_path(project_name, REPORT_NAME, sortie_dir=sortie_dir),
            render_report(bundle, tests=tests),
        ),
    }
    return written


__all__ = ["artifact_path", "write_audit_bundle"]
