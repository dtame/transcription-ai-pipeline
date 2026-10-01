"""Isolated A.3.1 audit paths. Never analysis/editorial_plan.json production."""

from __future__ import annotations

from pathlib import Path

from app.editorial_planner_forensics_4a31.constants import (
    A3_AUDIT_RELATIVE,
    CANDIDATE_NAME,
    PROJECT_NAME,
    RAW_BIN_RELATIVE,
    RAW_STRUCTURED_NAME,
    RAW_TEXT_NAME,
    REPORT_NAME,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _PROJECT_ROOT


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def a3_audit_dir(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / Path(A3_AUDIT_RELATIVE)


def candidate_path(*, root: Path | None = None) -> Path:
    return a3_audit_dir(root=root) / CANDIDATE_NAME


def raw_structured_path(*, root: Path | None = None) -> Path:
    return a3_audit_dir(root=root) / RAW_STRUCTURED_NAME


def raw_text_path(*, root: Path | None = None) -> Path:
    return a3_audit_dir(root=root) / RAW_TEXT_NAME


def raw_bin_path(*, root: Path | None = None) -> Path:
    return a3_audit_dir(root=root) / RAW_BIN_RELATIVE


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


__all__ = [
    "a3_audit_dir",
    "audit_root",
    "candidate_path",
    "production_editorial_plan_path",
    "production_source_map_path",
    "raw_bin_path",
    "raw_structured_path",
    "raw_text_path",
    "repo_root",
    "report_path",
]
