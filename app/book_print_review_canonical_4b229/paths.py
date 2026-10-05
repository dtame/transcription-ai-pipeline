"""4B.2.29 paths. Official book.json is the production analysis artifact."""

from __future__ import annotations

from pathlib import Path

from app.book_full_manuscript_review_4b228.paths import (
    ch001_approved_json_path,
    ch001_approved_md_path,
    ch001_existing_manifest_path,
    ch002_approved_json_path,
    ch002_approved_md_path,
    ch002_existing_manifest_path,
    ch002_original_json_path,
    ch002_original_md_path,
    ch003_accepted_manifest_path,
    ch003_approved_json_path,
    ch003_approved_md_path,
    ch004_accepted_manifest_path,
    ch004_approved_json_path,
    ch004_approved_md_path,
    ch012_accepted_manifest_path,
    ch012_original_json_path,
    ch012_original_md_path,
    ch018_accepted_manifest_path,
    ch018_json_path,
    ch018_md_path,
    historical_rel as _historical_rel,
    remaining13_chapter_dir,
    remaining13_json_path,
    remaining13_md_path,
    repo_root as _repo_root,
    venv_python_path as _venv_python_path,
)
from app.book_generation.paths import book_path
from app.book_print_review_canonical_4b229.constants import (
    AUDIT_DIRNAME,
    MANUSCRIPT_REL,
    PROJECT_NAME,
    REPORT_NAME,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _repo_root()


def historical_rel(relative: str, *, root: Path | None = None) -> Path:
    if root is None:
        return _historical_rel(relative)
    return (root or repo_root()) / Path(*relative.split("/"))


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def manuscript_path(*, root: Path | None = None) -> Path:
    return historical_rel(MANUSCRIPT_REL, root=root)


def production_book_path(*, root: Path | None = None) -> Path:
    if root is None:
        return book_path(PROJECT_NAME)
    return root / "sortie" / PROJECT_NAME / "analysis" / "book.json"


def audit_book_copy_path(*, root: Path | None = None) -> Path:
    return phase_audit_dir(root=root) / "book.json"


def venv_python_path(*, root: Path | None = None) -> Path:
    return _venv_python_path(root=root)


assert _PROJECT_ROOT == repo_root()

__all__ = [
    "audit_book_copy_path",
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
    "remaining13_chapter_dir",
    "remaining13_json_path",
    "remaining13_md_path",
    "report_path",
    "repo_root",
    "venv_python_path",
]
