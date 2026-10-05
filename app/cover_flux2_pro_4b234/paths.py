"""Audit paths for phase 4B.2.34. Publication files stay read-only."""

from __future__ import annotations

from pathlib import Path

from app.cover_flux2_pro_4b234.constants import AUDIT_DIRNAME, REPORT_NAME
from app.cover_generator_foundation_4b233.paths import repo_root


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit" / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit" / REPORT_NAME


__all__ = ["phase_audit_dir", "report_path"]
