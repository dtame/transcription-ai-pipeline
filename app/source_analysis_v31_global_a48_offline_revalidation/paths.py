"""Chemins A.48. Lecture seule A.46. Jamais analysis/source_map.json."""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_a47_contract_forensics.paths import (
    a46_candidate_path,
    a46_canary_root,
    a46_execution_path,
    a46_identity_path,
    a46_raw_path,
    a46_report_path,
)
from app.source_analysis_v31_global_a48_offline_revalidation.constants import (
    CANDIDATE_SOURCE_MAP_NAME,
    PROJECT_NAME,
    REPORT_NAME,
)


def artifact_path(
    project_name: str,
    name: str,
    *,
    sortie_dir: Path | None = None,
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / name


def candidate_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return a46_canary_root(project_name, sortie_dir=sortie_dir) / CANDIDATE_SOURCE_MAP_NAME


def report_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / REPORT_NAME


def production_source_map_present(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> bool:
    return source_map_path(project_name, sortie_dir=sortie_dir).is_file()


__all__ = [
    "a46_candidate_path",
    "a46_canary_root",
    "a46_execution_path",
    "a46_identity_path",
    "a46_raw_path",
    "a46_report_path",
    "artifact_path",
    "candidate_path",
    "production_source_map_present",
    "report_path",
]
