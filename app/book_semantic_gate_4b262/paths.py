"""Isolated 4B.2.6.2 audit paths. Never production book.json. Never historical audits."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.paths import book_path
from app.book_semantic_gate_4b262.constants import AUDIT_DIRNAME, PROJECT_NAME, REPORT_NAME

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


def historical_4b26_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "real" / "book_semantic_gate_4b26"


def historical_audit_dirs(*, root: Path | None = None) -> dict[str, Path]:
    base = audit_root(root=root)
    real = base / "real"
    return {
        "4b23": base / "book_semantic_gate_4b23",
        "4b24": real / "book_semantic_gate_4b24",
        "4b241": base / "book_semantic_gate_4b241",
        "4b25": real / "book_semantic_gate_4b25",
        "4b251": base / "book_semantic_gate_4b251",
        "4b26": real / "book_semantic_gate_4b26",
        "4b261": base / "book_semantic_gate_4b261",
    }


def venv_python_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / ".venv" / "Scripts" / "python.exe"


__all__ = [
    "audit_root",
    "historical_4b26_dir",
    "historical_audit_dirs",
    "phase_audit_dir",
    "production_book_path",
    "report_path",
    "repo_root",
    "venv_python_path",
]
