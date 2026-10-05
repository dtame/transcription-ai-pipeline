"""Local transport and SDK preflight. No remote consumption."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

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
from app.book_semantic_gate_4b26.runtime import interpreter_match, runtime_snapshot
from app.book_semantic_gate_4b261.costing import estimate_cost, pricing_context
from app.book_semantic_gate_4b29.transport import semantic_transport_20_candidate
from app.book_semantic_gate_4b210.constants import (
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_OPENAI_SDK_VERSION,
    EXPECTED_SOURCE_MAP,
    FALLBACKS,
    H01_COMPLETION_TOKENS,
    H01_COST_USD,
    H01_INPUT_TOKENS,
    H01_REASONING_TOKENS,
    H02_COMPLETION_TOKENS,
    H02_COST_USD,
    H02_INPUT_TOKENS,
    H02_REASONING_TOKENS,
    H11_COMPLETION_TOKENS,
    H11_COST_USD,
    H11_INPUT_TOKENS,
    H11_REASONING_TOKENS,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PRODUCTION_ENDPOINT,
    PROJECT_NAME,
    PROVIDER,
    RETRIES,
    SDK_MAX_RETRIES,
    SELECTED_CASE_HANDLE,
    SEMANTIC_TOKEN_BUDGET,
    TOKEN_FIELD,
    TRANSPORT_VERSION_20_ACTIVATED,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b210.request import freeze_selected_request, serialize_selected_sdk


SERVER_ONLY_UNKNOWNS = (
    {
        "field": "json_object_server_capability",
        "status": CONFIDENCE_UNKNOWN,
        "note": (
            "Local serialization of response_format=json_object is PASS. "
            "Whether gpt-5.6-terra will emit a usable JSON object for this "
            "2.0 request remains UNKNOWN_SERVER_SIDE."
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


def _user_and_system(payload: Mapping[str, Any]) -> tuple[str, str]:
    system = ""
    user = ""
    for message in payload.get("messages") or []:
        if message.get("role") == "system":
            system = str(message.get("content") or "")
        elif message.get("role") == "user":
            user = str(message.get("content") or "")
    return system, user


def transport_20_preflight() -> dict[str, Any]:
    transport = semantic_transport_20_candidate()
    contract = resolve_chat_completions_token_contract(MODEL)
    return {
        "phase": PHASE,
        "transport_version": TRANSPORT_VERSION_20_CANDIDATE,
        "transport_activated": TRANSPORT_VERSION_20_ACTIVATED,
        "schema_sha256": transport.get("schema_sha256"),
        "model_must_not_emit_offsets": transport.get("model_must_not_emit_offsets"),
        "model_must_not_copy_unit_text": transport.get("model_must_not_copy_unit_text"),
        "output_fields": transport.get("output_fields"),
        "errors_not_repaired": transport.get("errors"),
        "provider": PROVIDER,
        "model": MODEL,
        "endpoint": PRODUCTION_ENDPOINT,
        "token_field": TOKEN_FIELD,
        "token_parameter": contract.parameter,
        "do_not_send": list(contract.do_not_send),
        "max_completion_tokens": SEMANTIC_TOKEN_BUDGET,
        "response_format": {"type": OUTPUT_MODE},
        "temperature": "omit",
        "reasoning_effort": "omit",
        "retries": RETRIES,
        "fallbacks": FALLBACKS,
        "sdk_max_retries": SDK_MAX_RETRIES,
        "finish_reason_capture_planned": True,
        "usage_capture_planned": True,
        "reasoning_tokens_capture_planned_when_available": True,
        "real_transport_not_activated": True,
        "secrets_included": False,
    }


def sdk_compatibility(*, root: Path | None = None) -> dict[str, Any]:
    runtime = runtime_snapshot(root=root)
    interp = interpreter_match(root=root)
    contract = resolve_chat_completions_token_contract(MODEL)
    version = str(runtime.get("openai_sdk_version") or "")
    return {
        "phase": PHASE,
        "canonical_python": CANONICAL_PYTHON_EXECUTABLE,
        "actual_python": interp.get("actual"),
        "interpreter_match": interp.get("match"),
        "openai_sdk_version": version,
        "historical_openai_sdk_version": EXPECTED_OPENAI_SDK_VERSION,
        "openai_sdk_version_match": version == EXPECTED_OPENAI_SDK_VERSION,
        "do_not_assume_historical_version": True,
        "token_contract": contract.to_dict(),
        "json_object_local_serialization": "LOCALLY_VERIFIED",
        "json_object_server_acceptance": CONFIDENCE_UNKNOWN,
        "max_tokens_forbidden_for_terra": True,
        "temperature_omitted": True,
        "reasoning_effort_omitted": True,
        "sdk_import": (runtime.get("sdk") or {}).get("import"),
        "from_openai_import_OpenAI": (runtime.get("sdk") or {}).get(
            "from_openai_import_OpenAI"
        ),
        "no_real_api_key_used": True,
        "client_not_used_to_send": True,
        "secrets_included": False,
    }


def context_budget(
    payload: Mapping[str, Any],
    *,
    frozen: Mapping[str, Any] | None = None,
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
        "minimal_json_tokens_estimate": 80,
        "plausible_detailed_json_tokens_estimate": 500,
        "high_reasoning_json_tokens_estimate": H02_COMPLETION_TOKENS,
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
    payload: Mapping[str, Any],
    *,
    budget: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    input_tokens = int((budget or {}).get("estimated_input_tokens") or 0)
    if input_tokens <= 0:
        system, user = _user_and_system(payload)
        input_tokens = estimate_tokens(system + "\n" + user).tokens
    short_out = int((budget or {}).get("minimal_json_tokens_estimate") or 80)
    detailed_out = int((budget or {}).get("plausible_detailed_json_tokens_estimate") or 500)
    high_out = int((budget or {}).get("high_reasoning_json_tokens_estimate") or H02_COMPLETION_TOKENS)
    exhausted = SEMANTIC_TOKEN_BUDGET
    pricing = pricing_context()
    short = estimate_cost(input_tokens, short_out)
    high = estimate_cost(input_tokens, high_out)
    full = estimate_cost(input_tokens, exhausted)
    recommended = estimate_cost(input_tokens, high_out)
    return {
        "phase": PHASE,
        "pricing": pricing,
        "pricing_effective_date": pricing.get("effective_date"),
        "pricing_are_configured_project_rates": True,
        "not_live_provider_prices": True,
        "configured_rates": {
            "input_usd_per_million": pricing.get("input_cost_per_1m_tokens"),
            "output_usd_per_million": pricing.get("output_cost_per_1m_tokens"),
            "historical_reference_input": 2.0,
            "historical_reference_output": 12.0,
        },
        "input_tokens_estimate": input_tokens,
        "estimated": True,
        "output_tokens_plausible": detailed_out,
        "reasoning_tokens": "UNKNOWN",
        "reasoning_tokens_not_double_counted": True,
        "completion_tokens_may_include_reasoning": True,
        "observed_not_estimated": {
            "h01": {
                "input_tokens": H01_INPUT_TOKENS,
                "completion_tokens": H01_COMPLETION_TOKENS,
                "reasoning_tokens": H01_REASONING_TOKENS,
                "cost_usd": H01_COST_USD,
            },
            "h02": {
                "input_tokens": H02_INPUT_TOKENS,
                "completion_tokens": H02_COMPLETION_TOKENS,
                "reasoning_tokens": H02_REASONING_TOKENS,
                "cost_usd": H02_COST_USD,
            },
            "h11": {
                "input_tokens": H11_INPUT_TOKENS,
                "completion_tokens": H11_COMPLETION_TOKENS,
                "reasoning_tokens": H11_REASONING_TOKENS,
                "cost_usd": H11_COST_USD,
            },
        },
        "central_estimate": recommended,
        "short_json": short,
        "detailed_json": estimate_cost(input_tokens, detailed_out),
        "high_reasoning_like_h02": high,
        "if_8192_exhausted": full,
        "theoretical_maximum_usd": full.get("total_cost_usd"),
        "short_response_cost_estimate": short.get("total_cost_usd"),
        "full_budget_cost_estimate": full.get("total_cost_usd"),
        "cost_estimate": recommended.get("total_cost_usd"),
        "maximum_cost_estimate": full.get("total_cost_usd"),
        "reasoning_token_uncertainty": {
            "reasoning_tokens": "UNKNOWN",
            "visible_output_may_be_less_than_completion": True,
            "cost_not_linear_with_max_completion_tokens": True,
            "unknown_is_not_zero": True,
            "reasoning_tokens_can_change_actual_cost": True,
            "do_not_assume_low_reasoning": True,
            "do_not_count_reasoning_twice_if_inside_completion": True,
        },
        "not_a_guarantee": True,
        "no_provider_cost_in_this_phase": True,
        "secrets_included": False,
    }


def canary_success_criteria() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "selected_handle": SELECTED_CASE_HANDLE,
        "PASS": [
            "Response is complete",
            "JSON is valid",
            "Contract 2.0.1 is respected",
            "All units are covered",
            "Evidence handles are valid",
            "Reason codes are from the closed catalog",
            "Supported propositions are accepted",
            "Unsupported semantic additions are blocked",
            "No substantial false rejection is observed",
            "No unsupported semantic addition is accepted",
        ],
        "PARTIAL": [
            "The targeted phenomenon is correctly detected",
            "But false rejections appear",
            "Or contract problems remain",
            "Or compliance is insufficient for promotion",
        ],
        "FAIL": [
            "An important invention is accepted",
            "A targeted error is not detected",
            "The response is unusable",
            "The output is truncated",
            "The model does not respect fundamental constraints",
        ],
        "BLOCKED_PRECALL": [
            "Canonical hashes do not match",
            "Request is not deterministic",
            "A label leak is detected",
            "SDK serialization fails",
            "Provider configuration is incompatible",
        ],
        "http_failure_after_send_is_not_blocked_precall": True,
        "not_executed": True,
        "fakeai_is_not_terra_proof": True,
        "secrets_included": False,
    }


def strategic_stop_rule() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "rule": (
            "If the future real canary still shows substantial false "
            "rejections, poor paraphrase recognition, insufficient detection "
            "of additions, or an inability to respect the simplified contract, "
            "do not automatically launch another series of paid corrections "
            "and tests. The next action must be a human review of the "
            "validator's role in the architecture."
        ),
        "options_for_human_review_only": [
            "Targeted semantic validation of high-risk propositions",
            "Chapter-level validation with human review",
            "Reduced granularity",
            "Different model or verification strategy",
            "More conservative acceptance policy",
            "Different split between automatic checks and human review",
        ],
        "none_of_these_options_activated": True,
        "no_automatic_paid_retry_series": True,
        "secrets_included": False,
    }


def build_preflight(*, root: Path | None = None) -> dict[str, Any]:
    interp = interpreter_match(root=root)
    runtime = runtime_snapshot(root=root)
    before = verify_canonical_inputs(root=root)
    frozen = freeze_selected_request(root=root)
    serialized = serialize_selected_sdk(root=root)
    after = verify_canonical_inputs(root=root)
    payload = dict(frozen.get("payload") or {})
    budget = context_budget(payload, frozen=frozen)
    cost = cost_estimate(payload, budget=budget)
    contract = resolve_chat_completions_token_contract(MODEL)

    blockers: list[str] = []
    if not interp.get("match"):
        blockers.append("canonical_runtime")
    if (before.get("source_map") or {}).get("sha256") != EXPECTED_SOURCE_MAP:
        blockers.append("source_map")
    if (before.get("editorial_plan") or {}).get("sha256") != EXPECTED_EDITORIAL_PLAN:
        blockers.append("editorial_plan")
    if (before.get("clean_transcript") or {}).get("sha256") != EXPECTED_CLEAN_TRANSCRIPT:
        blockers.append("clean_transcript")
    if (after.get("source_map") or {}).get("sha256") != EXPECTED_SOURCE_MAP:
        blockers.append("source_map_post")
    if not frozen.get("label_leak_pass"):
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
    if not budget.get("context_safe"):
        blockers.append("context_budget")
    if not production_book_absent(PROJECT_NAME):
        blockers.append("book_json_present")

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
                    "expected_historical": EXPECTED_OPENAI_SDK_VERSION,
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
                    "max_retries_future": 0,
                    "fallbacks": 0,
                },
                "artifact_identity": {
                    "before": snapshot_identities(before),
                    "after": snapshot_identities(after),
                },
                "human_labels_absent": frozen.get("label_leak_pass"),
                "sdk_serialization": serialized.get("serialization_pass"),
                "request_sha256": frozen.get("sha256"),
                "request_determinism": frozen.get("determinism"),
                "context_budget": budget.get("context_safe"),
                "cost_estimate_documented": cost.get("short_json") is not None,
            },
            "server_only_unknowns": list(SERVER_ONLY_UNKNOWNS),
            "json_object_server_capability": "UNKNOWN",
            "READY_FOR_ONE_REAL_TERRA_CANARY": not blocked,
            "REAL_TERRA_CANARY_AUTHORIZED": False,
            "secrets_included": False,
        }
    )


__all__ = [
    "build_preflight",
    "canary_success_criteria",
    "context_budget",
    "cost_estimate",
    "sdk_compatibility",
    "strategic_stop_rule",
    "transport_20_preflight",
]
