"""Evidence association. Missing proof is BLOCK. Never invent a handle."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_generation.constants import PARAGRAPH_KIND_SUBSTANTIVE
from app.book_generation_integration_4b213.constants import (
    DECISION_BLOCK,
    DECISION_PASS,
    PHASE,
    SYNTHETIC_PREFIX,
)
from app.file_utils import content_hash


def evidence_bundle_hash(handles: Sequence[str]) -> str:
    ordered = sorted({str(item).strip() for item in handles if str(item).strip()})
    return content_hash("|".join(ordered))


def validate_paragraph_evidence(
    paragraph: Mapping[str, Any],
    *,
    allowed_handles: Sequence[str],
    synthetic_chapter: bool,
) -> dict[str, Any]:
    errors: list[str] = []
    pid = str(paragraph.get("paragraph_id") or "")
    kind = str(paragraph.get("kind") or "")
    handles = [
        str(item).strip()
        for item in (paragraph.get("evidence_handles") or [])
        if str(item).strip()
    ]
    allowed_set = {str(item).strip() for item in allowed_handles if str(item).strip()}
    if kind == PARAGRAPH_KIND_SUBSTANTIVE and not handles:
        errors.append("missing_required_evidence")
    for handle in handles:
        if handle not in allowed_set:
            errors.append(f"unknown_evidence_handle:{handle}")
        if synthetic_chapter and not handle.startswith(SYNTHETIC_PREFIX):
            errors.append(f"real_handle_on_synthetic_fixture:{handle}")
    ok = not errors
    return {
        "phase": PHASE,
        "ok": ok,
        "status": DECISION_PASS if ok else DECISION_BLOCK,
        "paragraph_id": pid,
        "kind": kind,
        "evidence_handles": handles,
        "errors": errors,
        "does_not_invent_evidence": True,
        "bundle_hash": evidence_bundle_hash(handles),
        "secrets_included": False,
    }


__all__ = ["evidence_bundle_hash", "validate_paragraph_evidence"]
