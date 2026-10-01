"""Chemins A.41. Jamais analysis/source_map.json."""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_drop_domain.constants import (
    A40_CANARY_SUBDIR,
    A40_REPORT_NAME,
    A40_REQUEST_IDENTITY,
    A40_WINDOW_ID,
    PROJECT_NAME,
    REPORT_NAME,
)


def sortie_root(sortie_dir: Path | None = None) -> Path:
    return Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR


def a40_canary_root(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / Path(A40_CANARY_SUBDIR)


def a40_report_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / A40_REPORT_NAME


def a40_forensic_dir(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return (
        a40_canary_root(project_name, sortie_dir=sortie_dir)
        / "provider_forensics"
        / A40_WINDOW_ID
        / A40_REQUEST_IDENTITY
    )


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
    "a40_canary_root",
    "a40_forensic_dir",
    "a40_report_path",
    "artifact_path",
    "production_source_map_present",
    "report_path",
    "sortie_root",
]
