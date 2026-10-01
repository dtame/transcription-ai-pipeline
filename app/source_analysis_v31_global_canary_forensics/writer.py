"""Écriture atomique des artefacts A.36 — nouveaux fichiers seulement."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_canary_forensics.constants import (
    COUNTERFACTUAL_ARTIFACT,
    DISPOSITION_ARTIFACT,
    DROP_CONTRACT_ARTIFACT,
    FIXTURE_REVIEW_ARTIFACT,
    FORENSICS_ARTIFACT,
    NEXT_FIXTURE_ARTIFACT,
    NEXT_SCHEMA_ARTIFACT,
    PHASE,
    READINESS_ARTIFACT,
    REDESIGN_ARTIFACT,
    REPETITION_ARTIFACT,
    REPORT_NAME,
    SCHEMA_VERSION,
    TEST_DELTA_ARTIFACT,
)
from app.source_analysis_v31_global_canary_forensics.report import render_report


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
    tests: str = "offline A.36",
) -> dict[str, Path]:
    written = {
        "forensics": write_bytes_atomic(
            artifact_path(project_name, FORENSICS_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("forensics")),
        ),
        "dispositions": write_bytes_atomic(
            artifact_path(project_name, DISPOSITION_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("dispositions")),
        ),
        "drop_contract": write_bytes_atomic(
            artifact_path(project_name, DROP_CONTRACT_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("drop_contract")),
        ),
        "repetition": write_bytes_atomic(
            artifact_path(project_name, REPETITION_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("repetition")),
        ),
        "fixture_review": write_bytes_atomic(
            artifact_path(project_name, FIXTURE_REVIEW_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("fixture_review")),
        ),
        "redesign": write_bytes_atomic(
            artifact_path(project_name, REDESIGN_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("redesign")),
        ),
        "schema": write_bytes_atomic(
            artifact_path(project_name, NEXT_SCHEMA_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("schema")),
        ),
        "next_fixture": write_bytes_atomic(
            artifact_path(project_name, NEXT_FIXTURE_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("next_fixture")),
        ),
        "counterfactual": write_bytes_atomic(
            artifact_path(project_name, COUNTERFACTUAL_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("counterfactual")),
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


__all__ = ["artifact_path", "write_audit_bundle"]
