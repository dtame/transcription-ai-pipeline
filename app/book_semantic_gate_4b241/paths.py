"""Isolated 4B.2.4.1 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.paths import book_path
from app.book_semantic_gate_4b241.constants import AUDIT_DIRNAME, PROJECT_NAME, REPORT_NAME
from app.book_semantic_gate_4b24.paths import canary_lock_path, frozen_benchmark_path

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


def requirements_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "requirements.txt"


def venv_python_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / ".venv" / "Scripts" / "python.exe"


__all__ = [
    "audit_root",
    "canary_lock_path",
    "frozen_benchmark_path",
    "phase_audit_dir",
    "production_book_path",
    "report_path",
    "repo_root",
    "requirements_path",
    "venv_python_path",
]
