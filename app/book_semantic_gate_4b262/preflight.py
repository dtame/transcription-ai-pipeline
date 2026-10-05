"""Local preflight for a future single-case Terra call. No remote consumption."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from app.ai.capabilities import resolve_capabilities
from app.ai.estimation import estimate_tokens
from app.ai.openai_compat import (
    CONFIDENCE_UNKNOWN,
    TOKEN_PARAM_MAX_COMPLETION_TOKENS,
    TOKEN_PARAM_MAX_TOKENS,
    resolve_chat_completions_token_contract,
)
from app.ai.provider_preflight import redact_secrets
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.identity import snapshot_identities, verify_canonical_inputs
from app.book_semantic_gate_4b24.identity import benchmark_identity
from app.book_semantic_gate_4b26.runtime import interpreter_match, runtime_snapshot
from app.book_semantic_gate_4b261.costing import estimate_cost, pricing_context
from app.book_semantic_gate_4b262.constants import (
    CANDIDATE_PROMPT_VERSION,
    CANDIDATE_TRANSPORT_VERSION,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_OPENAI_SDK_VERSION,
    EXPECTED_REQUEST_SHA256_4B26,
    EXPECTED_SOURCE_MAP,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PRODUCTION_ENDPOINT,
    PROJECT_NAME,
    PROVIDER,
    SELECTED_CASE_HANDLE,
    SEMANTIC_TOKEN_BUDGET,
    TOKEN_FIELD,
)
from app.book_semantic_gate_4b262.request import (
    freeze_single_case_request,
    serialize_single_case_sdk,
)
from app.book_semantic_gate_4b262.selection import evidence_manifest, review_selected_case


SERVER_ONLY_UNKNOWNS = (
    {
        "field": "json_object_server_capability",
        "status": CONFIDENCE_UNKNOWN,
        "note": (
            "Local serialization of response_format=json_object is PASS. "
            "Whether gpt-5.6-terra will emit a usable JSON object remains "
            "UNKNOWN_SERVER_SIDE."
        ),
    },
    {
        "field": "reasoning_or_thinking_server_behavior",
        "status": CONFIDENCE_UNKNOWN,
        "note": "Thinking is omitted. Server reasoning remains UNKNOWN.",
    },
    {
        "field": "actual_cost",
        "status": CONFIDENCE_UNKNOWN,
        "note": "Estimates are not a guarantee. Unknown is not zero.",
    },
)


def _user_and_system(payload: dict[str, Any]) -> tuple[str, str]:
    system = ""
    user = ""
    for message in payload.get("messages") or []:
        if message.get("role") == "system":
            system = str(message.get("content") or "")
        elif message.get("role") == "user":
            user = str(message.get("content") or "")
    return system, user


def context_budget(
    payload: dict[str, Any],
    *,
    frozen: dict[str, Any] | None = None,
) -> dict[str, Any]:
    system, user = _user_and_system(payload)
    estimate = estimate_tokens(system + "\n" + user)
    caps = resolve_capabilities(PROVIDER, MODEL)
    reserved_output = SEMANTIC_TOKEN_BUDGET
    usable = None
    input_budget = None
    if caps is not None:
        usable = caps.usable_context()
        input_budget = caps.usable_input_context()
    remaining = None
    if input_budget is not None:
        remaining = int(input_budget) - int(estimate.tokens)
    safe = remaining is None or remaining > 0
    return {
        "phase": PHASE,
        "estimated_input_tokens": estimate.tokens,
        "estimated": True,
        "method": estimate.method,
        "max_completion_tokens": reserved_output,
        "do_not_confuse_budget_with_consumed_tokens": True,
        "model_context_window": getattr(caps, "context_window", None),
        "usable_context": usable,
        "usable_input_context": input_budget,
        "remaining_input_budget_estimate": remaining,
        "context_safe": safe,
        "long_context_regime": "NOT APPLICABLE",
        "request_sha256": (frozen or {}).get("sha256"),
        "secrets_included": False,
    }


def cost_estimate(
    payload: dict[str, Any],
    *,
    budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    input_tokens = int((budget or {}).get("estimated_input_tokens") or 0)
    if input_tokens <= 0:
        system, user = _user_and_system(payload)
        input_tokens = estimate_tokens(system + "\n" + user).tokens
    short_out = 80
    detailed_out = 400
    exhausted = SEMANTIC_TOKEN_BUDGET
    pricing = pricing_context()
    return {
        "phase": PHASE,
        "pricing": pricing,
        "input_tokens_estimate": input_tokens,
        "estimated": True,
        "short_json": estimate_cost(input_tokens, short_out),
        "detailed_json": estimate_cost(input_tokens, detailed_out),
        "if_8192_exhausted": estimate_cost(input_tokens, exhausted),
        "reasoning_token_uncertainty": {
            "reasoning_tokens": "UNKNOWN",
            "visible_output_may_be_less_than_completion": True,
            "cost_not_linear_with_max_completion_tokens": True,
            "unknown_is_not_zero": True,
        },
        "previous_4b261_approx": {
            "short_json_usd": 0.004,
            "full_budget_usd": 0.102,
            "not_a_guarantee": True,
        },
        "not_a_guarantee": True,
        "secrets_included": False,
    }


def future_canary_criteria() -> dict[str, Any]:
    return {
        "technical_pass": [
            "Exactly one remote invocation",
            "Request accepted",
            "Non-empty response",
            "Valid JSON",
            "Compact 1.1-candidate contract respected",
            "Single case correctly identified",
            "Every substantive claim covered",
            "Valid spans and references",
            "No missing result for the selected case",
            "Deterministic replay",
        ],
        "semantic_pass": [
            "Verdict matches the internal human label of the selected case",
            "Justifications and references actually support the verdict",
            "For a negative case the problematic addition is identified and blocked",
            "For a positive case supported content is not rejected without justification",
        ],
        "fail": [
            "API rejection",
            "Empty response",
            "Budget exhausted without a decision",
            "Invalid JSON",
            "Incomplete contract",
            "Unevaluated substantive claim",
            "Incorrect semantic verdict",
            "Invented or unauthorized evidence",
        ],
        "blocked_precall": "Any local check failure before invocation",
        "one_case_pass_is_not_ten_case_validation": True,
        "not_executed": True,
    }


def build_preflight(*, root: Path | None = None) -> dict[str, Any]:
    interp = interpreter_match(root=root)
    runtime = runtime_snapshot(root=root)
    before = verify_canonical_inputs(root=root)
    frozen = freeze_single_case_request(root=root)
    serialized = serialize_single_case_sdk(root=root)
    selection = review_selected_case(root=root)
    evidence = evidence_manifest(root=root)
    after = verify_canonical_inputs(root=root)
    bench = benchmark_identity(root=root)
    payload = dict(frozen.get("payload") or {})
    budget = context_budget(payload, frozen=frozen)
    cost = cost_estimate(payload, budget=budget)
    contract = resolve_chat_completions_token_contract(MODEL)

    blockers: list[str] = []
    if not interp.get("match"):
        blockers.append("canonical_runtime")
    if str(runtime.get("openai_sdk_version") or "") != EXPECTED_OPENAI_SDK_VERSION:
        blockers.append("openai_sdk_version")
    if runtime.get("openai_sdk_import") not in {"PASS", "pass", True, None}:
        if not runtime.get("openai_sdk_version"):
            blockers.append("sdk_unavailable")
    if (before.get("source_map") or {}).get("sha256") != EXPECTED_SOURCE_MAP:
        blockers.append("source_map")
    if (before.get("editorial_plan") or {}).get("sha256") != EXPECTED_EDITORIAL_PLAN:
        blockers.append("editorial_plan")
    if (before.get("clean_transcript") or {}).get("sha256") != EXPECTED_CLEAN_TRANSCRIPT:
        blockers.append("clean_transcript")
    if (after.get("source_map") or {}).get("sha256") != EXPECTED_SOURCE_MAP:
        blockers.append("source_map_post")
    if not selection.get("selected"):
        blockers.append("selected_case")
    if not evidence.get("complete"):
        blockers.append("evidence")
    if frozen.get("prompt_version") != CANDIDATE_PROMPT_VERSION:
        blockers.append("candidate_prompt")
    if frozen.get("transport_version") != CANDIDATE_TRANSPORT_VERSION:
        blockers.append("candidate_transport")
    if not frozen.get("exactly_one_case"):
        blockers.append("single_case")
    if int(frozen.get("label_leakage") or 0) != 0:
        blockers.append("label_leakage")
    if not serialized.get("serialization_pass"):
        blockers.append("sdk_serialization")
    if payload.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS) != SEMANTIC_TOKEN_BUDGET:
        blockers.append("max_completion_tokens")
    if TOKEN_PARAM_MAX_TOKENS in payload:
        blockers.append("max_tokens_present")
    if "temperature" in payload:
        blockers.append("temperature_present")
    if not frozen.get("determinism"):
        blockers.append("request_determinism")
    if not frozen.get("differs_from_4b26"):
        blockers.append("request_not_distinct_from_4b26")
    if not budget.get("context_safe"):
        blockers.append("context_budget")
    if not production_book_absent(PROJECT_NAME):
        blockers.append("book_json_present")
    if not bench.get("identity_match"):
        blockers.append("benchmark_identity")

    unique = list(dict.fromkeys(blockers))
    blocked = bool(unique)
    return redact_secrets(
        {
            "phase": PHASE,
            "status": "BLOCKED_PRECALL" if blocked else "LOCAL_PREFLIGHT_PASS",
            "blocked_precall": blocked,
            "blockers": unique,
            "remote_authorization_consumed": False,
            "provider_calls": 0,
            "checks": {
                "canonical_runtime": interp,
                "sdk_available": {
                    "version": runtime.get("openai_sdk_version"),
                    "expected": EXPECTED_OPENAI_SDK_VERSION,
                    "python": sys.executable,
                    "canonical_python": CANONICAL_PYTHON_EXECUTABLE,
                },
                "provider_configuration": {
                    "provider": PROVIDER,
                    "model": MODEL,
                    "endpoint": PRODUCTION_ENDPOINT,
                    "token_field": TOKEN_FIELD,
                    "contract_parameter": contract.parameter,
                    "output_mode": OUTPUT_MODE,
                },
                "artifact_identity": {
                    "before": snapshot_identities(before),
                    "after": snapshot_identities(after),
                },
                "candidate_contract": {
                    "prompt": CANDIDATE_PROMPT_VERSION,
                    "transport": CANDIDATE_TRANSPORT_VERSION,
                },
                "selected_case": SELECTED_CASE_HANDLE,
                "evidence_complete": evidence.get("complete"),
                "human_labels_absent": frozen.get("label_leak_pass"),
                "sdk_serialization": serialized.get("serialization_pass"),
                "local_parameter_compat": {
                    "max_completion_tokens": payload.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS),
                    "max_tokens_absent": TOKEN_PARAM_MAX_TOKENS not in payload,
                    "temperature_absent": "temperature" not in payload,
                },
                "request_sha256": frozen.get("sha256"),
                "request_determinism": frozen.get("determinism"),
                "historical_4b26_sha256": EXPECTED_REQUEST_SHA256_4B26,
                "context_budget": budget.get("context_safe"),
                "cost_estimate_documented": cost.get("short_json") is not None,
                "historical_artifacts_unchanged": (
                    (before.get("source_map") or {}).get("sha256") == EXPECTED_SOURCE_MAP
                    and (after.get("source_map") or {}).get("sha256") == EXPECTED_SOURCE_MAP
                ),
            },
            "server_only_unknowns": list(SERVER_ONLY_UNKNOWNS),
            "future_canary_criteria": future_canary_criteria(),
            "json_object_server_capability": "UNKNOWN",
            "secrets_included": False,
        }
    )


__all__ = [
    "SERVER_ONLY_UNKNOWNS",
    "build_preflight",
    "context_budget",
    "cost_estimate",
    "future_canary_criteria",
]
