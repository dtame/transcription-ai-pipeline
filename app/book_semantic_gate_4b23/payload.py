"""Offline semantic-gate request builder. Never calls generate."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.ai.contracts import AIRequest
from app.ai.estimation import estimate_tokens
from app.ai.providers.openai_engine import OpenAIEngine
from app.book_semantic_gate_4b23.constants import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    SEMANTIC_GATE_MODEL,
    SEMANTIC_GATE_STAGE,
    SEMANTIC_VALIDATION_TRANSPORT_VERSION,
    SEMANTIC_VALIDATOR_PROMPT_VERSION,
    STRUCTURED_OUTPUT_MODE,
    TEMPERATURE_POLICY,
    THINKING_MODE,
)
from app.book_semantic_gate_4b23.evidence import render_gate_input_json
from app.book_semantic_gate_4b23.prompt import (
    prompt_bundle,
    render_user_prompt,
    system_prompt,
)
from app.book_semantic_gate_4b23.schema import build_semantic_validation_schema
from app.file_utils import content_hash


def build_gate_request(
    gate_input: Mapping[str, Any],
    *,
    max_output_tokens: int | None = None,
) -> AIRequest:
    user = render_user_prompt(render_gate_input_json(gate_input))
    schema = build_semantic_validation_schema()
    output = (
        max_output_tokens if max_output_tokens is not None else DEFAULT_MAX_OUTPUT_TOKENS
    )
    return AIRequest(
        prompt=user,
        system_prompt=system_prompt(),
        model=SEMANTIC_GATE_MODEL,
        temperature=None,
        max_output_tokens=output,
        response_schema=schema,
        thinking_mode=None,
        effort=None,
        thinking_budget_tokens=None,
        metadata={
            "stage": SEMANTIC_GATE_STAGE,
            "prompt_version": SEMANTIC_VALIDATOR_PROMPT_VERSION,
            "transport_version": SEMANTIC_VALIDATION_TRANSPORT_VERSION,
            "authorization_scope": "phase4b23-offline-payload-only",
            "chapter_id": gate_input.get("chapter_handle"),
            "thinking_mode": THINKING_MODE,
            "temperature_policy": TEMPERATURE_POLICY,
            "structured_output_mode": STRUCTURED_OUTPUT_MODE,
            "schema_sha256": content_hash(
                json.dumps(schema, ensure_ascii=False, sort_keys=True)
            ),
        },
    )


def build_offline_openai_payload(
    gate_input: Mapping[str, Any],
    *,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    request = build_gate_request(gate_input, max_output_tokens=max_output_tokens)
    engine = OpenAIEngine(model=SEMANTIC_GATE_MODEL, api_key="offline-phase4b23-unused")
    payload = engine.build_payload(request, SEMANTIC_GATE_MODEL)
    for key in ("x-api-key", "api_key", "authorization", "timeout"):
        payload.pop(key, None)
    # Terra temperature is not a verified capability.
    payload.pop("temperature", None)
    return payload


def payload_audit(
    gate_input: Mapping[str, Any],
    *,
    max_output_tokens: int | None = None,
) -> dict[str, Any]:
    request = build_gate_request(gate_input, max_output_tokens=max_output_tokens)
    payload = build_offline_openai_payload(
        gate_input, max_output_tokens=max_output_tokens
    )
    system = str(request.system_prompt or "")
    user = str(request.prompt or "")
    local = estimate_tokens(system + "\n" + user)
    prompt = prompt_bundle()
    return {
        "http_sent": False,
        "engine_generate_called": False,
        "provider": "openai",
        "model": SEMANTIC_GATE_MODEL,
        "stage": SEMANTIC_GATE_STAGE,
        "thinking_mode": THINKING_MODE,
        "thinking_present": "thinking" in payload,
        "temperature_present": "temperature" in payload,
        "structured_output": payload.get("response_format"),
        "max_tokens": payload.get("max_tokens"),
        "system_prompt_chars": len(system),
        "user_prompt_chars": len(user),
        "payload_sha256": content_hash(
            json.dumps(payload, ensure_ascii=False, sort_keys=True)
        ),
        "prompt_sha256": prompt["prompt_sha256"],
        "local_input_token_estimate": {
            "tokens": local.tokens,
            "estimated": local.estimated,
            "method": local.method,
        },
        "request_identity": {
            "model": request.model,
            "thinking_mode": request.thinking_mode,
            "effort": request.effort,
            "temperature": request.temperature,
            "max_output_tokens": request.max_output_tokens,
            "stage": request.stage,
        },
    }


__all__ = [
    "build_gate_request",
    "build_offline_openai_payload",
    "payload_audit",
]
