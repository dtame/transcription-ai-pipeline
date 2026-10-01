"""Book Generator paths. Production book.json is never written in 4B.1."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.constants import (
    AUDIT_DIRNAME,
    AUDIT_READINESS,
    AUDIT_REPORT,
    BOOK_FILENAME,
)
from app.cleanup_application.writer import clean_json_path
from app.editorial_planning.writer import editorial_plan_path
from app.source_analysis.writer import analysis_dir, source_map_path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _PROJECT_ROOT


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_REPORT


def readiness_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_READINESS


def book_path(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return analysis_dir(project_name, sortie_dir=sortie_dir) / BOOK_FILENAME


def production_editorial_plan_path(
    project_name: str, *, sortie_dir: Path | None = None
) -> Path:
    return editorial_plan_path(project_name, sortie_dir=sortie_dir)


def production_source_map_path(
    project_name: str, *, sortie_dir: Path | None = None
) -> Path:
    return source_map_path(project_name, sortie_dir=sortie_dir)


def production_clean_transcript_path(
    project_name: str, *, sortie_dir: Path | None = None
) -> Path:
    return clean_json_path(project_name, sortie_dir=sortie_dir)
