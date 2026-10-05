"""Isolated 4B.2.27 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_full_generation_preparation_4b226.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    ch001_approved_json_path,
    ch001_approved_md_path,
    ch002_approved_json_path,
    ch002_approved_md_path,
    ch002_original_json_path,
    ch002_original_md_path,
    ch003_approved_json_path,
    ch003_approved_md_path,
    ch004_approved_json_path,
    ch004_approved_md_path,
    ch018_json_path,
    ch018_md_path,
    historical_prompt_paths,
    production_book_path as _production_book_path,
    production_cache_module_path,
    production_map_path as _production_map_path,
    production_plan_path as _production_plan_path,
    production_transcript_path as _production_transcript_path,
    repo_root as _repo_root,
    venv_python_path as _venv_python_path,
)
from app.book_generation.paths import book_path
from app.book_generation_4b227.constants import (
    AUDIT_DIRNAME,
    AUDIT_LOCK,
    AUDIT_REAL_PARENT,
    BATCH_LOCK_NAME,
    PREP_AUTHORIZATION_REL,
    PREP_COST_REL,
    PREP_INVENTORY_REL,
    PREP_PLAN_REL,
    PREP_READINESS_REL,
    PROJECT_NAME,
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
    return audit_root(root=root) / AUDIT_REAL_PARENT / AUDIT_DIRNAME


def chapter_audit_dir(chapter_id: str, *, root: Path | None = None) -> Path:
    return phase_audit_dir(root=root) / "chapters" / chapter_id


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def batch_lock_path(*, root: Path | None = None) -> Path:
    return phase_audit_dir(root=root) / BATCH_LOCK_NAME


def lock_path(chapter_id: str, *, root: Path | None = None) -> Path:
    return chapter_audit_dir(chapter_id, root=root) / AUDIT_LOCK


def forensic_root(chapter_id: str, *, root: Path | None = None) -> Path:
    return chapter_audit_dir(chapter_id, root=root) / "provider_forensics"


def progress_path(*, root: Path | None = None) -> Path:
    return phase_audit_dir(root=root) / "progress.json"


def production_book_path() -> Path:
    return book_path(PROJECT_NAME)


def venv_python_path(*, root: Path | None = None) -> Path:
    return _venv_python_path(root=root)


def prep_inventory_path() -> Path:
    return historical_rel(PREP_INVENTORY_REL)


def prep_plan_path() -> Path:
    return historical_rel(PREP_PLAN_REL)


def prep_cost_path() -> Path:
    return historical_rel(PREP_COST_REL)


def prep_authorization_path() -> Path:
    return historical_rel(PREP_AUTHORIZATION_REL)


def prep_readiness_path() -> Path:
    return historical_rel(PREP_READINESS_REL)


assert _PROJECT_ROOT == repo_root()
assert production_book_path() == _production_book_path()

__all__ = [
    "accepted_chapter_json_path",
    "accepted_chapter_md_path",
    "audit_root",
    "batch_lock_path",
    "ch001_approved_json_path",
    "ch001_approved_md_path",
    "ch002_approved_json_path",
    "ch002_approved_md_path",
    "ch002_original_json_path",
    "ch002_original_md_path",
    "ch003_approved_json_path",
    "ch003_approved_md_path",
    "ch004_approved_json_path",
    "ch004_approved_md_path",
    "ch018_json_path",
    "ch018_md_path",
    "chapter_audit_dir",
    "forensic_root",
    "historical_prompt_paths",
    "historical_rel",
    "lock_path",
    "phase_audit_dir",
    "prep_authorization_path",
    "prep_cost_path",
    "prep_inventory_path",
    "prep_plan_path",
    "prep_readiness_path",
    "production_book_path",
    "production_cache_module_path",
    "progress_path",
    "report_path",
    "repo_root",
    "venv_python_path",
]
