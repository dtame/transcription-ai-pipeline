"""Paths for the spiritual cover retry. The previous ledger stays untouched."""

from __future__ import annotations

from pathlib import Path

from app.cover_first_real_image_4b2344.paths import ledger_path as previous_ledger_path
from app.cover_first_real_image_4b2344_r1.constants import (
    AUDIT_DIRNAME,
    IMAGE_NAME,
    LEDGER_NAME,
    PROJECT_NAME,
    REPORT_NAME,
)
from app.cover_generator_foundation_4b233.paths import repo_root


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit" / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit" / REPORT_NAME


def generated_dir(*, root: Path | None = None) -> Path:
    return (
        (root or repo_root())
        / "sortie"
        / PROJECT_NAME
        / "publication"
        / "covers"
        / "generated"
    )


def image_path(*, root: Path | None = None) -> Path:
    return generated_dir(root=root) / IMAGE_NAME


def sidecar_path(*, root: Path | None = None) -> Path:
    return generated_dir(root=root) / (Path(IMAGE_NAME).stem + ".json")


def quarantine_path(*, root: Path | None = None) -> Path:
    return generated_dir(root=root) / "quarantine" / IMAGE_NAME


def ledger_path(*, root: Path | None = None) -> Path:
    return generated_dir(root=root) / LEDGER_NAME


def previous_phase_ledger_path(*, root: Path | None = None) -> Path:
    return previous_ledger_path(root=root)


__all__ = [
    "generated_dir",
    "image_path",
    "ledger_path",
    "phase_audit_dir",
    "previous_phase_ledger_path",
    "quarantine_path",
    "report_path",
    "sidecar_path",
]
