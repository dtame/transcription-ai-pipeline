"""Pre-call gates. Provider is not contacted. Remote slot is not consumed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.openai_compat import (
    CONFIDENCE_UNKNOWN,
    TOKEN_PARAM_MAX_COMPLETION_TOKENS,
    TOKEN_PARAM_MAX_TOKENS,
    resolve_chat_completions_token_contract,
)
from app.ai.provider_preflight import (
    READY_WITH_SERVER_UNVERIFIED_FIELDS,
    REASON_PROVIDER_CREDENTIAL_NOT_READY,
    check_provider_runtime_readiness,
    redact_secrets,
)
from app.book_semantic_gate_4b241.dry_run import dry_run_openai_provider
from app.book_semantic_gate_4b24.engine import credential_available
from app.book_semantic_gate_4b24.precall import build_precall as build_frozen_precall
from app.book_semantic_gate_4b251.forensics import sdk_serialization_capture
from app.book_semantic_gate_4b26.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_NEGATIVE_CASES,
    EXPECTED_OPENAI_SDK_VERSION,
    EXPECTED_POSITIVE_CASES,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_REQUEST_SHA256_HISTORICAL_4B25,
    EXPECTED_SCORED_CASES,
    EXPECTED_SOURCE_MAP,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PRODUCTION_ENDPOINT,
    PROVIDER,
    SEMANTIC_TOKEN_BUDGET,
    TOKEN_FIELD,
)
from app.book_semantic_gate_4b26.runtime import interpreter_match, runtime_snapshot


SERVER_ONLY_UNKNOWNS = (
    {
        "field": "json_object_server_acceptance",
        "status": CONFIDENCE_UNKNOWN,
        "note": (
            "Local serialization of response_format=json_object is PASS. "
            "Whether gpt-5.6-terra chat.completions accepts json_object "
            "has not been observed. 4B.2.5 failed on max_tokens before "
            "a JSON body was returned. UNKNOWN is not PASS."
        ),
    },
    {
        "field": "max_completion_tokens_server_acceptance",
        "status": CONFIDENCE_UNKNOWN,
        "note": (
            "Local mapping to max_completion_tokens=8192 is PASS. "
            "Whether the server accepts that field and budget for Terra "
            "has not been observed. UNKNOWN is not PASS."
        ),
    },
    {
        "field": "temperature_server_behavior",
        "status": CONFIDENCE_UNKNOWN,
        "note": "Temperature is omitted locally. Server default remains UNKNOWN.",
    },
    {
        "field": "reasoning_or_thinking_server_behavior",
        "status": CONFIDENCE_UNKNOWN,
        "note": (
            "Thinking is provider_default / omitted. No explicit thinking "
            "field is sent. Server reasoning behavior remains UNKNOWN."
        ),
    },
    {
        "field": "actual_cost",
        "status": CONFIDENCE_UNKNOWN,
        "note": (
            "Pre-call estimate is approximately 0.114384 USD and is not a "
            "guarantee. Unknown actual cost must not be reported as zero."
        ),
    },
)


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


def _local_compat_pass(compat: dict[str, Any], payload: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if compat.get("endpoint_selected") != "PASS":
        failures.append("endpoint_selected")
    if compat.get("request_serializable") != "PASS":
        failures.append("request_serializable")
    if compat.get("unsupported_optional_parameters") != "PASS":
        failures.append("unsupported_optional_parameters")
    if compat.get("output_mode_local") != "PASS":
        failures.append("json_object_local")
    if payload.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS) != SEMANTIC_TOKEN_BUDGET:
        failures.append("max_completion_tokens")
    if TOKEN_PARAM_MAX_TOKENS in payload:
        failures.append("max_tokens_present")
    if "temperature" in payload:
        failures.append("temperature_present")
    if "thinking" in payload:
        failures.append("thinking_present")
    if payload.get("response_format") != {"type": "json_object"}:
        failures.append("json_object_absent")
    if not isinstance(payload.get("messages"), list) or not payload.get("messages"):
        failures.append("messages_absent")
    token_supported = compat.get("token_parameter_supported")
    if token_supported not in {"PASS", CONFIDENCE_UNKNOWN}:
        failures.append("token_parameter_supported")
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

    payload = dict(frozen.get("payload") or {})
    request = dict(frozen.get("request") or {})
    capture = sdk_serialization_capture(payload)
    contract = resolve_chat_completions_token_contract(MODEL)
    compat_engine_readiness = check_provider_runtime_readiness(
        PROVIDER,
        model=MODEL,
        request=frozen.get("ai_request"),
        output_mode=OUTPUT_MODE,
        construct_client=True,
    )
    compat = dict((compat_engine_readiness.details or {}).get("compatibility") or {})
    if not compat:
        compat = {
            "endpoint": PRODUCTION_ENDPOINT,
            "endpoint_selected": compat_engine_readiness.endpoint_selected,
            "token_parameter": compat_engine_readiness.token_parameter,
            "token_parameter_supported": compat_engine_readiness.token_parameter_supported,
            "request_serializable": compat_engine_readiness.request_serializable,
            "unsupported_optional_parameters": (
                compat_engine_readiness.unsupported_optional_parameters
            ),
            "output_mode_local": compat_engine_readiness.output_mode_supported,
            "unknown_server_fields": [item["field"] for item in SERVER_ONLY_UNKNOWNS],
        }

    blockers: list[str] = []
    if not interp["match"]:
        blockers.append("interpreter")
    if not interp.get("python_version_match"):
        blockers.append("python_version")
    if str(runtime.get("openai_sdk_version") or "") != EXPECTED_OPENAI_SDK_VERSION:
        blockers.append("openai_sdk_version")
    if not runtime.get("env_ignored_by_git", {}).get("ignored"):
        blockers.append("env_not_ignored")

    historical_blockers = [
        reason
        for reason in (frozen.get("block_reasons") or [])
        if reason != "request_sha256"
    ]
    blockers.extend(str(item) for item in historical_blockers)

    actual_sha = request.get("sha256")
    repeat_sha = request.get("sha256_repeat")
    if actual_sha != EXPECTED_REQUEST_SHA256:
        blockers.append("request_sha256")
    if repeat_sha != EXPECTED_REQUEST_SHA256:
        blockers.append("request_determinism")
    if actual_sha != repeat_sha:
        if "request_determinism" not in blockers:
            blockers.append("request_determinism")

    identities = dict(frozen.get("identities_before") or {})
    identities_after = dict(frozen.get("identities_after") or {})
    source_sha = (identities.get("source_map") or {}).get("sha256")
    plan_sha = (identities.get("editorial_plan") or {}).get("sha256")
    transcript_sha = (identities.get("clean_transcript") or {}).get("sha256")
    source_after = (identities_after.get("source_map") or {}).get("sha256")
    plan_after = (identities_after.get("editorial_plan") or {}).get("sha256")
    transcript_after = (identities_after.get("clean_transcript") or {}).get("sha256")
    if source_sha != EXPECTED_SOURCE_MAP or source_after != EXPECTED_SOURCE_MAP:
        if "source_map" not in blockers:
            blockers.append("source_map")
    if plan_sha != EXPECTED_EDITORIAL_PLAN or plan_after != EXPECTED_EDITORIAL_PLAN:
        if "editorial_plan" not in blockers:
            blockers.append("editorial_plan")
    if (
        transcript_sha != EXPECTED_CLEAN_TRANSCRIPT
        or transcript_after != EXPECTED_CLEAN_TRANSCRIPT
    ):
        if "clean_transcript" not in blockers:
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
    live_ok, live_failures = _readiness_pass(compat_engine_readiness.to_dict())
    for item in live_failures:
        if item not in blockers:
            blockers.append(item)

    local_ok, local_failures = _local_compat_pass(compat, payload)
    for item in local_failures:
        if item not in blockers:
            blockers.append(item)
    if not capture.get("serialization_pass"):
        blockers.append("sdk_serialization")

    scored = list(frozen.get("scored_cases") or [])
    positives = [item for item in scored if item.get("role") == "positive"]
    negatives = [item for item in scored if item.get("role") == "negative"]
    if len(scored) != EXPECTED_SCORED_CASES:
        blockers.append("benchmark_count")
    if len(positives) != EXPECTED_POSITIVE_CASES or len(negatives) != EXPECTED_NEGATIVE_CASES:
        blockers.append("benchmark_roles")
    if not (frozen.get("benchmark") or {}).get("identity_match"):
        if "benchmark_identity" not in blockers:
            blockers.append("benchmark_identity")

    messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    unknown = 0
    if "unknown" in str(payload).lower() and "unknown_benchmark" in str(payload).lower():
        unknown = 1

    unique = list(dict.fromkeys(blockers))
    blocked = bool(unique)
    server_unknowns = [dict(item) for item in SERVER_ONLY_UNKNOWNS]
    local_checks = {
        "token_field": TOKEN_FIELD,
        "max_completion_tokens": payload.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS),
        "max_tokens_absent": TOKEN_PARAM_MAX_TOKENS not in payload,
        "temperature_absent": "temperature" not in payload,
        "thinking_absent": "thinking" not in payload,
        "json_object_local": payload.get("response_format") == {"type": "json_object"},
        "messages_present": bool(messages),
        "endpoint": PRODUCTION_ENDPOINT,
        "model": payload.get("model") or MODEL,
        "sdk_serialization": bool(capture.get("serialization_pass")),
        "token_parameter_local": (
            "PASS" if payload.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS) == SEMANTIC_TOKEN_BUDGET
            else "FAIL"
        ),
        "json_object_server_acceptance": CONFIDENCE_UNKNOWN,
        "max_completion_tokens_server_acceptance": CONFIDENCE_UNKNOWN,
        "unknown_is_not_pass": True,
    }
    api_compatibility = {
        "phase": PHASE,
        "provider": PROVIDER,
        "model": MODEL,
        "endpoint": PRODUCTION_ENDPOINT,
        "sdk_method": "client.chat.completions.create",
        "token_contract": contract.to_dict(),
        "local_checks": local_checks,
        "local_checkable_pass": local_ok and bool(capture.get("serialization_pass")),
        "local_failures": local_failures,
        "server_only_unknowns": server_unknowns,
        "server_only_unknown_fields": [item["field"] for item in server_unknowns],
        "unknown_is_not_pass": True,
        "no_live_probe_authorized": True,
        "readiness_class": (
            compat_engine_readiness.readiness_class
            or READY_WITH_SERVER_UNVERIFIED_FIELDS
        ),
        "cannot_claim_server_acceptance": True,
        "sdk_capture": {
            "serialization_pass": capture.get("serialization_pass"),
            "max_completion_tokens": capture.get("token_limit"),
            "max_tokens_absent": capture.get("max_tokens_absent"),
            "temperature_absent": capture.get("temperature_absent"),
            "thinking_absent": capture.get("thinking_absent"),
            "json_object": capture.get("json_object"),
            "network_calls": capture.get("network_calls"),
            "prepared_without_send": capture.get("prepared_without_send"),
        },
        "compatibility": compat,
        "historical_4b25_request_sha256": EXPECTED_REQUEST_SHA256_HISTORICAL_4B25,
        "corrected_request_sha256": actual_sha,
        "secrets_included": False,
        "http_sent": False,
        "remote_invocations": 0,
    }
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
                "readiness_class": readiness.get("readiness_class")
                or compat_engine_readiness.readiness_class,
            },
            "identities_before": frozen.get("identities_before"),
            "identities_after": frozen.get("identities_after"),
            "inputs_unchanged": frozen.get("inputs_unchanged"),
            "canonical_hashes": {
                "source_map_pre": source_sha,
                "editorial_plan_pre": plan_sha,
                "clean_transcript_pre": transcript_sha,
                "source_map_post": source_after,
                "editorial_plan_post": plan_after,
                "clean_transcript_post": transcript_after,
                "match": (
                    source_sha == EXPECTED_SOURCE_MAP
                    and plan_sha == EXPECTED_EDITORIAL_PLAN
                    and transcript_sha == EXPECTED_CLEAN_TRANSCRIPT
                    and source_after == EXPECTED_SOURCE_MAP
                    and plan_after == EXPECTED_EDITORIAL_PLAN
                    and transcript_after == EXPECTED_CLEAN_TRANSCRIPT
                ),
            },
            "language": frozen.get("language"),
            "benchmark": frozen.get("benchmark"),
            "contracts": frozen.get("contracts"),
            "evidence_sha256": frozen.get("evidence_sha256"),
            "candidate_handles": frozen.get("candidate_handles"),
            "paragraph_texts": frozen.get("paragraph_texts"),
            "gate_input": frozen.get("gate_input"),
            "request": {
                **request,
                "expected_sha256": EXPECTED_REQUEST_SHA256,
                "identity_match": actual_sha == EXPECTED_REQUEST_SHA256,
                "historical_4b25_sha256": EXPECTED_REQUEST_SHA256_HISTORICAL_4B25,
            },
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
            "api_compatibility": api_compatibility,
            "server_only_unknowns": server_unknowns,
            "http_sent": False,
            "engine_generate_called": False,
            "remote_invocations": 0,
            "expected_request_sha256": EXPECTED_REQUEST_SHA256,
            "secrets_included": False,
        }
    )


__all__ = ["SERVER_ONLY_UNKNOWNS", "build_precall"]
