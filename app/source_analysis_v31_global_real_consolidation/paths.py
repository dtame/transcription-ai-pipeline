"""Chemins isolés A.38. Jamais analysis/source_map.json."""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_real_consolidation.constants import (
    CANARY_SUBDIR,
    CANDIDATE_SOURCE_MAP_NAME,
    LOCK_NAME,
    PROJECT_NAME,
    REPORT_NAME,
)


def canary_root(project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / Path(CANARY_SUBDIR)


def canary_windows_root(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return canary_root(project_name, sortie_dir=sortie_dir) / "windows"


def canary_lock_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return canary_root(project_name, sortie_dir=sortie_dir) / LOCK_NAME


def canary_artifact_path(
    project_name: str,
    name: str,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return canary_root(project_name, sortie_dir=sortie_dir) / name


def candidate_source_map_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return canary_root(project_name, sortie_dir=sortie_dir) / CANDIDATE_SOURCE_MAP_NAME


def report_path(project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / REPORT_NAME


def production_source_map_present(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> bool:
    return source_map_path(project_name, sortie_dir=sortie_dir).is_file()


__all__ = [
    "canary_artifact_path",
    "canary_lock_path",
    "canary_root",
    "canary_windows_root",
    "candidate_source_map_path",
    "production_source_map_present",
    "report_path",
]
