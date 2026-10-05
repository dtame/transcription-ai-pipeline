"""Isolated 4B.2.7.3 audit paths. Never production book.json. Never historical audits."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.paths import book_path
from app.book_semantic_gate_4b273.constants import (
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
        "4b23": base / "book_semantic_gate_4b23",
        "4b24": real / "book_semantic_gate_4b24",
        "4b241": base / "book_semantic_gate_4b241",
        "4b25": real / "book_semantic_gate_4b25",
        "4b251": base / "book_semantic_gate_4b251",
        "4b26": real / "book_semantic_gate_4b26",
        "4b261": base / "book_semantic_gate_4b261",
        "4b262": base / "book_semantic_gate_4b262",
        "4b27": real / "book_semantic_gate_4b27",
        "4b271": base / "book_semantic_gate_4b271",
        "4b272": base / "book_semantic_gate_4b272",
    }


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
    "historical_audit_dirs",
    "production_book_path",
    "repo_root",
    "report_path",
    "venv_python_path",
]
