"""Isolated 4B.2.11 audit paths. Never production book.json. Never historical mutation."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.paths import book_path
from app.book_semantic_gate_4b211.constants import (
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


def historical_audit_dirs(*, root: Path | None = None) -> dict[str, Path]:
    base = audit_root(root=root)
    real = base / AUDIT_REAL_PARENT
    return {
        "4b210": base / "book_semantic_gate_4b210",
        "4b29": base / "book_semantic_gate_4b29",
        "4b27": real / "book_semantic_gate_4b27",
        "4b273": real / "book_semantic_gate_4b273",
        "4b277": real / "book_semantic_gate_4b277",
        "4b26": real / "book_semantic_gate_4b26",
    }


def frozen_4b210_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "book_semantic_gate_4b210"


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


def venv_python_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / ".venv" / "Scripts" / "python.exe"


__all__ = [
    "audit_root",
    "canary_audit_dir",
    "canary_lock_path",
    "forensic_root",
    "frozen_4b210_dir",
    "historical_audit_dirs",
    "production_book_path",
    "repo_root",
    "report_path",
    "venv_python_path",
]
