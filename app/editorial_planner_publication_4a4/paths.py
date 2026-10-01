"""Phase 4A.4 paths. Canonical production artifact is analysis/editorial_plan.json."""

from __future__ import annotations

from pathlib import Path

from app.editorial_planner_canary_4a35.paths import (
    a3_candidate_path,
    a33_candidate_path,
)
from app.editorial_planner_publication_4a4.constants import (
    A35_ACCOUNTABILITY_NAME,
    A35_AUDIT_RELATIVE,
    A35_CANDIDATE_NAME,
    A35_EXECUTION_NAME,
    A35_LANGUAGE_NAME,
    A35_PRECALL_NAME,
    A35_PUBLICATION_NAME,
    A35_READINESS_NAME,
    A35_RESPONSE_NAME,
    A35_SEMANTIC_NAME,
    A35_TECHNICAL_NAME,
    AUDIT_DIRNAME,
    AUDIT_READINESS,
    PROJECT_NAME,
    REPORT_NAME,
)
from app.editorial_planning.writer import editorial_plan_path
from app.source_analysis.writer import source_map_path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _PROJECT_ROOT


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def readiness_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_READINESS


def production_editorial_plan_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return editorial_plan_path(project_name, sortie_dir=sortie_dir)


def production_source_map_path(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    return source_map_path(project_name, sortie_dir=sortie_dir)


def a35_audit_dir(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / Path(A35_AUDIT_RELATIVE)


def a35_candidate_path(*, root: Path | None = None) -> Path:
    return a35_audit_dir(root=root) / A35_CANDIDATE_NAME


def a35_semantic_path(*, root: Path | None = None) -> Path:
    return a35_audit_dir(root=root) / A35_SEMANTIC_NAME


def a35_technical_path(*, root: Path | None = None) -> Path:
    return a35_audit_dir(root=root) / A35_TECHNICAL_NAME


def a35_accountability_path(*, root: Path | None = None) -> Path:
    return a35_audit_dir(root=root) / A35_ACCOUNTABILITY_NAME


def a35_language_path(*, root: Path | None = None) -> Path:
    return a35_audit_dir(root=root) / A35_LANGUAGE_NAME


def a35_publication_path(*, root: Path | None = None) -> Path:
    return a35_audit_dir(root=root) / A35_PUBLICATION_NAME


def a35_execution_path(*, root: Path | None = None) -> Path:
    return a35_audit_dir(root=root) / A35_EXECUTION_NAME


def a35_precall_path(*, root: Path | None = None) -> Path:
    return a35_audit_dir(root=root) / A35_PRECALL_NAME


def a35_response_path(*, root: Path | None = None) -> Path:
    return a35_audit_dir(root=root) / A35_RESPONSE_NAME


def a35_readiness_path(*, root: Path | None = None) -> Path:
    return a35_audit_dir(root=root) / A35_READINESS_NAME


__all__ = [
    "a3_candidate_path",
    "a33_candidate_path",
    "a35_accountability_path",
    "a35_audit_dir",
    "a35_candidate_path",
    "a35_execution_path",
    "a35_language_path",
    "a35_precall_path",
    "a35_publication_path",
    "a35_readiness_path",
    "a35_response_path",
    "a35_semantic_path",
    "a35_technical_path",
    "audit_root",
    "phase_audit_dir",
    "production_editorial_plan_path",
    "production_source_map_path",
    "readiness_path",
    "repo_root",
    "report_path",
]
