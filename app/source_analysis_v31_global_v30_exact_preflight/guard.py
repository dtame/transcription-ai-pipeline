"""Garde future du unique appel 3.0. A.45 ne l'exécute pas."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    AUTO_RETRY,
    CONNECT_TIMEOUT_SECONDS,
    FUTURE_AUTHORIZATION_SCOPE,
    MATERIAL_BOUND_DELTA_RATIO,
    MAX_ANTHROPIC_POST,
    MAX_ATTEMPTS,
    MAX_ENGINE_GENERATE,
    MODEL,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROMPT_VERSION,
    READ_TIMEOUT_SECONDS,
    SCHEMA_HASH,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v30_exact_preflight.offline import (
    GlobalExactPreflightError,
)


def future_call_guard_spec(
    *,
    normalized_input_hash: str,
    request_hash: str,
    provider_visible_hash: str,
    window_set_sha256: str,
    prompt_hash: str,
    schema_hash: str,
    hard_planning: int,
    estimated_input: int,
) -> dict[str, Any]:
    return {
        "authorization_scope": FUTURE_AUTHORIZATION_SCOPE,
        "max_engine_generate": MAX_ENGINE_GENERATE,
        "max_anthropic_post": MAX_ANTHROPIC_POST,
        "max_attempts": MAX_ATTEMPTS,
        "retries": 0 if not AUTO_RETRY else 1,
        "auto_retry": False,
        "json_repair": False,
        "truncated_repair": False,
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "prompt_version": PROMPT_VERSION,
        "transport_version": TRANSPORT_VERSION,
        "schema_hash": schema_hash or SCHEMA_HASH,
        "prompt_hash": prompt_hash,
        "normalized_input_hash": normalized_input_hash,
        "request_hash": request_hash,
        "provider_visible_hash": provider_visible_hash,
        "window_set_sha256": window_set_sha256,
        "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": READ_TIMEOUT_SECONDS,
        "approved_hard_planning": hard_planning,
        "approved_estimated_input": estimated_input,
        "precall_must_recompute": (
            "request_hash",
            "normalized_input_hash",
            "input_estimate",
            "output_hard_bound",
            "schema_identity",
        ),
        "mismatch_verdict": "BLOCKED_PRECALL",
        "material_bound_delta_ratio": MATERIAL_BOUND_DELTA_RATIO,
        "a45_executes_call": False,
    }


def authorize_future_call(observed: Mapping[str, Any], approved: Mapping[str, Any]) -> dict[str, Any]:
    """Fail-closed comparison used by the future real-call phase. No network."""
    checks = {
        "normalized_input_hash": observed.get("normalized_input_hash")
        == approved.get("normalized_input_hash"),
        "request_hash": observed.get("request_hash") == approved.get("request_hash"),
        "provider_visible_hash": observed.get("provider_visible_hash")
        == approved.get("provider_visible_hash"),
        "window_set_sha256": observed.get("window_set_sha256")
        == approved.get("window_set_sha256"),
        "prompt_version": observed.get("prompt_version") == approved.get("prompt_version"),
        "prompt_hash": observed.get("prompt_hash") == approved.get("prompt_hash"),
        "transport_version": observed.get("transport_version")
        == approved.get("transport_version"),
        "schema_hash": observed.get("schema_hash") == approved.get("schema_hash"),
        "model": observed.get("model") == approved.get("model"),
        "thinking_mode": observed.get("thinking_mode") == approved.get("thinking_mode"),
        "max_output": observed.get("max_output") == approved.get("max_output"),
        "authorization_scope": observed.get("authorization_scope")
        == approved.get("authorization_scope"),
        "retries": int(observed.get("retries") or 0) == 0,
        "max_engine_generate": int(observed.get("max_engine_generate") or 0) == 1,
    }
    approved_hard = int(approved.get("approved_hard_planning") or 0)
    observed_hard = int(observed.get("hard_planning") or approved_hard)
    if approved_hard:
        delta = abs(observed_hard - approved_hard) / approved_hard
        checks["hard_bound_stable"] = delta <= float(
            approved.get("material_bound_delta_ratio") or MATERIAL_BOUND_DELTA_RATIO
        )
    else:
        checks["hard_bound_stable"] = False
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise GlobalExactPreflightError(
            "BLOCKED_PRECALL: future-call guard mismatch: " + ", ".join(failed)
        )
    return {"ok": True, "checks": checks, "failed": []}


__all__ = ["authorize_future_call", "future_call_guard_spec"]
