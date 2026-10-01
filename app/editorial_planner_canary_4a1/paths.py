"""Chemins d'audit isolés — jamais analysis/editorial_plan.json production."""

from __future__ import annotations

from pathlib import Path

from app.editorial_planner_canary_4a1.constants import (
    AUDIT_DIRNAME,
    LOCK_NAME,
    REPORT_NAME,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _PROJECT_ROOT


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def canary_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_DIRNAME


def canary_lock_path(*, root: Path | None = None) -> Path:
    return canary_audit_dir(root=root) / LOCK_NAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def forensic_root(*, root: Path | None = None) -> Path:
    return canary_audit_dir(root=root) / "forensics"


def production_editorial_plan_path() -> Path:
    return (
        repo_root()
        / "sortie"
        / "pastoral_retreat_v2_validation"
        / "analysis"
        / "editorial_plan.json"
    )


def production_source_map_path() -> Path:
    return (
        repo_root()
        / "sortie"
        / "pastoral_retreat_v2_validation"
        / "analysis"
        / "source_map.json"
    )


__all__ = [
    "audit_root",
    "canary_audit_dir",
    "canary_lock_path",
    "forensic_root",
    "production_editorial_plan_path",
    "production_source_map_path",
    "repo_root",
    "report_path",
]
