"""Isolated 4B.2.18 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_authorial_voice_4b218.constants import (
    AUDIT_DIRNAME,
    ORIGINAL_CHAPTER_JSON,
    ORIGINAL_CHAPTER_MD,
    ORIGINAL_LOCK,
    PROJECT_NAME,
    REPORT_NAME,
)
from app.book_generation.paths import (
    book_path,
    production_clean_transcript_path,
    production_editorial_plan_path,
    production_source_map_path,
)
from app.book_generation_4b217.constants import AUDIT_DIRNAME as ORIGINAL_AUDIT_DIRNAME
from app.book_generation_4b217.constants import AUDIT_REAL_PARENT

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _PROJECT_ROOT


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def original_chapter_dir() -> Path:
    return repo_root() / "audit" / AUDIT_REAL_PARENT / ORIGINAL_AUDIT_DIRNAME


def original_chapter_json_path() -> Path:
    return original_chapter_dir() / ORIGINAL_CHAPTER_JSON


def original_chapter_md_path() -> Path:
    return original_chapter_dir() / ORIGINAL_CHAPTER_MD


def original_lock_path() -> Path:
    return original_chapter_dir() / ORIGINAL_LOCK


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
        "faithful_prompt_1_0_candidate": (
            base / "book_editorial_alignment_4b216" / "prompt_candidate.py"
        ),
        "semantic_contract_2_0_2": base / "book_semantic_gate_4b212" / "contract.py",
        "production_pipeline": base / "book_generation" / "pipeline.py",
        "production_cache": base / "book_generation" / "cache.py",
    }


__all__ = [
    "audit_root",
    "historical_prompt_paths",
    "original_chapter_dir",
    "original_chapter_json_path",
    "original_chapter_md_path",
    "original_lock_path",
    "phase_audit_dir",
    "production_book_path",
    "production_map_path",
    "production_plan_path",
    "production_transcript_path",
    "report_path",
    "repo_root",
    "venv_python_path",
]
