"""Atomic print-review publication. Refuse protected overwrite. No fake PDF."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document

from app.book_print_review_render_4b231.constants import (
    BOOK_STATUS,
    BOOK_VERSION,
    PHASE,
    PUBLICATION_STATUS,
)
from app.book_print_review_render_4b231.guard import (
    BookPrintReviewRender4231Error,
    assert_publication_target_allowed,
)
from app.book_print_review_render_4b231.hashes import file_sha256
from app.book_print_review_render_4b231.paths import official_docx_path, official_pdf_path
from app.book_print_review_render_4b231.writer import write_binary_atomic


def inspect_existing_docx(path: Path) -> dict[str, Any]:
    hashed = file_sha256(path)
    if not hashed.get("exists"):
        return {
            "exists": False,
            "path": str(path).replace("\\", "/"),
            "sha256": "",
            "bytes": 0,
            "category": "",
            "subject": "",
            "protected": False,
        }
    category = ""
    subject = ""
    comments = ""
    try:
        doc = Document(path)
        category = str(doc.core_properties.category or "")
        subject = str(doc.core_properties.subject or "")
        comments = str(doc.core_properties.comments or "")
    except Exception:
        category = "UNREADABLE"
    protected = False
    if category and category != PUBLICATION_STATUS:
        protected = True
    if BOOK_VERSION not in subject and category not in {"", PUBLICATION_STATUS}:
        protected = True
    if "FINAL" in category.upper() and category != PUBLICATION_STATUS:
        protected = True
    return {
        "exists": True,
        "path": hashed.get("path"),
        "sha256": hashed.get("sha256"),
        "bytes": hashed.get("bytes"),
        "category": category,
        "subject": subject,
        "comments": comments,
        "protected": protected,
        "phase": PHASE,
    }


def assert_replace_allowed(existing: dict[str, Any], *, new_sha256: str) -> str:
    if not existing.get("exists"):
        return "create"
    if existing.get("protected"):
        raise BookPrintReviewRender4231Error(
            f"Protected publication already exists at {existing.get('path')} "
            f"(category={existing.get('category')!r}). STOP."
        )
    if existing.get("sha256") == new_sha256:
        return "idempotent"
    if existing.get("category") in {"", PUBLICATION_STATUS}:
        return "replace_same_phase_draft"
    raise BookPrintReviewRender4231Error(
        f"Existing file at {existing.get('path')} is not a replaceable "
        f"{BOOK_STATUS} {BOOK_VERSION} print-review draft. STOP."
    )


def publish_print_review(
    *,
    finalized_docx: Path,
    pdf_path: Path | None,
    destination_docx: Path,
    destination_pdf: Path,
    allow_official: bool,
) -> dict[str, Any]:
    assert_publication_target_allowed(destination_docx, allow_official=allow_official)
    if pdf_path is not None:
        assert_publication_target_allowed(destination_pdf, allow_official=allow_official)
    source = Path(finalized_docx)
    if not source.is_file():
        raise BookPrintReviewRender4231Error("finalized DOCX is missing. STOP.")
    data = source.read_bytes()
    digest = __import__("hashlib").sha256(data).hexdigest()
    existing = inspect_existing_docx(destination_docx)
    action = assert_replace_allowed(existing, new_sha256=digest)
    destination_docx.parent.mkdir(parents=True, exist_ok=True)
    if action != "idempotent":
        write_binary_atomic(destination_docx, data)
    published = file_sha256(destination_docx)
    if published.get("sha256") != digest:
        raise BookPrintReviewRender4231Error("Published DOCX hash drifted. STOP.")
    leftover = destination_docx.with_name(destination_docx.name + ".partial")
    if leftover.exists():
        raise BookPrintReviewRender4231Error("Atomic publication left a .partial DOCX. STOP.")
    pdf_info: dict[str, Any] = {
        "generated": False,
        "path": "",
        "sha256": "",
        "bytes": 0,
        "action": "skipped",
    }
    if pdf_path is not None and Path(pdf_path).is_file() and Path(pdf_path).stat().st_size > 0:
        pdf_bytes = Path(pdf_path).read_bytes()
        if not pdf_bytes.startswith(b"%PDF"):
            raise BookPrintReviewRender4231Error("refusing to publish a non-PDF as the print-review PDF.")
        existing_pdf = file_sha256(destination_pdf)
        pdf_digest = __import__("hashlib").sha256(pdf_bytes).hexdigest()
        pdf_action = "create"
        if existing_pdf.get("exists"):
            if existing_pdf.get("sha256") == pdf_digest:
                pdf_action = "idempotent"
            else:
                pdf_action = "replace_same_phase_draft"
        if pdf_action != "idempotent":
            write_binary_atomic(destination_pdf, pdf_bytes)
        leftover_pdf = destination_pdf.with_name(destination_pdf.name + ".partial")
        if leftover_pdf.exists():
            raise BookPrintReviewRender4231Error("Atomic publication left a .partial PDF. STOP.")
        published_pdf = file_sha256(destination_pdf)
        pdf_info = {
            "generated": True,
            "path": published_pdf.get("path"),
            "sha256": published_pdf.get("sha256"),
            "bytes": published_pdf.get("bytes"),
            "action": pdf_action,
        }
    elif destination_pdf.exists():
        raise BookPrintReviewRender4231Error(
            "A PDF path was requested without a finalized PDF. "
            "Refusing to create or keep a fake official PDF. STOP."
        )
    return {
        "phase": PHASE,
        "action": action,
        "atomic": True,
        "publication_status": PUBLICATION_STATUS,
        "book_status": BOOK_STATUS,
        "book_version": BOOK_VERSION,
        "destination_docx": published.get("path"),
        "docx_sha256": published.get("sha256"),
        "docx_bytes": published.get("bytes"),
        "existing_before": existing,
        "pdf": pdf_info,
        "official_docx_default": str(official_docx_path()).replace("\\", "/"),
        "official_pdf_default": str(official_pdf_path()).replace("\\", "/"),
        "secrets_included": False,
    }


__all__ = [
    "assert_replace_allowed",
    "inspect_existing_docx",
    "publish_print_review",
]
