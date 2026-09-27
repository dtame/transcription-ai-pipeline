"""Runner offline 3B.7.7A.1 — artefacts déterministes, 0 appel provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_win001_failure_diagnosis.constants import (
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_VERSION,
)
from app.source_analysis_win001_failure_diagnosis.diagnosis import build_diagnosis
from app.source_analysis_win001_failure_diagnosis.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_win001_failure_diagnosis.report import render_report
from app.source_analysis_win001_failure_diagnosis.writer import (
    failure_path,
    observability_path,
    report_path,
    token_path,
    write_bytes_atomic,
)


def write_diagnosis_artifacts(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    diagnosis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    payload = diagnosis or build_diagnosis(project_name, sortie_dir=sortie_dir)
    failure = dict(payload["failure"])
    token = dict(payload["token"])
    observability = dict(payload["observability"])
    paths = {
        "failure": write_bytes_atomic(
            failure_path(project_name, sortie_dir=sortie_dir), failure
        ),
        "token": write_bytes_atomic(
            token_path(project_name, sortie_dir=sortie_dir), token
        ),
        "observability": write_bytes_atomic(
            observability_path(project_name, sortie_dir=sortie_dir), observability
        ),
        "report": write_bytes_atomic(
            report_path(project_name, sortie_dir=sortie_dir),
            render_report(payload),
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "paths": {key: str(path) for key, path in paths.items()},
        "sha256": {key: sha256_of_file(path) for key, path in paths.items()},
        "content_hash": payload.get("content_hash"),
    }


def write_twice_and_verify(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    first = write_diagnosis_artifacts(project_name, sortie_dir=sortie_dir)
    second = write_diagnosis_artifacts(project_name, sortie_dir=sortie_dir)
    if first["sha256"] != second["sha256"]:
        raise RuntimeError(
            f"artefacts non déterministes : {first['sha256']} ≠ {second['sha256']}"
        )
    return first


def run_win001_failure_diagnosis(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    return write_twice_and_verify(project_name, sortie_dir=sortie_dir)
