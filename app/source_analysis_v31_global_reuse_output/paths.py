"""Chemins A.43. Jamais analysis/source_map.json."""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_reuse_output.constants import (
    A42_CANARY_SUBDIR,
    A42_REPORT_NAME,
    PROJECT_NAME,
    REPORT_NAME,
)


def sortie_root(sortie_dir: Path | None = None) -> Path:
    return Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR


def a42_canary_root(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / Path(A42_CANARY_SUBDIR)


def a42_report_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / A42_REPORT_NAME


def artifact_path(
    project_name: str,
    name: str,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / name


def report_path(project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / REPORT_NAME


def production_source_map_present(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> bool:
    return source_map_path(project_name, sortie_dir=sortie_dir).is_file()


__all__ = [
    "a42_canary_root",
    "a42_report_path",
    "artifact_path",
    "production_source_map_present",
    "report_path",
    "sortie_root",
]
