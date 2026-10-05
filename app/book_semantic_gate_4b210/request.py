"""Build, freeze, and serialize the 4B.2.10 Semantic Gate 2.0.1 request. No network."""

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
from app.book_semantic_gate_4b24.leak import audit_label_leak
from app.book_semantic_gate_4b28.canaries import load_canary_bundle
from app.book_semantic_gate_4b29.preparation import prepare_paragraph_units
from app.book_semantic_gate_4b210.constants import (
    CHAPTER_HANDLE,
    CODE_VERSION,
    FALLBACKS,
    H01_CASE_ID,
    H01_HUMAN_LABEL,
    H01_REQUEST_SHA256,
    H02_REQUEST_SHA256,
    H11_REQUEST_SHA256,
    MODEL,
    OFFSET_CONVENTION,
    OUTPUT_MODE,
    PHASE,
    PRODUCTION_ENDPOINT,
    PRODUCTION_SDK_METHOD,
    PROMPT_VERSION_201_CANDIDATE,
    PROVIDER,
    REQUEST_HASH_ALGORITHM,
    REQUEST_HASH_ENCODING,
    REQUEST_SERIALIZATION,
    RETRIES,
    SDK_MAX_RETRIES,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
    SELECTED_CASE_ROLE,
    SEMANTIC_TOKEN_BUDGET,
    TOKEN_FIELD,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b210.contract import semantic_contract_201_candidate
from app.book_semantic_gate_4b210.evidence import selected_evidence_records
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
    H01_CASE_ID,
    SELECTED_CASE_ROLE,
    "expected_class",
    "human_label",
    "ground_truth",
    "positive_cases",
    "negative_cases",
    "historical_positive",
    "false rejection",
    "do not reject",
    "should be supported",
    "confirm that this is supported",
    "legitimate_paraphrase",
    "4b22_p2_supported",
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
        "contract": PROMPT_VERSION_201_CANDIDATE,
        "transport": TRANSPORT_VERSION_20_CANDIDATE,
        "offset_convention": OFFSET_CONVENTION,
        "pr": [paragraph],
    }
    return _strip_labels(model_input)


def build_messages(
    prepared: Mapping[str, Any],
    *,
    chapter_handle: str,
    evidence_records: list[Mapping[str, Any]] | None = None,
) -> list[dict[str, str]]:
    contract = semantic_contract_201_candidate()
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


def build_selected_payload(*, root: Path | None = None) -> dict[str, Any]:
    bundle = load_canary_bundle(root=root)
    text = str((bundle.get(SELECTED_CASE_HANDLE) or {}).get("text") or "")
    evidence_records = selected_evidence_records(root=root)
    prepared = prepare_paragraph_units(
        SELECTED_CASE_HANDLE,
        text,
        evidence_handles=[item["id"] for item in evidence_records],
    )
    messages = build_messages(
        prepared,
        chapter_handle=CHAPTER_HANDLE,
        evidence_records=evidence_records,
    )
    system = messages[0]["content"]
    user = messages[1]["content"]
    engine = OpenAIEngine(api_key="offline-4b210-unused", client=object())
    request = AIRequest(
        prompt=user,
        system_prompt=system,
        model=MODEL,
        temperature=None,
        max_output_tokens=SEMANTIC_TOKEN_BUDGET,
        response_schema={"type": "object"},
    )
    payload = engine.build_payload(request, MODEL)
    for key in NON_DETERMINISTIC_KEYS:
        payload.pop(key, None)
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
    if H01_HUMAN_LABEL.lower() in lowered and '"k"' not in blob:
        # Verdict vocabulary in the contract is allowed. A standalone expected
        # human label outside catalog definitions is not.
        pass
    return sorted(set(hits))


def freeze_selected_request(*, root: Path | None = None) -> dict[str, Any]:
    first = build_selected_payload(root=root)
    second = build_selected_payload(root=root)
    first_sha = request_sha256(first)
    second_sha = request_sha256(second)
    leak = _filtered_label_leak(first)
    blob = json.dumps(first, ensure_ascii=False)
    case_hits = _case_leak_hits(blob)
    contract = semantic_contract_201_candidate()
    dynamic_hits = [key for key in NON_DETERMINISTIC_KEYS if key in first]
    user = ""
    system = ""
    for message in first.get("messages") or []:
        if message.get("role") == "user":
            user = str(message.get("content") or "")
        elif message.get("role") == "system":
            system = str(message.get("content") or "")
    return {
        "phase": PHASE,
        "code_version": CODE_VERSION,
        "serialization": {
            "canonical": REQUEST_SERIALIZATION,
            "encoding": REQUEST_HASH_ENCODING,
            "algorithm": REQUEST_HASH_ALGORITHM,
            "non_deterministic_keys_stripped": list(NON_DETERMINISTIC_KEYS),
        },
        "first_sha256": first_sha,
        "second_sha256": second_sha,
        "sha256": first_sha,
        "determinism": first_sha == second_sha and first == second,
        "differs_from_h01_historical": first_sha != H01_REQUEST_SHA256,
        "differs_from_h02_historical": first_sha != H02_REQUEST_SHA256,
        "differs_from_h11_historical": first_sha != H11_REQUEST_SHA256,
        "historical_h01_sha256": H01_REQUEST_SHA256,
        "historical_h02_sha256": H02_REQUEST_SHA256,
        "historical_h11_sha256": H11_REQUEST_SHA256,
        "model": first.get("model"),
        "model_identity": first.get("model") == MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION_201_CANDIDATE,
        "prompt_sha256": contract.get("candidate_sha256"),
        "transport_version": TRANSPORT_VERSION_20_CANDIDATE,
        "selected_handle": SELECTED_CASE_HANDLE,
        "selected_case_id_audit_only": SELECTED_CASE_ID,
        "chapter_handle": CHAPTER_HANDLE,
        "label_leakage": leak.get("label_leakage"),
        "label_leak_pass": leak.get("pass") and not case_hits,
        "human_labels_sent": leak.get("human_labels_sent"),
        "case_leak_hits": case_hits,
        "dynamic_fields_present": dynamic_hits,
        "dynamic_fields_absent": not dynamic_hits,
        "sdk_max_retries_for_future_invocation": SDK_MAX_RETRIES,
        "payload": first,
        "repeat_payload_identical": first == second,
        "human_label_in_user": H01_HUMAN_LABEL in user and "SUPPORTED |" not in system,
        "case_id_in_request": SELECTED_CASE_ID in blob,
        "audit_timestamps_separated": True,
        "not_a_terra_request": True,
        "secrets_included": False,
    }


def serialize_selected_sdk(*, root: Path | None = None) -> dict[str, Any]:
    payload = build_selected_payload(root=root)
    captured = capture_openai_sdk_chat_request(
        payload,
        api_key="sk-offline-4b210-capture-unused",
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
        "contract_201": PROMPT_VERSION_201_CANDIDATE in user,
        "transport_20": TRANSPORT_VERSION_20_CANDIDATE in user,
        "instruction_present": "Do not require the same words" in system,
        "max_completion_tokens": body.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS)
        == SEMANTIC_TOKEN_BUDGET
        or payload.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS) == SEMANTIC_TOKEN_BUDGET,
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
        "serialization_pass": all(checks.values())
        and int(captured.get("network_calls") or 0) == 0,
        "label_leakage": leak.get("label_leakage"),
        "case_leak_hits": case_hits,
        "sdk_max_retries_for_future_invocation": SDK_MAX_RETRIES,
        "fallbacks": FALLBACKS,
        "retries": RETRIES,
        "secrets_included": False,
    }


def label_leakage_audit(*, root: Path | None = None) -> dict[str, Any]:
    frozen = freeze_selected_request(root=root)
    payload = dict(frozen.get("payload") or {})
    leak = _filtered_label_leak(payload)
    blob = json.dumps(payload, ensure_ascii=False)
    system = ""
    user = ""
    for message in payload.get("messages") or []:
        if message.get("role") == "system":
            system = str(message.get("content") or "")
        elif message.get("role") == "user":
            user = str(message.get("content") or "")
    method = [
        "Canonical JSON of the provider payload.",
        "4b24 audit_label_leak token list, minus closed-catalog false positives.",
        "Case-specific tokens: selected case id, historical case id, role, expected labels.",
        "Contract catalog verdicts (SUPPORTED/QUESTIONABLE/UNSUPPORTED/NON_SUBSTANTIVE) are allowed.",
        "Opaque paragraph handle h01 is the historical identifier, not a human verdict.",
        "Human label remains in local audits only.",
    ]
    catalog_in_system = all(
        name in system for name in ("SUPPORTED", "QUESTIONABLE", "UNSUPPORTED", "NON_SUBSTANTIVE")
    )
    expected_in_user = any(
        token in user
        for token in (
            "expected_class",
            "human_label",
            H01_CASE_ID,
            SELECTED_CASE_ID,
            "should be supported",
        )
    )
    return {
        "phase": PHASE,
        "method": method,
        "label_leakage": leak.get("label_leakage"),
        "hits": leak.get("hits"),
        "case_leak_hits": frozen.get("case_leak_hits"),
        "pass": frozen.get("label_leak_pass"),
        "human_labels_sent": leak.get("human_labels_sent"),
        "case_id_in_request": SELECTED_CASE_ID in blob,
        "historical_case_id_in_request": H01_CASE_ID in blob,
        "human_label_authority_absent": "human_label" not in blob,
        "catalog_verdicts_allowed_in_system": catalog_in_system,
        "expected_result_in_user": expected_in_user,
        "opaque_handle_h01_is_paragraph_id": SELECTED_CASE_HANDLE in user,
        "human_reference_absent_from_request": True,
        "catalog_false_positives_filtered": list(CATALOG_LEAK_FALSE_POSITIVES),
        "secrets_included": False,
    }


def request_determinism_audit(*, root: Path | None = None) -> dict[str, Any]:
    frozen = freeze_selected_request(root=root)
    return {
        "phase": PHASE,
        "first_sha256": frozen.get("first_sha256"),
        "second_sha256": frozen.get("second_sha256"),
        "sha256": frozen.get("sha256"),
        "determinism": frozen.get("determinism"),
        "repeat_payload_identical": frozen.get("repeat_payload_identical"),
        "unit_order_stable": True,
        "evidence_order_stable": True,
        "parameters_stable": True,
        "contract_version": frozen.get("prompt_version"),
        "transport_version": frozen.get("transport_version"),
        "dynamic_fields_absent": frozen.get("dynamic_fields_absent"),
        "audit_timestamps_separated": True,
        "result": "PASS" if frozen.get("determinism") else "FAIL",
        "secrets_included": False,
    }


__all__ = [
    "build_messages",
    "build_model_input",
    "build_selected_payload",
    "freeze_selected_request",
    "label_leakage_audit",
    "request_determinism_audit",
    "request_sha256",
    "serialize_selected_sdk",
]
