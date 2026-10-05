"""Load the frozen 4B.2.10 h01 request. No network. Do not mutate the freeze."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.ai.contracts import AIRequest
from app.book_semantic_gate_4b210.constants import AUDIT_REQUEST as FROZEN_REQUEST_NAME
from app.book_semantic_gate_4b210.evidence import selected_evidence_records
from app.book_semantic_gate_4b210.request import (
    freeze_selected_request,
    label_leakage_audit,
    request_determinism_audit,
    request_sha256,
    serialize_selected_sdk,
)
from app.book_semantic_gate_4b210.units import inspect_prepared_case
from app.book_semantic_gate_4b211.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_REQUEST_SHA256,
    H01_EVIDENCE_HANDLES,
    MODEL,
    PHASE,
    REQUIRED_UNIT_IDS,
    SELECTED_CASE_HANDLE,
    SEMANTIC_TOKEN_BUDGET,
    STAGE_CANARY,
    TARGET_CLAUSE,
    TARGET_UNIT_ID,
)
from app.book_semantic_gate_4b211.paths import frozen_4b210_dir


def load_frozen_4b210_payload(*, root: Path | None = None) -> dict[str, Any]:
    path = frozen_4b210_dir(root=root) / FROZEN_REQUEST_NAME
    return json.loads(path.read_text(encoding="utf-8"))


def frozen_artifact_sha(*, root: Path | None = None) -> str:
    return request_sha256(load_frozen_4b210_payload(root=root))


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


def paragraph_context(*, root: Path | None = None) -> dict[str, Any]:
    inspected = inspect_prepared_case(SELECTED_CASE_HANDLE, root=root)
    prepared = dict(inspected.get("prepared") or {})
    text = str(inspected.get("units") and prepared.get("paragraph") or "")
    if not text:
        text = str(prepared.get("paragraph") or "")
    units = list(prepared.get("units") or inspected.get("units") or [])
    records = selected_evidence_records(root=root)
    allowed = [str(item["id"]) for item in records]
    return {
        "prepared": prepared,
        "paragraph_text": text,
        "units": units,
        "unit_ids": [str(unit.get("unit_id") or "") for unit in units],
        "allowed_handles": allowed or list(H01_EVIDENCE_HANDLES),
        "evidence_records": records,
        "target_unit_id": TARGET_UNIT_ID,
        "target_clause": TARGET_CLAUSE,
        "required_unit_ids": list(REQUIRED_UNIT_IDS),
    }


def freeze_and_identify(*, root: Path | None = None) -> dict[str, Any]:
    rebuilt = freeze_selected_request(root=root)
    serialized = serialize_selected_sdk(root=root)
    leak = label_leakage_audit(root=root)
    determinism = request_determinism_audit(root=root)
    frozen_payload = load_frozen_4b210_payload(root=root)
    artifact_sha = request_sha256(frozen_payload)
    rebuilt_sha = str(rebuilt.get("sha256") or "")
    rebuilt_repeat = str(rebuilt.get("second_sha256") or "")
    identity_match = (
        artifact_sha == EXPECTED_REQUEST_SHA256
        and rebuilt_sha == EXPECTED_REQUEST_SHA256
        and rebuilt_repeat == EXPECTED_REQUEST_SHA256
    )
    blob = json.dumps(frozen_payload, ensure_ascii=False)
    return {
        **rebuilt,
        "phase": PHASE,
        "frozen_source_phase": "4B.2.10",
        "payload": frozen_payload,
        "rebuilt_payload": rebuilt.get("payload"),
        "sha256": artifact_sha,
        "first_sha256": rebuilt.get("first_sha256"),
        "second_sha256": rebuilt.get("second_sha256"),
        "rebuilt_sha256": rebuilt_sha,
        "expected_sha256": EXPECTED_REQUEST_SHA256,
        "frozen_artifact_sha256": artifact_sha,
        "identity_match": identity_match,
        "matches_frozen_4b210_artifact": artifact_sha == rebuilt_sha,
        "determinism": bool(rebuilt.get("determinism")) and bool(determinism.get("determinism")),
        "label_leakage": leak.get("label_leakage"),
        "label_leak_pass": leak.get("pass"),
        "human_labels_sent": leak.get("human_labels_sent"),
        "case_id_in_request": leak.get("case_id_in_request"),
        "sdk": serialized,
        "ai_request": build_ai_request(frozen_payload),
        "recomputed_sha256": artifact_sha,
        "request_content_unmodified_by_retry_settings": True,
        "exactly_one_case": SELECTED_CASE_HANDLE in blob and '"h02"' not in blob and '"h11"' not in blob,
        "handles_in_request": [SELECTED_CASE_HANDLE] if SELECTED_CASE_HANDLE in blob else [],
        "secrets_included": False,
    }


__all__ = [
    "build_ai_request",
    "freeze_and_identify",
    "frozen_artifact_sha",
    "load_frozen_4b210_payload",
    "paragraph_context",
]
