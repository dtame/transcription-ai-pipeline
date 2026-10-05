"""Atomic provisional publication. Refuse protected overwrite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.book_print_review_canonical_4b229.builder import render_book
from app.book_print_review_canonical_4b229.constants import (
    BOOK_STATUS,
    BOOK_VERSION,
    PHASE,
)
from app.book_print_review_canonical_4b229.guard import BookPrintReviewCanonical4229Error
from app.book_print_review_canonical_4b229.hashes import file_sha256
from app.file_utils import content_hash
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


def inspect_existing_book(path: Path) -> dict[str, Any]:
    hashed = file_sha256(path)
    if not hashed.get("exists"):
        return {
            "exists": False,
            "path": str(path).replace("\\", "/"),
            "sha256": "",
            "bytes": 0,
            "version": "",
            "status": "",
            "protected": False,
            "phase": "",
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BookPrintReviewCanonical4229Error(
            f"Existing book.json is not an object: {path}. STOP."
        )
    protection = payload.get("protection") if isinstance(payload.get("protection"), dict) else {}
    protected = protection.get("protected") is True
    status = str(payload.get("editorial_status") or "")
    if status and status != BOOK_STATUS:
        protected = True
    return {
        "exists": True,
        "path": str(path).replace("\\", "/"),
        "sha256": hashed.get("sha256") or "",
        "bytes": hashed.get("bytes") or 0,
        "version": str(payload.get("document_version") or ""),
        "status": str(payload.get("editorial_status") or ""),
        "protected": protected,
        "phase": str(payload.get("phase") or ""),
        "protection": protection,
    }


def assert_publication_allowed(existing: dict[str, Any], *, new_sha256: str) -> str:
    if not existing.get("exists"):
        return "create"
    if existing.get("protected"):
        raise BookPrintReviewCanonical4229Error(
            f"Protected canonical book.json already exists at {existing.get('path')} "
            f"(status={existing.get('status')!r}, version={existing.get('version')!r}). STOP."
        )
    same_phase = (
        existing.get("phase") == PHASE
        and existing.get("version") == BOOK_VERSION
        and existing.get("status") == BOOK_STATUS
    )
    if not same_phase:
        raise BookPrintReviewCanonical4229Error(
            f"Existing book.json at {existing.get('path')} is not a replaceable "
            f"{BOOK_STATUS} {BOOK_VERSION} artifact. STOP."
        )
    if existing.get("sha256") == new_sha256:
        return "idempotent"
    return "replace_same_phase_draft"


def publish_atomic(
    payload: dict[str, Any],
    *,
    destination: Path,
    audit_copy: Path,
) -> dict[str, Any]:
    rendered = render_book(payload)
    digest = content_hash(rendered)
    existing = inspect_existing_book(destination)
    action = assert_publication_allowed(existing, new_sha256=digest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    audit_copy.parent.mkdir(parents=True, exist_ok=True)
    if action != "idempotent":
        write_bytes_atomic(destination, rendered)
    write_bytes_atomic(audit_copy, rendered)
    leftover_dest = destination.with_name(destination.name + ".partial")
    leftover_audit = audit_copy.with_name(audit_copy.name + ".partial")
    if leftover_dest.exists() or leftover_audit.exists():
        raise BookPrintReviewCanonical4229Error("Atomic publication left a .partial file. STOP.")
    published = file_sha256(destination)
    copied = file_sha256(audit_copy)
    if published.get("sha256") != digest or copied.get("sha256") != digest:
        raise BookPrintReviewCanonical4229Error("Published book.json hash drifted. STOP.")
    return {
        "phase": PHASE,
        "action": action,
        "atomic": True,
        "destination": str(destination).replace("\\", "/"),
        "audit_copy": str(audit_copy).replace("\\", "/"),
        "sha256": digest,
        "bytes": published.get("bytes") or 0,
        "existing_before": existing,
        "canonical_used_by_next_steps": str(destination).replace("\\", "/"),
        "audit_copy_is_not_the_runtime_canonical": True,
        "docx_generated": False,
        "pdf_generated": False,
        "secrets_included": False,
    }


__all__ = [
    "assert_publication_allowed",
    "inspect_existing_book",
    "publish_atomic",
]
