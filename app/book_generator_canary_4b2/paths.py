"""Isolated 4B.2 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.paths import (
    book_path,
    production_clean_transcript_path,
    production_editorial_plan_path,
    production_source_map_path,
)
from app.book_generator_canary_4b2.constants import (
    AUDIT_DIRNAME,
    AUDIT_REAL_PARENT,
    LOCK_NAME,
    PROJECT_NAME,
    REPORT_NAME,
)
from app.source_analysis.writer import transcripts_dir

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


def production_book_path() -> Path:
    return book_path(PROJECT_NAME)


def production_plan_path() -> Path:
    return production_editorial_plan_path(PROJECT_NAME)


def production_map_path() -> Path:
    return production_source_map_path(PROJECT_NAME)


def production_transcript_path() -> Path:
    return production_clean_transcript_path(PROJECT_NAME)


def production_preclean_transcript_path() -> Path:
    return transcripts_dir(PROJECT_NAME) / "transcript_data.json"


__all__ = [
    "audit_root",
    "canary_audit_dir",
    "canary_lock_path",
    "forensic_root",
    "production_book_path",
    "production_map_path",
    "production_plan_path",
    "production_preclean_transcript_path",
    "production_transcript_path",
    "repo_root",
    "report_path",
]
