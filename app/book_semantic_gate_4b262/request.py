"""Build, serialize, and freeze the single-case compact request. No network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.ai.openai_compat import (
    TOKEN_PARAM_MAX_COMPLETION_TOKENS,
    TOKEN_PARAM_MAX_TOKENS,
    capture_openai_sdk_chat_request,
)
from app.book_semantic_gate_4b24.leak import audit_label_leak
from app.book_semantic_gate_4b261.complexity import extract_gate_input, extract_gate_paragraphs
from app.book_semantic_gate_4b261.evidence import load_4b26_bundle
from app.book_semantic_gate_4b261.strategies import _slice_gate_input, build_candidate_payload
from app.book_semantic_gate_4b262.constants import (
    CANDIDATE_PROMPT_VERSION,
    CANDIDATE_TRANSPORT_VERSION,
    EXPECTED_REQUEST_SHA256_4B26,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PRODUCTION_ENDPOINT,
    PRODUCTION_SDK_METHOD,
    PROVIDER,
    REQUEST_HASH_ALGORITHM,
    REQUEST_HASH_ENCODING,
    REQUEST_SERIALIZATION,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
    SEMANTIC_TOKEN_BUDGET,
    TOKEN_FIELD,
)
from app.book_semantic_gate_4b262.contract import (
    candidate_prompt_bundle,
    candidate_schema_identity,
)
from app.file_utils import content_hash


NON_DETERMINISTIC_KEYS = ("timeout", "request_id", "created", "timestamp", "id")


def slice_single_case_gate(gate: Mapping[str, Any]) -> dict[str, Any]:
    return _slice_gate_input(gate, [SELECTED_CASE_HANDLE])


def build_single_case_payload(*, root: Path | None = None) -> dict[str, Any]:
    bundle = load_4b26_bundle(root=root)
    gate = extract_gate_input(dict(bundle.get("payload") or {}))
    sliced = slice_single_case_gate(gate)
    payload = build_candidate_payload(
        sliced,
        max_completion_tokens=SEMANTIC_TOKEN_BUDGET,
    )
    for key in NON_DETERMINISTIC_KEYS:
        payload.pop(key, None)
    return payload


def request_sha256(payload: Mapping[str, Any]) -> str:
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def freeze_single_case_request(*, root: Path | None = None) -> dict[str, Any]:
    first = build_single_case_payload(root=root)
    second = build_single_case_payload(root=root)
    first_sha = request_sha256(first)
    second_sha = request_sha256(second)
    leak = audit_label_leak(first)
    paragraphs = extract_gate_paragraphs({"messages": first.get("messages")})
    if not paragraphs:
        gate = extract_gate_input(first)
        paragraphs = extract_gate_paragraphs(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "SEMANTIC_GATE_INPUT_JSON\n"
                        + json.dumps(gate, ensure_ascii=False, separators=(",", ":")),
                    }
                ]
            }
        )
    handles = [str(item.get("handle") or "") for item in paragraphs]
    prompt = candidate_prompt_bundle()
    schema = candidate_schema_identity()
    blob = json.dumps(first, ensure_ascii=False)
    dynamic_hits = [
        key for key in NON_DETERMINISTIC_KEYS if f'"{key}"' in blob and key in first
    ]
    return {
        "phase": PHASE,
        "serialization": {
            "canonical": REQUEST_SERIALIZATION,
            "encoding": REQUEST_HASH_ENCODING,
            "algorithm": REQUEST_HASH_ALGORITHM,
            "non_deterministic_keys_stripped": list(NON_DETERMINISTIC_KEYS),
        },
        "first_sha256": first_sha,
        "second_sha256": second_sha,
        "sha256": first_sha,
        "determinism": first_sha == second_sha,
        "differs_from_4b26": first_sha != EXPECTED_REQUEST_SHA256_4B26,
        "historical_4b26_sha256": EXPECTED_REQUEST_SHA256_4B26,
        "model": first.get("model"),
        "model_identity": first.get("model") == MODEL,
        "provider": PROVIDER,
        "prompt_version": CANDIDATE_PROMPT_VERSION,
        "prompt_sha256": prompt["prompt_sha256"],
        "transport_version": CANDIDATE_TRANSPORT_VERSION,
        "transport_sha256": schema["raw_schema_sha256"],
        "selected_handle": SELECTED_CASE_HANDLE,
        "selected_case_id_audit_only": SELECTED_CASE_ID,
        "handles_in_request": handles,
        "exactly_one_case": handles == [SELECTED_CASE_HANDLE],
        "label_leakage": leak.get("label_leakage"),
        "label_leak_pass": leak.get("pass"),
        "human_labels_sent": leak.get("human_labels_sent"),
        "dynamic_fields_present": dynamic_hits,
        "dynamic_fields_absent": not dynamic_hits,
        "payload": first,
        "repeat_payload_identical": first == second,
        "secrets_included": False,
    }


def serialize_single_case_sdk(*, root: Path | None = None) -> dict[str, Any]:
    payload = build_single_case_payload(root=root)
    captured = capture_openai_sdk_chat_request(payload)
    body = dict(captured.get("body") or {})
    messages = list(body.get("messages") or payload.get("messages") or [])
    user = ""
    for message in messages:
        if message.get("role") == "user":
            user = str(message.get("content") or "")
            break
    leak = audit_label_leak(body or payload)
    checks = {
        "exactly_one_case": SELECTED_CASE_HANDLE in user and "h02" not in user,
        "compact_contract": CANDIDATE_PROMPT_VERSION
        or "Do not emit pr[].c[].t" in (messages[0].get("content") if messages else ""),
        "compact_instruction_present": "Do not emit pr[].c[].t" in str(messages),
        "evidence_present": "src_text" in user or "SRC" in user,
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
    }
    compact_ok = (
        "Do not emit pr[].c[].t" in str(messages)
        or "Do not copy claim text" in str(messages)
    )
    checks["compact_contract"] = compact_ok
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
        "secrets_included": False,
    }


def request_identity(*, root: Path | None = None) -> dict[str, Any]:
    frozen = freeze_single_case_request(root=root)
    serialized = serialize_single_case_sdk(root=root)
    payload = dict(frozen.get("payload") or {})
    return {
        **frozen,
        "sdk": {
            "serialization_pass": serialized.get("serialization_pass"),
            "network_calls": serialized.get("network_calls"),
            "checks": serialized.get("checks"),
        },
        "local_compat": {
            "max_completion_tokens": payload.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS),
            "max_tokens_absent": TOKEN_PARAM_MAX_TOKENS not in payload,
            "temperature_absent": "temperature" not in payload,
            "thinking_absent": "thinking" not in payload,
            "json_object": payload.get("response_format") == {"type": OUTPUT_MODE},
        },
        "payload_omitted_from_this_view": True,
        "payload": payload,
    }


__all__ = [
    "build_single_case_payload",
    "freeze_single_case_request",
    "request_identity",
    "request_sha256",
    "serialize_single_case_sdk",
    "slice_single_case_gate",
]
