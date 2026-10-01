"""Chemins d'audit isolés — jamais analysis/editorial_plan.json production."""

from __future__ import annotations

from pathlib import Path

from app.editorial_planner_preflight_4a2.constants import (
    AUDIT_DIRNAME,
    PROJECT_NAME,
    REPORT_NAME,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _PROJECT_ROOT


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def preflight_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def production_editorial_plan_path() -> Path:
    return (
        repo_root()
        / "sortie"
        / PROJECT_NAME
        / "analysis"
        / "editorial_plan.json"
    )


def production_source_map_path() -> Path:
    return (
        repo_root()
        / "sortie"
        / PROJECT_NAME
        / "analysis"
        / "source_map.json"
    )


__all__ = [
    "audit_root",
    "preflight_audit_dir",
    "production_editorial_plan_path",
    "production_source_map_path",
    "repo_root",
    "report_path",
]
