"""Écriture atomique des artefacts 3B.7.4 — audit seulement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.consolidation_writer import production_consolidation_exist
from app.source_analysis.window_writer import production_windows_exist
from app.source_analysis.writer import source_map_path
from app.source_analysis_global_clean.writer import production_source_map_path
from app.source_analysis_consolidation.constants import (
    IMPLEMENTATION_ARTIFACT_NAME,
    PHASE,
    PREFLIGHT_ARTIFACT_NAME,
    REPORT_NAME,
    SCHEMA_METRICS_ARTIFACT_NAME,
    SCHEMA_VERSION,
    SYNTHETIC_ARTIFACT_NAME,
)


def implementation_artifact_path(
    project_name: str, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / IMPLEMENTATION_ARTIFACT_NAME


def synthetic_artifact_path(
    project_name: str, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / SYNTHETIC_ARTIFACT_NAME


def preflight_artifact_path(
    project_name: str, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / PREFLIGHT_ARTIFACT_NAME


def schema_metrics_artifact_path(
    project_name: str, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / SCHEMA_METRICS_ARTIFACT_NAME


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


def assert_no_production_windows(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> None:
    if production_windows_exist(project_name, sortie_dir=sortie_dir):
        raise RuntimeError(
            f"dossiers production windows créés pour {project_name}"
        )


def assert_no_production_consolidation(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> None:
    if production_consolidation_exist(project_name, sortie_dir=sortie_dir):
        raise RuntimeError(
            f"dossiers production consolidation créés pour {project_name}"
        )
