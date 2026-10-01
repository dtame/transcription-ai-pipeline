"""Isolated 4B.2.4 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.paths import book_path
from app.book_semantic_gate_4b23.paths import (
    historical_4b21_dir,
    historical_4b22_dir,
    historical_4b2_dir,
    production_map_path,
    production_plan_path,
    production_transcript_path,
)
from app.book_semantic_gate_4b24.constants import (
    AUDIT_DIRNAME,
    AUDIT_LOCK,
    AUDIT_REAL_PARENT,
    PROJECT_NAME,
    REPORT_NAME,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _PROJECT_ROOT


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def frozen_4b23_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "book_semantic_gate_4b23"


def frozen_benchmark_path(*, root: Path | None = None) -> Path:
    return frozen_4b23_dir(root=root) / "book_semantic_gate_4b23_historical_benchmark.json"


def canary_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_REAL_PARENT / AUDIT_DIRNAME


def forensic_root(*, root: Path | None = None) -> Path:
    return canary_audit_dir(root=root) / "forensics"


def canary_lock_path(*, root: Path | None = None) -> Path:
    return canary_audit_dir(root=root) / AUDIT_LOCK


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def production_book_path() -> Path:
    return book_path(PROJECT_NAME)


__all__ = [
    "audit_root",
    "canary_audit_dir",
    "canary_lock_path",
    "forensic_root",
    "frozen_4b23_dir",
    "frozen_benchmark_path",
    "historical_4b21_dir",
    "historical_4b22_dir",
    "historical_4b2_dir",
    "production_book_path",
    "production_map_path",
    "production_plan_path",
    "production_transcript_path",
    "repo_root",
    "report_path",
]
