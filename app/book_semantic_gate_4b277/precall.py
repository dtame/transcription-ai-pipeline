"""Pre-call gates. Provider is not contacted. Remote slot is not consumed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.ai.openai_compat import (
    TOKEN_PARAM_MAX_COMPLETION_TOKENS,
    TOKEN_PARAM_MAX_TOKENS,
)
from app.ai.provider_preflight import (
    REASON_PROVIDER_CREDENTIAL_NOT_READY,
    check_provider_runtime_readiness,
    redact_secrets,
)
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
from app.book_semantic_gate_4b24.engine import credential_available
from app.book_semantic_gate_4b24.identity import benchmark_identity
from app.book_semantic_gate_4b26.runtime import interpreter_match, runtime_snapshot
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle
from app.book_semantic_gate_4b276.evidence import build_canonical_evidence_inventory
from app.book_semantic_gate_4b276.identity import clause_offsets, synthetic_paragraph_text
from app.book_semantic_gate_4b276.preflight import context_budget, cost_estimate
from app.book_semantic_gate_4b276.request import label_leakage_audit
from app.file_utils import content_hash
from app.book_semantic_gate_4b277.constants import (
    AUTHORIZATION_SCOPE,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_CLAUSE_END,
    EXPECTED_CLAUSE_START,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_OPENAI_SDK_VERSION,
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_112_SHA256,
    EXPECTED_PROMPT_113_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_SOURCE_MAP,
    H01_REQUEST_SHA256,
    H02_REQUEST_SHA256,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PRODUCTION_ENDPOINT,
    PROJECT_NAME,
    PROVIDER,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
    SEMANTIC_TOKEN_BUDGET,
    TOKEN_FIELD,
)
from app.book_semantic_gate_4b277.engine import inspect_sdk_retry_policy
from app.book_semantic_gate_4b277.paths import canary_lock_path
from app.book_semantic_gate_4b277.request import (
    evidence_matches_manifest,
    freeze_and_identify,
)


SERVER_ONLY_UNKNOWNS = (
    {
        "field": "json_object_server_capability",
        "status": "UNKNOWN",
        "note": (
            "Local serialization of response_format=json_object is PASS. "
            "Whether gpt-5.6-terra will emit a usable JSON object for h11 "
            "remains UNKNOWN_SERVER_SIDE."
        ),
    },
    {
        "field": "reasoning_or_thinking_server_behavior",
        "status": "UNKNOWN",
        "note": "Thinking is omitted. Server reasoning remains UNKNOWN.",
    },
    {
        "field": "actual_cost",
        "status": "UNKNOWN",
        "note": "Estimates are not a guarantee. Unknown is not zero.",
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


def build_precall(*, root: Path | None = None) -> dict[str, Any]:
    interp = interpreter_match(root=root)
    runtime = runtime_snapshot(root=root)
    runtime["phase"] = PHASE
    before = verify_canonical_inputs(root=root)
    identified = freeze_and_identify(root=root)
    after = verify_canonical_inputs(root=root)
    inventory = build_canonical_evidence_inventory(root=root)
    leak = label_leakage_audit(root=root)
    text = synthetic_paragraph_text(root=root)
    clause = clause_offsets(text)
    bench = benchmark_identity(root=root)
    payload = dict(identified.get("payload") or {})
    serialized = dict(identified.get("sdk") or {})
    budget = context_budget(payload, frozen=identified)
    cost = cost_estimate(payload, budget=budget)
    retry_inspect = inspect_sdk_retry_policy()
    lock_path = canary_lock_path(root=root)
    lock_available = not lock_path.exists()
    credential = credential_available()
    book_absent = production_book_absent(PROJECT_NAME)

    prompt_10_ok = (
        content_hash(system_prompt()) == EXPECTED_PROMPT_SYSTEM_SHA256
        and content_hash(instruction_prompt()) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
    )
    prompt_11_ok = candidate_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256
    prompt_111_ok = candidate_111_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256
    prompt_112_ok = candidate_112_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_112_SHA256
    prompt_113_ok = candidate_113_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256

    readiness = check_provider_runtime_readiness(
        PROVIDER,
        model=MODEL,
        request=identified.get("ai_request"),
        output_mode=OUTPUT_MODE,
        construct_client=True,
    )
    ready_ok, ready_failures = _readiness_pass(readiness.to_dict())

    blockers: list[str] = []
    if not interp.get("match"):
        blockers.append("canonical_runtime")
    if not interp.get("python_version_match"):
        blockers.append("python_version")
    if str(runtime.get("openai_sdk_version") or "") != EXPECTED_OPENAI_SDK_VERSION:
        blockers.append("openai_sdk_version")
    if not runtime.get("env_ignored_by_git", {}).get("ignored"):
        blockers.append("env_not_ignored")
    if not credential:
        blockers.append("openai_credential")
    for item in ready_failures:
        if item not in blockers:
            blockers.append(item)
    source_pre = (before.get("source_map") or {}).get("sha256")
    plan_pre = (before.get("editorial_plan") or {}).get("sha256")
    transcript_pre = (before.get("clean_transcript") or {}).get("sha256")
    source_post = (after.get("source_map") or {}).get("sha256")
    plan_post = (after.get("editorial_plan") or {}).get("sha256")
    transcript_post = (after.get("clean_transcript") or {}).get("sha256")
    if source_pre != EXPECTED_SOURCE_MAP or source_post != EXPECTED_SOURCE_MAP:
        blockers.append("source_map")
    if plan_pre != EXPECTED_EDITORIAL_PLAN or plan_post != EXPECTED_EDITORIAL_PLAN:
        blockers.append("editorial_plan")
    if (
        transcript_pre != EXPECTED_CLEAN_TRANSCRIPT
        or transcript_post != EXPECTED_CLEAN_TRANSCRIPT
    ):
        blockers.append("clean_transcript")
    if not prompt_10_ok:
        blockers.append("historical_prompt_1_0")
    if not prompt_11_ok:
        blockers.append("historical_prompt_1_1")
    if not prompt_111_ok:
        blockers.append("historical_prompt_1_1_1")
    if not prompt_112_ok:
        blockers.append("historical_prompt_1_1_2")
    if not prompt_113_ok:
        blockers.append("candidate_prompt_1_1_3")
    if not bench.get("identity_match"):
        blockers.append("benchmark_identity")
    if clause.get("start") != EXPECTED_CLAUSE_START or clause.get("end") != EXPECTED_CLAUSE_END:
        blockers.append("h11_clause_offsets")
    if not evidence_matches_manifest(inventory):
        blockers.append("evidence_manifest")
    if int(identified.get("label_leakage") or 0) != 0:
        blockers.append("label_leakage")
    if not identified.get("label_leak_pass"):
        blockers.append("label_leakage")
    if not leak.get("pass"):
        blockers.append("label_leakage")
    if leak.get("case_id_in_request"):
        blockers.append("case_id_leak")
    if leak.get("reason_codes_as_target_in_user"):
        blockers.append("target_reason_code_leak")
    if not identified.get("independent_of_h01_h02"):
        blockers.append("historical_independence")
    if not identified.get("identity_match"):
        blockers.append("request_sha256")
    if str(identified.get("sha256") or "") != EXPECTED_REQUEST_SHA256:
        blockers.append("request_sha256")
    if str(identified.get("frozen_artifact_sha256") or "") != EXPECTED_REQUEST_SHA256:
        blockers.append("frozen_4b276_artifact_sha256")
    if not identified.get("matches_frozen_4b276_artifact"):
        blockers.append("request_differs_from_frozen_artifact")
    if str(identified.get("sha256") or "") in {H01_REQUEST_SHA256, H02_REQUEST_SHA256}:
        blockers.append("request_is_historical_canary")
    if not identified.get("determinism"):
        blockers.append("request_determinism")
    if str(identified.get("first_sha256") or "") != str(identified.get("second_sha256") or ""):
        blockers.append("request_determinism")
    if not serialized.get("serialization_pass"):
        blockers.append("sdk_serialization")
    if int(serialized.get("network_calls") or 0) != 0:
        blockers.append("sdk_serialization_network")
    if not retry_inspect.get("pass"):
        blockers.append("no_retry_enforcement")
    if not budget.get("context_safe"):
        blockers.append("context_budget")
    if cost.get("short_json") is None:
        blockers.append("cost_estimate")
    if not lock_available:
        blockers.append("authorization_already_consumed")
    if not book_absent:
        blockers.append("book_json_present")
    if payload.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS) != SEMANTIC_TOKEN_BUDGET:
        blockers.append("max_completion_tokens")
    if TOKEN_PARAM_MAX_TOKENS in payload:
        blockers.append("max_tokens_present")
    if "temperature" in payload:
        blockers.append("temperature_present")
    if "thinking" in payload or "reasoning" in payload or "reasoning_effort" in payload:
        blockers.append("reasoning_params_present")
    if not identified.get("exactly_one_case"):
        blockers.append("single_case")
    if identified.get("handles_in_request") != [SELECTED_CASE_HANDLE]:
        blockers.append("single_case")

    unique = list(dict.fromkeys(blockers))
    blocked = bool(unique)
    hashes_match = (
        source_pre == EXPECTED_SOURCE_MAP
        and plan_pre == EXPECTED_EDITORIAL_PLAN
        and transcript_pre == EXPECTED_CLEAN_TRANSCRIPT
        and source_post == EXPECTED_SOURCE_MAP
        and plan_post == EXPECTED_EDITORIAL_PLAN
        and transcript_post == EXPECTED_CLEAN_TRANSCRIPT
    )
    checks = {
        "runtime": "PASS" if interp.get("match") and interp.get("python_version_match") else "FAIL",
        "sdk": "PASS" if str(runtime.get("openai_sdk_version") or "") == EXPECTED_OPENAI_SDK_VERSION else "FAIL",
        "credentials": "PASS" if credential else "FAIL",
        "provider_initialization": "PASS" if ready_ok else "FAIL",
        "canonical_hashes": "PASS" if hashes_match else "FAIL",
        "historical_contracts": "PASS" if prompt_10_ok and prompt_11_ok and prompt_111_ok and prompt_112_ok else "FAIL",
        "candidate_113": "PASS" if prompt_113_ok else "FAIL",
        "h11_identity": "PASS" if clause.get("start") == EXPECTED_CLAUSE_START else "FAIL",
        "evidence_manifest": "PASS" if evidence_matches_manifest(inventory) else "FAIL",
        "label_leakage": 0 if identified.get("label_leak_pass") else identified.get("label_leakage"),
        "request_sha": "PASS" if identified.get("identity_match") else "FAIL",
        "request_determinism": "PASS" if identified.get("determinism") else "FAIL",
        "sdk_serialization": "PASS" if serialized.get("serialization_pass") else "FAIL",
        "no_retry_enforcement": "PASS" if retry_inspect.get("pass") else "FAIL",
        "context_budget": "PASS" if budget.get("context_safe") else "FAIL",
        "cost_estimate": "RECORDED" if cost.get("short_json") is not None else "FAIL",
        "one_shot_authorization": "AVAILABLE" if lock_available else "CONSUMED",
    }
    return redact_secrets(
        {
            "phase": PHASE,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "blocked_precall": blocked,
            "block_reasons": unique,
            "block_reason": unique[0] if unique else None,
            "status": "BLOCKED_PRECALL" if blocked else "LOCAL_PREFLIGHT_PASS",
            "checks": checks,
            "interpreter": interp,
            "runtime": runtime,
            "provider_readiness": readiness.to_dict(),
            "identities_before": before,
            "identities_after": after,
            "canonical_hashes": {
                "source_map_pre": source_pre,
                "editorial_plan_pre": plan_pre,
                "clean_transcript_pre": transcript_pre,
                "source_map_post": source_post,
                "editorial_plan_post": plan_post,
                "clean_transcript_post": transcript_post,
                "match": hashes_match,
            },
            "contracts": {
                "prompt_1_0": prompt_10_ok,
                "prompt_1_1": prompt_11_ok,
                "prompt_1_1_1": prompt_111_ok,
                "prompt_1_1_2": prompt_112_ok,
                "prompt_1_1_3": prompt_113_ok,
            },
            "benchmark": bench,
            "h11_identity": {
                "handle": SELECTED_CASE_HANDLE,
                "case_id_audit_only": SELECTED_CASE_ID,
                "clause_start": clause.get("start"),
                "clause_end": clause.get("end"),
                "human_label_not_transmitted": True,
            },
            "evidence": {
                "complete": inventory.get("complete"),
                "present_ids": inventory.get("present_ids"),
                "declared_handles": inventory.get("allowed_handles_in_request"),
                "match": evidence_matches_manifest(inventory),
                "h01_handles_injected": inventory.get("h01_handles_injected"),
                "h02_handles_injected": inventory.get("h02_handles_injected"),
                "fabricated_evidence_added": inventory.get("fabricated_evidence_added"),
            },
            "request": {
                "sha256": identified.get("sha256"),
                "sha256_repeat": identified.get("second_sha256"),
                "frozen_artifact_sha256": identified.get("frozen_artifact_sha256"),
                "expected_sha256": EXPECTED_REQUEST_SHA256,
                "identity_match": identified.get("identity_match"),
                "deterministic": identified.get("determinism"),
                "differs_from_h01": identified.get("differs_from_h01"),
                "differs_from_h02": identified.get("differs_from_h02"),
                "model": identified.get("model"),
                "max_completion_tokens": payload.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS),
                "max_tokens_absent": TOKEN_PARAM_MAX_TOKENS not in payload,
                "temperature_present": "temperature" in payload,
                "thinking_present": "thinking" in payload,
                "response_format": payload.get("response_format"),
                "exactly_one_case": identified.get("exactly_one_case"),
                "label_leakage": identified.get("label_leakage"),
                "label_leak_pass": identified.get("label_leak_pass"),
            },
            "payload": payload,
            "ai_request": identified.get("ai_request"),
            "sdk_serialization": serialized,
            "no_retry": retry_inspect,
            "cost_estimate": cost,
            "budget": budget,
            "label_leak": leak,
            "server_only_unknowns": list(SERVER_ONLY_UNKNOWNS),
            "credential_available": credential,
            "production_book_absent": book_absent,
            "lock_available": lock_available,
            "canonical_python": CANONICAL_PYTHON_EXECUTABLE,
            "token_field": TOKEN_FIELD,
            "endpoint": PRODUCTION_ENDPOINT,
            "http_sent": False,
            "remote_invocations": 0,
            "json_object_server_capability": "UNKNOWN",
            "secrets_included": False,
        }
    )


__all__ = ["SERVER_ONLY_UNKNOWNS", "build_precall"]
