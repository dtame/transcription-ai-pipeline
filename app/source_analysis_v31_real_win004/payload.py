"""Requête v3.1-local-lite WIN004 prompt 1.4.0 + audit payload sûr. 0 POST ici."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.file_utils import content_hash
from app.source_analysis.schema import build_response_schema
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.pipeline import build_v140_window_request
from app.source_analysis_local_v3.schema import (
    build_semantic_transport_v31_local_lite_schema,
    measure_v31_local_lite_schema_pair,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis_v3_symbolic_grammar_canary.payload import measure_v3_schema_bytes
from app.source_analysis_v31_real_win004.constants import (
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    EXPECTED_SCHEMA_HASH,
    MAX_OUTPUT_TOKENS,
    MODEL,
    PROMPT_VERSION,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    THINKING_CONTRACT,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_real_win004.guard import (
    LocalLiteWin004Error,
    validate_provider,
)


def measure_schema() -> dict[str, Any]:
    v3 = measure_v3_schema_bytes()
    v31 = measure_v31_local_lite_schema_pair()
    measured = dict(v31)
    measured["raw_hash"] = semantic_transport_v31_local_lite_fingerprint()
    measured["matches_expected"] = (
        int(v31.get("raw_bytes") or 0) == EXPECTED_RAW_SCHEMA_BYTES
        and int(v31.get("adapted_bytes") or 0) == EXPECTED_ADAPTED_SCHEMA_BYTES
        and measured["raw_hash"] == EXPECTED_SCHEMA_HASH
    )
    measured["matches_a17_fingerprint"] = measured["raw_hash"] == EXPECTED_SCHEMA_HASH
    measured["v3_raw_bytes"] = v3.get("raw_bytes")
    measured["v3_adapted_bytes"] = v3.get("adapted_bytes")
    measured["schema_changed"] = not (
        measured["matches_expected"] and measured["matches_a17_fingerprint"]
    )
    return measured


def assert_schema_identity(metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    measured = metrics or measure_schema()
    if (
        measured["raw_bytes"] != EXPECTED_RAW_SCHEMA_BYTES
        or measured["adapted_bytes"] != EXPECTED_ADAPTED_SCHEMA_BYTES
        or measured["raw_hash"] != EXPECTED_SCHEMA_HASH
        or not measured["matches_expected"]
        or not measured["matches_a17_fingerprint"]
    ):
        raise LocalLiteWin004Error(
            "v3.1-local-lite schema identity unexpected vs A.17/A.18 "
            f"({measured['raw_bytes']}/{measured['adapted_bytes']} "
            f"hash={measured['raw_hash']}). STOP WITHOUT NETWORK."
        )
    return measured


def assert_schema_py_excluded(request: AIRequest) -> dict[str, Any]:
    local = build_semantic_transport_v31_local_lite_schema()
    publication = build_response_schema()
    equals_local = request.response_schema == local
    equals_publication = request.response_schema == publication
    if not equals_local or equals_publication:
        raise LocalLiteWin004Error(
            "A.27 request schema must be local-lite compact schema and must "
            "not be app/source_analysis/schema.py. STOP WITHOUT NETWORK."
        )
    return {
        "request_schema_equals_local_lite": True,
        "request_schema_equals_schema_py": False,
        "schema_py_path": "app/source_analysis/schema.py",
        "schema_py_role": "OLD_GLOBAL_SOURCE_ANALYZER_PROVIDER_STRUCTURED_OUTPUT",
        "on_a27_local_lite_path": False,
    }


def build_a27_request(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    model: str = MODEL,
) -> AIRequest:
    validate_provider(provider=PROVIDER, model=model)
    request = build_v140_window_request(window, transcript, model=model)
    return replace(
        request,
        model=model,
        temperature=None,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        timeout_seconds=READ_TIMEOUT_SECONDS,
        thinking_mode=THINKING_MODE,
        effort=None,
        thinking_budget_tokens=None,
    )


def _nested_has(payload: Any, key: str) -> bool:
    if isinstance(payload, dict):
        if key in payload:
            return True
        return any(_nested_has(value, key) for value in payload.values())
    if isinstance(payload, list):
        return any(_nested_has(item, key) for item in payload)
    return False


def inspect_safe_payload(request: AIRequest, payload: dict[str, Any]) -> dict[str, Any]:
    output_config = payload.get("output_config")
    format_block = output_config.get("format") if isinstance(output_config, dict) else None
    thinking = payload.get("thinking")
    thinking_type = thinking.get("type") if isinstance(thinking, dict) else None
    effort_present = isinstance(output_config, dict) and "effort" in output_config
    return {
        "model": payload.get("model"),
        "max_tokens": payload.get("max_tokens"),
        "thinking": {"type": thinking_type} if thinking_type else thinking,
        "thinking_type": thinking_type,
        "effort_present": effort_present,
        "budget_tokens_present": _nested_has(payload, "budget_tokens"),
        "task_budget_present": _nested_has(payload, "task_budget"),
        "temperature_present": "temperature" in payload,
        "output_config_present": isinstance(output_config, dict),
        "format_type": format_block.get("type") if isinstance(format_block, dict) else None,
        "message_count": len(payload.get("messages") or []),
        "system_present": bool(payload.get("system")),
        "system_chars": len(str(payload.get("system") or "")),
        "user_chars": sum(
            len(str(item.get("content") or ""))
            for item in (payload.get("messages") or [])
            if isinstance(item, dict)
        ),
        "prompt_sha256": request.metadata.get("prompt_sha256"),
        "schema_sha256": request.metadata.get("schema_sha256"),
        "prompt_version": request.metadata.get("prompt_version"),
        "transport_version": request.metadata.get("transport_version"),
        "thinking_contract": THINKING_CONTRACT,
        "provider": PROVIDER,
        "secrets_included": False,
        "authorization_header_included": False,
        "full_transcript_duplicated": False,
        "payload_hash": content_hash(
            json.dumps(
                {
                    "model": payload.get("model"),
                    "max_tokens": payload.get("max_tokens"),
                    "thinking": thinking,
                    "format_type": format_block.get("type")
                    if isinstance(format_block, dict)
                    else None,
                    "prompt_sha256": request.metadata.get("prompt_sha256"),
                    "schema_sha256": request.metadata.get("schema_sha256"),
                    "prompt_version": request.metadata.get("prompt_version"),
                    "transport_version": request.metadata.get("transport_version"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        ),
    }


def assert_payload_conditions(audit: dict[str, Any]) -> None:
    failures: list[str] = []
    if audit.get("model") != MODEL:
        failures.append(f"model={audit.get('model')!r}")
    if audit.get("thinking_type") != "disabled":
        failures.append(f"thinking.type={audit.get('thinking_type')!r}")
    if audit.get("effort_present"):
        failures.append("effort present")
    if audit.get("budget_tokens_present"):
        failures.append("budget_tokens present")
    if audit.get("task_budget_present"):
        failures.append("task_budget present")
    if audit.get("temperature_present"):
        failures.append("temperature present")
    if audit.get("max_tokens") != MAX_OUTPUT_TOKENS:
        failures.append(f"max_tokens={audit.get('max_tokens')!r}")
    if not audit.get("output_config_present"):
        failures.append("output_config absent")
    if audit.get("format_type") != "json_schema":
        failures.append(f"format.type={audit.get('format_type')!r}")
    if audit.get("schema_sha256") != EXPECTED_SCHEMA_HASH:
        failures.append(f"schema_sha256={audit.get('schema_sha256')!r}")
    if audit.get("prompt_version") != PROMPT_VERSION:
        failures.append(f"prompt_version={audit.get('prompt_version')!r}")
    if audit.get("transport_version") != TRANSPORT_VERSION:
        failures.append(f"transport_version={audit.get('transport_version')!r}")
    if failures:
        raise LocalLiteWin004Error(
            "Payload conditions failed — STOP WITHOUT PROVIDER CALL: "
            + "; ".join(failures)
        )


def build_audited_request(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    model: str = MODEL,
) -> dict[str, Any]:
    schema = assert_schema_identity()
    request = build_a27_request(window, transcript, model=model)
    schema_py = assert_schema_py_excluded(request)
    payload = AnthropicEngine(model=MODEL, api_key="cle-de-test").build_payload(
        request, MODEL
    )
    audit = inspect_safe_payload(request, payload)
    assert_payload_conditions(audit)
    return {
        "request": request,
        "audit": audit,
        "schema_metrics": schema,
        "schema_py_exclusion": schema_py,
        "source_hash": window.input_hash,
        "prompt_hash": audit.get("prompt_sha256"),
        "schema_hash": audit.get("schema_sha256"),
        "request_identity": audit.get("payload_hash"),
    }


def dry_run_twice(
    window: WindowInput,
    transcript: TranscriptInput,
) -> dict[str, Any]:
    first = build_audited_request(window, transcript)
    second = build_audited_request(window, transcript)
    keys = ("request_identity", "prompt_hash", "schema_hash", "source_hash")
    match = all(first[key] == second[key] for key in keys)
    if not match:
        raise LocalLiteWin004Error(
            "Dry-run identities are not deterministic — STOP WITHOUT NETWORK."
        )
    return {
        "deterministic": True,
        "request_identity": first["request_identity"],
        "prompt_hash": first["prompt_hash"],
        "schema_hash": first["schema_hash"],
        "source_hash": first["source_hash"],
        "first": {key: first[key] for key in keys},
        "second": {key: second[key] for key in keys},
        "provider_calls": 0,
    }


__all__ = [
    "assert_payload_conditions",
    "assert_schema_identity",
    "assert_schema_py_excluded",
    "build_a27_request",
    "build_audited_request",
    "dry_run_twice",
    "inspect_safe_payload",
    "measure_schema",
]
