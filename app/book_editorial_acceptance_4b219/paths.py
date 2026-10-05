"""Isolated 4B.2.19 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_authorial_voice_4b218.paths import (
    historical_prompt_paths,
    original_chapter_dir,
    original_chapter_json_path,
    original_chapter_md_path,
    original_lock_path,
    production_book_path,
    production_map_path,
    production_plan_path,
    production_transcript_path,
    repo_root,
    venv_python_path,
)
from app.book_editorial_acceptance_4b219.constants import (
    ACCEPTED_JSON_NAME,
    ACCEPTED_MD_NAME,
    ACCEPTED_SOURCE_DIRNAME,
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

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def audit_root(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit"


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return audit_root(root=root) / REPORT_NAME


def accepted_chapter_dir() -> Path:
    return repo_root() / "audit" / ACCEPTED_SOURCE_DIRNAME


def accepted_chapter_json_path() -> Path:
    return accepted_chapter_dir() / ACCEPTED_JSON_NAME


def accepted_chapter_md_path() -> Path:
    return accepted_chapter_dir() / ACCEPTED_MD_NAME


def accepted_idea_proposals_path() -> Path:
    return accepted_chapter_dir() / "idea_paragraph_mapping_proposals.json"


def historical_4b217_report_path() -> Path:
    return audit_root() / "PHASE_4B217_CH012_FAITHFUL_REAL_PILOT_GENERATION_REPORT.md"


def historical_4b218_report_path() -> Path:
    return (
        audit_root()
        / "PHASE_4B218_AUTHORIAL_VOICE_PRESERVATION_AND_CH012_TARGETED_CORRECTION_REPORT.md"
    )


# Re-export production identity helpers so hashes stay aligned with 4B.2.18.
assert book_path(PROJECT_NAME) == production_book_path()
assert production_editorial_plan_path(PROJECT_NAME) == production_plan_path()
assert production_source_map_path(PROJECT_NAME) == production_map_path()
assert production_clean_transcript_path(PROJECT_NAME) == production_transcript_path()
assert _PROJECT_ROOT == repo_root()

__all__ = [
    "accepted_chapter_dir",
    "accepted_chapter_json_path",
    "accepted_chapter_md_path",
    "accepted_idea_proposals_path",
    "audit_root",
    "historical_4b217_report_path",
    "historical_4b218_report_path",
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
