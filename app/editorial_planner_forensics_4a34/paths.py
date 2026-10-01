"""Isolated A.3.4 audit paths. Never analysis/editorial_plan.json production."""

from __future__ import annotations

from pathlib import Path

from app.editorial_planner_forensics_4a34.constants import (
    A3_AUDIT_RELATIVE,
    A33_AUDIT_RELATIVE,
    A33_RAW_NAME,
    AUDIT_DIRNAME,
    CANDIDATE_NAME,
    PROJECT_NAME,
    REPORT_NAME,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _PROJECT_ROOT


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def production_editorial_plan_path(*, root: Path | None = None) -> Path:
    return (
        (root or repo_root())
        / "sortie"
        / PROJECT_NAME
        / "analysis"
        / "editorial_plan.json"
    )


def production_source_map_path(*, root: Path | None = None) -> Path:
    return (
        (root or repo_root())
        / "sortie"
        / PROJECT_NAME
        / "analysis"
        / "source_map.json"
    )


def a33_candidate_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / Path(A33_AUDIT_RELATIVE) / CANDIDATE_NAME


def a33_raw_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / Path(A33_AUDIT_RELATIVE) / A33_RAW_NAME


def a3_candidate_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / Path(A3_AUDIT_RELATIVE) / CANDIDATE_NAME


__all__ = [
    "a3_candidate_path",
    "a33_candidate_path",
    "a33_raw_path",
    "audit_root",
    "phase_audit_dir",
    "production_editorial_plan_path",
    "production_source_map_path",
    "repo_root",
    "report_path",
]
