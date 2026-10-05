"""Output paths for the print-review covers. The interior stays untouched."""

from __future__ import annotations

from pathlib import Path

from app.cover_generator_foundation_4b233.paths import (
    author_library_root,
    interior_docx_path,
    interior_pdf_path,
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.cover_print_ready_4b235.constants import (
    AUDIT_DIRNAME,
    BACK_DOCX_NAME,
    BACK_FIELD_NAME,
    BACK_PDF_NAME,
    BACK_PREVIEW_NAME,
    CONTACT_SHEET_NAME,
    COVER_RECORD_NAME,
    FRONT_DOCX_NAME,
    FRONT_PDF_NAME,
    FRONT_PREVIEW_NAME,
    IMAGE_NAME,
    OUTPUT_REL,
    PREPARED_IMAGE_NAME,
    PROJECT_NAME,
    REPORT_NAME,
    VALIDATION_NAME,
)


def output_dir(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / OUTPUT_REL


def generated_image_path(*, root: Path | None = None) -> Path:
    return (
        (root or repo_root())
        / "sortie"
        / PROJECT_NAME
        / "publication"
        / "covers"
        / "generated"
        / IMAGE_NAME
    )


def prepared_image_path(*, root: Path | None = None) -> Path:
    return output_dir(root=root) / PREPARED_IMAGE_NAME


def back_field_path(*, root: Path | None = None) -> Path:
    return output_dir(root=root) / BACK_FIELD_NAME


def front_docx_path(*, root: Path | None = None) -> Path:
    return output_dir(root=root) / FRONT_DOCX_NAME


def front_pdf_path(*, root: Path | None = None) -> Path:
    return output_dir(root=root) / FRONT_PDF_NAME


def back_docx_path(*, root: Path | None = None) -> Path:
    return output_dir(root=root) / BACK_DOCX_NAME


def back_pdf_path(*, root: Path | None = None) -> Path:
    return output_dir(root=root) / BACK_PDF_NAME


def front_preview_path(*, root: Path | None = None) -> Path:
    return output_dir(root=root) / FRONT_PREVIEW_NAME


def back_preview_path(*, root: Path | None = None) -> Path:
    return output_dir(root=root) / BACK_PREVIEW_NAME


def contact_sheet_path(*, root: Path | None = None) -> Path:
    return output_dir(root=root) / CONTACT_SHEET_NAME


def cover_record_path(*, root: Path | None = None) -> Path:
    return output_dir(root=root) / COVER_RECORD_NAME


def validation_path(*, root: Path | None = None) -> Path:
    return output_dir(root=root) / VALIDATION_NAME


def phase_audit_dir(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit" / AUDIT_DIRNAME


def report_path(*, root: Path | None = None) -> Path:
    return (root or repo_root()) / "audit" / REPORT_NAME


__all__ = [
    "author_library_root",
    "back_docx_path",
    "back_field_path",
    "back_pdf_path",
    "back_preview_path",
    "contact_sheet_path",
    "cover_record_path",
    "front_docx_path",
    "front_pdf_path",
    "front_preview_path",
    "generated_image_path",
    "interior_docx_path",
    "interior_pdf_path",
    "output_dir",
    "phase_audit_dir",
    "prepared_image_path",
    "production_book_path",
    "report_path",
    "repo_root",
    "validation_path",
    "venv_python_path",
]
