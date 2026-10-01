"""Chemins A.49. Cible production via source_map_path. Candidat A.48 en lecture."""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.paths import SORTIE_DIR
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_a48_offline_revalidation.constants import (
    CANDIDATE_SOURCE_MAP_NAME as A48_CANDIDATE_SOURCE_MAP_NAME,
    PUBLICATION_ARTIFACT as A48_PUBLICATION_ARTIFACT,
    SEMANTIC_ARTIFACT as A48_SEMANTIC_ARTIFACT,
    TECHNICAL_ARTIFACT as A48_TECHNICAL_ARTIFACT,
)
from app.source_analysis_v31_global_a48_offline_revalidation.paths import (
    a46_canary_root,
    a46_candidate_path,
    a46_identity_path,
    a46_raw_path,
    a46_report_path,
    candidate_path as a48_candidate_path,
)
from app.source_analysis_v31_global_a49_source_map_publication.constants import (
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


def report_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / REPORT_NAME


def production_source_map_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return source_map_path(project_name, sortie_dir=sortie_dir)


def project_root(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    return root / project_name


def project_state_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return project_root(project_name, sortie_dir=sortie_dir) / "project_state.json"


def project_report_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return project_root(project_name, sortie_dir=sortie_dir) / "report.json"


def a48_publication_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return artifact_path(
        project_name, A48_PUBLICATION_ARTIFACT, sortie_dir=sortie_dir
    )


def a48_semantic_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return artifact_path(project_name, A48_SEMANTIC_ARTIFACT, sortie_dir=sortie_dir)


def a48_technical_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return artifact_path(project_name, A48_TECHNICAL_ARTIFACT, sortie_dir=sortie_dir)


__all__ = [
    "A48_CANDIDATE_SOURCE_MAP_NAME",
    "a46_canary_root",
    "a46_candidate_path",
    "a46_identity_path",
    "a46_raw_path",
    "a46_report_path",
    "a48_candidate_path",
    "a48_publication_path",
    "a48_semantic_path",
    "a48_technical_path",
    "artifact_path",
    "production_source_map_path",
    "project_report_path",
    "project_root",
    "project_state_path",
    "report_path",
]
