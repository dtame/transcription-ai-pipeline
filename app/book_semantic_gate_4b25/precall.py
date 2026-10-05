"""Pre-call gates. Provider is not contacted. Remote slot is not consumed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.provider_preflight import (
    REASON_PROVIDER_CREDENTIAL_NOT_READY,
    check_provider_runtime_readiness,
    redact_secrets,
)
from app.book_semantic_gate_4b241.dry_run import dry_run_openai_provider
from app.book_semantic_gate_4b24.constants import EXPECTED_REQUEST_SHA256
from app.book_semantic_gate_4b24.engine import credential_available
from app.book_semantic_gate_4b24.precall import build_precall as build_frozen_precall
from app.book_semantic_gate_4b25.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_NEGATIVE_CASES,
    EXPECTED_POSITIVE_CASES,
    EXPECTED_REQUEST_SHA256_FROZEN,
    EXPECTED_SCORED_CASES,
    EXPECTED_SOURCE_MAP,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PROVIDER,
)
from app.book_semantic_gate_4b25.runtime import interpreter_match, runtime_snapshot


def _readiness_pass(runtime: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    mapping = {
        "SDK_IMPORT": "openai_sdk_import",
        "sdk_supported": "openai_sdk_compatible",
        "CREDENTIAL_AVAILABLE": "openai_credential",
        "CLIENT_CONSTRUCTION": "client_construction",
        "PROVIDER_INITIALIZATION": "provider_initialization",
        "MODEL_RESOLUTION": "model_resolution",
        "REQUEST_CONSTRUCTION": "request_construction",
    }
    expected = {
        "SDK_IMPORT": "PASS",
        "sdk_supported": "PASS",
        "CREDENTIAL_AVAILABLE": "YES",
        "CLIENT_CONSTRUCTION": "PASS",
        "PROVIDER_INITIALIZATION": "PASS",
        "MODEL_RESOLUTION": "PASS",
        "REQUEST_CONSTRUCTION": "PASS",
    }
    for key, reason in mapping.items():
        actual = runtime.get(key)
        if key == "sdk_supported" and actual in {None, "NOT_REQUIRED"}:
            continue
        if actual != expected[key]:
            failures.append(reason)
    if int(runtime.get("NETWORK_CALLS") or 0) != 0:
        failures.append("readiness_network")
    if runtime.get("ready") is not True:
        if runtime.get("primary_reason") == REASON_PROVIDER_CREDENTIAL_NOT_READY:
            if "openai_credential" not in failures:
                failures.append("openai_credential")
        elif "openai_runtime" not in failures and failures == []:
            failures.append("openai_runtime")
    return (not failures, failures)


def build_precall(*, root: Path | None = None) -> dict[str, Any]:
    interp = interpreter_match(root=root)
    runtime = runtime_snapshot(root=root)
    frozen = build_frozen_precall(root=root)
    dry = dry_run_openai_provider(root=root)
    readiness = dict(dry.get("readiness") or frozen.get("provider_runtime") or {})
    if not readiness:
        live = check_provider_runtime_readiness(
            PROVIDER,
            model=MODEL,
            request=frozen.get("ai_request"),
            output_mode=OUTPUT_MODE,
            construct_client=True,
        )
        readiness = live.to_dict()

    blockers: list[str] = []
    if not interp["match"]:
        blockers.append("interpreter")
    blockers.extend(str(item) for item in (frozen.get("block_reasons") or []))

    request = dict(frozen.get("request") or {})
    if request.get("sha256") != EXPECTED_REQUEST_SHA256_FROZEN:
        if "request_sha256" not in blockers:
            blockers.append("request_sha256")
    if request.get("sha256_repeat") != EXPECTED_REQUEST_SHA256_FROZEN:
        if "request_determinism" not in blockers:
            blockers.append("request_determinism")

    identities = dict(frozen.get("identities_before") or {})
    source_sha = (identities.get("source_map") or {}).get("sha256")
    plan_sha = (identities.get("editorial_plan") or {}).get("sha256")
    transcript_sha = (identities.get("clean_transcript") or {}).get("sha256")
    if source_sha != EXPECTED_SOURCE_MAP and "source_map" not in blockers:
        blockers.append("source_map")
    if plan_sha != EXPECTED_EDITORIAL_PLAN and "editorial_plan" not in blockers:
        blockers.append("editorial_plan")
    if transcript_sha != EXPECTED_CLEAN_TRANSCRIPT and "clean_transcript" not in blockers:
        blockers.append("clean_transcript")

    leak = dict(frozen.get("label_leak") or {})
    if int(leak.get("label_leakage") or 0) != 0 and "label_leakage" not in blockers:
        blockers.append("label_leakage")

    estimate = dict(frozen.get("cost_estimate") or {})
    long_context = estimate.get("long_context_regime")
    if long_context != "NOT APPLICABLE":
        blockers.append("long_context")
    if not estimate.get("context_safe") and "context_safety" not in blockers:
        blockers.append("context_safety")

    ready_ok, ready_failures = _readiness_pass(readiness)
    for item in ready_failures:
        if item not in blockers:
            blockers.append(item)

    scored = list(frozen.get("scored_cases") or [])
    positives = [item for item in scored if item.get("role") == "positive"]
    negatives = [item for item in scored if item.get("role") == "negative"]
    if len(scored) != EXPECTED_SCORED_CASES:
        blockers.append("benchmark_count")
    if len(positives) != EXPECTED_POSITIVE_CASES or len(negatives) != EXPECTED_NEGATIVE_CASES:
        blockers.append("benchmark_roles")

    payload = dict(frozen.get("payload") or {})
    unknown = 0
    if isinstance(payload.get("messages"), list):
        blob = str(payload)
        if "unknown" in blob.lower() and "unknown_benchmark" in blob.lower():
            unknown = 1

    unique = list(dict.fromkeys(blockers))
    blocked = bool(unique)
    return redact_secrets(
        {
            "phase": PHASE,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "blocked_precall": blocked,
            "block_reasons": unique,
            "block_reason": unique[0] if unique else None,
            "interpreter": interp,
            "runtime": runtime,
            "provider_readiness": {
                "SDK_IMPORT": readiness.get("SDK_IMPORT"),
                "sdk_compatible": readiness.get("sdk_supported"),
                "CREDENTIAL_AVAILABLE": readiness.get("CREDENTIAL_AVAILABLE"),
                "CLIENT_CONSTRUCTION": readiness.get("CLIENT_CONSTRUCTION"),
                "PROVIDER_INITIALIZATION": readiness.get("PROVIDER_INITIALIZATION"),
                "MODEL_RESOLUTION": readiness.get("MODEL_RESOLUTION"),
                "REQUEST_CONSTRUCTION": readiness.get("REQUEST_CONSTRUCTION"),
                "NETWORK_CALLS": readiness.get("NETWORK_CALLS") or 0,
                "ready": ready_ok and readiness.get("ready") is True,
                "primary_reason": readiness.get("primary_reason"),
                "sdk_version": readiness.get("sdk_version"),
            },
            "identities_before": frozen.get("identities_before"),
            "identities_after": frozen.get("identities_after"),
            "inputs_unchanged": frozen.get("inputs_unchanged"),
            "language": frozen.get("language"),
            "benchmark": frozen.get("benchmark"),
            "contracts": frozen.get("contracts"),
            "evidence_sha256": frozen.get("evidence_sha256"),
            "candidate_handles": frozen.get("candidate_handles"),
            "paragraph_texts": frozen.get("paragraph_texts"),
            "gate_input": frozen.get("gate_input"),
            "request": request,
            "payload": payload,
            "ai_request": frozen.get("ai_request"),
            "label_leak": leak,
            "cost_estimate": estimate,
            "budget": frozen.get("budget"),
            "credential_available": credential_available(),
            "production_book_absent": frozen.get("production_book_absent"),
            "allowed_handles": frozen.get("allowed_handles"),
            "scored_cases": scored,
            "case_coverage": {
                "required": EXPECTED_SCORED_CASES,
                "present": len(frozen.get("candidate_handles") or []),
                "unknown_benchmark_cases": unknown,
                "evaluator_labels": int(leak.get("label_leakage") or 0),
            },
            "context_safety": "PASS" if estimate.get("context_safe") else "FAIL",
            "long_context": long_context,
            "http_sent": False,
            "engine_generate_called": False,
            "remote_invocations": 0,
            "expected_request_sha256": EXPECTED_REQUEST_SHA256,
            "secrets_included": False,
        }
    )


__all__ = ["build_precall"]
