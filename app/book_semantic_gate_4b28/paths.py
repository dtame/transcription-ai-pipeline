"""Isolated 4B.2.8 audit paths. Never production book.json. Never historical mutation."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.paths import book_path
from app.book_semantic_gate_4b28.constants import AUDIT_DIRNAME, PROJECT_NAME, REPORT_NAME

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


def historical_h01_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "real" / "book_semantic_gate_4b27"


def historical_h02_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "real" / "book_semantic_gate_4b273"


def historical_h11_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "real" / "book_semantic_gate_4b277"


def historical_4b271_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "book_semantic_gate_4b271"


def historical_4b274_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "book_semantic_gate_4b274"


def historical_4b275_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "book_semantic_gate_4b275"


def historical_4b276_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "book_semantic_gate_4b276"


def venv_python_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / ".venv" / "Scripts" / "python.exe"


__all__ = [
    "audit_root",
    "historical_4b271_dir",
    "historical_4b274_dir",
    "historical_4b275_dir",
    "historical_4b276_dir",
    "historical_h01_dir",
    "historical_h02_dir",
    "historical_h11_dir",
    "phase_audit_dir",
    "production_book_path",
    "report_path",
    "repo_root",
    "venv_python_path",
]
