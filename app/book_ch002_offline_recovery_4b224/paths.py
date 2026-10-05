"""Isolated 4B.2.24 audit paths. Originals stay in the 4B.2.23 real audit."""

from __future__ import annotations

from pathlib import Path

from app.book_ch002_offline_recovery_4b224.constants import (
    AUDIT_DIRNAME,
    BATCH01_AUDIT_REL,
    CH012_MANIFEST_REL,
    CH018_MANIFEST_REL,
    REPORT_NAME,
)
from app.book_generation_4b223.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    accepted_editorial_manifest_path,
    ch018_json_path,
    ch018_lock_path,
    ch018_md_path,
    historical_prompt_paths,
    original_chapter_json_path,
    original_chapter_md_path,
    original_lock_path,
    production_book_path,
    production_cache_module_path,
    production_map_path,
    production_plan_path,
    production_transcript_path,
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


def venv_python_path(*, root: Path | None = None) -> Path:
    return _venv_python_path(root=root)


def batch01_dir(*, root: Path | None = None) -> Path:
    del root
    return repo_root() / Path(*BATCH01_AUDIT_REL.split("/"))


def batch01_chapter_dir(chapter_id: str, *, root: Path | None = None) -> Path:
    return batch01_dir(root=root) / "chapters" / chapter_id


def ch002_dir(*, root: Path | None = None) -> Path:
    return batch01_chapter_dir("CH002", root=root)


def ch001_dir(*, root: Path | None = None) -> Path:
    return batch01_chapter_dir("CH001", root=root)


def original_candidate_json_path(chapter_id: str, *, root: Path | None = None) -> Path:
    return batch01_chapter_dir(chapter_id, root=root) / "chapter_candidate.json"


def original_candidate_md_path(chapter_id: str, *, root: Path | None = None) -> Path:
    return batch01_chapter_dir(chapter_id, root=root) / "chapter_candidate.md"


def original_raw_response_path(chapter_id: str, *, root: Path | None = None) -> Path:
    return batch01_chapter_dir(chapter_id, root=root) / "provider_response_raw.json"


def original_structural_path(chapter_id: str, *, root: Path | None = None) -> Path:
    return batch01_chapter_dir(chapter_id, root=root) / "structural_validation.json"


def original_lock_file(chapter_id: str, *, root: Path | None = None) -> Path:
    return batch01_chapter_dir(chapter_id, root=root) / "call_lock.json"


def batch01_lock_path(*, root: Path | None = None) -> Path:
    return batch01_dir(root=root) / "batch_lock.json"


def batch01_summary_path(*, root: Path | None = None) -> Path:
    return batch01_dir(root=root) / "batch_summary.json"


def batch01_ledger_path(*, root: Path | None = None) -> Path:
    return batch01_dir(root=root) / "batch_budget_ledger.json"


def ch012_accepted_manifest_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / Path(*CH012_MANIFEST_REL.split("/"))


def ch018_accepted_manifest_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / Path(*CH018_MANIFEST_REL.split("/"))


assert _PROJECT_ROOT == repo_root()

__all__ = [
    "accepted_chapter_json_path",
    "accepted_chapter_md_path",
    "accepted_editorial_manifest_path",
    "audit_root",
    "batch01_chapter_dir",
    "batch01_dir",
    "batch01_ledger_path",
    "batch01_lock_path",
    "batch01_summary_path",
    "ch001_dir",
    "ch002_dir",
    "ch012_accepted_manifest_path",
    "ch018_accepted_manifest_path",
    "ch018_json_path",
    "ch018_lock_path",
    "ch018_md_path",
    "historical_prompt_paths",
    "original_candidate_json_path",
    "original_candidate_md_path",
    "original_chapter_json_path",
    "original_chapter_md_path",
    "original_lock_file",
    "original_lock_path",
    "original_raw_response_path",
    "original_structural_path",
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
