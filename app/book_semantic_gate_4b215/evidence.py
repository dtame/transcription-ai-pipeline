"""Canonical h11 evidence. Read-only. No invented SRC. No human labels."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b215.constants import (
    H11_EVIDENCE,
    PHASE,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
)
from app.book_semantic_gate_4b276.evidence import build_canonical_evidence_inventory


def selected_evidence_records(*, root: Path | None = None) -> list[dict[str, str]]:
    inventory = build_canonical_evidence_inventory(root=root)
    by_id: dict[str, str] = {}
    for idea in inventory.get("ideas") or []:
        handle = str(idea.get("id") or "")
        text = str(idea.get("exact_text") or idea.get("gate_request_text") or "")
        if handle:
            by_id[handle] = text
    for src in inventory.get("src") or []:
        handle = str(src.get("id") or "")
        text = str(src.get("exact_text") or src.get("gate_request_text") or "")
        if handle:
            by_id[handle] = text
    records = []
    for handle in H11_EVIDENCE:
        records.append({"id": handle, "text": by_id.get(handle, "")})
    return records


def selected_evidence_audit(*, root: Path | None = None) -> dict[str, Any]:
    inventory = build_canonical_evidence_inventory(root=root)
    records = selected_evidence_records(root=root)
    missing = [item["id"] for item in records if not str(item.get("text") or "").strip()]
    return {
        "phase": PHASE,
        "handle": SELECTED_CASE_HANDLE,
        "case_id_audit_only": SELECTED_CASE_ID,
        "allowed_handles": list(H11_EVIDENCE),
        "records": records,
        "complete": not missing,
        "missing_texts": missing,
        "neighboring_canonical_src_not_sent": True,
        "inventory_allowed_handles": inventory.get("allowed_handles_in_request"),
        "canonical_hashes": inventory.get("canonical_hashes"),
        "external_religious_knowledge_used": False,
        "fabricated_evidence_added": False,
        "secrets_included": False,
    }


__all__ = ["selected_evidence_audit", "selected_evidence_records"]
