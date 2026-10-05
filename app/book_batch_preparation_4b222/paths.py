"""Isolated 4B.2.22 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_batch_preparation_4b222.constants import (
    AUDIT_DIRNAME,
    PROJECT_NAME,
    REPORT_NAME,
)
from app.book_generation.paths import (
    book_path,
    production_clean_transcript_path,
    production_editorial_plan_path,
    production_source_map_path,
)
from app.book_generation_4b221.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    accepted_editorial_manifest_path,
    historical_prompt_paths,
    original_chapter_json_path,
    original_chapter_md_path,
    original_lock_path,
    production_book_path as _production_book_path,
    production_cache_module_path,
    production_map_path as _production_map_path,
    production_plan_path as _production_plan_path,
    production_transcript_path as _production_transcript_path,
    repo_root as _repo_root,
    venv_python_path as _venv_python_path,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _repo_root()


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def ch018_dir() -> Path:
    return audit_root() / "real" / "book_generation_4b221_ch018"


def ch018_json_path() -> Path:
    return ch018_dir() / "chapter_candidate.json"


def ch018_md_path() -> Path:
    return ch018_dir() / "chapter_candidate.md"


def ch018_lock_path() -> Path:
    return ch018_dir() / "call_lock.json"


def ch018_report_path() -> Path:
    return audit_root() / "PHASE_4B221_CH018_FIRST_REAL_CONTROLLED_GENERATION_REPORT.md"


def ch012_accepted_manifest_path() -> Path:
    return accepted_editorial_manifest_path()


def production_book_path() -> Path:
    return book_path(PROJECT_NAME)


def production_plan_path() -> Path:
    return production_editorial_plan_path(PROJECT_NAME)


def production_map_path() -> Path:
    return production_source_map_path(PROJECT_NAME)


def production_transcript_path() -> Path:
    return production_clean_transcript_path(PROJECT_NAME)


def venv_python_path(*, root: Path | None = None) -> Path:
    return _venv_python_path(root=root)


assert _PROJECT_ROOT == repo_root()
assert production_book_path() == _production_book_path()
assert production_plan_path() == _production_plan_path()
assert production_map_path() == _production_map_path()
assert production_transcript_path() == _production_transcript_path()

__all__ = [
    "accepted_chapter_json_path",
    "accepted_chapter_md_path",
    "accepted_editorial_manifest_path",
    "audit_root",
    "ch012_accepted_manifest_path",
    "ch018_dir",
    "ch018_json_path",
    "ch018_lock_path",
    "ch018_md_path",
    "ch018_report_path",
    "historical_prompt_paths",
    "original_chapter_json_path",
    "original_chapter_md_path",
    "original_lock_path",
    "phase_audit_dir",
    "production_book_path",
    "production_cache_module_path",
    "production_map_path",
    "production_plan_path",
    "production_transcript_path",
    "report_path",
    "repo_root",
    "venv_python_path",
]
