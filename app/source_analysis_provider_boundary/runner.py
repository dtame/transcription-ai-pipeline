"""Runner offline 3B.7.7A.5 — artefacts déterministes, 0 appel provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_provider_boundary.constants import (
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_VERSION,
)
from app.source_analysis_provider_boundary.facts import build_all
from app.source_analysis_provider_boundary.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_provider_boundary.report import render_report
from app.source_analysis_provider_boundary.writer import (
    architecture_path,
    diagnosis_path,
    matrix_path,
    report_path,
    two_call_path,
    write_bytes_atomic,
)


def write_boundary_artifacts(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    payload = bundle or build_all(project_name, sortie_dir=sortie_dir)
    paths = {
        "diagnosis": write_bytes_atomic(
            diagnosis_path(project_name, sortie_dir=sortie_dir),
            payload["diagnosis"],
        ),
        "matrix": write_bytes_atomic(
            matrix_path(project_name, sortie_dir=sortie_dir),
            payload["matrix"],
        ),
        "architecture": write_bytes_atomic(
            architecture_path(project_name, sortie_dir=sortie_dir),
            payload["architecture"],
        ),
        "two_call": write_bytes_atomic(
            two_call_path(project_name, sortie_dir=sortie_dir),
            payload["two_call"],
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
    }


def write_twice_and_verify(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    first = write_boundary_artifacts(project_name, sortie_dir=sortie_dir)
    second = write_boundary_artifacts(project_name, sortie_dir=sortie_dir)
    if first["sha256"] != second["sha256"]:
        raise RuntimeError(
            f"artefacts non déterministes : {first['sha256']} ≠ {second['sha256']}"
        )
    return first


def run_provider_boundary_review(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    return write_twice_and_verify(project_name, sortie_dir=sortie_dir)
