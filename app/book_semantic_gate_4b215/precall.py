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
from app.book_semantic_gate_4b215.budget import reserve_budget
from app.book_semantic_gate_4b215.constants import (
    AUTHORIZATION_SCOPE,
    CANONICAL_PYTHON_EXECUTABLE,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_OPENAI_SDK_VERSION,
    EXPECTED_SOURCE_MAP,
    H11_EVIDENCE,
    HISTORICAL_CONSERVATIVE_OUTPUT,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PRODUCTION_ENDPOINT,
    PROJECT_NAME,
    PROVIDER,
    REQUIRED_UNIT_IDS,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
    TARGET_CLAUSE,
    TARGET_UNIT_ID,
    TOKEN_FIELD,
)
from app.book_semantic_gate_4b215.engine import inspect_sdk_retry_policy
from app.book_semantic_gate_4b215.paths import canary_lock_path
from app.book_semantic_gate_4b215.request import (
    freeze_and_identify,
    label_leakage_audit,
    prepare_h11_units,
    serialize_selected_sdk,
)
from app.book_semantic_gate_4b23.identity import snapshot_identities, verify_canonical_inputs
from app.book_semantic_gate_4b24.engine import credential_available
from app.book_semantic_gate_4b26.runtime import interpreter_match, runtime_snapshot


SERVER_ONLY_UNKNOWNS = (
    {
        "field": "json_object_server_capability",
        "status": "UNKNOWN",
        "note": (
            "Local serialization of response_format=json_object is PASS. "
            "Whether gpt-5.6-terra will emit a usable JSON object for this "
            "2.0.2 h11 request remains UNKNOWN_SERVER_SIDE."
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


def _probe_payload(root: Path | None) -> dict[str, Any]:
    identified = freeze_and_identify(
        max_completion_tokens=int(HISTORICAL_CONSERVATIVE_OUTPUT),
        root=root,
    )
    return dict(identified.get("payload") or {})


def build_precall(*, root: Path | None = None) -> dict[str, Any]:
    interp = interpreter_match(root=root)
    runtime = runtime_snapshot(root=root)
    runtime["phase"] = PHASE
    before = verify_canonical_inputs(root=root)
    units = prepare_h11_units(root=root)
    probe = _probe_payload(root)
    budget = reserve_budget(probe)
    chosen_cap = budget.get("max_completion_tokens")
    cap_ok = bool(budget.get("within_budget")) and chosen_cap is not None
    identified = (
        freeze_and_identify(max_completion_tokens=int(chosen_cap), root=root)
        if cap_ok
        else freeze_and_identify(
            max_completion_tokens=int(HISTORICAL_CONSERVATIVE_OUTPUT),
            root=root,
        )
    )
    after = verify_canonical_inputs(root=root)
    leak = label_leakage_audit(
        max_completion_tokens=int(identified.get("max_completion_tokens") or chosen_cap or HISTORICAL_CONSERVATIVE_OUTPUT),
        root=root,
    )
    serialized = serialize_selected_sdk(
        max_completion_tokens=int(identified.get("max_completion_tokens") or chosen_cap or HISTORICAL_CONSERVATIVE_OUTPUT),
        root=root,
    )
    payload = dict(identified.get("payload") or {})
    retry_inspect = inspect_sdk_retry_policy()
    lock_path = canary_lock_path(root=root)
    lock_available = not lock_path.exists()
    credential = credential_available()
    book_absent = production_book_absent(PROJECT_NAME)
    python_exists = Path(CANONICAL_PYTHON_EXECUTABLE).is_file()

    readiness = check_provider_runtime_readiness(
        PROVIDER,
        model=MODEL,
        request=identified.get("ai_request"),
        output_mode=OUTPUT_MODE,
        construct_client=True,
    )
    ready_ok, ready_failures = _readiness_pass(readiness.to_dict())

    blockers: list[str] = []
    if not python_exists:
        blockers.append("canonical_python_missing")
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
    if int(identified.get("label_leakage") or 0) != 0:
        blockers.append("label_leakage")
    if not identified.get("label_leak_pass"):
        blockers.append("label_leakage")
    if not leak.get("pass"):
        blockers.append("label_leakage")
    if leak.get("case_id_in_request"):
        blockers.append("case_id_leak")
    if leak.get("expected_result_in_user"):
        blockers.append("expected_result_leak")
    if not identified.get("determinism"):
        blockers.append("request_determinism")
    if str(identified.get("first_sha256") or "") != str(identified.get("second_sha256") or ""):
        blockers.append("request_determinism")
    if identified.get("matches_frozen_artifact") is False:
        blockers.append("frozen_request_mutated")
    if not serialized.get("serialization_pass"):
        blockers.append("sdk_serialization")
    if int(serialized.get("network_calls") or 0) != 0:
        blockers.append("sdk_serialization_network")
    if not retry_inspect.get("pass"):
        blockers.append("no_retry_enforcement")
    if not budget.get("within_budget"):
        blockers.append(str(budget.get("block_reason") or "budget_cap"))
    if not cap_ok:
        blockers.append("output_cap")
    if not lock_available:
        blockers.append("authorization_already_consumed")
    if not book_absent:
        blockers.append("book_json_present")
    if cap_ok and payload.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS) != chosen_cap:
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
    if tuple(units.get("unit_ids") or ()) != REQUIRED_UNIT_IDS:
        blockers.append("unit_ids")
    if not units.get("clause_in_target_unit"):
        blockers.append("target_clause_unit")
    if not units.get("guarantee_independently_evaluable"):
        blockers.append("guarantee_merged")
    if units.get("merged_with_other_unit"):
        blockers.append("guarantee_merged")
    if not units.get("coverage_ok"):
        blockers.append("unit_coverage_preparation")
    evidence_ids = list(units.get("evidence_handles") or [])
    if evidence_ids != list(H11_EVIDENCE):
        blockers.append("evidence_handles")
    if any(not str(item.get("text") or "").strip() for item in units.get("evidence_records") or []):
        blockers.append("evidence_text_missing")

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
        "canonical_python": "PASS" if python_exists else "FAIL",
        "runtime": "PASS" if interp.get("match") and interp.get("python_version_match") else "FAIL",
        "sdk": (
            "PASS"
            if str(runtime.get("openai_sdk_version") or "") == EXPECTED_OPENAI_SDK_VERSION
            else "FAIL"
        ),
        "credentials": "PASS" if credential else "FAIL",
        "provider_initialization": "PASS" if ready_ok else "FAIL",
        "canonical_hashes": "PASS" if hashes_match else "FAIL",
        "unit_integrity": (
            "PASS"
            if units.get("coverage_ok") and units.get("guarantee_independently_evaluable")
            else "FAIL"
        ),
        "label_leakage": 0 if identified.get("label_leak_pass") else identified.get("label_leakage"),
        "request_determinism": "PASS" if identified.get("determinism") else "FAIL",
        "sdk_serialization": "PASS" if serialized.get("serialization_pass") else "FAIL",
        "no_retry_enforcement": "PASS" if retry_inspect.get("pass") else "FAIL",
        "budget": "PASS" if budget.get("within_budget") else "FAIL",
        "one_shot_authorization": "AVAILABLE" if lock_available else "CONSUMED",
        "retries": 0,
        "fallbacks": 0,
        "second_endpoint": False,
        "sonnet_calls": 0,
        "other_terra_cases": 0,
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
                "expected_source_map": EXPECTED_SOURCE_MAP,
                "expected_editorial_plan": EXPECTED_EDITORIAL_PLAN,
                "expected_clean_transcript": EXPECTED_CLEAN_TRANSCRIPT,
                "match": hashes_match,
            },
            "units": {
                "unit_ids": units.get("unit_ids"),
                "coverage_ok": units.get("coverage_ok"),
                "target_unit_id": TARGET_UNIT_ID,
                "target_clause": TARGET_CLAUSE,
                "clause_in_target_unit": units.get("clause_in_target_unit"),
                "guarantee_independently_evaluable": units.get(
                    "guarantee_independently_evaluable"
                ),
                "merged_with_other_unit": units.get("merged_with_other_unit"),
                "paragraph_unchanged": units.get("paragraph_unchanged"),
            },
            "h11_identity": {
                "handle": SELECTED_CASE_HANDLE,
                "case_id_audit_only": SELECTED_CASE_ID,
                "human_label_not_transmitted": True,
            },
            "evidence": {
                "allowed_handles": evidence_ids,
                "expected_handles": list(H11_EVIDENCE),
                "match": evidence_ids == list(H11_EVIDENCE),
            },
            "request": {
                "sha256": identified.get("sha256"),
                "sha256_repeat": identified.get("second_sha256"),
                "frozen_artifact_sha256": identified.get("frozen_artifact_sha256"),
                "expected_sha256": identified.get("sha256"),
                "identity_match": identified.get("identity_match"),
                "deterministic": identified.get("determinism"),
                "model": identified.get("model") or payload.get("model"),
                "max_completion_tokens": payload.get(TOKEN_PARAM_MAX_COMPLETION_TOKENS),
                "max_tokens_absent": TOKEN_PARAM_MAX_TOKENS not in payload,
                "temperature_present": "temperature" in payload,
                "thinking_present": identified.get("thinking_present"),
                "response_format": payload.get("response_format"),
                "exactly_one_case": identified.get("exactly_one_case"),
                "label_leakage": identified.get("label_leakage"),
                "label_leak_pass": identified.get("label_leak_pass"),
            },
            "payload": payload,
            "ai_request": identified.get("ai_request"),
            "sdk_serialization": serialized,
            "no_retry": retry_inspect,
            "budget_reservation": budget,
            "label_leak": leak,
            "context": units,
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
