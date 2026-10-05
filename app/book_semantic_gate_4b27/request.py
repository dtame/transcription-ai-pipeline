"""Rebuild the frozen 4B.2.6.2 single-case request. No network."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.ai.contracts import AIRequest
from app.book_semantic_gate_4b261.complexity import extract_gate_input, extract_gate_paragraphs
from app.book_semantic_gate_4b27.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_EVIDENCE_HANDLES,
    EXPECTED_REQUEST_SHA256,
    MODEL,
    PHASE,
    SELECTED_CASE_HANDLE,
    SEMANTIC_TOKEN_BUDGET,
    STAGE_CANARY,
)
from app.book_semantic_gate_4b262.request import (
    freeze_single_case_request,
    request_sha256,
    serialize_single_case_sdk,
)
from app.book_semantic_gate_4b262.selection import evidence_manifest


def paragraph_context(*, root: Path | None = None) -> dict[str, Any]:
    frozen = freeze_single_case_request(root=root)
    payload = dict(frozen.get("payload") or {})
    paragraphs = extract_gate_paragraphs(payload)
    if not paragraphs:
        gate = extract_gate_input(payload)
        paragraphs = extract_gate_paragraphs({"candidate": gate.get("candidate")})
    texts = {
        str(item.get("handle") or ""): str(item.get("text") or "")
        for item in paragraphs
        if item.get("handle")
    }
    kinds = {
        str(item.get("handle") or ""): str(item.get("kind") or "substantive")
        for item in paragraphs
        if item.get("handle")
    }
    evidence = evidence_manifest(root=root)
    allowed = list(evidence.get("present_ids") or [])
    return {
        "payload": payload,
        "paragraph_texts": texts,
        "paragraph_kinds": kinds,
        "allowed_handles": allowed,
        "required_handles": [SELECTED_CASE_HANDLE],
        "evidence": evidence,
    }


def evidence_matches_manifest(evidence: Mapping[str, Any]) -> bool:
    present = set(str(item) for item in (evidence.get("present_ids") or []) if item)
    declared = set(str(item) for item in (evidence.get("declared_handles") or []) if item)
    expected = set(EXPECTED_EVIDENCE_HANDLES)
    return (
        bool(evidence.get("complete"))
        and present == expected
        and declared == expected
        and not evidence.get("missing_required_handles")
    )


def build_ai_request(payload: Mapping[str, Any]) -> AIRequest:
    system = ""
    user = ""
    for message in payload.get("messages") or []:
        if message.get("role") == "system":
            system = str(message.get("content") or "")
        elif message.get("role") == "user":
            user = str(message.get("content") or "")
    return AIRequest(
        prompt=user,
        system_prompt=system or None,
        model=str(payload.get("model") or MODEL),
        temperature=None,
        max_output_tokens=int(
            payload.get("max_completion_tokens") or SEMANTIC_TOKEN_BUDGET
        ),
        response_schema={"type": "object"},
        thinking_mode=None,
        effort=None,
        thinking_budget_tokens=None,
        metadata={
            "phase": PHASE,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "stage": STAGE_CANARY,
            "frozen_payload": dict(payload),
        },
    )


def freeze_and_identify(*, root: Path | None = None) -> dict[str, Any]:
    frozen = freeze_single_case_request(root=root)
    serialized = serialize_single_case_sdk(root=root)
    payload = dict(frozen.get("payload") or {})
    sha = str(frozen.get("sha256") or "")
    repeat = str(frozen.get("second_sha256") or "")
    identity_match = sha == EXPECTED_REQUEST_SHA256 and repeat == EXPECTED_REQUEST_SHA256
    return {
        **frozen,
        "expected_sha256": EXPECTED_REQUEST_SHA256,
        "identity_match": identity_match,
        "sdk": serialized,
        "ai_request": build_ai_request(payload),
        "recomputed_sha256": request_sha256(payload),
    }


__all__ = [
    "build_ai_request",
    "evidence_matches_manifest",
    "freeze_and_identify",
    "paragraph_context",
]
