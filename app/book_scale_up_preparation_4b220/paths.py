"""Isolated 4B.2.20 audit paths. Never production book.json."""

from __future__ import annotations

from pathlib import Path

from app.book_authorial_voice_4b218.paths import (
    historical_prompt_paths as historical_prompt_paths_4b218,
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
from app.book_editorial_acceptance_4b219.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    historical_4b217_report_path,
    historical_4b218_report_path,
)
from app.book_scale_up_preparation_4b220.constants import (
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


def historical_4b219_report_path() -> Path:
    return (
        audit_root()
        / "PHASE_4B219_CH012_EDITORIAL_ACCEPTANCE_"
        "AND_SEMANTIC_VALIDATION_READINESS_REPORT.md"
    )


def accepted_editorial_manifest_path() -> Path:
    return (
        audit_root()
        / "book_editorial_acceptance_4b219"
        / "ch012_accepted_editorial_manifest.json"
    )


def prompt_1_1_module_path() -> Path:
    return repo_root() / "app" / "book_authorial_voice_4b218" / "prompt_candidate.py"


def prompt_1_0_module_path() -> Path:
    return (
        repo_root() / "app" / "book_editorial_alignment_4b216" / "prompt_candidate.py"
    )


def production_prompt_select_path() -> Path:
    return repo_root() / "app" / "book_generation" / "prompt_select.py"


def historical_prompt_paths(*, root: Path | None = None) -> dict[str, Path]:
    paths = historical_prompt_paths_4b218(root=root)
    paths["faithful_prompt_1_1_candidate"] = prompt_1_1_module_path()
    paths["faithful_prompt_1_0_candidate"] = prompt_1_0_module_path()
    return paths


assert book_path(PROJECT_NAME) == production_book_path()
assert production_editorial_plan_path(PROJECT_NAME) == production_plan_path()
assert production_source_map_path(PROJECT_NAME) == production_map_path()
assert production_clean_transcript_path(PROJECT_NAME) == production_transcript_path()
assert _PROJECT_ROOT == repo_root()

__all__ = [
    "accepted_chapter_json_path",
    "accepted_chapter_md_path",
    "accepted_editorial_manifest_path",
    "audit_root",
    "historical_4b217_report_path",
    "historical_4b218_report_path",
    "historical_4b219_report_path",
    "historical_prompt_paths",
    "original_chapter_dir",
    "original_chapter_json_path",
    "original_chapter_md_path",
    "original_lock_path",
    "phase_audit_dir",
    "production_book_path",
    "production_map_path",
    "production_plan_path",
    "production_prompt_select_path",
    "production_transcript_path",
    "prompt_1_0_module_path",
    "prompt_1_1_module_path",
    "report_path",
    "repo_root",
    "venv_python_path",
]
