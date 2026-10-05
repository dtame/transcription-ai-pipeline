"""Publish print-review-v1.1 only. Never replace print-review-v1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_print_review_pagination_fix_4b232.constants import (
    BOOK_STATUS,
    OUTPUT_VERSION,
    PHASE,
    PUBLICATION_STATUS,
    SOURCE_VERSION,
)
from app.book_print_review_pagination_fix_4b232.guard import (
    BookPrintReviewPaginationFix4232Error,
    assert_not_v1_target,
    assert_publication_target_allowed,
)
from app.book_print_review_pagination_fix_4b232.hashes import file_sha256
from app.book_print_review_pagination_fix_4b232.paths import official_docx_path, official_pdf_path
from app.book_print_review_pagination_fix_4b232.writer import write_binary_atomic


def publish_print_review(
    *,
    finalized_docx: Path,
    pdf_path: Path | None,
    destination_docx: Path,
    destination_pdf: Path,
    allow_official: bool,
) -> dict[str, Any]:
    assert_not_v1_target(destination_docx)
    assert_not_v1_target(destination_pdf)
    assert_publication_target_allowed(destination_docx, allow_official=allow_official)
    if pdf_path is not None:
        assert_publication_target_allowed(destination_pdf, allow_official=allow_official)
    source = Path(finalized_docx)
    if not source.is_file():
        raise BookPrintReviewPaginationFix4232Error("finalized DOCX is missing. STOP.")
    data = source.read_bytes()
    digest = __import__("hashlib").sha256(data).hexdigest()
    destination_docx.parent.mkdir(parents=True, exist_ok=True)
    existing = file_sha256(destination_docx)
    action = "create"
    if existing.get("exists"):
        action = "idempotent" if existing.get("sha256") == digest else "replace_v11_draft"
    if action != "idempotent":
        write_binary_atomic(destination_docx, data)
    published = file_sha256(destination_docx)
    if published.get("sha256") != digest:
        raise BookPrintReviewPaginationFix4232Error("Published DOCX hash drifted. STOP.")
    leftover = destination_docx.with_name(destination_docx.name + ".partial")
    if leftover.exists():
        raise BookPrintReviewPaginationFix4232Error("Atomic publication left a .partial DOCX. STOP.")
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
            raise BookPrintReviewPaginationFix4232Error(
                "refusing to publish a non-PDF as the print-review PDF."
            )
        existing_pdf = file_sha256(destination_pdf)
        pdf_digest = __import__("hashlib").sha256(pdf_bytes).hexdigest()
        pdf_action = "create"
        if existing_pdf.get("exists"):
            pdf_action = (
                "idempotent" if existing_pdf.get("sha256") == pdf_digest else "replace_v11_draft"
            )
        if pdf_action != "idempotent":
            write_binary_atomic(destination_pdf, pdf_bytes)
        leftover_pdf = destination_pdf.with_name(destination_pdf.name + ".partial")
        if leftover_pdf.exists():
            raise BookPrintReviewPaginationFix4232Error(
                "Atomic publication left a .partial PDF. STOP."
            )
        published_pdf = file_sha256(destination_pdf)
        pdf_info = {
            "generated": True,
            "path": published_pdf.get("path"),
            "sha256": published_pdf.get("sha256"),
            "bytes": published_pdf.get("bytes"),
            "action": pdf_action,
        }
    return {
        "phase": PHASE,
        "action": action,
        "atomic": True,
        "publication_status": PUBLICATION_STATUS,
        "book_status": BOOK_STATUS,
        "source_version": SOURCE_VERSION,
        "output_version": OUTPUT_VERSION,
        "destination_docx": published.get("path"),
        "docx_sha256": published.get("sha256"),
        "docx_bytes": published.get("bytes"),
        "pdf": pdf_info,
        "official_docx_default": str(official_docx_path()).replace("\\", "/"),
        "official_pdf_default": str(official_pdf_path()).replace("\\", "/"),
        "overwrote_v1": False,
        "secrets_included": False,
    }


__all__ = ["publish_print_review"]
