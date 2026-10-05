"""Rebuild the frozen 4B.2.7.6 h11 request. No network. Do not mutate the freeze."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.ai.contracts import AIRequest
from app.book_semantic_gate_4b261.complexity import extract_gate_input, extract_gate_paragraphs
from app.book_semantic_gate_4b276.constants import AUDIT_REQUEST
from app.book_semantic_gate_4b276.evidence import build_canonical_evidence_inventory
from app.book_semantic_gate_4b276.request import (
    freeze_selected_request,
    request_sha256,
    serialize_selected_sdk,
)
from app.book_semantic_gate_4b277.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_REQUEST_SHA256,
    MODEL,
    P4_EVIDENCE_HANDLES,
    PHASE,
    SELECTED_CASE_HANDLE,
    SEMANTIC_TOKEN_BUDGET,
    STAGE_CANARY,
)
from app.book_semantic_gate_4b277.paths import frozen_4b276_dir


def paragraph_context(*, root: Path | None = None) -> dict[str, Any]:
    frozen = freeze_selected_request(root=root)
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
    inventory = build_canonical_evidence_inventory(root=root)
    allowed = list(inventory.get("present_ids") or list(P4_EVIDENCE_HANDLES))
    return {
        "payload": payload,
        "paragraph_texts": texts,
        "paragraph_kinds": kinds,
        "allowed_handles": allowed,
        "required_handles": [SELECTED_CASE_HANDLE],
        "evidence": inventory,
    }


def evidence_matches_manifest(inventory: Mapping[str, Any]) -> bool:
    present = set(str(item) for item in (inventory.get("present_ids") or []) if item)
    declared = set(
        str(item) for item in (inventory.get("allowed_handles_in_request") or []) if item
    )
    expected = set(P4_EVIDENCE_HANDLES)
    return (
        bool(inventory.get("complete"))
        and present == expected
        and declared == expected
        and not inventory.get("missing_required_handles")
        and not inventory.get("h01_handles_injected")
        and not inventory.get("h02_handles_injected")
        and inventory.get("fabricated_evidence_added") is False
    )


def load_frozen_4b276_payload(*, root: Path | None = None) -> dict[str, Any]:
    path = frozen_4b276_dir(root=root) / AUDIT_REQUEST
    return json.loads(path.read_text(encoding="utf-8"))


def frozen_artifact_sha(*, root: Path | None = None) -> str:
    return request_sha256(load_frozen_4b276_payload(root=root))


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
    frozen = freeze_selected_request(root=root)
    serialized = serialize_selected_sdk(root=root)
    payload = dict(frozen.get("payload") or {})
    sha = str(frozen.get("sha256") or "")
    repeat = str(frozen.get("second_sha256") or "")
    artifact_sha = frozen_artifact_sha(root=root)
    identity_match = (
        sha == EXPECTED_REQUEST_SHA256
        and repeat == EXPECTED_REQUEST_SHA256
        and artifact_sha == EXPECTED_REQUEST_SHA256
    )
    return {
        **frozen,
        "phase": PHASE,
        "frozen_source_phase": "4B.2.7.6",
        "expected_sha256": EXPECTED_REQUEST_SHA256,
        "frozen_artifact_sha256": artifact_sha,
        "identity_match": identity_match,
        "matches_frozen_4b276_artifact": artifact_sha == sha,
        "sdk": serialized,
        "ai_request": build_ai_request(payload),
        "recomputed_sha256": request_sha256(payload),
        "request_content_unmodified_by_retry_settings": True,
    }


__all__ = [
    "build_ai_request",
    "evidence_matches_manifest",
    "freeze_and_identify",
    "frozen_artifact_sha",
    "load_frozen_4b276_payload",
    "paragraph_context",
]
