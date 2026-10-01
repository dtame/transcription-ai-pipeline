"""
Runner Phase 4B.2.4.

Default: pre-call only, 0 POST.
Real: --execute-real + exact scope. One Terra attempt. No retry. No fallback.
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
from app.ai.structured_forensics import persist_structured_output_forensics
from app.ai.thinking import extract_thinking_tokens_from_usage
from app.ai.usage_store import record_call
from app.book_semantic_gate_4b24.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_WINDOW_ID,
    CONSERVATIVE_MAX_OUTPUT_TOKENS,
    EXPECTED_REQUEST_SHA256,
    HISTORICAL_4B21_STATUS,
    HISTORICAL_4B22_STATUS,
    HISTORICAL_4B2_STATUS,
    MAX_ENGINE_GENERATE,
    MODEL,
    PHASE,
    PROJECT_NAME,
    PROVIDER,
    SCORED_CASE_ORDER,
    STAGE_CANARY,
)
from app.book_semantic_gate_4b24.costing import actual_cost, cost_calibration
from app.book_semantic_gate_4b24.engine import (
    CountingOpenAIEngine,
    build_real_canary_engine,
    describe_engine,
)
from app.book_semantic_gate_4b24.guard import (
    BookSemanticGateCanaryError,
    OneShotCallGuard,
    assert_no_publication,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b24.identity import post_input_hashes, snapshot_identities
from app.book_semantic_gate_4b24.paths import (
    canary_lock_path,
    forensic_root,
    production_book_path,
    repo_root,
)
from app.book_semantic_gate_4b24.precall import build_precall
from app.book_semantic_gate_4b24.report import render_report
from app.book_semantic_gate_4b24.review import review_terra_output
from app.book_semantic_gate_4b24.score import classify_canary, score_benchmark
from app.book_semantic_gate_4b24.validate import (
    deterministic_replay,
    map_handle_results,
    validate_semantic_response,
)
from app.book_semantic_gate_4b23.sufficiency import sufficiency_assessment
from app.file_utils import content_hash
from app.source_analysis.errors import MaxRealCallsExceededError


def _consume_lock(*, root: Path | None) -> None:
    path = canary_lock_path(root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise BookSemanticGateCanaryError(
            "Canary real-call lock already present — authorization consumed. "
            "NO RETRY."
        )
    path.write_text(
        f"{PHASE}\n{AUTHORIZATION_SCOPE}\nconsumed=1\n",
        encoding="utf-8",
    )


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_semantic_gate_4b24.py",
        "app/tests/test_book_semantic_gate_4b23.py",
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
    return {
        "returncode": completed.returncode,
        "summary": summary,
        "passed": int(passed_match.group(1)) if passed_match else 0,
        "stderr_tail": "\n".join((completed.stderr or "").strip().splitlines()[-8:]),
        "new_failures": 0 if not failed else 1,
        "network_blocked": True,
        "suites": tests,
    }


def _strip_precall(identity: Mapping[str, Any]) -> dict[str, Any]:
    skip = {"payload", "ai_request", "gate_input", "scored_cases", "paragraph_texts"}
    return {key: value for key, value in identity.items() if key not in skip}


def _request_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
    request = dict(identity.get("request") or {})
    payload = dict(identity.get("payload") or {})
    for key in ("x-api-key", "api_key", "authorization", "timeout"):
        payload.pop(key, None)
    return {
        "phase": PHASE,
        "request_sha256": request.get("sha256"),
        "request_sha256_repeat": request.get("sha256_repeat"),
        "chars": request.get("chars"),
        "bytes": request.get("bytes"),
        "determinism": request.get("deterministic"),
        "model": request.get("model"),
        "max_tokens": request.get("max_tokens"),
        "temperature_present": request.get("temperature_present"),
        "thinking_present": request.get("thinking_present"),
        "response_format": request.get("response_format"),
        "gate_input_sha256": request.get("gate_input_sha256"),
        "payload": payload,
        "secrets_included": False,
        "http_sent": False,
        "production_request_builder": True,
        "human_labels_included": False,
    }


def _case_summary(row: Mapping[str, Any] | None) -> str:
    if not row:
        return "MISSING"
    classification = str(row.get("terra_class") or "MISSING")
    blocked = "BLOCKED" if row.get("blocked") else classification
    reasons = "/".join(row.get("terra_reasons") or []) or "none"
    return f"{blocked} ({reasons})"


@dataclass
class CanaryRunResult:
    mode: str
    authorization_scope: str = ""
    accepted: bool = False
    error: str | None = None
    engine_generate_attempts: int = 0
    openai_post_attempts: int = 0
    bundle: dict[str, Any] = field(default_factory=dict)


def _offline_bundle(
    identity: Mapping[str, Any],
    *,
    tests: Mapping[str, Any],
    verdict: str,
    notes: str,
) -> dict[str, Any]:
    after = post_input_hashes()
    after_snap = snapshot_identities(after)
    before = dict(identity.get("identities_before") or {})
    before_snap = snapshot_identities(before) if before else {}
    estimate = dict(identity.get("cost_estimate") or {})
    leak = dict(identity.get("label_leak") or {})
    request = dict(identity.get("request") or {})
    benchmark = dict(identity.get("benchmark") or {})
    header = {
        "result": verdict,
        "actual_terra_calls": 0,
        "source_map_sha256_pre": (before.get("source_map") or {}).get("sha256"),
        "source_map_sha256_post": (after.get("source_map") or {}).get("sha256"),
        "editorial_plan_sha256_pre": (before.get("editorial_plan") or {}).get("sha256"),
        "editorial_plan_sha256_post": (after.get("editorial_plan") or {}).get("sha256"),
        "clean_transcript_sha256_pre": (before.get("clean_transcript") or {}).get(
            "sha256"
        ),
        "clean_transcript_sha256_post": (after.get("clean_transcript") or {}).get(
            "sha256"
        ),
        "benchmark_sha256": benchmark.get("sha256"),
        "label_leakage": leak.get("label_leakage"),
        "request_sha256": request.get("sha256"),
        "request_determinism": "PASS" if request.get("deterministic") else "FAIL",
        "context_estimate": estimate.get("provider_adjusted_pessimistic"),
        "long_context_regime": estimate.get("long_context_regime"),
        "estimated_cost": estimate.get("total_cost_display"),
        "http_finish": None,
        "request_id": None,
        "input_tokens": None,
        "output_tokens": None,
        "thinking_tokens": None,
        "actual_cost": None,
        "json_parse": "n/a",
        "transport_decode": "n/a",
        "case_coverage": "n/a",
        "unknown_cases": "n/a",
        "duplicate_results": "n/a",
        "span_validation": "n/a",
        "positive_accepted": "n/a",
        "positive_false_rejections": "n/a",
        "negative_blocked": "n/a",
        "negative_false_negatives": "n/a",
        "verdict_accuracy": "n/a",
        "negative_recall": "n/a",
        "positive_specificity": "n/a",
        "reason_code_compatible": "n/a",
        "funeral_case": "n/a",
        "connective_case": "n/a",
        "p3_case": "n/a",
        "p8_case": "n/a",
        "partial_paragraph_detection": "n/a",
        "external_knowledge_resistance": "n/a",
        "rationale_quality": "n/a",
        "deterministic_replay": "n/a",
        "ready_for_book_generator_production_preflight": "NO",
        "notes": notes,
        "tests": tests.get("summary"),
        "new_failures": tests.get("new_failures"),
        "historical_4b2": HISTORICAL_4B2_STATUS,
        "historical_4b21": HISTORICAL_4B21_STATUS,
        "historical_4b22": HISTORICAL_4B22_STATUS,
        "inputs_unchanged": _yn(before_snap == after_snap) if before_snap else "n/a",
    }
    if notes == "openai_credential":
        notes = (
            "BLOCKED_PRECALL: OPENAI_API_KEY is not available in the environment "
            "or local .env. All other pre-call gates passed. The frozen "
            "benchmark request was built and not sent. ACTUAL TERRA CALLS = 0. "
            "No Sonnet call. No retry. Set OPENAI_API_KEY locally and "
            "re-authorize a later 4B.2.4 execution; do not invent a second "
            "automatic call."
        )
        header["notes"] = notes
    blocked_record = {
        "status": "BLOCKED_PRECALL",
        "actual_terra_calls": 0,
        "reason": notes,
        "http_sent": False,
    }
    readiness = {
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "4b22_candidate_cache": "NOT ACCEPTED",
        "book_generator_101": "SUFFICIENT_WITH_SEMANTIC_GATE",
        "why": notes,
    }
    bundle = {
        "header": header,
        "precall": _strip_precall(identity),
        "benchmark_identity": benchmark,
        "label_leak": leak,
        "request_identity": _request_identity(identity),
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
        "response_identity": {
            **blocked_record,
            "raw_text_chars": 0,
            "immutable": True,
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
        "reason_code_review": blocked_record,
        "human_review": {
            **blocked_record,
            "human_labels_remain_ground_truth": True,
            "terra_did_not_redefine_labels": True,
            "notes": [
                "Provider was not called. Frozen human labels were not modified.",
                "10 cases are an engineering canary, not a statistical model-quality benchmark.",
            ],
        },
        "readiness": readiness,
        "cost": {
            "phase": PHASE,
            "stage": STAGE_CANARY,
            "production_chapter_validation": False,
            "estimate": estimate,
            "estimate_status": "ESTIMATED",
            "actual": None,
            "blocked_precall": True,
        },
        "tests": tests,
        "execution": {
            "mode": "OFFLINE" if verdict != "BLOCKED_PRECALL" else "BLOCKED_PRECALL",
            "actual_terra_calls": 0,
            "sonnet_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
    }
    bundle["report_text"] = render_report(bundle)
    return bundle


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
    except BookSemanticGateCanaryError as exc:
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
        else {"skipped": True, "new_failures": 0, "network_blocked": True, "summary": "deferred"}
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
            from app.book_semantic_gate_4b24.writer import write_canary_artifacts

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
        except BookSemanticGateCanaryError as exc:
            result.accepted = False
            result.error = str(exc)
            result.mode = "REJECTED"
            bundle = _offline_bundle(
                identity,
                tests=tests,
                verdict="BLOCKED_PRECALL",
                notes=str(exc),
            )
            if write_artifacts:
                from app.book_semantic_gate_4b24.writer import write_canary_artifacts

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
            from app.book_semantic_gate_4b24.writer import write_canary_artifacts

            write_canary_artifacts(bundle, root=root)
        result.bundle = bundle
        return result

    forensic_dir = forensic_root(root=root)
    forensic_dir.mkdir(parents=True, exist_ok=True)
    guard = OneShotCallGuard(max_calls=MAX_ENGINE_GENERATE)
    identity_hash = str((identity.get("request") or {}).get("sha256") or PHASE)
    if isinstance(engine, CountingOpenAIEngine):
        _consume_lock(root=root)

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
        result.error = "KeyboardInterrupt"
        result.engine_generate_attempts = guard.generate_attempts
        result.openai_post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
        return result

    post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
    if post_attempts == 0:
        post_attempts = int(getattr(engine, "call_count", 0) or 0)
    result.engine_generate_attempts = guard.generate_attempts
    result.openai_post_attempts = post_attempts

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
    response_identity = {
        "phase": PHASE,
        "request_id": request_id,
        "http_status": http_status,
        "http_success": http_success,
        "finish_reason": finish,
        "elapsed_ms": elapsed,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "thinking_tokens_status": "unknown" if thinking_tokens is None else "reported",
        "cost": cost,
        "raw_structured_response_sha256": raw_response_hash,
        "raw_text_chars": len(raw_text or ""),
        "provider_metadata": http_meta,
        "airesponse": {
            key: value
            for key, value in response_meta.items()
            if key not in {"text", "parsed"}
        },
        "secrets_included": False,
        "forensic_path": forensic_path,
        "error": error_text,
        "immutable": True,
    }
    provider_evidence = {
        "phase": PHASE,
        "request_id": request_id,
        "http_status": http_status,
        "http_success": http_success,
        "finish_reason": finish,
        "elapsed_ms": elapsed,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "cost": cost,
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
        "response_identity": response_identity,
    }
    if write_artifacts:
        from app.book_semantic_gate_4b24.writer import persist_raw_evidence

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
    human = review_terra_output(score, structural=structural)
    tests = _run_focused_tests(root=base) if run_tests else {
        "skipped": True,
        "new_failures": 0,
        "network_blocked": True,
        "summary": "not-run",
    }
    leak = dict(identity.get("label_leak") or {})
    verdict = classify_canary(
        terra_calls=post_attempts,
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
    if error_text and http_success is not True:
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
            (identity.get("request") or {}).get("max_tokens")
            or CONSERVATIVE_MAX_OUTPUT_TOKENS
        ),
    )
    reason_review = {
        "funeral": {
            "compatible": bool((score.get("funeral") or {}).get("reason_compatible")),
            "reasons": (score.get("funeral") or {}).get("terra_reasons"),
            "expected": ["INVENTED_EXAMPLE"],
        },
        "connective": {
            "compatible": bool((score.get("connective") or {}).get("reason_compatible")),
            "reasons": (score.get("connective") or {}).get("terra_reasons"),
            "expected": ["NEW_ARGUMENT", "NEW_CONCLUSION", "NEW_IMPLICATION"],
        },
        "p3": {
            "compatible": bool((score.get("p3") or {}).get("reason_compatible")),
            "reasons": (score.get("p3") or {}).get("terra_reasons"),
            "expected": ["NEW_CAUSAL_LINK", "NEW_IMPLICATION"],
        },
        "p8": {
            "compatible": bool((score.get("p8") or {}).get("reason_compatible")),
            "reasons": (score.get("p8") or {}).get("terra_reasons"),
            "expected": ["REFERENCE_COMPLETION", "REFERENCE_EXPANSION"],
        },
        "compatible_count": score.get("reason_code_compatible"),
        "of": 4,
        "exact_single_code_not_required": True,
    }
    header = {
        "result": verdict,
        "actual_terra_calls": post_attempts,
        "source_map_sha256_pre": (before.get("source_map") or {}).get("sha256"),
        "source_map_sha256_post": (after.get("source_map") or {}).get("sha256"),
        "editorial_plan_sha256_pre": (before.get("editorial_plan") or {}).get("sha256"),
        "editorial_plan_sha256_post": (after.get("editorial_plan") or {}).get("sha256"),
        "clean_transcript_sha256_pre": (before.get("clean_transcript") or {}).get(
            "sha256"
        ),
        "clean_transcript_sha256_post": (after.get("clean_transcript") or {}).get(
            "sha256"
        ),
        "benchmark_sha256": (identity.get("benchmark") or {}).get("sha256"),
        "label_leakage": leak.get("label_leakage"),
        "request_sha256": (identity.get("request") or {}).get("sha256"),
        "request_determinism": (
            "PASS" if (identity.get("request") or {}).get("deterministic") else "FAIL"
        ),
        "context_estimate": estimate.get("provider_adjusted_pessimistic"),
        "long_context_regime": estimate.get("long_context_regime"),
        "estimated_cost": estimate.get("total_cost_display"),
        "http_finish": f"{http_status} / {finish}",
        "request_id": request_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens if thinking_tokens is not None else "unknown",
        "actual_cost": cost.get("display"),
        "json_parse": structural.get("json_parse"),
        "transport_decode": structural.get("transport_decode"),
        "case_coverage": structural.get("case_coverage"),
        "unknown_cases": len(structural.get("unknown_cases") or []),
        "duplicate_results": len(structural.get("duplicate_results") or []),
        "span_validation": structural.get("span_validation"),
        "positive_accepted": f"{score.get('positive_accepted')} / 6",
        "positive_false_rejections": score.get("positive_false_rejections"),
        "negative_blocked": f"{score.get('negative_blocked')} / 4",
        "negative_false_negatives": score.get("negative_false_negatives"),
        "verdict_accuracy": score.get("verdict_accuracy"),
        "negative_recall": score.get("negative_recall"),
        "positive_specificity": score.get("positive_specificity"),
        "reason_code_compatible": f"{score.get('reason_code_compatible')} / 4",
        "funeral_case": _case_summary(score.get("funeral")),
        "connective_case": _case_summary(score.get("connective")),
        "p3_case": _case_summary(score.get("p3")),
        "p8_case": _case_summary(score.get("p8")),
        "partial_paragraph_detection": (
            "PASS"
            if (score.get("p3") or {}).get("blocked")
            and (score.get("p8") or {}).get("blocked")
            else "FAIL"
        ),
        "external_knowledge_resistance": (
            "PASS"
            if (score.get("p8") or {}).get("blocked")
            and not (human.get("p8_case") or {}).get("external_knowledge_rescue")
            else "FAIL"
        ),
        "rationale_quality": human.get("rationale_quality"),
        "deterministic_replay": "PASS" if replay.get("pass") else "FAIL",
        "ready_for_book_generator_production_preflight": _yn(ready_preflight),
        "notes": error_text
        or score.get("small_sample_warning")
        or "Terra benchmark canary complete.",
        "tests": tests.get("summary"),
        "new_failures": tests.get("new_failures"),
        "inputs_unchanged": _yn(inputs_unchanged),
        "historical_4b2": HISTORICAL_4B2_STATUS,
        "historical_4b21": HISTORICAL_4B21_STATUS,
        "historical_4b22": HISTORICAL_4B22_STATUS,
        "book_generator_101": sufficiency.get("classification"),
    }
    readiness = {
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": ready_preflight,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": "HUMAN REVIEW",
        "book_json": "NOT PUBLISHED",
        "4b22_candidate_cache": "NOT ACCEPTED",
        "book_generator_101": sufficiency.get("classification"),
        "why": (
            "Clean Terra benchmark PASS. Next phase is OFFLINE production "
            "rollout preflight. Do not start 19-chapter generation."
            if ready_preflight
            else "Not ready for production preflight. Use saved evidence. No retry."
        ),
        "future_offline_preflight": [
            "all 19 generation requests",
            "semantic-gate request construction rules",
            "cost budgets",
            "cache/recovery",
            "CH016 treatment",
            "rollout batching",
            "stop conditions",
        ],
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
        "benchmark_identity": identity.get("benchmark"),
        "label_leak": leak,
        "request_identity": {**_request_identity(identity), "http_sent": True},
        "raw_response": raw_response,
        "provider_evidence": provider_evidence,
        "response_identity": response_identity,
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
            "funeral": {
                k: (score.get("funeral") or {}).get(k)
                for k in (
                    "case_id",
                    "terra_class",
                    "terra_reasons",
                    "blocked",
                    "reason_compatible",
                    "false_negative",
                )
            },
            "connective": {
                k: (score.get("connective") or {}).get(k)
                for k in (
                    "case_id",
                    "terra_class",
                    "terra_reasons",
                    "blocked",
                    "reason_compatible",
                    "false_negative",
                )
            },
            "p3": {
                k: (score.get("p3") or {}).get(k)
                for k in (
                    "case_id",
                    "terra_class",
                    "terra_reasons",
                    "blocked",
                    "reason_compatible",
                    "partial_clause_detected",
                )
            },
            "p8": {
                k: (score.get("p8") or {}).get(k)
                for k in (
                    "case_id",
                    "terra_class",
                    "terra_reasons",
                    "blocked",
                    "reason_compatible",
                    "partial_clause_detected",
                )
            },
        },
        "reason_code_review": reason_review,
        "human_review": human,
        "cost": calibration,
        "readiness": readiness,
        "tests": tests,
        "execution": {
            "result": verdict,
            "engine": describe_engine(engine),
            "engine_generate_attempts": guard.generate_attempts,
            "openai_post_attempts": post_attempts,
            "retries": 0,
            "fallbacks": 0,
            "sonnet_calls": 0,
            "error": error_text,
            "forensic_path": forensic_path,
            "book_json": "NOT PUBLISHED",
            "production_cache": "NOT ACCEPTED",
            "inputs_unchanged": inputs_unchanged,
            "stage": STAGE_CANARY,
        },
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        from app.book_semantic_gate_4b24.writer import write_canary_artifacts

        write_canary_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.error = error_text
    result.mode = "EXECUTE"
    return result


__all__ = ["CanaryRunResult", "run_canary"]
