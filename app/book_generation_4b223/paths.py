"""Isolated 4B.2.23 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_batch_preparation_4b222.paths import (
    ch018_dir,
    ch018_json_path,
    ch018_lock_path,
    ch018_md_path,
    ch018_report_path,
)
from app.book_generation.paths import (
    book_path,
    production_clean_transcript_path,
    production_editorial_plan_path,
    production_source_map_path,
)
from app.book_generation_4b223.constants import (
    AUDIT_DIRNAME,
    AUDIT_LOCK,
    AUDIT_REAL_PARENT,
    BATCH_LOCK_NAME,
    CH012_MANIFEST_REL,
    CH018_MANIFEST_REL,
    PREP_AUDIT_DIRNAME,
    PREP_ENVELOPE_NAME,
    PREP_INVENTORY_NAME,
    PREP_PLAN_NAME,
    PROJECT_NAME,
    REPORT_NAME,
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


def prep_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / PREP_AUDIT_DIRNAME


def batch_plan_path(*, root: Path | None = None) -> Path:
    return prep_dir(root=root) / PREP_PLAN_NAME


def batch_envelope_path(*, root: Path | None = None) -> Path:
    return prep_dir(root=root) / PREP_ENVELOPE_NAME


def remaining_inventory_path(*, root: Path | None = None) -> Path:
    return prep_dir(root=root) / PREP_INVENTORY_NAME


def ch012_accepted_manifest_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / CH012_MANIFEST_REL.replace("/", "\\") if False else (
        (root or repo_root()) / Path(*CH012_MANIFEST_REL.split("/"))
    )


def ch018_accepted_manifest_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / Path(*CH018_MANIFEST_REL.split("/"))


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
    "batch_envelope_path",
    "batch_lock_path",
    "batch_plan_path",
    "ch012_accepted_manifest_path",
    "ch018_accepted_manifest_path",
    "ch018_dir",
    "ch018_json_path",
    "ch018_lock_path",
    "ch018_md_path",
    "ch018_report_path",
    "chapter_audit_dir",
    "forensic_root",
    "historical_prompt_paths",
    "lock_path",
    "original_chapter_json_path",
    "original_chapter_md_path",
    "original_lock_path",
    "phase_audit_dir",
    "prep_dir",
    "production_book_path",
    "production_cache_module_path",
    "production_map_path",
    "production_plan_path",
    "production_transcript_path",
    "remaining_inventory_path",
    "report_path",
    "repo_root",
    "venv_python_path",
]
