"""Local preflight for a future P3 Terra call. No remote consumption."""

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
from app.book_semantic_gate_4b272.constants import (
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_OPENAI_SDK_VERSION,
    EXPECTED_SOURCE_MAP,
    H01_REQUEST_SHA256,
    MODEL,
    OBSERVED_4B27_COMPLETION_TOKENS,
    OBSERVED_4B27_COST_USD,
    OBSERVED_4B27_INPUT_TOKENS,
    OBSERVED_4B27_REASONING_TOKENS,
    OUTPUT_MODE,
    PHASE,
    PRODUCTION_ENDPOINT,
    PROJECT_NAME,
    PROMPT_VERSION_111,
    PROVIDER,
    SELECTED_CASE_HANDLE,
    SEMANTIC_TOKEN_BUDGET,
    TOKEN_FIELD,
    TRANSPORT_VERSION_11,
)
from app.book_semantic_gate_4b272.causal import review_causal_claim
from app.book_semantic_gate_4b272.evidence import build_canonical_evidence_inventory
from app.book_semantic_gate_4b272.identity import p3_benchmark_identity
from app.book_semantic_gate_4b272.request import freeze_p3_request, serialize_p3_sdk


SERVER_ONLY_UNKNOWNS = (
    {
        "field": "json_object_server_capability",
        "status": CONFIDENCE_UNKNOWN,
        "note": (
            "Local serialization of response_format=json_object is PASS. "
            "Whether gpt-5.6-terra will emit a usable JSON object for P3 "
            "remains UNKNOWN_SERVER_SIDE."
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
    min_json = 80
    detailed_json = 500
    return {
        "phase": PHASE,
        "estimated_input_tokens": estimate.tokens,
        "estimated": True,
        "method": estimate.method,
        "max_completion_tokens": reserved_output,
        "do_not_confuse_budget_with_consumed_tokens": True,
        "minimal_json_tokens_estimate": min_json,
        "plausible_detailed_json_tokens_estimate": detailed_json,
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
    short_out = int((budget or {}).get("minimal_json_tokens_estimate") or 80)
    detailed_out = int((budget or {}).get("plausible_detailed_json_tokens_estimate") or 500)
    exhausted = SEMANTIC_TOKEN_BUDGET
    pricing = pricing_context()
    return {
        "phase": PHASE,
        "pricing": pricing,
        "pricing_effective_date": pricing.get("effective_date"),
        "input_tokens_estimate": input_tokens,
        "estimated": True,
        "short_json": estimate_cost(input_tokens, short_out),
        "detailed_json": estimate_cost(input_tokens, detailed_out),
        "if_8192_exhausted": estimate_cost(input_tokens, exhausted),
        "observed_h01_4b27": {
            "input_tokens": OBSERVED_4B27_INPUT_TOKENS,
            "completion_tokens": OBSERVED_4B27_COMPLETION_TOKENS,
            "reasoning_tokens": OBSERVED_4B27_REASONING_TOKENS,
            "total_cost_usd": OBSERVED_4B27_COST_USD,
        },
        "reasoning_token_uncertainty": {
            "reasoning_tokens": "UNKNOWN",
            "visible_output_may_be_less_than_completion": True,
            "cost_not_linear_with_max_completion_tokens": True,
            "unknown_is_not_zero": True,
            "reasoning_tokens_can_change_actual_cost": True,
        },
        "not_a_guarantee": True,
        "no_provider_cost_in_this_phase": True,
        "secrets_included": False,
    }


def future_canary_criteria() -> dict[str, Any]:
    return {
        "technical_pass": [
            "API accepts the request",
            "Non-empty response",
            "Valid JSON",
            "finish_reason compatible with a complete response",
            "Compact contract respected",
            "P3 identified",
            "Every substantive proposition covered",
            "Valid spans and evidence handles",
            "Reason codes present when required",
            "Deterministic replay",
        ],
        "semantic_pass": [
            "The unjustified causal relation is identified",
            "The corresponding proposition is QUESTIONABLE or UNSUPPORTED",
            "A relevant reason code is supplied",
            "Other supported propositions are not rejected without reason",
            "The global verdict blocks paragraph acceptance",
            "Justification rests on the available evidence",
        ],
        "partial": (
            "Technically usable response with semantic disagreement or uncertainty"
        ),
        "fail": [
            "API error",
            "Empty response",
            "Invalid JSON",
            "Incomplete contract",
            "Unevaluated substantive clause",
            "Invalid evidence",
            "Unjustified acceptance of the causal relation",
        ],
        "blocked_precall": "Any local check failure before invocation",
        "not_executed": True,
    }


def build_preflight(*, root: Path | None = None) -> dict[str, Any]:
    interp = interpreter_match(root=root)
    runtime = runtime_snapshot(root=root)
    before = verify_canonical_inputs(root=root)
    identity = p3_benchmark_identity(root=root)
    inventory = build_canonical_evidence_inventory(root=root)
    causal = review_causal_claim(inventory, root=root)
    frozen = freeze_p3_request(root=root)
    serialized = serialize_p3_sdk(root=root)
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
    if (before.get("source_map") or {}).get("sha256") != EXPECTED_SOURCE_MAP:
        blockers.append("source_map")
    if (before.get("editorial_plan") or {}).get("sha256") != EXPECTED_EDITORIAL_PLAN:
        blockers.append("editorial_plan")
    if (before.get("clean_transcript") or {}).get("sha256") != EXPECTED_CLEAN_TRANSCRIPT:
        blockers.append("clean_transcript")
    if (after.get("source_map") or {}).get("sha256") != EXPECTED_SOURCE_MAP:
        blockers.append("source_map_post")
    if not identity.get("identified"):
        blockers.append("p3_identity")
    if not inventory.get("complete"):
        blockers.append("evidence")
    if causal.get("BENCHMARK_EVIDENCE_CONFLICT"):
        blockers.append("BENCHMARK_EVIDENCE_CONFLICT")
    if frozen.get("prompt_version") != PROMPT_VERSION_111:
        blockers.append("candidate_prompt")
    if frozen.get("transport_version") != TRANSPORT_VERSION_11:
        blockers.append("candidate_transport")
    if not frozen.get("exactly_one_case"):
        blockers.append("single_case")
    if not frozen.get("label_leak_pass"):
        blockers.append("label_leakage")
    if not frozen.get("independent_of_h01"):
        blockers.append("h01_independence")
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
    if not frozen.get("differs_from_h01"):
        blockers.append("request_not_distinct_from_h01")
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
            "openai_http": 0,
            "anthropic_http": 0,
            "selected_case": SELECTED_CASE_HANDLE,
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
                    "prompt": PROMPT_VERSION_111,
                    "transport": TRANSPORT_VERSION_11,
                },
                "evidence_complete": inventory.get("complete"),
                "benchmark_evidence_conflict": causal.get("BENCHMARK_EVIDENCE_CONFLICT"),
                "human_labels_absent": frozen.get("label_leak_pass"),
                "sdk_serialization": serialized.get("serialization_pass"),
                "request_sha256": frozen.get("sha256"),
                "request_determinism": frozen.get("determinism"),
                "historical_h01_sha256": H01_REQUEST_SHA256,
                "context_budget": budget.get("context_safe"),
                "cost_estimate_documented": cost.get("short_json") is not None,
            },
            "server_only_unknowns": list(SERVER_ONLY_UNKNOWNS),
            "future_canary_criteria": future_canary_criteria(),
            "json_object_server_capability": "UNKNOWN",
            "READY_FOR_P3_REAL_CANARY_HUMAN_REVIEW": not blocked,
            "READY_FOR_NEW_REMOTE_TERRA_CALL": False,
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
