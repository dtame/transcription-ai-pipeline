"""Requête V3 WIN001 prompt 1.3.1 + audit payload sûr. 0 POST ici."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.file_utils import content_hash
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_local_v3.pipeline import build_v131_window_request
from app.source_analysis_v3_hardened_win001.constants import (
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    EXPECTED_SCHEMA_HASH,
    MAX_OUTPUT_TOKENS,
    MODEL,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    THINKING_CONTRACT,
    THINKING_MODE,
)
from app.source_analysis_v3_hardened_win001.guard import (
    HardenedV3Win001Error,
    validate_provider,
)
from app.source_analysis_v3_symbolic_grammar_canary.payload import measure_v3_schema_bytes


def measure_schema() -> dict[str, Any]:
    measured = measure_v3_schema_bytes()
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
        raise HardenedV3Win001Error(
            "V3 schema identity unexpected vs A.17/A.18 "
            f"({measured['raw_bytes']}/{measured['adapted_bytes']} "
            f"hash={measured['raw_hash']}). STOP WITHOUT NETWORK."
        )
    return measured


def build_a21_request(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    model: str = MODEL,
) -> AIRequest:
    validate_provider(provider=PROVIDER, model=model)
    request = build_v131_window_request(window, transcript, model=model)
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
    if audit.get("prompt_version") != "window-analysis-1.3.1":
        failures.append(f"prompt_version={audit.get('prompt_version')!r}")
    if failures:
        raise HardenedV3Win001Error(
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
    request = build_a21_request(window, transcript, model=model)
    payload = AnthropicEngine(model=MODEL, api_key="cle-de-test").build_payload(
        request, MODEL
    )
    audit = inspect_safe_payload(request, payload)
    assert_payload_conditions(audit)
    return {
        "request": request,
        "audit": audit,
        "schema_metrics": schema,
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
        raise HardenedV3Win001Error(
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
    "build_a21_request",
    "build_audited_request",
    "dry_run_twice",
    "inspect_safe_payload",
    "measure_schema",
]
