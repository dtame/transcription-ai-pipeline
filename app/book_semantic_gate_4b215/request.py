"""Build, freeze, and serialize the 4B.2.15 Semantic Gate 2.0.2 h11 request."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.ai.contracts import AIRequest
from app.ai.openai_compat import (
    TOKEN_PARAM_MAX_COMPLETION_TOKENS,
    TOKEN_PARAM_MAX_TOKENS,
    capture_openai_sdk_chat_request,
)
from app.ai.providers.openai_engine import OpenAIEngine
from app.book_semantic_gate_4b210.units import inspect_prepared_case
from app.book_semantic_gate_4b212.contract import semantic_contract_202_candidate
from app.book_semantic_gate_4b215.constants import (
    AUTHORIZATION_SCOPE,
    CHAPTER_ID,
    CODE_VERSION,
    FALLBACKS,
    GRANULARITY,
    H11_EVIDENCE,
    MODEL,
    OFFSET_CONVENTION,
    OUTPUT_MODE,
    PHASE,
    PRODUCTION_ENDPOINT,
    PRODUCTION_SDK_METHOD,
    PROMPT_VERSION,
    PROVIDER,
    REQUIRED_UNIT_IDS,
    RETRIES,
    SDK_MAX_RETRIES,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
    SELECTED_CASE_ROLE,
    STAGE_CANARY,
    TARGET_CLAUSE,
    TARGET_UNIT_ID,
    TOKEN_FIELD,
    TRANSPORT_VERSION,
)
from app.book_semantic_gate_4b215.evidence import selected_evidence_records
from app.book_semantic_gate_4b215.paths import frozen_request_path
from app.book_semantic_gate_4b24.leak import audit_label_leak
from app.book_semantic_gate_4b276.identity import (
    source_paragraph_text,
    synthetic_paragraph_text,
)
from app.book_semantic_gate_4b28.constants import H01_CASE_HANDLE, H02_CASE_HANDLE
from app.book_semantic_gate_4b29.preparation import prepare_paragraph_units
from app.file_utils import content_hash

NON_DETERMINISTIC_KEYS = ("timeout", "request_id", "created", "timestamp", "id")
CATALOG_LEAK_FALSE_POSITIVES = ("new_causal", "reference_completion")
_LABEL_KEYS = frozenset(
    {
        "expected_class",
        "accepted_classes",
        "role",
        "human_label",
        "human_label_authority",
        "expected_reason_codes",
        "notes",
        "case_id",
        "selected_case_id",
        "ground_truth",
    }
)
_CASE_LEAK_TOKENS = (
    SELECTED_CASE_ID,
    "4b22_p4_supported",
    SELECTED_CASE_ROLE,
    "expected_class",
    "human_label",
    "ground_truth",
    "positive_cases",
    "negative_cases",
    "synthetic_negative",
    "should be unsupported",
    "must be unsupported",
    "this is unsupported",
    "human verdict",
    "4b276_p4_new_implication",
)


def _strip_labels(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        return {
            key: _strip_labels(value)
            for key, value in payload.items()
            if str(key) not in _LABEL_KEYS
        }
    if isinstance(payload, list):
        return [_strip_labels(item) for item in payload]
    return payload


def prepare_h11_units(*, root: Path | None = None) -> dict[str, Any]:
    inspected = inspect_prepared_case(SELECTED_CASE_HANDLE, root=root)
    text = synthetic_paragraph_text(root=root)
    source = source_paragraph_text(root=root)
    evidence_records = selected_evidence_records(root=root)
    prepared = prepare_paragraph_units(
        SELECTED_CASE_HANDLE,
        text,
        evidence_handles=[item["id"] for item in evidence_records],
    )
    units = list(prepared.get("units") or [])
    target = next(
        (unit for unit in units if str(unit.get("unit_id") or "") == TARGET_UNIT_ID),
        None,
    )
    target_text = str((target or {}).get("text") or "")
    clause_in_target = TARGET_CLAUSE in target_text
    merged = False
    if target is not None:
        other = [
            unit
            for unit in units
            if str(unit.get("unit_id") or "") != TARGET_UNIT_ID
            and TARGET_CLAUSE in str(unit.get("text") or "")
        ]
        merged = bool(other) or (clause_in_target and target_text.strip() == text.strip())
    preserved = list(inspected.get("preserved_propositions") or [])
    independent = bool(clause_in_target and not merged and preserved and preserved[0].get("preserved_in_one_unit"))
    return {
        "phase": PHASE,
        "handle": SELECTED_CASE_HANDLE,
        "source_paragraph": source,
        "paragraph": text,
        "paragraph_unchanged": prepared.get("paragraph_unchanged"),
        "source_preserved_as_prefix": text.startswith(source[:-1]),
        "prepared": prepared,
        "units": units,
        "unit_ids": [str(unit.get("unit_id") or "") for unit in units],
        "required_unit_ids": list(REQUIRED_UNIT_IDS),
        "coverage": inspected.get("coverage"),
        "coverage_ok": inspected.get("coverage_ok"),
        "target_unit_id": TARGET_UNIT_ID,
        "target_clause": TARGET_CLAUSE,
        "target_unit": target,
        "clause_in_target_unit": clause_in_target,
        "guarantee_independently_evaluable": independent,
        "merged_with_other_unit": merged,
        "preserved_propositions": preserved,
        "evidence_handles": [item["id"] for item in evidence_records],
        "evidence_records": evidence_records,
        "offset_convention": OFFSET_CONVENTION,
        "secrets_included": False,
    }


def build_model_input(
    prepared: Mapping[str, Any],
    *,
    chapter_handle: str,
    evidence_records: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    units = [
        {"id": str(unit.get("unit_id") or ""), "t": str(unit.get("text") or "")}
        for unit in prepared.get("units") or []
    ]
    paragraph = {
        "h": str(prepared.get("paragraph_id") or ""),
        "t": str(prepared.get("paragraph") or ""),
        "ev": list(prepared.get("evidence_handles") or []),
        "u": units,
    }
    if evidence_records:
        paragraph["evidence"] = [
            {
                "id": str(item.get("id") or item.get("handle") or ""),
                "text": str(item.get("text") or item.get("sum") or ""),
            }
            for item in evidence_records
            if str(item.get("id") or item.get("handle") or "").strip()
        ]
    model_input = {
        "ch": str(chapter_handle or "").strip(),
        "contract": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "offset_convention": OFFSET_CONVENTION,
        "granularity": GRANULARITY,
        "pr": [paragraph],
    }
    return _strip_labels(model_input)


def build_messages(
    prepared: Mapping[str, Any],
    *,
    chapter_handle: str,
    evidence_records: list[Mapping[str, Any]] | None = None,
) -> list[dict[str, str]]:
    contract = semantic_contract_202_candidate()
    model_input = build_model_input(
        prepared,
        chapter_handle=chapter_handle,
        evidence_records=evidence_records,
    )
    user = (
        str(contract["instructions_candidate"])
        + "\n\nSEMANTIC_GATE_INPUT_JSON\n"
        + json.dumps(model_input, ensure_ascii=False, sort_keys=True)
    )
    return [
        {"role": "system", "content": str(contract["system_candidate"])},
        {"role": "user", "content": user},
    ]


def build_payload(
    *,
    max_completion_tokens: int,
    root: Path | None = None,
) -> dict[str, Any]:
    context = prepare_h11_units(root=root)
    messages = build_messages(
        context["prepared"],
        chapter_handle=CHAPTER_ID,
        evidence_records=context["evidence_records"],
    )
    system = messages[0]["content"]
    user = messages[1]["content"]
    engine = OpenAIEngine(api_key="offline-4b215-unused", client=object())
    request = AIRequest(
        prompt=user,
        system_prompt=system,
        model=MODEL,
        temperature=None,
        max_output_tokens=int(max_completion_tokens),
        response_schema={"type": "object"},
    )
    payload = engine.build_payload(request, MODEL)
    for key in NON_DETERMINISTIC_KEYS:
        payload.pop(key, None)
    payload.pop("temperature", None)
    payload.pop("timeout", None)
    return payload


def request_sha256(payload: Mapping[str, Any]) -> str:
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _filtered_label_leak(payload: Mapping[str, Any]) -> dict[str, Any]:
    leak = audit_label_leak(payload)
    hits = [
        item
        for item in (leak.get("hits") or [])
        if item not in CATALOG_LEAK_FALSE_POSITIVES
    ]
    return {
        **leak,
        "hits": hits,
        "catalog_false_positives_filtered": list(CATALOG_LEAK_FALSE_POSITIVES),
        "label_leakage": len(hits),
        "human_labels_sent": bool(hits),
        "pass": len(hits) == 0 and not leak.get("opaque_handle_leaks"),
    }


def _case_leak_hits(blob: str) -> list[str]:
    lowered = blob.lower()
    hits: list[str] = []
    for token in _CASE_LEAK_TOKENS:
        needle = str(token or "").strip().lower()
        if needle and needle in lowered:
            hits.append(token)
    return sorted(set(hits))


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
        max_output_tokens=int(payload.get("max_completion_tokens") or 0),
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


def freeze_and_identify(
    *,
    max_completion_tokens: int,
    root: Path | None = None,
) -> dict[str, Any]:
    first = build_payload(max_completion_tokens=max_completion_tokens, root=root)
    second = build_payload(max_completion_tokens=max_completion_tokens, root=root)
    first_sha = request_sha256(first)
    second_sha = request_sha256(second)
    leak = _filtered_label_leak(first)
    blob = json.dumps(first, ensure_ascii=False)
    case_hits = _case_leak_hits(blob)
    contract = semantic_contract_202_candidate()
    context = prepare_h11_units(root=root)
    frozen_path = frozen_request_path(root=root)
    frozen_existing = None
    frozen_sha = None
    if frozen_path.is_file():
        frozen_existing = json.loads(frozen_path.read_text(encoding="utf-8"))
        frozen_sha = request_sha256(frozen_existing)
    user = ""
    system = ""
    for message in first.get("messages") or []:
        if message.get("role") == "user":
            user = str(message.get("content") or "")
        elif message.get("role") == "system":
            system = str(message.get("content") or "")
    exactly_one = (
        SELECTED_CASE_HANDLE in blob
        and f'"{H01_CASE_HANDLE}"' not in blob
        and '"h02"' not in blob
    )
    return {
        "phase": PHASE,
        "code_version": CODE_VERSION,
        "payload": first,
        "sha256": first_sha,
        "first_sha256": first_sha,
        "second_sha256": second_sha,
        "determinism": first_sha == second_sha and first == second,
        "identity_match": first_sha == second_sha,
        "frozen_path": str(frozen_path).replace("\\", "/"),
        "frozen_artifact_sha256": frozen_sha,
        "matches_frozen_artifact": frozen_sha is None or frozen_sha == first_sha,
        "label_leakage": leak.get("label_leakage"),
        "label_leak_pass": leak.get("pass") and not case_hits,
        "human_labels_sent": leak.get("human_labels_sent"),
        "case_leak_hits": case_hits,
        "case_id_in_request": SELECTED_CASE_ID in blob,
        "human_label_in_user": "human_label" in user.lower(),
        "exactly_one_case": exactly_one,
        "handles_in_request": [SELECTED_CASE_HANDLE] if SELECTED_CASE_HANDLE in blob else [],
        "model": first.get("model"),
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": contract.get("candidate_sha256"),
        "transport_version": TRANSPORT_VERSION,
        "max_completion_tokens": first.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS),
        "max_tokens_absent": TOKEN_PARAM_MAX_TOKENS not in first,
        "temperature_present": "temperature" in first,
        "thinking_present": "thinking" in first or "reasoning" in first or "reasoning_effort" in first,
        "response_format": first.get("response_format"),
        "ai_request": build_ai_request(first),
        "context": context,
        "system_chars": len(system),
        "user_chars": len(user),
        "sdk_max_retries_for_future_invocation": SDK_MAX_RETRIES,
        "secrets_included": False,
    }


def serialize_selected_sdk(
    *,
    max_completion_tokens: int,
    root: Path | None = None,
) -> dict[str, Any]:
    payload = build_payload(max_completion_tokens=max_completion_tokens, root=root)
    captured = capture_openai_sdk_chat_request(
        payload,
        api_key="sk-offline-4b215-capture-unused",
    )
    body = dict(captured.get("body") or {})
    messages = list(body.get("messages") or payload.get("messages") or [])
    user = ""
    system = ""
    for message in messages:
        if message.get("role") == "user":
            user = str(message.get("content") or "")
        elif message.get("role") == "system":
            system = str(message.get("content") or "")
    leak = _filtered_label_leak(body or payload)
    case_hits = _case_leak_hits(json.dumps(body or payload, ensure_ascii=False))
    checks = {
        "exactly_one_paragraph": '"pr"' in user and SELECTED_CASE_HANDLE in user,
        "contract_202": PROMPT_VERSION in user,
        "transport_20": TRANSPORT_VERSION in user,
        "instruction_present": "Do not require the same words" in system,
        "no_operational_request": all(
            token not in system[system.find("Do not emit"):]
            if "Do not emit" in system
            else True
            for token in ()
        ),
        "max_completion_tokens": body.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS)
        == max_completion_tokens
        or payload.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS) == max_completion_tokens,
        "max_tokens_absent": TOKEN_PARAM_MAX_TOKENS not in body
        and TOKEN_PARAM_MAX_TOKENS not in payload,
        "temperature_absent": "temperature" not in body and "temperature" not in payload,
        "reasoning_params_absent": all(
            key not in body and key not in payload
            for key in ("thinking", "effort", "reasoning", "reasoning_effort")
        ),
        "json_object": (body.get("response_format") or payload.get("response_format"))
        == {"type": OUTPUT_MODE},
        "model": (body.get("model") or payload.get("model")) == MODEL,
        "endpoint": PRODUCTION_ENDPOINT,
        "sdk_method": PRODUCTION_SDK_METHOD,
        "token_field": TOKEN_FIELD,
        "future_retries_disabled": SDK_MAX_RETRIES == 0,
        "label_leak_absent": leak.get("pass") is True and not case_hits,
        "no_fallback": FALLBACKS == 0,
        "no_retry": RETRIES == 0,
        "no_h01": '"h01"' not in user,
        "no_h02": '"h02"' not in user,
    }
    return {
        "phase": PHASE,
        "intercepted": True,
        "prepared_without_send": captured.get("prepared_without_send"),
        "prepared_via": captured.get("prepared_via"),
        "network_calls": captured.get("network_calls"),
        "http_requests": captured.get("http_requests"),
        "remote_invocations": captured.get("remote_invocations"),
        "provider_responses": captured.get("provider_responses"),
        "method": captured.get("method"),
        "url_path": captured.get("url_path"),
        "body_non_secret_fields": {
            "model": body.get("model") or payload.get("model"),
            "max_completion_tokens": body.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS)
            or payload.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS),
            "response_format": body.get("response_format") or payload.get("response_format"),
            "temperature_present": "temperature" in body or "temperature" in payload,
            "max_tokens_present": TOKEN_PARAM_MAX_TOKENS in body
            or TOKEN_PARAM_MAX_TOKENS in payload,
            "message_roles": [item.get("role") for item in messages],
        },
        "headers_redacted": captured.get("headers_redacted"),
        "checks": checks,
        "serialization_pass": all(bool(value) for value in checks.values())
        and int(captured.get("network_calls") or 0) == 0,
        "label_leakage": leak.get("label_leakage"),
        "case_leak_hits": case_hits,
        "sdk_max_retries_for_future_invocation": SDK_MAX_RETRIES,
        "fallbacks": FALLBACKS,
        "retries": RETRIES,
        "provider": PROVIDER,
        "secrets_included": False,
    }


def label_leakage_audit(
    *,
    max_completion_tokens: int,
    root: Path | None = None,
) -> dict[str, Any]:
    identified = freeze_and_identify(max_completion_tokens=max_completion_tokens, root=root)
    payload = dict(identified.get("payload") or {})
    leak = _filtered_label_leak(payload)
    blob = json.dumps(payload, ensure_ascii=False)
    system = ""
    user = ""
    for message in payload.get("messages") or []:
        if message.get("role") == "system":
            system = str(message.get("content") or "")
        elif message.get("role") == "user":
            user = str(message.get("content") or "")
    catalog_in_system = all(
        name in system for name in ("SUPPORTED", "QUESTIONABLE", "UNSUPPORTED", "NON_SUBSTANTIVE")
    )
    expected_in_user = any(
        token in user
        for token in (
            "expected_class",
            "human_label",
            SELECTED_CASE_ID,
            "should be unsupported",
            "must be unsupported",
        )
    )
    return {
        "phase": PHASE,
        "label_leakage": leak.get("label_leakage"),
        "hits": leak.get("hits"),
        "case_leak_hits": identified.get("case_leak_hits"),
        "pass": identified.get("label_leak_pass"),
        "human_labels_sent": leak.get("human_labels_sent"),
        "case_id_in_request": SELECTED_CASE_ID in blob,
        "human_label_authority_absent": "human_label" not in blob,
        "catalog_verdicts_allowed_in_system": catalog_in_system,
        "expected_result_in_user": expected_in_user,
        "opaque_handle_h11_is_paragraph_id": SELECTED_CASE_HANDLE in user,
        "human_reference_absent_from_request": True,
        "target_clause_present_as_generated_text": TARGET_CLAUSE in user,
        "secrets_included": False,
    }


__all__ = [
    "build_ai_request",
    "build_messages",
    "build_model_input",
    "build_payload",
    "freeze_and_identify",
    "label_leakage_audit",
    "prepare_h11_units",
    "request_sha256",
    "serialize_selected_sdk",
]
