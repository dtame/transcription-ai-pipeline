"""Écriture atomique des artefacts 3B.7.6 — audit seulement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.consolidation_writer import production_consolidation_exist
from app.source_analysis.window_writer import production_windows_exist
from app.source_analysis.writer import source_map_path
from app.source_analysis_global_clean.writer import production_source_map_path
from app.source_analysis_hybrid_readiness.constants import (
    DRY_RUN_ARTIFACT_NAME,
    FAILURE_MATRIX_ARTIFACT_NAME,
    PHASE,
    READINESS_ARTIFACT_NAME,
    REAL_CALL_PLAN_ARTIFACT_NAME,
    REPORT_NAME,
    SCHEMA_VERSION,
)


def readiness_artifact_path(
    project_name: str, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / READINESS_ARTIFACT_NAME


def real_call_plan_path(
    project_name: str, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / REAL_CALL_PLAN_ARTIFACT_NAME


def failure_matrix_path(
    project_name: str, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / FAILURE_MATRIX_ARTIFACT_NAME


def dry_run_artifact_path(
    project_name: str, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / DRY_RUN_ARTIFACT_NAME


def report_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / REPORT_NAME


def write_bytes_atomic(path: Path, payload: Mapping[str, Any] | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        content = payload if payload.endswith("\n") else payload + "\n"
    else:
        content = json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    encoded = content.encode("utf-8")
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_bytes(encoded)
        if partial.read_bytes() != encoded:
            raise ValueError(f"Octets partiels ≠ contenu canonique pour {path.name}.")
        if not isinstance(payload, str):
            loaded = json.loads(encoded.decode("utf-8"))
            if not isinstance(loaded, dict) or loaded.get("schema_version") != SCHEMA_VERSION:
                raise ValueError(f"Artefact partiel invalide : {path.name}.")
            if loaded.get("phase") != PHASE:
                raise ValueError(f"phase inattendue dans {path.name}.")
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()
    return path


def assert_no_production_source_map(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> None:
    for path in (
        source_map_path(project_name, sortie_dir=sortie_dir),
        production_source_map_path(project_name, sortie_dir=sortie_dir),
    ):
        if path.exists():
            raise RuntimeError(f"source_map de production présent : {path}")


def production_semantic_windows_present(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> bool:
    return production_windows_exist(project_name, sortie_dir=sortie_dir)


def production_semantic_consolidation_present(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> bool:
    return production_consolidation_exist(project_name, sortie_dir=sortie_dir)
