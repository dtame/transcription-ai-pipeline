"""Load historical canary payloads and paragraph texts. Read-only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.book_semantic_gate_4b27.request import paragraph_context as h01_paragraph_context
from app.book_semantic_gate_4b271.evidence import load_saved_terra_payload as load_h01_payload
from app.book_semantic_gate_4b272.identity import load_p3_gate_paragraph
from app.book_semantic_gate_4b274.claims import load_saved_h02_payload
from app.book_semantic_gate_4b277.request import paragraph_context as h11_paragraph_context
from app.book_semantic_gate_4b28.constants import (
    H01_CASE_HANDLE,
    H02_CASE_HANDLE,
    H11_CASE_HANDLE,
)
from app.book_semantic_gate_4b28.paths import historical_h11_dir


def load_h11_payload(*, root: Path | None = None) -> dict[str, Any]:
    path = historical_h11_dir(root=root) / "provider_response_raw.json"
    if not path.is_file():
        return {"MISSING_HISTORICAL_EVIDENCE": str(path).replace("\\", "/")}
    payload = json.loads(path.read_text(encoding="utf-8"))
    parsed = payload.get("parsed")
    if not isinstance(parsed, dict):
        return {"MISSING_HISTORICAL_EVIDENCE": "parsed_object"}
    return parsed


def _claims_for(payload: dict[str, Any], handle: str) -> list[dict[str, Any]]:
    for para in payload.get("pr") or []:
        if str(para.get("h") or "") == handle:
            return list(para.get("c") or [])
    return []


def _paragraph_verdict(payload: dict[str, Any], handle: str) -> str:
    for para in payload.get("pr") or []:
        if str(para.get("h") or "") == handle:
            return str(para.get("v") or "")
    return ""


def load_canary_bundle(*, root: Path | None = None) -> dict[str, Any]:
    h01_payload = load_h01_payload(root=root)
    h02_payload = load_saved_h02_payload(root=root)
    h11_payload = load_h11_payload(root=root)
    h01_text = str(
        (h01_paragraph_context(root=root).get("paragraph_texts") or {}).get(
            H01_CASE_HANDLE
        )
        or ""
    )
    h02_text = str(load_p3_gate_paragraph(root=root).get("text") or "")
    h11_text = str(
        (h11_paragraph_context(root=root).get("paragraph_texts") or {}).get(
            H11_CASE_HANDLE
        )
        or ""
    )
    return {
        "h01": {
            "handle": H01_CASE_HANDLE,
            "text": h01_text,
            "payload": h01_payload,
            "claims": _claims_for(h01_payload, H01_CASE_HANDLE),
            "paragraph_verdict": _paragraph_verdict(h01_payload, H01_CASE_HANDLE),
            "global_verdict": str(h01_payload.get("v") or ""),
        },
        "h02": {
            "handle": H02_CASE_HANDLE,
            "text": h02_text,
            "payload": h02_payload,
            "claims": _claims_for(h02_payload, H02_CASE_HANDLE),
            "paragraph_verdict": _paragraph_verdict(h02_payload, H02_CASE_HANDLE),
            "global_verdict": str(h02_payload.get("v") or ""),
        },
        "h11": {
            "handle": H11_CASE_HANDLE,
            "text": h11_text,
            "payload": h11_payload,
            "claims": _claims_for(h11_payload, H11_CASE_HANDLE),
            "paragraph_verdict": _paragraph_verdict(h11_payload, H11_CASE_HANDLE),
            "global_verdict": str(h11_payload.get("v") or ""),
        },
    }


__all__ = ["load_canary_bundle", "load_h11_payload"]
