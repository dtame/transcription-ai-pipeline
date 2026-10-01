"""Isolated 4B.2.3 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.paths import (
    book_path,
    production_clean_transcript_path,
    production_editorial_plan_path,
    production_source_map_path,
)
from app.book_generator_canary_4b2.constants import AUDIT_DIRNAME as HISTORICAL_4B2
from app.book_generator_canary_4b2.constants import AUDIT_REAL_PARENT
from app.book_generator_canary_4b22.constants import AUDIT_DIRNAME as HISTORICAL_4B22
from app.book_semantic_gate_4b23.constants import (
    AUDIT_DIRNAME,
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


def historical_4b2_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_REAL_PARENT / HISTORICAL_4B2


def historical_4b22_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_REAL_PARENT / HISTORICAL_4B22


def historical_4b21_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "book_generator_4b21"


def production_book_path() -> Path:
    return book_path(PROJECT_NAME)


def production_plan_path() -> Path:
    return production_editorial_plan_path(PROJECT_NAME)


def production_map_path() -> Path:
    return production_source_map_path(PROJECT_NAME)


def production_transcript_path() -> Path:
    return production_clean_transcript_path(PROJECT_NAME)


__all__ = [
    "audit_root",
    "historical_4b21_dir",
    "historical_4b22_dir",
    "historical_4b2_dir",
    "phase_audit_dir",
    "production_book_path",
    "production_map_path",
    "production_plan_path",
    "production_transcript_path",
    "repo_root",
    "report_path",
]
