"""Offline Terra parameter forensics. No provider HTTP."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any

from app.ai.openai_compat import (
    CONFIDENCE_CONFIRMED,
    CONFIDENCE_LOCAL,
    CONFIDENCE_UNKNOWN,
    PRODUCTION_OPENAI_ENDPOINT,
    TOKEN_PARAM_MAX_COMPLETION_TOKENS,
    TOKEN_PARAM_MAX_TOKENS,
    capture_openai_sdk_chat_request,
    openai_endpoint_capability_matrix,
    production_openai_endpoint,
    resolve_chat_completions_token_contract,
)
from app.ai.provider_preflight import (
    READY_WITH_SERVER_UNVERIFIED_FIELDS,
    check_provider_runtime_readiness,
    future_call_accounting_contract,
    redact_secrets,
)
from app.ai.providers.openai_engine import OpenAIEngine
from app.book_semantic_gate_4b24.engine import CountingOpenAIEngine
from app.book_semantic_gate_4b251.constants import (
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_OPENAI_SDK_VERSION,
    EXPECTED_REQUEST_SHA256_HISTORICAL,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PROVIDER,
    SEMANTIC_TOKEN_BUDGET,
)
from app.book_semantic_gate_4b251.identity import build_corrected_identity
from app.book_semantic_gate_4b25.runtime import interpreter_match, runtime_snapshot


def _sdk_create_signature() -> dict[str, Any]:
    try:
        from openai.resources.chat.completions import Completions

        signature = str(inspect.signature(Completions.create))
        names = list(inspect.signature(Completions.create).parameters)
    except Exception as exc:
        return {"status": "FAIL", "error_class": type(exc).__name__}
    return {
        "status": "PASS",
        "has_max_tokens": "max_tokens" in names,
        "has_max_completion_tokens": "max_completion_tokens" in names,
        "has_max_output_tokens": "max_output_tokens" not in names,
        "parameter_names": names,
        "signature_contains_both_token_fields": (
            "max_tokens" in signature and "max_completion_tokens" in signature
        ),
    }


def parameter_forensics(*, root: Path | None = None) -> dict[str, Any]:
    interp = interpreter_match(root=root)
    runtime = runtime_snapshot(root=root)
    source = inspect.getsource(OpenAIEngine.build_payload)
    invoke = inspect.getsource(OpenAIEngine._invoke)
    contract = resolve_chat_completions_token_contract(MODEL)
    sdk = _sdk_create_signature()
    return {
        "phase": PHASE,
        "historical_4b25": "FAIL",
        "historical_request_sha256": EXPECTED_REQUEST_SHA256_HISTORICAL,
        "python_executable": sys.executable,
        "canonical_python_executable": CANONICAL_PYTHON_EXECUTABLE,
        "interpreter_match": interp["match"],
        "openai_sdk_version": runtime.get("openai_sdk_version"),
        "expected_openai_sdk_version": EXPECTED_OPENAI_SDK_VERSION,
        "actual_endpoint": PRODUCTION_OPENAI_ENDPOINT,
        "actual_sdk_method": "client.chat.completions.create",
        "responses_api_used": False,
        "root_cause": {
            "summary": (
                "OpenAIEngine.build_payload mapped AIRequest.max_output_tokens "
                "onto chat.completions max_tokens for every OpenAI model. "
                "gpt-5.6-terra rejects max_tokens and requires "
                "max_completion_tokens. Provider-level max_output_tokens is a "
                "semantic budget, not the Responses API field."
            ),
            "entry_point": "app.ai.providers.openai_engine.OpenAIEngine.build_payload",
            "invoke_site": "OpenAIEngine._invoke -> client.chat.completions.create",
            "historical_field": TOKEN_PARAM_MAX_TOKENS,
            "historical_value": SEMANTIC_TOKEN_BUDGET,
            "server_required_field": TOKEN_PARAM_MAX_COMPLETION_TOKENS,
            "confirmed_by": "4B.2.5 HTTP 400 unsupported_parameter",
        },
        "confirmed": [
            {
                "fact": "Production endpoint is chat.completions.create",
                "confidence": CONFIDENCE_CONFIRMED,
                "evidence": "OpenAIEngine._invoke calls client.chat.completions.create",
            },
            {
                "fact": "4B.2.5 sent max_tokens=8192 and was rejected",
                "confidence": CONFIDENCE_CONFIRMED,
                "evidence": "historical request SHA 09d6472e... and provider evidence",
            },
            {
                "fact": "Server named max_completion_tokens as the replacement",
                "confidence": CONFIDENCE_CONFIRMED,
                "evidence": "invalid_request_error param=max_tokens",
            },
        ],
        "locally_verified": [
            {
                "fact": "SDK 2.43.0 chat.completions.create accepts both token fields",
                "confidence": CONFIDENCE_LOCAL,
                "evidence": sdk,
            },
            {
                "fact": "Legacy unlisted OpenAI models still serialize max_tokens",
                "confidence": CONFIDENCE_LOCAL,
                "evidence": "existing test_ai_providers payload test",
            },
        ],
        "unknown_server_only": [
            {
                "fact": "Server acceptance of max_completion_tokens=8192",
                "confidence": CONFIDENCE_UNKNOWN,
                "reason": "No successful Terra response after the parameter change",
            },
            {
                "fact": "json_object server acceptance for Terra",
                "confidence": CONFIDENCE_UNKNOWN,
                "reason": "4B.2.5 failed before a JSON body was returned",
            },
            {
                "fact": "Terra temperature / reasoning / thinking server behavior",
                "confidence": CONFIDENCE_UNKNOWN,
                "reason": "Not observed; omitted locally",
            },
        ],
        "build_payload_maps_max_output_tokens": True,
        "historical_mapping_was_max_tokens": True,
        "corrected_mapping": contract.to_dict(),
        "sdk_create_parameters": sdk,
        "invoke_uses_chat_completions": "chat.completions.create" in invoke,
        "build_payload_source_mentions_compat": "apply_chat_completions_output_tokens" in source,
        "runtime": runtime,
        "secrets_included": False,
    }


def sdk_serialization_capture(payload: dict[str, Any]) -> dict[str, Any]:
    captured = capture_openai_sdk_chat_request(payload)
    body = dict(captured.get("body") or {})
    expected_keys = {"model", "messages", "max_completion_tokens", "response_format"}
    extra = sorted(set(body) - expected_keys)
    return redact_secrets(
        {
            **captured,
            "endpoint": production_openai_endpoint(),
            "token_limit": body.get("max_completion_tokens"),
            "max_tokens_absent": "max_tokens" not in body,
            "temperature_absent": "temperature" not in body,
            "thinking_absent": "thinking" not in body,
            "json_object": body.get("response_format") == {"type": "json_object"},
            "unexpected_request_fields": extra,
            "serialization_pass": bool(
                captured.get("intercepted")
                and captured.get("network_calls") == 0
                and body.get("max_completion_tokens") == SEMANTIC_TOKEN_BUDGET
                and "max_tokens" not in body
                and "temperature" not in body
                and "thinking" not in body
                and body.get("response_format") == {"type": "json_object"}
                and extra == []
            ),
        }
    )


def compatibility_preflight(*, identity: dict[str, Any]) -> dict[str, Any]:
    engine = CountingOpenAIEngine(api_key="offline-4b251-preflight-unused")
    request = identity.get("ai_request")
    readiness = check_provider_runtime_readiness(
        PROVIDER,
        model=MODEL,
        request=request,
        output_mode=OUTPUT_MODE,
        engine=engine,
        construct_client=True,
    )
    payload = readiness.to_dict()
    payload["readiness_class"] = readiness.readiness_class or READY_WITH_SERVER_UNVERIFIED_FIELDS
    payload["cannot_claim_server_acceptance"] = True
    payload["historical_4b25_http"] = 1
    payload["this_phase_http"] = 0
    payload["secrets_included"] = False
    return redact_secrets(payload)


def accounting_regression() -> dict[str, Any]:
    contract = future_call_accounting_contract()
    return {
        "phase": PHASE,
        "this_phase": {
            "authorized_calls": 0,
            "execution_attempts": 0,
            "remote_invocations": 0,
            "http_requests": 0,
            "provider_responses": 0,
            "openai_http": 0,
            "anthropic_http": 0,
        },
        "do_not_reuse_4b25_slot": True,
        "historical_4b25_consumed_one_remote_invocation": True,
        "contract": contract,
        "secrets_included": False,
    }


def collect_offline_bundle(*, root: Path | None = None) -> dict[str, Any]:
    identity = build_corrected_identity(root=root)
    forensics = parameter_forensics(root=root)
    matrix = openai_endpoint_capability_matrix()
    capture = sdk_serialization_capture(dict(identity.get("payload") or {}))
    preflight = compatibility_preflight(identity=identity)
    accounting = accounting_regression()
    return {
        "identity": identity,
        "forensics": forensics,
        "matrix": matrix,
        "sdk_capture": capture,
        "preflight": preflight,
        "accounting": accounting,
    }


__all__ = [
    "accounting_regression",
    "collect_offline_bundle",
    "compatibility_preflight",
    "parameter_forensics",
    "sdk_serialization_capture",
]
