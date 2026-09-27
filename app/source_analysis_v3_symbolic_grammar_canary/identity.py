"""Identité déterministe du canary V3 — isolée du cache fenêtre production."""

from __future__ import annotations

import json
from typing import Any

from app.file_utils import content_hash
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_CONNECT_TIMEOUT_SECONDS,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_READ_TIMEOUT_SECONDS,
    CANARY_VERSION,
    EFFORT,
    MODEL,
    PROVIDER,
    SEMANTIC_TRANSPORT_VERSION_V3,
    THINKING_MODE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WRAPPER_VERSION,
)


def canary_identity_payload(
    *,
    schema_hash: str,
    prompt_hash: str,
    wrapper_hash: str,
    fixture_hash: str,
    max_output: int = CANARY_MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    return {
        "canary_version": CANARY_VERSION,
        "wrapper_version": WRAPPER_VERSION,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider": PROVIDER,
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "effort": EFFORT,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V13,
        "prompt_hash": prompt_hash,
        "transport_version": SEMANTIC_TRANSPORT_VERSION_V3,
        "schema_hash": schema_hash,
        "wrapper_hash": wrapper_hash,
        "fixture_hash": fixture_hash,
        "max_output": int(max_output),
        "temperature": None,
        "connect_timeout_seconds": CANARY_CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": CANARY_READ_TIMEOUT_SECONDS,
        "manual_budget_tokens": None,
        "task_budget": None,
    }


def canary_request_identity(**kwargs: Any) -> str:
    payload = canary_identity_payload(**kwargs)
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


__all__ = ["canary_identity_payload", "canary_request_identity"]
