"""
Runner Phase 4B.2.15.

Precall, freeze, and budget first. The new remote slot is consumed only at
the actual provider create() boundary. One Terra attempt. No retry.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from app.ai.cost import CostTracker
from app.ai.errors import AIError, AIStructuredOutputError
from app.ai.provider_forensics import (
    current_http_envelope,
    persist_error_forensics,
    persist_interrupt_forensics,
    persist_provider_forensics,
    provider_forensic_scope,
)
from app.ai.provider_preflight import (
    ProviderNotReadyError,
    assert_provider_ready_for_authorization,
    check_provider_runtime_readiness,
    redact_secrets,
)
from app.ai.structured_forensics import persist_structured_output_forensics
from app.ai.thinking import UNKNOWN_TOKEN_COUNT, extract_openai_usage_telemetry
from app.ai.usage_store import record_call
from app.book_semantic_gate_4b215.accounting import CallAccounting, empty_accounting
from app.book_semantic_gate_4b215.budget import tokens_to_usd
from app.book_semantic_gate_4b215.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_REMOTE_TERRA_INVOCATIONS,
    BUDGET_CAP_DISPLAY,
    CANARY_WINDOW_ID,
    CANONICAL_PYTHON_EXECUTABLE,
    GRANULARITY,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    MAX_ENGINE_GENERATE,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PRODUCTION_ENDPOINT,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_ID,
    STAGE_CANARY,
    TOKEN_FIELD,
    TRANSPORT_VERSION,
)
from app.book_semantic_gate_4b215.engine import (
    NoRetryAccountingOpenAIEngine,
    build_real_canary_engine,
    describe_accounting_engine,
)
from app.book_semantic_gate_4b215.guard import (
    BookSemanticGate215Error,
    OneShotCallGuard,
    assert_no_publication,
    consume_remote_lock,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b215.historical import historical_comparison
from app.book_semantic_gate_4b215.paths import (
    canary_lock_path,
    forensic_root,
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_semantic_gate_4b215.precall import build_precall
from app.book_semantic_gate_4b215.replay import replay_saved_response
from app.book_semantic_gate_4b215.report import render_report
from app.book_semantic_gate_4b215.review import review_h11_semantic_response
from app.book_semantic_gate_4b215.safety import provider_safety
from app.book_semantic_gate_4b215.validation import (
    apply_policy,
    evidence_validation,
    extract_target_verdict,
    parse_saved_response,
    unit_coverage_validation,
    validate_contract,
)
from app.book_semantic_gate_4b215.writer import freeze_provider_request
from app.book_semantic_gate_4b23.identity import snapshot_identities
from app.book_semantic_gate_4b24.identity import post_input_hashes
from app.file_utils import content_hash
from app.source_analysis.errors import MaxRealCallsExceededError


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b215.py",
        "app/tests/test_book_semantic_gate_4b212.py",
        "app/tests/test_book_semantic_gate_4b29.py",
        "app/tests/test_ai_providers.py",
    ]
    python = str(venv_python_path(root=root))
    command = [python, "-m", "pytest", "-q", "--tb=no", *tests]
    completed = subprocess.run(
        command,
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = completed.stdout or ""
    failed = completed.returncode != 0
    summary = next(
        (
            line.strip()
            for line in reversed(stdout.splitlines())
            if "passed" in line or "failed" in line
        ),
        stdout.strip().splitlines()[-1] if stdout.strip() else "",
    )
    passed_match = re.search(r"(\d+) passed", summary)
    failed_match = re.search(r"(\d+) failed", summary)
    return {
        "returncode": completed.returncode,
        "summary": summary,
        "passed": int(passed_match.group(1)) if passed_match else 0,
        "failed": int(failed_match.group(1)) if failed_match else 0,
        "stderr_tail": "\n".join((completed.stderr or "").strip().splitlines()[-8:]),
        "new_failures": 0 if not failed else int(failed_match.group(1) if failed_match else 1),
        "network_blocked": True,
        "suites": tests,
        "real_provider_calls": 0,
        "canonical_python": python,
        "phase": PHASE,
    }


def _strip_precall(identity: Mapping[str, Any]) -> dict[str, Any]:
    skip = {"payload", "ai_request", "context"}
    return {key: value for key, value in identity.items() if key not in skip}


def _authorization_manifest(*, consumed: bool, sha256: str | None) -> dict[str, Any]:
    return {
        "phase": PHASE,
        "case_id": SELECTED_CASE_ID,
        "model": MODEL,
        "maximum_remote_calls": 1,
        "maximum_budget": BUDGET_CAP_DISPLAY,
        "contract": PROMPT_VERSION,
        "granularity": "one paragraph",
        "retry": 0,
        "fallback": "forbidden",
        "sonnet": "forbidden",
        "production_writes": "forbidden",
        "reusable": False,
        "consumed": consumed,
        "one_shot": True,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "request_sha256": sha256,
        "secrets_included": False,
    }


def _request_identity(identity: Mapping[str, Any], *, http_sent: bool) -> dict[str, Any]:
    request = dict(identity.get("request") or {})
    payload = dict(identity.get("payload") or {})
    for key in ("x-api-key", "api_key", "authorization", "timeout"):
        payload.pop(key, None)
    return {
        "phase": PHASE,
        "request_sha256": request.get("sha256"),
        "request_sha256_repeat": request.get("sha256_repeat"),
        "determinism": request.get("deterministic"),
        "model": request.get("model"),
        "max_completion_tokens": request.get("max_completion_tokens"),
        "token_field": TOKEN_FIELD,
        "max_tokens_absent": request.get("max_tokens_absent"),
        "temperature_present": request.get("temperature_present"),
        "thinking_present": request.get("thinking_present"),
        "response_format": request.get("response_format"),
        "exactly_one_case": request.get("exactly_one_case"),
        "payload": payload,
        "secrets_included": False,
        "http_sent": http_sent,
        "human_labels_included": False,
    }


def _accounting_from(engine: Any | None, fallback: CallAccounting | None = None) -> CallAccounting:
    if engine is not None and isinstance(getattr(engine, "accounting", None), CallAccounting):
        return engine.accounting
    return fallback or empty_accounting()


def _hashes_display(identity: Mapping[str, Any]) -> dict[str, Any]:
    return dict(identity.get("canonical_hashes") or {})


def _classify(
    *,
    remote: int,
    error_text: str | None,
    http_success: bool | None,
    finish: str | None,
    raw_text: str | None,
    json_parse: str,
    contract_status: str,
    coverage_ok: bool,
    evidence_ok: bool,
    guarantee_unsupported: bool,
    guarantee_accepted: bool,
    other_false_rejections: list[str],
    semantic_status: str,
    python_decision: str | None,
    replay_pass: bool,
    test_failures: int,
    inputs_unchanged: bool,
) -> str:
    if remote == 0:
        return "BLOCKED_PRECALL"
    usable_json = json_parse == "PASS" and bool(raw_text and str(raw_text).strip())
    if error_text and http_success is not True and not usable_json:
        return "FAIL"
    if str(finish or "") in {"length", "max_tokens"} and not usable_json:
        return "FAIL"
    if not usable_json:
        return "FAIL"
    if guarantee_accepted or semantic_status == "FAIL":
        return "FAIL"
    if (
        not guarantee_unsupported
        or contract_status != "PASS"
        or not coverage_ok
        or not evidence_ok
        or semantic_status != "PASS"
        or other_false_rejections
        or python_decision != "BLOCK"
        or str(finish or "") != "stop"
        or not replay_pass
        or test_failures
        or not inputs_unchanged
    ):
        return "PARTIAL"
    return "PASS"


@dataclass
class CanaryRunResult:
    mode: str
    authorization_scope: str = ""
    accepted: bool = False
    error: str | None = None
    execution_attempts: int = 0
    remote_invocations: int = 0
    http_requests: int = 0
    provider_responses: int = 0
    bundle: dict[str, Any] = field(default_factory=dict)


def _offline_bundle(
    identity: Mapping[str, Any],
    *,
    tests: Mapping[str, Any],
    verdict: str,
    notes: str,
    accounting: CallAccounting | None = None,
    authorization_consumed: bool = False,
) -> dict[str, Any]:
    after = post_input_hashes()
    after_snap = snapshot_identities(after)
    before = dict(identity.get("identities_before") or {})
    counts = accounting or empty_accounting()
    request = dict(identity.get("request") or {})
    runtime = dict(identity.get("runtime") or {})
    leak = dict(identity.get("label_leak") or {})
    estimate = dict(identity.get("budget_reservation") or {})
    hashes = _hashes_display(identity)
    sha = request.get("sha256")
    header = {
        "result": verdict,
        "execution_attempts": counts.execution_attempts,
        "remote_invocations": counts.remote_invocations,
        "http_requests": counts.http_requests,
        "provider_responses": counts.provider_responses,
        "canonical_python": CANONICAL_PYTHON_EXECUTABLE,
        "openai_sdk_version": runtime.get("openai_sdk_version"),
        "case_handle": SELECTED_CASE_HANDLE,
        "case_id": SELECTED_CASE_ID,
        "label_leakage": leak.get("label_leakage"),
        "transport": TRANSPORT_VERSION,
        "max_completion_tokens": request.get("max_completion_tokens"),
        "precall_max_cost": estimate.get("theoretical_maximum_usd"),
        "source_hashes": {
            "source_pre": hashes.get("source_map_pre"),
            "plan_pre": hashes.get("editorial_plan_pre"),
            "transcript_pre": hashes.get("clean_transcript_pre"),
            "source_post": hashes.get("source_map_post"),
            "plan_post": hashes.get("editorial_plan_post"),
            "transcript_post": hashes.get("clean_transcript_post"),
        },
        "request_sha256": sha,
        "http_status": None,
        "finish_reason": None,
        "input_tokens": None,
        "completion_tokens": None,
        "reasoning_tokens": UNKNOWN_TOKEN_COUNT,
        "actual_cost": None,
        "json_parse": "n/a",
        "contract_validation": "n/a",
        "unit_coverage": "n/a",
        "evidence_validity": "n/a",
        "universal_guarantee_classification": None,
        "supported_claims_review": "n/a",
        "semantic_human_review": "n/a",
        "acceptance_policy_result": "n/a",
        "deterministic_replay": "n/a",
        "tests_passed_failed": f"{tests.get('passed') or 0} / {tests.get('failed') or 0}",
        "new_regressions": tests.get("new_failures"),
        "ready_for_one_real_chapter_experiment": "NO",
        "notes": notes,
        "historical_h01": HISTORICAL_H01_STATUS,
        "historical_h02": HISTORICAL_H02_STATUS,
        "historical_h11": HISTORICAL_H11_STATUS,
        "historical_4b211": HISTORICAL_4B211_STATUS,
        "inputs_unchanged": _yn(snapshot_identities(before) == after_snap) if before else "n/a",
        "authorized_remote_invocations": AUTHORIZED_REMOTE_TERRA_INVOCATIONS,
        "endpoint": PRODUCTION_ENDPOINT,
    }
    blocked_record = {
        "status": "BLOCKED_PRECALL" if verdict == "BLOCKED_PRECALL" else verdict,
        "remote_invocations": 0,
        "reason": notes,
        "http_sent": False,
    }
    hashes_after = {
        "source_map": after_snap.get("source_map"),
        "editorial_plan": after_snap.get("editorial_plan"),
        "clean_transcript": after_snap.get("clean_transcript"),
        "match": snapshot_identities(before) == after_snap if before else None,
    }
    semantic = {
        **blocked_record,
        "human_verdict_audit_only": "UNSUPPORTED",
        "human_verdict_not_transmitted": True,
    }
    bundle = {
        "header": header,
        "precall": _strip_precall(identity),
        "preflight": _strip_precall(identity),
        "canonical_hashes_before": identity.get("canonical_hashes"),
        "canonical_hashes_pre": identity.get("canonical_hashes"),
        "canonical_hashes_after": hashes_after,
        "canonical_hashes_post": hashes_after,
        "runtime": runtime,
        "request_identity": _request_identity(identity, http_sent=False),
        "provider_request": identity.get("payload"),
        "request_sha256_payload": {
            "phase": PHASE,
            "algorithm": "sha256",
            "request_sha256": sha,
            "secrets_included": False,
        },
        "authorization_manifest": _authorization_manifest(
            consumed=authorization_consumed, sha256=sha
        ),
        "budget_reservation": estimate,
        "label_leakage_check": identity.get("label_leak"),
        "sdk_serialization": identity.get("sdk_serialization"),
        "call_accounting": counts.to_dict(),
        "provider_usage": {
            **blocked_record,
            "input_tokens": UNKNOWN_TOKEN_COUNT,
            "completion_tokens": UNKNOWN_TOKEN_COUNT,
            "reasoning_tokens": UNKNOWN_TOKEN_COUNT,
            "unknown_is_not_zero": True,
        },
        "provider_cost": {
            "phase": PHASE,
            "estimate": estimate,
            "actual": None,
            "blocked_precall": verdict == "BLOCKED_PRECALL",
            "unknown_must_not_be_reported_as_zero": True,
            "not_a_provider_invoice": True,
        },
        "contract_validation": {**blocked_record, "json_parse": "n/a"},
        "unit_coverage": {**blocked_record},
        "evidence_validation": {**blocked_record},
        "semantic_review": semantic,
        "historical_comparison": historical_comparison(current_result=verdict, semantic=semantic),
        "acceptance_policy": {**blocked_record},
        "deterministic_replay": {**blocked_record, "provider_calls": 0},
        "provider_safety": provider_safety(remote_invocations=0),
        "offline_tests": tests,
        "tests": tests,
        "readiness": {
            "READY_FOR_ONE_REAL_CHAPTER_EXPERIMENT": False,
            "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
            "READY_FOR_NEW_REMOTE_TERRA_CALL": False,
            "NEXT_ACTION": "HUMAN REVIEW",
            "book_json": "NOT PUBLISHED",
            "production_cache": "UNCHANGED",
            "production_pipeline": "UNCHANGED",
            "why": notes,
        },
        "execution": {
            "mode": verdict,
            "remote_invocations": 0,
            "sonnet_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
    }
    bundle["report_text"] = render_report(bundle)
    return redact_secrets(bundle)


def run_canary(
    *,
    dry_run: bool = True,
    execute_real: bool = False,
    authorization_scope: str | None = None,
    allow_real_provider: bool = False,
    engine=None,
    root: Path | None = None,
    write_artifacts: bool = True,
    persist_usage: bool = False,
    run_tests: bool = True,
) -> CanaryRunResult:
    result = CanaryRunResult(
        mode="DRY_RUN" if (dry_run or not execute_real) else "EXECUTE",
        authorization_scope=str(authorization_scope or ""),
    )
    try:
        scope = validate_authorization_scope(authorization_scope)
        result.authorization_scope = scope
        assert_no_publication(production_book_path())
    except BookSemanticGate215Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if execute_real and dry_run:
        result.error = "--dry-run and --execute-real are exclusive."
        result.mode = "REJECTED"
        return result

    identity = build_precall(root=root)
    blocked = bool(identity.get("blocked_precall"))
    base = root or repo_root()
    tests = (
        _run_focused_tests(root=base)
        if run_tests and (blocked or not execute_real)
        else {
            "skipped": True,
            "new_failures": 0,
            "network_blocked": True,
            "summary": "deferred",
            "passed": 0,
            "failed": 0,
        }
    )

    if write_artifacts and identity.get("payload") and identity.get("request"):
        freeze_provider_request(
            dict(identity.get("payload") or {}),
            str((identity.get("request") or {}).get("sha256") or ""),
            root=root,
        )

    if blocked or not execute_real:
        verdict = "BLOCKED_PRECALL" if blocked else "DRY_RUN"
        notes = (
            str(identity.get("block_reason") or "pre-call blocker")
            if blocked
            else "offline pre-call only; provider not called"
        )
        bundle = _offline_bundle(identity, tests=tests, verdict=verdict, notes=notes)
        if write_artifacts:
            from app.book_semantic_gate_4b215.writer import write_canary_artifacts

            write_canary_artifacts(bundle, root=root)
        result.bundle = bundle
        result.accepted = not blocked
        if blocked:
            result.error = str(identity.get("block_reason"))
            result.mode = "BLOCKED_PRECALL"
        return result

    if engine is None and not allow_real_provider:
        result.accepted = False
        result.error = "exécution réelle refusée : allow_real_provider=false."
        result.mode = "REJECTED"
        return result

    if engine is None:
        try:
            engine = build_real_canary_engine()
        except BookSemanticGate215Error as exc:
            result.accepted = False
            result.error = str(exc)
            result.mode = "BLOCKED_PRECALL"
            bundle = _offline_bundle(
                identity,
                tests=tests,
                verdict="BLOCKED_PRECALL",
                notes=str(exc),
            )
            if write_artifacts:
                from app.book_semantic_gate_4b215.writer import write_canary_artifacts

                write_canary_artifacts(bundle, root=root)
            result.bundle = bundle
            return result

    request = identity.get("ai_request")
    actual_sha = str((identity.get("request") or {}).get("sha256") or "")
    if request is None:
        result.error = "BLOCKED_PRECALL: missing AIRequest"
        result.mode = "BLOCKED_PRECALL"
        bundle = _offline_bundle(
            identity,
            tests=tests,
            verdict="BLOCKED_PRECALL",
            notes=result.error,
        )
        if write_artifacts:
            from app.book_semantic_gate_4b215.writer import write_canary_artifacts

            write_canary_artifacts(bundle, root=root)
        result.bundle = bundle
        return result

    forensic_dir = forensic_root(root=root)
    forensic_dir.mkdir(parents=True, exist_ok=True)
    guard = OneShotCallGuard(max_calls=MAX_ENGINE_GENERATE)
    readiness = check_provider_runtime_readiness(
        PROVIDER,
        model=MODEL,
        request=request,
        output_mode=OUTPUT_MODE,
        engine=engine,
    )
    try:
        assert_provider_ready_for_authorization(readiness)
    except ProviderNotReadyError as exc:
        result.accepted = False
        result.error = exc.reason
        result.mode = "BLOCKED_PRECALL"
        bundle = _offline_bundle(
            identity,
            tests=tests,
            verdict="BLOCKED_PRECALL",
            notes=exc.reason,
        )
        if write_artifacts:
            from app.book_semantic_gate_4b215.writer import write_canary_artifacts

            write_canary_artifacts(bundle, root=root)
        result.bundle = bundle
        return result

    def _mark_remote_boundary() -> None:
        if isinstance(engine, NoRetryAccountingOpenAIEngine):
            consume_remote_lock(
                path=canary_lock_path(root=root),
                phase=PHASE,
                scope=AUTHORIZATION_SCOPE,
            )
            engine.accounting.lock_consumed = True

    if isinstance(engine, NoRetryAccountingOpenAIEngine):
        engine.set_remote_boundary_hook(_mark_remote_boundary)

    http_meta: dict[str, Any] = {}
    response_meta: dict[str, Any] = {}
    raw_parsed = None
    raw_text = None
    error_text = None
    http_success = None
    forensic_path = None
    tracker = CostTracker()
    cost_record = None
    response = None

    try:
        with provider_forensic_scope(
            windows_root=forensic_dir,
            window_id=CANARY_WINDOW_ID,
            analysis_signature=actual_sha,
            provider=PROVIDER,
            model=MODEL,
        ):
            try:
                response = guard.guarded_generate(engine, request)
            except KeyboardInterrupt:
                persist_interrupt_forensics()
                raise
            except AIStructuredOutputError as exc:
                persist_structured_output_forensics(
                    error=exc,
                    windows_root=forensic_dir,
                    window_id=CANARY_WINDOW_ID,
                    analysis_signature=actual_sha,
                    provider=getattr(getattr(exc, "response", None), "provider", None),
                    model=getattr(getattr(exc, "response", None), "model", None) or MODEL,
                    stage=STAGE_CANARY,
                )
                persist_error_forensics(
                    exc,
                    windows_root=forensic_dir,
                    window_id=CANARY_WINDOW_ID,
                    analysis_signature=actual_sha,
                )
                envelope = getattr(exc, "http_envelope", None) or current_http_envelope()
                if envelope is not None:
                    http_meta = envelope.compact_metadata()
                    forensic_path = str(envelope.forensic_path or "")
                    http_success = envelope.http_success
                attached = getattr(exc, "response", None)
                if attached is not None:
                    response_meta = attached.to_dict()
                    raw_text = attached.text
                    try:
                        cost_record = tracker.record_failure(
                            provider=PROVIDER,
                            model=MODEL,
                            stage=STAGE_CANARY,
                            error=exc,
                            latency_ms=attached.latency_ms,
                            response=attached,
                        )
                    except Exception:
                        cost_record = None
                error_text = str(exc)
                response = None
            except AIError as exc:
                persist_error_forensics(
                    exc,
                    windows_root=forensic_dir,
                    window_id=CANARY_WINDOW_ID,
                    analysis_signature=actual_sha,
                )
                envelope = getattr(exc, "http_envelope", None) or current_http_envelope()
                if envelope is not None:
                    http_meta = envelope.compact_metadata()
                    forensic_path = str(envelope.forensic_path or "")
                    http_success = envelope.http_success
                attached = getattr(exc, "response", None)
                if attached is not None:
                    response_meta = attached.to_dict()
                    raw_text = attached.text
                error_text = str(exc)
                response = None
            except MaxRealCallsExceededError as exc:
                error_text = str(exc)
                response = None
            else:
                envelope = current_http_envelope()
                if envelope is None and isinstance(getattr(response, "metadata", None), dict):
                    http_meta = dict(response.metadata.get("provider_http") or {})
                    http_success = http_meta.get("http_success")
                if envelope is not None:
                    persist_provider_forensics(envelope)
                    http_meta = envelope.compact_metadata()
                    forensic_path = str(envelope.forensic_path or "")
                    http_success = envelope.http_success
                elif response is not None:
                    http_success = True
                response_meta = response.to_dict()
                raw_text = response.text
                raw_parsed = response.parsed if isinstance(response.parsed, dict) else None
                cost_record = tracker.record_response(response, stage=STAGE_CANARY)
    except KeyboardInterrupt:
        counts = _accounting_from(engine)
        result.error = "KeyboardInterrupt"
        result.execution_attempts = counts.execution_attempts
        result.remote_invocations = counts.remote_invocations
        result.http_requests = counts.http_requests
        result.provider_responses = counts.provider_responses
        return result

    counts = _accounting_from(engine)
    if http_meta.get("post_attempted") and counts.http_requests == 0:
        counts.http_requests = 1
    if http_meta.get("response_received") and counts.provider_responses == 0:
        counts.provider_responses = 1
    result.execution_attempts = counts.execution_attempts or guard.generate_attempts
    result.remote_invocations = counts.remote_invocations
    result.http_requests = counts.http_requests
    result.provider_responses = counts.provider_responses

    usage = http_meta.get("usage") if isinstance(http_meta.get("usage"), dict) else {}
    raw_usage = dict(response_meta.get("raw_usage") or {})
    if isinstance(engine, NoRetryAccountingOpenAIEngine) and engine.last_raw_usage:
        raw_usage = dict(engine.last_raw_usage)
    telemetry = extract_openai_usage_telemetry(raw_usage or usage)
    input_tokens = telemetry.get("input_tokens")
    output_tokens = telemetry.get("completion_tokens")
    reasoning_tokens = telemetry.get("reasoning_tokens")
    if input_tokens == UNKNOWN_TOKEN_COUNT:
        input_tokens = response_meta.get("input_tokens")
        if input_tokens is None:
            input_tokens = http_meta.get("input_tokens")
    if output_tokens == UNKNOWN_TOKEN_COUNT:
        output_tokens = response_meta.get("output_tokens")
        if output_tokens is None:
            output_tokens = http_meta.get("output_tokens")
    finish = response_meta.get("finish_reason") or http_meta.get("finish_reason")
    if isinstance(engine, NoRetryAccountingOpenAIEngine) and engine.last_finish_reason:
        finish = engine.last_finish_reason
    refusal = None
    if isinstance(engine, NoRetryAccountingOpenAIEngine):
        refusal = engine.last_refusal
        if engine.last_message_content is not None and raw_text is None:
            raw_text = engine.last_message_content

    numeric_in = input_tokens if isinstance(input_tokens, int) else None
    numeric_out = output_tokens if isinstance(output_tokens, int) else None
    usage_complete = numeric_in is not None and numeric_out is not None
    if usage_complete:
        priced = tokens_to_usd(input_tokens=numeric_in, output_tokens=numeric_out)
        cost = {
            **{key: value for key, value in priced.items() if key != "decimal_total"},
            "status": "calculated_from_configured_rates",
            "display": f"{priced['total_cost_usd']:.6f} USD" if priced["total_cost_usd"] is not None else "UNKNOWN",
            "notes": (
                "Calculated 4B.2.15 Terra h11 cost from configured project rates "
                "dated 2026-09-18. Reasoning tokens are included in completion "
                "tokens when the API reports them that way and are not billed "
                "twice. This is not a provider invoice. Unknown is not reported "
                "as zero."
            ),
            "not_a_provider_invoice": True,
        }
        actual_cost_display = cost.get("display")
    else:
        cost = {
            "status": "unknown",
            "total_cost_usd": None,
            "display": "UNKNOWN",
            "notes": (
                "Provider usage incomplete — ACTUAL COST = UNKNOWN. "
                "Not inferred as zero. Estimate recorded separately."
            ),
            "not_a_provider_invoice": True,
        }
        actual_cost_display = "UNKNOWN"
    if cost_record is not None:
        cost["call_record"] = cost_record.to_dict()
        if persist_usage:
            record_call(PROJECT_NAME, cost_record)

    elapsed = http_meta.get("elapsed_ms") or response_meta.get("latency_ms")
    request_id = http_meta.get("request_id") or response_meta.get("request_id")
    http_status = http_meta.get("http_status")
    raw_response_hash = content_hash(raw_text) if raw_text else None
    parsed_saved = parse_saved_response(raw_text)
    if raw_parsed is None and isinstance(parsed_saved.get("parsed"), dict):
        raw_parsed = parsed_saved.get("parsed")
    raw_response = {
        "parsed": raw_parsed,
        "text": raw_text,
        "sha256": raw_response_hash,
        "repaired": False,
        "truncated": str(finish or "") == "length",
        "manually_edited": False,
        "immutable": True,
        "refusal": refusal,
        "returned_model": response_meta.get("model"),
        "request_id": request_id,
        "finish_reason": finish,
        "http_status": http_status if http_status is not None else "UNKNOWN",
    }
    token_usage = {
        "phase": PHASE,
        "raw_usage": raw_usage or usage,
        "telemetry": telemetry,
        "input_tokens": input_tokens if input_tokens is not None else UNKNOWN_TOKEN_COUNT,
        "completion_tokens": (
            output_tokens if output_tokens is not None else UNKNOWN_TOKEN_COUNT
        ),
        "reasoning_tokens": (
            reasoning_tokens if reasoning_tokens is not None else UNKNOWN_TOKEN_COUNT
        ),
        "reasoning_source": telemetry.get("reasoning_source"),
        "visible_output_tokens": telemetry.get("visible_output_tokens"),
        "did_not_infer_visible_by_subtraction": True,
        "did_not_convert_absent_to_zero": True,
        "unknown_is_not_zero": True,
        "reasoning_included_in_completion_unless_separately_priced": True,
        "secrets_included": False,
    }

    after = post_input_hashes()
    before = dict(identity.get("identities_before") or {})
    inputs_unchanged = snapshot_identities(before) == snapshot_identities(after)
    context = dict(identity.get("context") or {})
    prepared = dict(context.get("prepared") or {})
    allowed = list(context.get("evidence_handles") or [])
    contract = validate_contract(
        raw_parsed if isinstance(raw_parsed, dict) else raw_text,
        prepared,
        allowed_evidence=allowed,
    )
    json_parse = parsed_saved.get("json_parse") or contract.get("json_parse") or "FAIL"
    coverage = unit_coverage_validation(contract, required_ids=list(context.get("unit_ids") or []))
    evidence = evidence_validation(contract, allowed_handles=allowed)
    policy = apply_policy(prepared, contract)
    replay = replay_saved_response(
        raw_text,
        prepared=prepared,
        allowed_handles=allowed,
    )
    semantic = review_h11_semantic_response(
        raw_parsed if isinstance(raw_parsed, dict) else None,
        prepared_units=list(context.get("units") or []),
        allowed_handles=allowed,
        contract_status=str(contract.get("status") or "FAIL"),
        coverage_ok=bool(coverage.get("ok")),
        evidence_ok=bool(evidence.get("ok")),
        python_decision=str(policy.get("decision") or ""),
    )
    tests = _run_focused_tests(root=base) if run_tests else {
        "skipped": True,
        "new_failures": 0,
        "network_blocked": True,
        "summary": "not-run",
        "passed": 0,
        "failed": 0,
    }
    leak = dict(identity.get("label_leak") or {})
    remote = counts.remote_invocations
    target = extract_target_verdict(contract)
    verdict = _classify(
        remote=remote,
        error_text=error_text,
        http_success=http_success,
        finish=finish,
        raw_text=raw_text,
        json_parse=str(json_parse),
        contract_status=str(contract.get("status") or "FAIL"),
        coverage_ok=bool(coverage.get("ok")),
        evidence_ok=bool(evidence.get("ok")),
        guarantee_unsupported=bool(semantic.get("universal_guarantee_unsupported")),
        guarantee_accepted=bool(semantic.get("universal_guarantee_accepted")),
        other_false_rejections=list(semantic.get("other_supported_false_rejections") or []),
        semantic_status=str(semantic.get("semantic_status") or "FAIL"),
        python_decision=str(policy.get("decision") or ""),
        replay_pass=bool(replay.get("pass")),
        test_failures=int(tests.get("new_failures") or 0),
        inputs_unchanged=inputs_unchanged,
    )
    estimate = dict(identity.get("budget_reservation") or {})
    runtime = dict(identity.get("runtime") or {})
    hashes = _hashes_display(identity)
    hashes_after_snap = snapshot_identities(after)
    if isinstance(hashes_after_snap.get("source_map"), str):
        hashes["source_map_post"] = hashes_after_snap.get("source_map")
        hashes["editorial_plan_post"] = hashes_after_snap.get("editorial_plan")
        hashes["clean_transcript_post"] = hashes_after_snap.get("clean_transcript")
    if not inputs_unchanged:
        notes = "CRITICAL ANOMALY: canonical hashes changed after the provider call."
    else:
        notes = error_text or semantic.get("finding") or "Terra h11 Semantic Gate 2.0.2 canary complete."
    header = {
        "result": verdict,
        "execution_attempts": counts.execution_attempts or guard.generate_attempts,
        "remote_invocations": remote,
        "http_requests": counts.http_requests,
        "provider_responses": counts.provider_responses,
        "canonical_python": CANONICAL_PYTHON_EXECUTABLE,
        "openai_sdk_version": runtime.get("openai_sdk_version") or readiness.sdk_version,
        "case_handle": SELECTED_CASE_HANDLE,
        "case_id": SELECTED_CASE_ID,
        "label_leakage": leak.get("label_leakage"),
        "transport": TRANSPORT_VERSION,
        "max_completion_tokens": (identity.get("request") or {}).get("max_completion_tokens"),
        "precall_max_cost": estimate.get("theoretical_maximum_usd"),
        "source_hashes": {
            "source_pre": hashes.get("source_map_pre"),
            "plan_pre": hashes.get("editorial_plan_pre"),
            "transcript_pre": hashes.get("clean_transcript_pre"),
            "source_post": hashes.get("source_map_post"),
            "plan_post": hashes.get("editorial_plan_post"),
            "transcript_post": hashes.get("clean_transcript_post"),
        },
        "request_sha256": (identity.get("request") or {}).get("sha256"),
        "http_status": http_status if http_status is not None else "UNKNOWN",
        "finish_reason": finish,
        "input_tokens": input_tokens if input_tokens is not None else UNKNOWN_TOKEN_COUNT,
        "completion_tokens": output_tokens if output_tokens is not None else UNKNOWN_TOKEN_COUNT,
        "reasoning_tokens": (
            reasoning_tokens if reasoning_tokens is not None else UNKNOWN_TOKEN_COUNT
        ),
        "actual_cost": actual_cost_display,
        "json_parse": json_parse,
        "contract_validation": contract.get("status"),
        "unit_coverage": coverage.get("status"),
        "evidence_validity": evidence.get("status"),
        "universal_guarantee_classification": semantic.get("universal_guarantee_classification")
        or target.get("k"),
        "supported_claims_review": semantic.get("supported_claims_review"),
        "semantic_human_review": semantic.get("semantic_status"),
        "acceptance_policy_result": policy.get("decision"),
        "deterministic_replay": "PASS" if replay.get("pass") else "FAIL",
        "tests_passed_failed": f"{tests.get('passed') or 0} / {tests.get('failed') or 0}",
        "new_regressions": tests.get("new_failures"),
        "ready_for_one_real_chapter_experiment": "NO",
        "notes": notes,
        "historical_h01": HISTORICAL_H01_STATUS,
        "historical_h02": HISTORICAL_H02_STATUS,
        "historical_h11": HISTORICAL_H11_STATUS,
        "historical_4b211": HISTORICAL_4B211_STATUS,
        "inputs_unchanged": _yn(inputs_unchanged),
        "authorized_remote_invocations": AUTHORIZED_REMOTE_TERRA_INVOCATIONS,
        "endpoint": PRODUCTION_ENDPOINT,
        "granularity": GRANULARITY,
        "elapsed_ms": elapsed,
        "request_id": request_id,
    }
    post = {
        "READY_FOR_ONE_REAL_CHAPTER_EXPERIMENT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "READY_FOR_NEW_REMOTE_TERRA_CALL": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "production_pipeline": "UNCHANGED",
        "candidate_promoted": False,
        "why": (
            "Analyze saved evidence. No retry. No new Terra call is authorized."
        ),
    }
    hashes_after = {
        "source_map": hashes_after_snap.get("source_map"),
        "editorial_plan": hashes_after_snap.get("editorial_plan"),
        "clean_transcript": hashes_after_snap.get("clean_transcript"),
        "match": inputs_unchanged,
        "critical_anomaly": not inputs_unchanged,
    }
    if write_artifacts:
        from app.book_semantic_gate_4b215.writer import persist_raw_evidence

        persist_raw_evidence(
            {
                "raw_response": raw_response,
                "provider_usage": token_usage,
                "provider_cost": {
                    "phase": PHASE,
                    "estimate": estimate,
                    "actual": cost,
                    "unknown_must_not_be_reported_as_zero": True,
                    "not_a_provider_invoice": True,
                },
            },
            root=root,
        )
    bundle = {
        "header": header,
        "precall": _strip_precall(identity),
        "preflight": _strip_precall(identity),
        "canonical_hashes_before": identity.get("canonical_hashes"),
        "canonical_hashes_pre": identity.get("canonical_hashes"),
        "canonical_hashes_after": hashes_after,
        "canonical_hashes_post": hashes_after,
        "runtime": {**runtime, "live_readiness": readiness.to_dict()},
        "request_identity": _request_identity(identity, http_sent=True),
        "provider_request": identity.get("payload"),
        "request_sha256_payload": {
            "phase": PHASE,
            "algorithm": "sha256",
            "request_sha256": actual_sha,
            "secrets_included": False,
        },
        "authorization_manifest": _authorization_manifest(consumed=True, sha256=actual_sha),
        "budget_reservation": estimate,
        "label_leakage_check": identity.get("label_leak"),
        "sdk_serialization": identity.get("sdk_serialization"),
        "call_accounting": counts.to_dict(),
        "raw_response": raw_response,
        "provider_response_raw": raw_response,
        "token_usage": token_usage,
        "provider_usage": token_usage,
        "provider_cost": {
            "phase": PHASE,
            "estimate": estimate,
            "actual": cost,
            "unknown_must_not_be_reported_as_zero": True,
            "not_a_provider_invoice": True,
        },
        "contract_validation": contract,
        "unit_coverage": coverage,
        "evidence_validation": evidence,
        "semantic_review": semantic,
        "historical_comparison": historical_comparison(current_result=verdict, semantic=semantic),
        "acceptance_policy": policy,
        "deterministic_replay": replay,
        "provider_safety": provider_safety(remote_invocations=remote),
        "offline_tests": tests,
        "tests": tests,
        "readiness": post,
        "execution": {
            "result": verdict,
            "engine": describe_accounting_engine(engine),
            "execution_attempts": counts.execution_attempts,
            "remote_invocations": remote,
            "http_requests": counts.http_requests,
            "provider_responses": counts.provider_responses,
            "successful_payloads": counts.successful_payloads,
            "retries": 0,
            "fallbacks": 0,
            "sonnet_calls": 0,
            "error": error_text,
            "forensic_path": forensic_path,
            "book_json": "NOT PUBLISHED",
            "production_cache": "UNCHANGED",
            "inputs_unchanged": inputs_unchanged,
            "stage": STAGE_CANARY,
            "authorization_consumed": True,
        },
    }
    bundle["report_text"] = render_report(bundle)
    bundle = redact_secrets(bundle)
    if write_artifacts:
        from app.book_semantic_gate_4b215.writer import write_canary_artifacts

        write_canary_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.error = error_text
    result.mode = "EXECUTE"
    return result


__all__ = ["CanaryRunResult", "run_canary", "_classify"]
