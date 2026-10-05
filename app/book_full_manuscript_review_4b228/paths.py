"""Isolated 4B.2.28 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_full_generation_preparation_4b226.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    ch001_approved_json_path,
    ch001_approved_md_path,
    ch001_existing_manifest_path,
    ch002_approved_json_path,
    ch002_approved_md_path,
    ch002_existing_manifest_path,
    ch002_original_json_path,
    ch002_original_md_path,
    ch003_approved_json_path,
    ch003_approved_md_path,
    ch004_approved_json_path,
    ch004_approved_md_path,
    ch012_accepted_manifest_path,
    ch018_accepted_manifest_path,
    ch018_json_path,
    ch018_md_path,
    production_book_path as _production_book_path,
    production_cache_module_path,
    production_map_path as _production_map_path,
    production_plan_path as _production_plan_path,
    production_transcript_path as _production_transcript_path,
    repo_root as _repo_root,
    venv_python_path as _venv_python_path,
)
from app.book_generation.paths import book_path
from app.book_full_manuscript_review_4b228.constants import (
    AUDIT_DIRNAME,
    CH003_MANIFEST_REL,
    CH004_MANIFEST_REL,
    CH012_ORIGINAL_JSON_REL,
    CH012_ORIGINAL_MD_REL,
    PROJECT_NAME,
    REMAINING13_CHAPTER_REL,
    REPORT_NAME,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _repo_root()


def historical_rel(relative: str) -> Path:
    return repo_root() / Path(*relative.split("/"))


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def manuscript_path(*, root: Path | None = None) -> Path:
    return phase_audit_dir(root=root) / "manuscript_reading_draft.md"


def production_book_path() -> Path:
    return book_path(PROJECT_NAME)


def venv_python_path(*, root: Path | None = None) -> Path:
    return _venv_python_path(root=root)


def ch003_accepted_manifest_path() -> Path:
    return historical_rel(CH003_MANIFEST_REL)


def ch004_accepted_manifest_path() -> Path:
    return historical_rel(CH004_MANIFEST_REL)


def ch012_original_json_path() -> Path:
    return historical_rel(CH012_ORIGINAL_JSON_REL)


def ch012_original_md_path() -> Path:
    return historical_rel(CH012_ORIGINAL_MD_REL)


def remaining13_chapter_dir(chapter_id: str, *, root: Path | None = None) -> Path:
    relative = REMAINING13_CHAPTER_REL.format(chapter_id=chapter_id)
    return (root or repo_root()) / Path(*relative.split("/"))


def remaining13_json_path(chapter_id: str, *, root: Path | None = None) -> Path:
    return remaining13_chapter_dir(chapter_id, root=root) / "chapter_candidate.json"


def remaining13_md_path(chapter_id: str, *, root: Path | None = None) -> Path:
    return remaining13_chapter_dir(chapter_id, root=root) / "chapter_candidate.md"


assert _PROJECT_ROOT == repo_root()
assert production_book_path() == _production_book_path()

__all__ = [
    "accepted_chapter_json_path",
    "accepted_chapter_md_path",
    "audit_root",
    "ch001_approved_json_path",
    "ch001_approved_md_path",
    "ch001_existing_manifest_path",
    "ch002_approved_json_path",
    "ch002_approved_md_path",
    "ch002_existing_manifest_path",
    "ch002_original_json_path",
    "ch002_original_md_path",
    "ch003_accepted_manifest_path",
    "ch003_approved_json_path",
    "ch003_approved_md_path",
    "ch004_accepted_manifest_path",
    "ch004_approved_json_path",
    "ch004_approved_md_path",
    "ch012_accepted_manifest_path",
    "ch012_original_json_path",
    "ch012_original_md_path",
    "ch018_accepted_manifest_path",
    "ch018_json_path",
    "ch018_md_path",
    "historical_rel",
    "manuscript_path",
    "phase_audit_dir",
    "production_book_path",
    "production_cache_module_path",
    "production_map_path",
    "production_plan_path",
    "production_transcript_path",
    "remaining13_chapter_dir",
    "remaining13_json_path",
    "remaining13_md_path",
    "report_path",
    "repo_root",
    "venv_python_path",
]


def production_map_path():
    return _production_map_path()


def production_plan_path():
    return _production_plan_path()


def production_transcript_path():
    return _production_transcript_path()
