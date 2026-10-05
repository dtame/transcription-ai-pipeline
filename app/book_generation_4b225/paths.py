"""Isolated 4B.2.25 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_generation.paths import (
    book_path,
    production_clean_transcript_path,
    production_editorial_plan_path,
    production_source_map_path,
)
from app.book_generation_4b221.paths import (
    historical_prompt_paths,
    production_book_path as _production_book_path,
    production_cache_module_path,
    production_map_path as _production_map_path,
    production_plan_path as _production_plan_path,
    production_transcript_path as _production_transcript_path,
    repo_root as _repo_root,
    venv_python_path as _venv_python_path,
)
from app.book_generation_4b223.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    accepted_editorial_manifest_path,
    ch018_json_path,
    ch018_lock_path,
    ch018_md_path,
)
from app.book_generation_4b225.constants import (
    AUDIT_DIRNAME,
    AUDIT_LOCK,
    AUDIT_REAL_PARENT,
    BATCH_LOCK_NAME,
    CH001_APPROVED_JSON_REL,
    CH001_APPROVED_MD_REL,
    CH001_LOCK_REL,
    CH001_STRUCTURAL_REL,
    CH002_APPROVED_JSON_REL,
    CH002_APPROVED_MD_REL,
    CH002_LOCK_REL,
    CH002_ORIGINAL_JSON_REL,
    CH002_ORIGINAL_MD_REL,
    CH002_RECOVERY_VALIDATION_REL,
    CH003_HISTORICAL_LOCK_REL,
    CH004_HISTORICAL_LOCK_REL,
    CH012_MANIFEST_REL,
    CH018_MANIFEST_REL,
    PROJECT_NAME,
    REPORT_NAME,
    RESUME_PLAN_REL,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _repo_root()


def _rel(relative: str, *, root: Path | None = None) -> Path:
    return (root or repo_root()) / Path(*relative.split("/"))


def historical_rel(relative: str) -> Path:
    """Historical artifacts always live in the real repository."""
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


def ch001_approved_json_path() -> Path:
    return historical_rel(CH001_APPROVED_JSON_REL)


def ch001_approved_md_path() -> Path:
    return historical_rel(CH001_APPROVED_MD_REL)


def ch001_historical_lock_path() -> Path:
    return historical_rel(CH001_LOCK_REL)


def ch001_structural_path() -> Path:
    return historical_rel(CH001_STRUCTURAL_REL)


def ch002_approved_json_path() -> Path:
    return historical_rel(CH002_APPROVED_JSON_REL)


def ch002_approved_md_path() -> Path:
    return historical_rel(CH002_APPROVED_MD_REL)


def ch002_original_json_path() -> Path:
    return historical_rel(CH002_ORIGINAL_JSON_REL)


def ch002_original_md_path() -> Path:
    return historical_rel(CH002_ORIGINAL_MD_REL)


def ch002_historical_lock_path() -> Path:
    return historical_rel(CH002_LOCK_REL)


def ch002_recovery_validation_path() -> Path:
    return historical_rel(CH002_RECOVERY_VALIDATION_REL)


def ch003_historical_lock_path() -> Path:
    return historical_rel(CH003_HISTORICAL_LOCK_REL)


def ch004_historical_lock_path() -> Path:
    return historical_rel(CH004_HISTORICAL_LOCK_REL)


def resume_plan_path() -> Path:
    return historical_rel(RESUME_PLAN_REL)


def ch012_accepted_manifest_path(*, root: Path | None = None) -> Path:
    del root
    return historical_rel(CH012_MANIFEST_REL)


def ch018_accepted_manifest_path(*, root: Path | None = None) -> Path:
    del root
    return historical_rel(CH018_MANIFEST_REL)


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
    "batch_lock_path",
    "ch001_approved_json_path",
    "ch001_approved_md_path",
    "ch001_historical_lock_path",
    "ch001_structural_path",
    "ch002_approved_json_path",
    "ch002_approved_md_path",
    "ch002_historical_lock_path",
    "ch002_original_json_path",
    "ch002_original_md_path",
    "ch002_recovery_validation_path",
    "ch003_historical_lock_path",
    "ch004_historical_lock_path",
    "ch012_accepted_manifest_path",
    "ch018_accepted_manifest_path",
    "ch018_json_path",
    "ch018_lock_path",
    "ch018_md_path",
    "chapter_audit_dir",
    "forensic_root",
    "historical_prompt_paths",
    "historical_rel",
    "lock_path",
    "phase_audit_dir",
    "production_book_path",
    "production_cache_module_path",
    "production_map_path",
    "production_plan_path",
    "production_transcript_path",
    "report_path",
    "repo_root",
    "resume_plan_path",
    "venv_python_path",
]
