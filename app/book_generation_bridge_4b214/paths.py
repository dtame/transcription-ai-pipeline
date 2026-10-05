"""Isolated 4B.2.14 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.paths import (
    book_path,
    production_clean_transcript_path,
    production_editorial_plan_path,
    production_source_map_path,
)
from app.book_generation_bridge_4b214.constants import (
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


def production_book_path() -> Path:
    return book_path(PROJECT_NAME)


def production_plan_path() -> Path:
    return production_editorial_plan_path(PROJECT_NAME)


def production_map_path() -> Path:
    return production_source_map_path(PROJECT_NAME)


def production_transcript_path() -> Path:
    return production_clean_transcript_path(PROJECT_NAME)


def venv_python_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / ".venv" / "Scripts" / "python.exe"


def production_pipeline_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "app" / "book_generation" / "pipeline.py"


def production_cache_module_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "app" / "book_generation" / "cache.py"


__all__ = [
    "audit_root",
    "phase_audit_dir",
    "production_book_path",
    "production_cache_module_path",
    "production_map_path",
    "production_pipeline_path",
    "production_plan_path",
    "production_transcript_path",
    "report_path",
    "repo_root",
    "venv_python_path",
]
