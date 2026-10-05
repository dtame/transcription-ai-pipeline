"""
Runner Phase 4B.2.6.

Precall and corrected-contract identity first. The new remote slot is
consumed only at the actual provider create() boundary. One Terra attempt.
No retry. No request adaptation after HTTP 400.
"""

from __future__ import annotations

import re
import subprocess
import sys
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
from app.ai.thinking import extract_thinking_tokens_from_usage
from app.ai.usage_store import record_call
from app.book_semantic_gate_4b23.sufficiency import sufficiency_assessment
from app.book_semantic_gate_4b24.costing import actual_cost, cost_calibration
from app.book_semantic_gate_4b24.identity import post_input_hashes, snapshot_identities
from app.book_semantic_gate_4b24.score import classify_canary, score_benchmark
from app.book_semantic_gate_4b24.validate import (
    deterministic_replay,
    map_handle_results,
    validate_semantic_response,
)
from app.book_semantic_gate_4b26.accounting import CallAccounting, empty_accounting
from app.book_semantic_gate_4b26.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_REMOTE_TERRA_INVOCATIONS,
    CANARY_WINDOW_ID,
    CONSERVATIVE_MAX_OUTPUT_TOKENS,
    EXPECTED_REQUEST_SHA256,
    HISTORICAL_4B21_STATUS,
    HISTORICAL_4B22_STATUS,
    HISTORICAL_4B23_STATUS,
    HISTORICAL_4B241_STATUS,
    HISTORICAL_4B24_STATUS,
    HISTORICAL_4B251_STATUS,
    HISTORICAL_4B25_STATUS,
    HISTORICAL_4B2_STATUS,
    MAX_ENGINE_GENERATE,
    MODEL,
    OUTPUT_MODE,
    PHASE,
    PRODUCTION_ENDPOINT,
    PROJECT_NAME,
    PROVIDER,
    SCORED_CASE_ORDER,
    SEMANTIC_TOKEN_BUDGET,
    STAGE_CANARY,
    TOKEN_FIELD,
)
from app.book_semantic_gate_4b26.engine import (
    AccountingOpenAIEngine,
    build_real_canary_engine,
    describe_accounting_engine,
)
from app.book_semantic_gate_4b26.guard import (
    BookSemanticGate26Error,
    OneShotCallGuard,
    assert_no_publication,
    consume_remote_lock,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b26.paths import (
    canary_lock_path,
    forensic_root,
    production_book_path,
    repo_root,
)
from app.book_semantic_gate_4b26.precall import build_precall
from app.book_semantic_gate_4b26.report import render_report
from app.book_semantic_gate_4b26.review import review_all_cases
from app.file_utils import content_hash
from app.source_analysis.errors import MaxRealCallsExceededError


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b26.py",
        "app/tests/test_book_semantic_gate_4b251.py",
        "app/tests/test_book_semantic_gate_4b241.py",
        "app/tests/test_book_semantic_gate_4b23.py",
        "app/tests/test_book_semantic_gate_4b24.py",
        "app/tests/test_book_semantic_gate_4b25.py",
        "app/tests/test_ai_providers.py",
        "app/tests/test_ai_production_models.py",
    ]
    command = [sys.executable, "-m", "pytest", "-q", "--tb=no", *tests]
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
    }


def _strip_precall(identity: Mapping[str, Any]) -> dict[str, Any]:
    skip = {"payload", "ai_request", "gate_input", "scored_cases", "paragraph_texts"}
    return {key: value for key, value in identity.items() if key not in skip}


def _request_identity(identity: Mapping[str, Any], *, http_sent: bool) -> dict[str, Any]:
    request = dict(identity.get("request") or {})
    payload = dict(identity.get("payload") or {})
    for key in ("x-api-key", "api_key", "authorization", "timeout"):
        payload.pop(key, None)
    return {
        "phase": PHASE,
        "request_sha256": request.get("sha256"),
        "request_sha256_repeat": request.get("sha256_repeat"),
        "expected_sha256": EXPECTED_REQUEST_SHA256,
        "chars": request.get("chars"),
        "bytes": request.get("bytes"),
        "determinism": request.get("deterministic"),
        "identity_match": request.get("sha256") == EXPECTED_REQUEST_SHA256,
        "model": request.get("model"),
        "max_tokens": request.get("max_tokens"),
        "max_completion_tokens": request.get("max_completion_tokens"),
        "token_field": TOKEN_FIELD,
        "token_budget": SEMANTIC_TOKEN_BUDGET,
        "max_tokens_absent": "max_tokens" not in payload,
        "temperature_present": request.get("temperature_present"),
        "thinking_present": request.get("thinking_present"),
        "response_format": request.get("response_format"),
        "gate_input_sha256": request.get("gate_input_sha256"),
        "payload": payload,
        "secrets_included": False,
        "http_sent": http_sent,
        "production_request_builder": True,
        "human_labels_included": False,
    }


def _case_summary(row: Mapping[str, Any] | None) -> str:
    if not row:
        return "MISSING"
    classification = str(row.get("terra_class") or row.get("terra_verdict") or "MISSING")
    blocked = "BLOCKED" if row.get("blocked") else classification
    reasons = "/".join(row.get("terra_reasons") or row.get("reason_codes") or []) or "none"
    return f"{blocked} ({reasons})"


def _accounting_from(engine: Any | None, fallback: CallAccounting | None = None) -> CallAccounting:
    if engine is not None and isinstance(getattr(engine, "accounting", None), CallAccounting):
        return engine.accounting
    return fallback or empty_accounting()


def _unknowns_display(identity: Mapping[str, Any]) -> str:
    items = list(identity.get("server_only_unknowns") or [])
    if not items:
        return "UNKNOWN"
    return "; ".join(
        f"{item.get('field')}={item.get('status')}" for item in items
    )


def _hashes_display(identity: Mapping[str, Any]) -> str:
    hashes = dict(identity.get("canonical_hashes") or {})
    return (
        f"pre source={hashes.get('source_map_pre')} "
        f"plan={hashes.get('editorial_plan_pre')} "
        f"transcript={hashes.get('clean_transcript_pre')}; "
        f"post source={hashes.get('source_map_post')} "
        f"plan={hashes.get('editorial_plan_post')} "
        f"transcript={hashes.get('clean_transcript_post')}"
    )


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
) -> dict[str, Any]:
    after = post_input_hashes()
    after_snap = snapshot_identities(after)
    before = dict(identity.get("identities_before") or {})
    before_snap = snapshot_identities(before) if before else {}
    estimate = dict(identity.get("cost_estimate") or {})
    leak = dict(identity.get("label_leak") or {})
    request = dict(identity.get("request") or {})
    benchmark = dict(identity.get("benchmark") or {})
    runtime = dict(identity.get("runtime") or {})
    readiness = dict(identity.get("provider_readiness") or {})
    counts = accounting or empty_accounting()
    compat = dict(identity.get("api_compatibility") or {})
    header = {
        "result": verdict,
        "execution_attempts": counts.execution_attempts,
        "remote_invocations": counts.remote_invocations,
        "http_requests": counts.http_requests,
        "provider_responses": counts.provider_responses,
        "python_executable": runtime.get("actual_interpreter"),
        "openai_sdk_version": runtime.get("openai_sdk_version") or readiness.get("sdk_version"),
        "model_endpoint": f"{MODEL} / {PRODUCTION_ENDPOINT}",
        "provider_readiness": "PASS" if readiness.get("ready") else "FAIL",
        "canonical_hashes": _hashes_display(identity),
        "source_map_sha": (before.get("source_map") or {}).get("sha256"),
        "editorial_plan_sha": (before.get("editorial_plan") or {}).get("sha256"),
        "clean_transcript_sha": (before.get("clean_transcript") or {}).get("sha256"),
        "benchmark_identity": "MATCH" if benchmark.get("identity_match") else "MISMATCH",
        "label_leakage": leak.get("label_leakage"),
        "request_sha256": request.get("sha256"),
        "request_determinism": "PASS" if request.get("deterministic") else "FAIL",
        "json_object": (
            "local PASS / server UNKNOWN"
            if (compat.get("local_checks") or {}).get("json_object_local")
            else "FAIL"
        ),
        "server_only_unknowns": _unknowns_display(identity),
        "server_only_unknowns_detail": identity.get("server_only_unknowns"),
        "context_safety": identity.get("context_safety"),
        "long_context": estimate.get("long_context_regime"),
        "estimated_cost": estimate.get("total_cost_display"),
        "http_finish": None,
        "request_id": None,
        "input_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "actual_cost": None,
        "json_parse": "n/a",
        "transport_decode": "n/a",
        "case_coverage": "n/a",
        "span_claim_coverage": "n/a",
        "positive_accepted": "n/a",
        "positive_false_rejections": "n/a",
        "negative_blocked": "n/a",
        "negative_false_negatives": "n/a",
        "funeral_case": "n/a",
        "connective_case": "n/a",
        "p3_case": "n/a",
        "p8_case": "n/a",
        "external_knowledge_resistance": "n/a",
        "reason_code_compatible": "n/a",
        "deterministic_replay": "n/a",
        "ready_for_book_generator_production_preflight": "NO",
        "notes": notes,
        "tests": tests.get("summary"),
        "historical_4b2": HISTORICAL_4B2_STATUS,
        "historical_4b21": HISTORICAL_4B21_STATUS,
        "historical_4b22": HISTORICAL_4B22_STATUS,
        "historical_4b23": HISTORICAL_4B23_STATUS,
        "historical_4b24": HISTORICAL_4B24_STATUS,
        "historical_4b241": HISTORICAL_4B241_STATUS,
        "historical_4b25": HISTORICAL_4B25_STATUS,
        "historical_4b251": HISTORICAL_4B251_STATUS,
        "inputs_unchanged": _yn(before_snap == after_snap) if before_snap else "n/a",
    }
    blocked_record = {
        "status": "BLOCKED_PRECALL",
        "remote_invocations": 0,
        "reason": notes,
        "http_sent": False,
    }
    post = {
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "book_generator_101": "SUFFICIENT_WITH_SEMANTIC_GATE",
        "why": notes,
    }
    bundle = {
        "header": header,
        "precall": _strip_precall(identity),
        "runtime": runtime,
        "request_identity": _request_identity(identity, http_sent=False),
        "api_compatibility": compat,
        "call_accounting": counts.to_dict(),
        "provider_evidence": {
            **blocked_record,
            "provider": "openai",
            "model": "gpt-5.6-terra",
            "secrets_included": False,
            "retries": 0,
            "fallbacks": 0,
            "sonnet_calls": 0,
            "stage": STAGE_CANARY,
        },
        "response_validation": {
            **blocked_record,
            "json_parse": "n/a",
            "transport_decode": "n/a",
            "structural_pass": False,
        },
        "case_results": {
            **blocked_record,
            "rows": [],
            "mapping": [
                {"opaque_handle": handle, "case_id": case_id}
                for handle, case_id in SCORED_CASE_ORDER
            ],
        },
        "benchmark_score": {
            **blocked_record,
            "cases": 10,
            "positive_cases": 6,
            "negative_cases": 4,
            "small_sample_warning": (
                "10 cases are an engineering canary, not a statistical "
                "model-quality benchmark."
            ),
        },
        "human_review": {
            **blocked_record,
            "human_labels_remain_ground_truth": True,
            "terra_did_not_redefine_labels": True,
            "cases": [],
        },
        "readiness": post,
        "cost": {
            "phase": PHASE,
            "stage": STAGE_CANARY,
            "production_chapter_validation": False,
            "estimate": estimate,
            "estimate_status": "ESTIMATED",
            "actual": None,
            "blocked_precall": True,
            "unknown_must_not_be_reported_as_zero": True,
        },
        "tests": tests,
        "execution": {
            "mode": "BLOCKED_PRECALL" if verdict == "BLOCKED_PRECALL" else "OFFLINE",
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
    except BookSemanticGate26Error as exc:
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
        }
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
            from app.book_semantic_gate_4b26.writer import write_canary_artifacts

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
        except BookSemanticGate26Error as exc:
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
                from app.book_semantic_gate_4b26.writer import write_canary_artifacts

                write_canary_artifacts(bundle, root=root)
            result.bundle = bundle
            return result

    request = identity.get("ai_request")
    actual_sha = str((identity.get("request") or {}).get("sha256") or "")
    if request is None or actual_sha != EXPECTED_REQUEST_SHA256:
        result.error = (
            "BLOCKED_PRECALL: missing AIRequest"
            if request is None
            else "BLOCKED_PRECALL: rebuilt request SHA-256 mismatch"
        )
        result.mode = "BLOCKED_PRECALL"
        bundle = _offline_bundle(
            identity,
            tests=tests,
            verdict="BLOCKED_PRECALL",
            notes=result.error,
        )
        if write_artifacts:
            from app.book_semantic_gate_4b26.writer import write_canary_artifacts

            write_canary_artifacts(bundle, root=root)
        result.bundle = bundle
        return result

    forensic_dir = forensic_root(root=root)
    forensic_dir.mkdir(parents=True, exist_ok=True)
    guard = OneShotCallGuard(max_calls=MAX_ENGINE_GENERATE)
    identity_hash = str((identity.get("request") or {}).get("sha256") or PHASE)
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
            from app.book_semantic_gate_4b26.writer import write_canary_artifacts

            write_canary_artifacts(bundle, root=root)
        result.bundle = bundle
        return result

    def _mark_remote_boundary() -> None:
        if isinstance(engine, AccountingOpenAIEngine):
            consume_remote_lock(
                path=canary_lock_path(root=root),
                phase=PHASE,
                scope=AUTHORIZATION_SCOPE,
            )
            engine.accounting.lock_consumed = True

    if isinstance(engine, AccountingOpenAIEngine):
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
            analysis_signature=str(identity_hash),
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
                    analysis_signature=str(identity_hash),
                    provider=getattr(getattr(exc, "response", None), "provider", None),
                    model=getattr(getattr(exc, "response", None), "model", None) or MODEL,
                    stage=STAGE_CANARY,
                )
                persist_error_forensics(
                    exc,
                    windows_root=forensic_dir,
                    window_id=CANARY_WINDOW_ID,
                    analysis_signature=str(identity_hash),
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
                    analysis_signature=str(identity_hash),
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
    thinking_tokens = response_meta.get("thinking_tokens")
    if thinking_tokens is None:
        thinking_tokens = extract_thinking_tokens_from_usage(usage)
    if thinking_tokens is None:
        thinking_tokens = extract_thinking_tokens_from_usage(
            response_meta.get("raw_usage") or {}
        )
    input_tokens = response_meta.get("input_tokens")
    output_tokens = response_meta.get("output_tokens")
    if input_tokens is None:
        input_tokens = http_meta.get("input_tokens")
    if output_tokens is None:
        output_tokens = http_meta.get("output_tokens")
    finish = response_meta.get("finish_reason") or http_meta.get("finish_reason")
    cost = actual_cost(input_tokens=input_tokens, output_tokens=output_tokens)
    cost["notes"] = (
        "Actual 4B.2.6 Terra semantic-validation canary cost. "
        "Unknown actual cost is not reported as zero. "
        "Not a completed production chapter validation."
    )
    if cost_record is not None:
        cost["call_record"] = cost_record.to_dict()
        if persist_usage:
            record_call(PROJECT_NAME, cost_record)

    elapsed = http_meta.get("elapsed_ms") or response_meta.get("latency_ms")
    request_id = http_meta.get("request_id") or response_meta.get("request_id")
    http_status = http_meta.get("http_status")
    raw_response_hash = content_hash(raw_text) if raw_text else None
    raw_response = {
        "parsed": raw_parsed,
        "text": raw_text,
        "sha256": raw_response_hash,
        "repaired": False,
        "truncated": str(finish or "") == "length",
        "manually_edited": False,
        "immutable": True,
    }
    provider_evidence = {
        "phase": PHASE,
        "request_sha256": actual_sha,
        "request_id": request_id,
        "http_status": http_status,
        "http_success": http_success,
        "finish_reason": finish,
        "elapsed_ms": elapsed,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "cost": cost,
        "raw_response": raw_text,
        "raw_response_sha256": raw_response_hash,
        "provider_metadata": http_meta,
        "secrets_included": False,
        "forensic_path": forensic_path,
        "error": error_text,
        "retries": 0,
        "fallbacks": 0,
        "sonnet_calls": 0,
        "stage": STAGE_CANARY,
    }
    raw_bundle = {
        "raw_response": raw_response,
        "provider_evidence": provider_evidence,
    }
    if write_artifacts:
        from app.book_semantic_gate_4b26.writer import persist_raw_evidence

        persist_raw_evidence(raw_bundle, root=root)

    after = post_input_hashes()
    before = dict(identity.get("identities_before") or {})
    inputs_unchanged = snapshot_identities(before) == snapshot_identities(after)
    required = list(identity.get("candidate_handles") or [])
    texts = dict(identity.get("paragraph_texts") or {})
    allowed = list(identity.get("allowed_handles") or [])
    structural = validate_semantic_response(
        raw_parsed,
        required_handles=required,
        paragraph_texts=texts,
        allowed_handles=allowed,
    )
    mapped = map_handle_results(structural.get("paragraph_results") or [])
    score = score_benchmark(
        cases=list(identity.get("scored_cases") or []),
        paragraph_results=list(mapped.values()),
    )
    replay = deterministic_replay(
        raw_parsed,
        required_handles=required,
        paragraph_texts=texts,
        allowed_handles=allowed,
    )
    human = review_all_cases(score, structural=structural)
    tests = _run_focused_tests(root=base) if run_tests else {
        "skipped": True,
        "new_failures": 0,
        "network_blocked": True,
        "summary": "not-run",
    }
    leak = dict(identity.get("label_leak") or {})
    remote = counts.remote_invocations
    verdict = classify_canary(
        terra_calls=remote,
        sonnet_calls=0,
        retries=0,
        fallbacks=0,
        structural_pass=bool(structural.get("structural_pass")),
        label_leakage=int(leak.get("label_leakage") or 0),
        score=score,
        replay_pass=bool(replay.get("pass")),
        inputs_unchanged=inputs_unchanged,
        test_failures=int(tests.get("new_failures") or 0),
        http_success=http_success,
        called_despite_leak=False,
    )
    if remote == 0:
        verdict = "BLOCKED_PRECALL"
    if error_text and http_success is not True and remote:
        verdict = "FAIL"
    if str(finish or "") in {"length", "max_tokens"}:
        verdict = "FAIL"
    ready_preflight = verdict == "PASS"
    sufficiency = sufficiency_assessment()
    estimate = dict(identity.get("cost_estimate") or {})
    calibration = cost_calibration(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
        actual=cost,
        estimate=estimate,
        max_output=int(
            (identity.get("request") or {}).get("max_completion_tokens")
            or CONSERVATIVE_MAX_OUTPUT_TOKENS
        ),
    )
    calibration["phase"] = PHASE
    calibration["unknown_must_not_be_reported_as_zero"] = True
    runtime = dict(identity.get("runtime") or {})
    readiness_meta = dict(identity.get("provider_readiness") or {})
    compat = dict(identity.get("api_compatibility") or {})
    header = {
        "result": verdict,
        "execution_attempts": counts.execution_attempts or guard.generate_attempts,
        "remote_invocations": remote,
        "http_requests": counts.http_requests,
        "provider_responses": counts.provider_responses,
        "python_executable": runtime.get("actual_interpreter"),
        "openai_sdk_version": runtime.get("openai_sdk_version") or readiness.sdk_version,
        "model_endpoint": f"{MODEL} / {PRODUCTION_ENDPOINT}",
        "provider_readiness": "PASS" if readiness.ready else "FAIL",
        "canonical_hashes": _hashes_display(identity),
        "source_map_sha": (before.get("source_map") or {}).get("sha256"),
        "editorial_plan_sha": (before.get("editorial_plan") or {}).get("sha256"),
        "clean_transcript_sha": (before.get("clean_transcript") or {}).get("sha256"),
        "benchmark_identity": (
            "MATCH" if (identity.get("benchmark") or {}).get("identity_match") else "MISMATCH"
        ),
        "label_leakage": leak.get("label_leakage"),
        "request_sha256": (identity.get("request") or {}).get("sha256"),
        "request_determinism": (
            "PASS" if (identity.get("request") or {}).get("deterministic") else "FAIL"
        ),
        "json_object": (
            "local PASS / server UNKNOWN"
            if (compat.get("local_checks") or {}).get("json_object_local")
            else str(structural.get("json_parse") or "UNKNOWN")
        ),
        "server_only_unknowns": _unknowns_display(identity),
        "server_only_unknowns_detail": identity.get("server_only_unknowns"),
        "context_safety": identity.get("context_safety"),
        "long_context": estimate.get("long_context_regime"),
        "estimated_cost": estimate.get("total_cost_display"),
        "http_finish": f"{http_status} / {finish}",
        "request_id": request_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": thinking_tokens if thinking_tokens is not None else "unknown",
        "actual_cost": cost.get("display"),
        "json_parse": structural.get("json_parse"),
        "transport_decode": structural.get("transport_decode"),
        "case_coverage": structural.get("case_coverage"),
        "span_claim_coverage": structural.get("span_validation"),
        "positive_accepted": f"{score.get('positive_accepted')} / 6",
        "positive_false_rejections": score.get("positive_false_rejections"),
        "negative_blocked": f"{score.get('negative_blocked')} / 4",
        "negative_false_negatives": score.get("negative_false_negatives"),
        "funeral_case": _case_summary(score.get("funeral")),
        "connective_case": _case_summary(score.get("connective")),
        "p3_case": _case_summary(score.get("p3")),
        "p8_case": _case_summary(score.get("p8")),
        "external_knowledge_resistance": (
            "PASS"
            if (score.get("p8") or {}).get("blocked")
            and not (human.get("p8_case") or {}).get("external_knowledge_rescue")
            else "FAIL"
        ),
        "reason_code_compatible": f"{score.get('reason_code_compatible')} / 4",
        "deterministic_replay": "PASS" if replay.get("pass") else "FAIL",
        "ready_for_book_generator_production_preflight": _yn(ready_preflight),
        "notes": error_text
        or score.get("small_sample_warning")
        or "Terra benchmark canary complete.",
        "tests": tests.get("summary"),
        "inputs_unchanged": _yn(inputs_unchanged),
        "historical_4b2": HISTORICAL_4B2_STATUS,
        "historical_4b21": HISTORICAL_4B21_STATUS,
        "historical_4b22": HISTORICAL_4B22_STATUS,
        "historical_4b23": HISTORICAL_4B23_STATUS,
        "historical_4b24": HISTORICAL_4B24_STATUS,
        "historical_4b241": HISTORICAL_4B241_STATUS,
        "historical_4b25": HISTORICAL_4B25_STATUS,
        "historical_4b251": HISTORICAL_4B251_STATUS,
        "book_generator_101": sufficiency.get("classification"),
        "authorized_remote_invocations": AUTHORIZED_REMOTE_TERRA_INVOCATIONS,
    }
    post = {
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": ready_preflight,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "production_cache": "UNCHANGED",
        "book_generator_101": sufficiency.get("classification"),
        "why": (
            "Clean Terra benchmark PASS. Next phase is OFFLINE production "
            "rollout preflight (Phase 4B.3), only after human review. "
            "Do not start 19-chapter generation."
            if ready_preflight
            else "Not ready for production preflight. Use saved evidence. No retry."
        ),
    }
    validation_artifact = {
        key: value
        for key, value in structural.items()
        if key not in {"decoded", "canonical"}
    }
    validation_artifact["canonical"] = structural.get("canonical")
    bundle = {
        "header": header,
        "precall": _strip_precall(identity),
        "runtime": {
            **runtime,
            "provider_readiness": readiness_meta,
            "live_readiness": readiness.to_dict(),
        },
        "request_identity": {**_request_identity(identity, http_sent=True)},
        "api_compatibility": compat,
        "call_accounting": counts.to_dict(),
        "raw_response": raw_response,
        "provider_evidence": provider_evidence,
        "response_validation": validation_artifact,
        "case_results": {
            "rows": score.get("rows"),
            "mapping": [
                {
                    "opaque_handle": handle,
                    "case_id": (row or {}).get("case_id"),
                }
                for handle, row in mapped.items()
            ],
        },
        "benchmark_score": {
            key: value
            for key, value in score.items()
            if key not in {"rows", "funeral", "connective", "p3", "p8"}
        }
        | {
            "funeral": score.get("funeral"),
            "connective": score.get("connective"),
            "p3": score.get("p3"),
            "p8": score.get("p8"),
        },
        "human_review": human,
        "cost": calibration,
        "readiness": post,
        "tests": tests,
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
        },
    }
    bundle["report_text"] = render_report(bundle)
    bundle = redact_secrets(bundle)
    if write_artifacts:
        from app.book_semantic_gate_4b26.writer import write_canary_artifacts

        write_canary_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.error = error_text
    result.mode = "EXECUTE"
    return result


__all__ = ["CanaryRunResult", "run_canary"]
