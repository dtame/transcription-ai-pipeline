"""Isolated A.3.5 audit paths. Never analysis/editorial_plan.json production."""

from __future__ import annotations

from pathlib import Path

from app.editorial_planner_canary_4a35.constants import (
    AUDIT_DIRNAME,
    AUDIT_REAL_PARENT,
    LOCK_NAME,
    PROJECT_NAME,
    REPORT_NAME,
)
from app.editorial_planner_forensics_4a34.paths import (
    a3_candidate_path,
    a33_candidate_path,
    a33_raw_path,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _PROJECT_ROOT


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def canary_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_REAL_PARENT / AUDIT_DIRNAME


def canary_lock_path(*, root: Path | None = None) -> Path:
    return canary_audit_dir(root=root) / LOCK_NAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def forensic_root(*, root: Path | None = None) -> Path:
    return canary_audit_dir(root=root) / "forensics"


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


__all__ = [
    "a3_candidate_path",
    "a33_candidate_path",
    "a33_raw_path",
    "audit_root",
    "canary_audit_dir",
    "canary_lock_path",
    "forensic_root",
    "production_editorial_plan_path",
    "production_source_map_path",
    "repo_root",
    "report_path",
]
