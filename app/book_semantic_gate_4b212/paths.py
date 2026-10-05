"""Isolated 4B.2.12 audit paths. Never production book.json. Never historical mutation."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.paths import book_path
from app.book_semantic_gate_4b212.constants import AUDIT_DIRNAME, PROJECT_NAME, REPORT_NAME

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


def venv_python_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / ".venv" / "Scripts" / "python.exe"


def historical_4b211_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "real" / "book_semantic_gate_4b211"


def historical_raw_response_path(*, root: Path | None = None) -> Path:
    return historical_4b211_dir(root=root) / "provider_response_raw.json"


def frozen_4b210_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "book_semantic_gate_4b210"


def historical_h01_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "real" / "book_semantic_gate_4b27"


def historical_h02_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "real" / "book_semantic_gate_4b273"


def historical_h11_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / "real" / "book_semantic_gate_4b277"


__all__ = [
    "audit_root",
    "frozen_4b210_dir",
    "historical_4b211_dir",
    "historical_h01_dir",
    "historical_h02_dir",
    "historical_h11_dir",
    "historical_raw_response_path",
    "phase_audit_dir",
    "production_book_path",
    "report_path",
    "repo_root",
    "venv_python_path",
]
