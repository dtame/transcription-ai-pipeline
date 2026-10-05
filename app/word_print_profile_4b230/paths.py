"""4B.2.30 paths. book.json is read-only. No published DOCX/PDF."""

from __future__ import annotations

from pathlib import Path

from app.book_print_review_canonical_4b229.paths import (
    production_book_path as _production_book_path,
    repo_root as _repo_root,
    venv_python_path as _venv_python_path,
)
from app.word_print_profile_4b230.constants import AUDIT_DIRNAME, PROJECT_NAME, REPORT_NAME
from app.word_renderer.profile import default_profile_path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _repo_root()


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def production_book_path(*, root: Path | None = None) -> Path:
    if root is None:
        return _production_book_path()
    return root / "sortie" / PROJECT_NAME / "analysis" / "book.json"


def print_profile_path() -> Path:
    return default_profile_path()


def venv_python_path(*, root: Path | None = None) -> Path:
    return _venv_python_path(root=root)


assert _PROJECT_ROOT == repo_root()

__all__ = [
    "audit_root",
    "phase_audit_dir",
    "print_profile_path",
    "production_book_path",
    "repo_root",
    "report_path",
    "venv_python_path",
]
