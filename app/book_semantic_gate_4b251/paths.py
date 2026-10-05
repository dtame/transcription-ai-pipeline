"""Isolated 4B.2.5.1 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.paths import book_path
from app.book_semantic_gate_4b251.constants import AUDIT_DIRNAME, PROJECT_NAME, REPORT_NAME

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


def historical_4b25_request_path(*, root: Path | None = None) -> Path:
    return (
        audit_root(root=root)
        / "real"
        / "book_semantic_gate_4b25"
        / "book_semantic_gate_4b25_request_identity.json"
    )


def historical_4b25_report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / (
        "PHASE_4B25_ONE_REAL_TERRA_SEMANTIC_GATE_BENCHMARK_CANARY_REPORT.md"
    )


def venv_python_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / ".venv" / "Scripts" / "python.exe"


__all__ = [
    "audit_root",
    "historical_4b25_report_path",
    "historical_4b25_request_path",
    "phase_audit_dir",
    "production_book_path",
    "report_path",
    "repo_root",
    "venv_python_path",
]
