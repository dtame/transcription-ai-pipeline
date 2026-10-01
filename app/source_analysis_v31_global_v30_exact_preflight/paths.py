"""Chemins A.45. Jamais analysis/source_map.json."""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    A44_CANARY_SUBDIR,
    A44_EXECUTION_ARTIFACT,
    A44_REPORT_NAME,
    A44_USAGE_ARTIFACT,
    PROJECT_NAME,
    REPORT_NAME,
)


def sortie_root(sortie_dir: Path | None = None) -> Path:
    return Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR


def artifact_path(
    project_name: str,
    name: str,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / name


def report_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / REPORT_NAME


def a44_canary_root(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / Path(A44_CANARY_SUBDIR)


def a44_usage_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return a44_canary_root(project_name, sortie_dir=sortie_dir) / A44_USAGE_ARTIFACT


def a44_execution_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return a44_canary_root(project_name, sortie_dir=sortie_dir) / A44_EXECUTION_ARTIFACT


def a44_report_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / A44_REPORT_NAME


def production_source_map_present(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> bool:
    return source_map_path(project_name, sortie_dir=sortie_dir).is_file()


__all__ = [
    "a44_canary_root",
    "a44_execution_path",
    "a44_report_path",
    "a44_usage_path",
    "artifact_path",
    "production_source_map_present",
    "report_path",
    "sortie_root",
]
