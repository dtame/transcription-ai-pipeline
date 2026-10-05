"""Isolated 4B.2.17 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.paths import (
    book_path,
    production_clean_transcript_path,
    production_editorial_plan_path,
    production_source_map_path,
)
from app.book_generation_4b217.constants import (
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


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_REAL_PARENT / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def lock_path(*, root: Path | None = None) -> Path:
    return phase_audit_dir(root=root) / AUDIT_LOCK


def forensic_root(*, root: Path | None = None) -> Path:
    return phase_audit_dir(root=root) / "provider_forensics"


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


def historical_prompt_paths(*, root: Path | None = None) -> dict[str, Path]:
    base = (root or repo_root()) / "app"
    return {
        "book_generator_1_0": base / "book_generation" / "prompt.py",
        "book_generator_1_0_1": base / "book_generation" / "prompt_v101.py",
        "prompt_select": base / "book_generation" / "prompt_select.py",
        "semantic_contract_2_0_2": base / "book_semantic_gate_4b212" / "contract.py",
        "production_pipeline": base / "book_generation" / "pipeline.py",
        "production_cache": base / "book_generation" / "cache.py",
        "faithful_prompt_candidate": (
            base / "book_editorial_alignment_4b216" / "prompt_candidate.py"
        ),
    }


__all__ = [
    "audit_root",
    "forensic_root",
    "historical_prompt_paths",
    "lock_path",
    "phase_audit_dir",
    "production_book_path",
    "production_map_path",
    "production_plan_path",
    "production_transcript_path",
    "report_path",
    "repo_root",
    "venv_python_path",
]
