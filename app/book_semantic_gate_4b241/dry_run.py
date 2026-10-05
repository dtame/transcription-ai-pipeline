"""Offline OpenAI provider dry-run. Stops before any remote SDK method."""

from __future__ import annotations

from typing import Any

from app.ai.provider_preflight import (
    check_provider_runtime_readiness,
    wrap_remote_openai_methods,
)
from app.ai.registry import get_engine_for_stage
from app.ai.settings import resolve_stage_settings
from app.book_semantic_gate_4b23.constants import SEMANTIC_GATE_STAGE
from app.book_semantic_gate_4b24.constants import MODEL, OUTPUT_MODE, PROVIDER
from app.book_semantic_gate_4b24.costing import estimate_canary_cost
from app.book_semantic_gate_4b24.engine import credential_available
from app.book_semantic_gate_4b24.identity import benchmark_identity
from app.book_semantic_gate_4b24.precall import build_precall


def production_provider_initialization() -> dict[str, Any]:
    settings = resolve_stage_settings("book_validation")
    engine, stage = get_engine_for_stage("book_validation")
    return {
        "status": "PASS",
        "provider": getattr(engine, "provider_name", None),
        "engine_class": type(engine).__name__,
        "stage": stage.stage,
        "stage_provider": settings.provider,
        "stage_model": settings.model,
        "semantic_gate_stage": SEMANTIC_GATE_STAGE,
        "registry_path": "get_engine_for_stage('book_validation')",
    }


def dry_run_openai_provider(*, root=None) -> dict[str, Any]:
    """
    Exercise configuration, registry, credential, SDK, client, model,
    request, json_object, and cost estimate. Never call a remote method.
    """
    init = production_provider_initialization()
    engine, _stage = get_engine_for_stage("book_validation")
    identity = build_precall(root=root)
    request = identity.get("ai_request")
    readiness = check_provider_runtime_readiness(
        PROVIDER,
        model=MODEL,
        request=request,
        output_mode=OUTPUT_MODE,
        engine=engine,
        construct_client=True,
    )
    if readiness.client_construction == "PASS" and hasattr(engine, "client"):
        # Dry-run only: block remote methods on this throwaway engine.
        wrap_remote_openai_methods(engine.client())

    estimate = dict(identity.get("cost_estimate") or {})
    request_meta = dict(identity.get("request") or {})
    payload = dict(identity.get("payload") or {})
    for key in ("x-api-key", "api_key", "authorization", "timeout"):
        payload.pop(key, None)

    return {
        "configuration_resolution": {
            "status": "PASS" if init["stage_provider"] == PROVIDER else "FAIL",
            "stage": init["stage"],
            "provider": init["stage_provider"],
            "model": init["stage_model"],
        },
        "provider_registry": {
            "status": init["status"],
            "engine_class": init["engine_class"],
            "path": init["registry_path"],
        },
        "credential_presence": "YES" if credential_available() else "NO",
        "sdk_import": readiness.sdk_import,
        "sdk_version": readiness.sdk_version,
        "client_construction": readiness.client_construction,
        "provider_initialization": readiness.provider_initialization,
        "model_resolution": readiness.model_resolution,
        "request_serialization": {
            "status": "PASS" if request_meta.get("identity_match") else "FAIL",
            "sha256": request_meta.get("sha256"),
            "sha256_repeat": request_meta.get("sha256_repeat"),
            "deterministic": request_meta.get("deterministic"),
        },
        "json_object_configuration": {
            "status": (
                "PASS"
                if request_meta.get("response_format") == {"type": "json_object"}
                else "FAIL"
            ),
            "response_format": request_meta.get("response_format"),
            "temperature_present": request_meta.get("temperature_present"),
            "thinking_present": request_meta.get("thinking_present"),
        },
        "token_cost_estimation": {
            "status": "PASS" if estimate.get("context_safe") else "FAIL",
            "context_safe": estimate.get("context_safe"),
            "estimated_cost": estimate.get("total_cost_display"),
            "provider_adjusted_pessimistic": estimate.get(
                "provider_adjusted_pessimistic"
            ),
        },
        "readiness": readiness.to_dict(),
        "payload_keys": sorted(payload),
        "benchmark": benchmark_identity(root=root),
        "precall_blocked": bool(identity.get("blocked_precall")),
        "precall_block_reasons": list(identity.get("block_reasons") or []),
        "http_sent": False,
        "engine_generate_called": False,
        "remote_invocations": 0,
        "NETWORK_CALLS": 0,
        "secrets_included": False,
    }


def estimate_from_identity(identity: dict[str, Any]) -> dict[str, Any]:
    request = identity.get("ai_request")
    if request is None:
        return {}
    return estimate_canary_cost(
        system_prompt=str(request.system_prompt or ""),
        user_prompt=str(request.prompt or ""),
        max_output_tokens=int(request.max_output_tokens or 0),
    )


__all__ = [
    "dry_run_openai_provider",
    "estimate_from_identity",
    "production_provider_initialization",
]
