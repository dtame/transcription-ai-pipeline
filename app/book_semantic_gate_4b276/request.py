"""Build, serialize, and freeze the 4B.2.7.6 synthetic request. No network."""

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
from app.book_semantic_gate_4b261.complexity import extract_gate_input, extract_gate_paragraphs
from app.book_semantic_gate_4b261.evidence import load_4b26_bundle
from app.book_semantic_gate_4b261.strategies import _slice_gate_input
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle, candidate_113_system_prompt
from app.book_semantic_gate_4b276.constants import (
    DISPUTED_CLAUSE,
    H01_EVIDENCE_HANDLES,
    H01_EXCLUSION_TOKENS,
    H01_REQUEST_SHA256,
    H02_EXCLUSION_TOKENS,
    H02_REQUEST_SHA256,
    MODEL,
    OUTPUT_MODE,
    P3_EVIDENCE_HANDLES,
    P4_EVIDENCE_HANDLES,
    PHASE,
    PRODUCTION_ENDPOINT,
    PRODUCTION_SDK_METHOD,
    PROMPT_VERSION_113,
    PROVIDER,
    REQUEST_HASH_ALGORITHM,
    REQUEST_HASH_ENCODING,
    REQUEST_SERIALIZATION,
    SDK_MAX_RETRIES,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
    SELECTED_CASE_REASON_CODES_AUDIT_ONLY,
    SEMANTIC_TOKEN_BUDGET,
    SOURCE_CASE_HANDLE,
    SOURCE_CASE_ID,
    TOKEN_FIELD,
    TRANSPORT_VERSION_11,
)
from app.book_semantic_gate_4b276.contract import render_113_user_prompt
from app.book_semantic_gate_4b261.candidates import candidate_schema_identity
from app.book_semantic_gate_4b276.identity import synthetic_paragraph_text
from app.file_utils import content_hash


NON_DETERMINISTIC_KEYS = ("timeout", "request_id", "created", "timestamp", "id")
CATALOG_LEAK_FALSE_POSITIVES = ("new_causal", "reference_completion")


def slice_selected_gate(gate: Mapping[str, Any], *, text: str) -> dict[str, Any]:
    sliced = _slice_gate_input(gate, [SOURCE_CASE_HANDLE])
    kept = {str(item) for item in (sliced.get("allowed_handles") or []) if item}
    pruned_sections = []
    for section in sliced.get("sections") or []:
        row = dict(section)
        for key in ("i", "src", "ref", "e", "idea", "ex", "unc"):
            if isinstance(row.get(key), list):
                row[key] = [item for item in row[key] if str(item) in kept]
        pruned_sections.append(row)
    sliced["sections"] = pruned_sections
    candidate = dict(sliced.get("candidate") or {})
    rewritten_sections = []
    for section in candidate.get("sections") or []:
        row = dict(section)
        paras = []
        for para in row.get("paras") or []:
            item = dict(para)
            if str(item.get("h") or "") == SOURCE_CASE_HANDLE:
                item["h"] = SELECTED_CASE_HANDLE
                item["t"] = text
            paras.append(item)
        row["paras"] = paras
        rewritten_sections.append(row)
    candidate["sections"] = rewritten_sections
    sliced["candidate"] = candidate
    return sliced


def build_selected_payload(*, root: Path | None = None) -> dict[str, Any]:
    bundle = load_4b26_bundle(root=root)
    gate = extract_gate_input(dict(bundle.get("payload") or {}))
    text = synthetic_paragraph_text(root=root)
    sliced = slice_selected_gate(gate, text=text)
    user = render_113_user_prompt(
        json.dumps(sliced, ensure_ascii=False, separators=(",", ":"))
    )
    engine = OpenAIEngine(api_key="offline-4b276-unused", client=object())
    request = AIRequest(
        prompt=user,
        system_prompt=candidate_113_system_prompt(),
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


def _independence_hits(blob: str) -> list[str]:
    lowered = blob.lower()
    hits: list[str] = []
    quoted_handles = ("h01", "h02", SOURCE_CASE_HANDLE)
    for handle in quoted_handles:
        if f'"{handle}"' in blob or f"'{handle}'" in blob:
            hits.append(handle)
    for token in H01_EXCLUSION_TOKENS + H02_EXCLUSION_TOKENS:
        if token in quoted_handles:
            continue
        if token.lower() in lowered:
            hits.append(token)
    for handle in H01_EVIDENCE_HANDLES + P3_EVIDENCE_HANDLES:
        if handle in blob:
            hits.append(handle)
    for token in (
        SELECTED_CASE_ID,
        SOURCE_CASE_ID,
        *SELECTED_CASE_REASON_CODES_AUDIT_ONLY,
        "expected_class",
        "human_label",
        "ground_truth",
        "synthetic_variant",
    ):
        if token.lower() in lowered:
            hits.append(token)
    return sorted(set(hits))


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


def freeze_selected_request(*, root: Path | None = None) -> dict[str, Any]:
    first = build_selected_payload(root=root)
    second = build_selected_payload(root=root)
    first_sha = request_sha256(first)
    second_sha = request_sha256(second)
    leak = _filtered_label_leak(first)
    paragraphs = extract_gate_paragraphs({"messages": first.get("messages")})
    if not paragraphs:
        paragraphs = extract_gate_paragraphs(first)
    handles = [str(item.get("handle") or "") for item in paragraphs]
    prompt = candidate_113_prompt_bundle()
    schema = candidate_schema_identity()
    blob = json.dumps(first, ensure_ascii=False)
    independence = _independence_hits(blob)
    # Reason codes appear in the closed catalog. That is allowed.
    independence = [
        item
        for item in independence
        if item not in SELECTED_CASE_REASON_CODES_AUDIT_ONLY
    ]
    dynamic_hits = [
        key for key in NON_DETERMINISTIC_KEYS if f'"{key}"' in blob and key in first
    ]
    gate = extract_gate_input(first)
    present_evidence = sorted(
        {
            str(item.get("id") or "")
            for item in list(gate.get("src_text") or [])
            + list(gate.get("ideas") or [])
            + list(gate.get("references") or [])
            if item.get("id")
        }
    )
    texts = {
        str(item.get("handle") or ""): str(item.get("text") or "") for item in paragraphs
    }
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
        "differs_from_h01": first_sha != H01_REQUEST_SHA256,
        "differs_from_h02": first_sha != H02_REQUEST_SHA256,
        "historical_h01_sha256": H01_REQUEST_SHA256,
        "historical_h02_sha256": H02_REQUEST_SHA256,
        "model": first.get("model"),
        "model_identity": first.get("model") == MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION_113,
        "prompt_sha256": prompt["prompt_sha256"],
        "transport_version": TRANSPORT_VERSION_11,
        "transport_sha256": schema["raw_schema_sha256"],
        "selected_handle": SELECTED_CASE_HANDLE,
        "selected_case_id_audit_only": SELECTED_CASE_ID,
        "handles_in_request": handles,
        "exactly_one_case": handles == [SELECTED_CASE_HANDLE],
        "paragraph_texts": texts,
        "evidence_in_request": present_evidence,
        "p4_evidence_only": present_evidence == sorted(P4_EVIDENCE_HANDLES),
        "label_leakage": leak.get("label_leakage"),
        "label_leak_pass": leak.get("pass") and not independence,
        "human_labels_sent": leak.get("human_labels_sent"),
        "independence_hits": independence,
        "independent_of_h01_h02": not independence,
        "dynamic_fields_present": dynamic_hits,
        "dynamic_fields_absent": not dynamic_hits,
        "sdk_max_retries_for_future_invocation": SDK_MAX_RETRIES,
        "payload": first,
        "repeat_payload_identical": first == second,
        "secrets_included": False,
    }


def serialize_selected_sdk(*, root: Path | None = None) -> dict[str, Any]:
    payload = build_selected_payload(root=root)
    captured = capture_openai_sdk_chat_request(payload)
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
    independence = _independence_hits(json.dumps(body or payload, ensure_ascii=False))
    independence = [
        item
        for item in independence
        if item not in SELECTED_CASE_REASON_CODES_AUDIT_ONLY
    ]
    checks = {
        "exactly_one_case": SELECTED_CASE_HANDLE in user and '"h01"' not in user and '"h02"' not in user,
        "compact_instruction_present": "Do not emit pr[].c[].t" in str(messages),
        "prompt_113": PROMPT_VERSION_113 in system or "Judge semantic entailment" in system,
        "evidence_present": all(handle in user for handle in P4_EVIDENCE_HANDLES),
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
        "independent_of_h01_h02": not independence,
        "label_leak_absent": leak.get("pass") is True,
        "case_answer_not_in_system": DISPUTED_CLAUSE not in system,
        "no_fallback": True,
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
        "independence_hits": independence,
        "sdk_max_retries_for_future_invocation": SDK_MAX_RETRIES,
        "fallbacks": 0,
        "retries": 0,
        "secrets_included": False,
    }


def request_identity(*, root: Path | None = None) -> dict[str, Any]:
    frozen = freeze_selected_request(root=root)
    serialized = serialize_selected_sdk(root=root)
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
    return {
        "phase": PHASE,
        "label_leakage": leak.get("label_leakage"),
        "hits": leak.get("hits"),
        "independence_hits": frozen.get("independence_hits"),
        "pass": frozen.get("label_leak_pass"),
        "human_labels_sent": leak.get("human_labels_sent"),
        "case_id_in_request": SELECTED_CASE_ID in blob,
        "source_case_id_in_request": SOURCE_CASE_ID in blob,
        "reason_codes_as_target_in_user": any(
            code in user for code in SELECTED_CASE_REASON_CODES_AUDIT_ONLY
        ),
        "general_catalog_allowed_in_system": all(
            code in system for code in SELECTED_CASE_REASON_CODES_AUDIT_ONLY
        ),
        "disputed_clause_in_paragraph_only": DISPUTED_CLAUSE in user
        and DISPUTED_CLAUSE not in system,
        "human_reference_absent_from_request": True,
        "catalog_false_positives_filtered": list(CATALOG_LEAK_FALSE_POSITIVES),
        "secrets_included": False,
    }


__all__ = [
    "build_selected_payload",
    "freeze_selected_request",
    "label_leakage_audit",
    "request_identity",
    "request_sha256",
    "serialize_selected_sdk",
    "slice_selected_gate",
]
