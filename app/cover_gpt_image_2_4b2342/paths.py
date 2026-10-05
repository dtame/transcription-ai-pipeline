"""Audit paths for phase 4B.2.34.2. Publication files stay read-only."""

from __future__ import annotations

from pathlib import Path

from app.cover_generator_foundation_4b233.paths import repo_root
from app.cover_gpt_image_2_4b2342.constants import AUDIT_DIRNAME, REPORT_NAME


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit" / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit" / REPORT_NAME


def planned_image_path() -> str:
    """Named for a later authorized test. This phase does not create the file."""

    return (
        "audit/cover_generator_gpt_image_2_4b2342/"
        "planned_first_image/door_already_open.png"
    )


__all__ = ["phase_audit_dir", "planned_image_path", "report_path"]
