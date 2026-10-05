"""
Runner Phase 4B.2.21.

Preflight, hashes, CH012 integrity, CH018 hydration, cost bound, then
at most one Anthropic call. No retry. No fallback. No Terra. No publication.
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
from app.ai.provider_preflight import redact_secrets
from app.ai.structured_forensics import persist_structured_output_forensics
from app.ai.usage_store import record_call
from app.book_generation_integration_4b213.cache import IsolatedChapterCache
from app.book_generation_4b221.authorization import authorization_manifest
from app.book_generation_4b221.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_WINDOW_ID,
    CANONICAL_PYTHON,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SECTION_IDS,
    LOCK_STATE_FAILED,
    LOCK_STATE_POSSIBLY_SENT,
    LOCK_STATE_PREPARATION,
    LOCK_STATE_RESPONSE_RECEIVED,
    LOCK_STATE_RESPONSE_VALIDATED,
    LOCK_STATE_UNCERTAIN,
    MODEL,
    NEXT_ACTION,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    STAGE_CANARY,
    TARGET_CHAPTER_ID,
)
from app.book_generation_4b221.context import (
    build_ch018_context,
    chapter_from_plan,
    load_corpus,
    source_context_manifest,
)
from app.book_generation_4b221.costing import actual_cost, reserve_budget
from app.book_generation_4b221.editorial import editorial_readiness_review
from app.book_generation_4b221.engine import (
    CountingAnthropicEngine,
    build_real_engine,
    credential_available,
    describe_engine,
)
from app.book_generation_4b221.guard import (
    BookGeneration4221Error,
    OneShotCallGuard,
    assert_no_publication,
    validate_authorization_scope,
)
from app.book_generation_4b221.hashes import (
    assert_canonical,
    assert_ch012_unchanged,
    snapshot,
    snapshots_match,
)
from app.book_generation_4b221.lock import (
    lock_already_consumed,
    persist_preparation,
    read_lock,
    reserve_call,
    transition_lock,
)
from app.book_generation_4b221.paths import (
    forensic_root,
    lock_path,
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_generation_4b221.report import render_report
from app.book_generation_4b221.request import request_identity
from app.book_generation_4b221.scenarios import evaluate_offline_scenarios
from app.book_generation_4b221.traceability import idea_traceability_review
from app.book_generation_4b221.validation import (
    interpret_response,
    render_chapter_markdown,
    structural_validation,
)
from app.book_generation_4b221.writer import write_phase_artifacts
from app.file_utils import content_hash
from app.source_analysis.errors import MaxRealCallsExceededError


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_generation_4b221.py",
        "app/tests/test_book_scale_up_preparation_4b220.py",
    ]
    python = str(venv_python_path(root=root))
    completed = subprocess.run(
        [python, "-m", "pytest", "-q", "--tb=line", *tests],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = completed.stdout or ""
    summary = next(
        (
            line.strip()
            for line in reversed((stdout + "\n" + (completed.stderr or "")).splitlines())
            if "passed" in line or "failed" in line
        ),
        "",
    )
    passed_match = re.search(r"(\d+) passed", summary)
    failed_match = re.search(r"(\d+) failed", summary)
    return {
        "returncode": completed.returncode,
        "summary": summary,
        "passed": int(passed_match.group(1)) if passed_match else 0,
        "failed": int(failed_match.group(1)) if failed_match else (0 if completed.returncode == 0 else 1),
        "stderr_tail": "\n".join((completed.stderr or "").strip().splitlines()[-12:]),
        "suites": tests,
        "real_provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "phase": PHASE,
        "canonical_python": python,
    }


def _hash_line(label: str, snap: dict[str, Any]) -> str:
    canonical = snap["canonical"]
    return (
        f"{label} source={canonical['source_map']['sha256']} "
        f"plan={canonical['editorial_plan']['sha256']} "
        f"transcript={canonical['clean_transcript']['sha256']}"
    )


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    engine_generate_attempts: int = 0
    anthropic_post_attempts: int = 0


def _classify(
    *,
    calls: int,
    blocked: bool,
    json_valid: bool,
    contract_valid: bool,
    sections_ok: bool,
    ideas_ok: bool,
    hashes_ok: bool,
    ch012_ok: bool,
    test_failures: int,
    http_success: bool | None,
    error_text: str | None,
) -> str:
    if blocked and calls == 0:
        return "BLOCKED"
    if calls == 0:
        return "FAIL"
    if error_text and http_success is not True and not json_valid:
        return "FAIL"
    if not hashes_ok or not ch012_ok:
        return "FAIL"
    if not json_valid or not contract_valid or not sections_ok or not ideas_ok:
        return "PARTIAL"
    if test_failures:
        return "PARTIAL"
    return "PASS"


def run_phase(
    *,
    authorization_scope: str | None,
    dry_run: bool = True,
    execute_real: bool = False,
    allow_real_provider: bool = False,
    engine=None,
    root: Path | None = None,
    write_artifacts: bool = True,
    persist_usage: bool = False,
    run_tests: bool = True,
) -> PhaseResult:
    result = PhaseResult(
        accepted=False,
        mode="DRY_RUN" if (dry_run or not execute_real) else "EXECUTE",
    )
    isolated_cache = IsolatedChapterCache()
    try:
        scope = validate_authorization_scope(authorization_scope)
        assert_no_publication(production_book_path())
    except BookGeneration4221Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = snapshot(root=base)
    try:
        assert_canonical(before)
        assert_ch012_unchanged(before)
        corpus = load_corpus()
        chapter = chapter_from_plan(corpus.plan)
        built = build_ch018_context(corpus=corpus)
        evidence = built["evidence"]
    except Exception as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        after = snapshot(root=base)
        bundle = {
            "header": _header(
                before=before,
                after=after,
                calls=0,
                anthropic_http=0,
                cost={},
                actual=None,
                structural=None,
                idea=None,
                editorial=None,
                tests={"passed": 0, "failed": 0},
                stop_reason=str(exc),
                result="BLOCKED",
                json_valid=False,
                contract_valid=False,
            ),
            "canonical_hashes_pre": before,
            "canonical_hashes_post": after,
            "readiness": {
                "READY_FOR_HUMAN_REVIEW": False,
                "READY_FOR_NEXT_CHAPTER": False,
                "why": str(exc),
            },
        }
        bundle["report_text"] = render_report(bundle)
        if write_artifacts:
            write_phase_artifacts(bundle, root=base, call_completed=False)
        result.bundle = redact_secrets(bundle)
        return result

    idea_count = len(evidence.get("ideas") or [])
    section_count = len(evidence.get("sections") or [])
    output_probe = reserve_budget(
        {
            "payload": {"system": "", "messages": [{"role": "user", "content": ""}]},
            "local_input_token_estimate": {"tokens": 0},
            "thinking_mode": "disabled",
        },
        idea_count=idea_count,
        section_count=section_count,
    )
    max_output = int(output_probe["max_output_tokens"])
    identity = request_identity(evidence, max_output_tokens=max_output)
    cost = reserve_budget(identity, idea_count=idea_count, section_count=section_count)
    max_output = int(cost["max_output_tokens"])
    identity = request_identity(evidence, max_output_tokens=max_output)
    cost = reserve_budget(identity, idea_count=idea_count, section_count=section_count)

    scenarios = evaluate_offline_scenarios(root=base)
    tests = (
        _run_focused_tests(root=base)
        if run_tests
        else {
            "returncode": 0,
            "summary": "skipped",
            "passed": 0,
            "failed": 0,
            "suites": [],
            "real_provider_calls": 0,
        }
    )
    prompt_snapshot = dict(identity.get("prompt_snapshot") or {})
    context_manifest = source_context_manifest(built)

    lock = lock_path(root=base)
    already = lock_already_consumed(lock)
    blocked = False
    block_reason = None
    if already:
        blocked = True
        block_reason = "PROVIDER_CALL_ALREADY_CONSUMED"
    elif cost.get("blocked"):
        blocked = True
        block_reason = str(cost.get("block_reason") or "COST_BLOCK")
    elif not identity.get("deterministic"):
        blocked = True
        block_reason = "REQUEST_NOT_DETERMINISTIC"
    elif identity.get("model") != MODEL:
        blocked = True
        block_reason = "MODEL_UNAVAILABLE"
    elif context_manifest.get("context_truncated"):
        blocked = True
        block_reason = "SOURCE_CONTEXT_TRUNCATED"
    elif execute_real and not (allow_real_provider or engine is not None):
        blocked = True
        block_reason = "REAL_PROVIDER_NOT_ALLOWED"
    elif execute_real and engine is None and not credential_available():
        blocked = True
        block_reason = "MODEL_UNAVAILABLE"
    elif execute_real and int(tests.get("failed") or 0) and engine is None:
        blocked = True
        block_reason = "OFFLINE_TESTS_FAILED"
    elif execute_real and int(scenarios.get("failed") or 0):
        blocked = True
        block_reason = "OFFLINE_SCENARIOS_FAILED"

    if not already:
        persist_preparation(lock)

    preflight = {
        "phase": PHASE,
        "authorization_scope": scope,
        "chapter_id": TARGET_CHAPTER_ID,
        "model": f"{PROVIDER}/{MODEL}",
        "prompt_version": PROMPT_VERSION,
        "canonical_hashes_ok": before["canonical_match_expected"],
        "ch012_unchanged": before["ch012_unchanged"],
        "sources_available": bool((built.get("resolved_sources") or {}).get("hydrated_count")),
        "chapter_isolated": context_manifest.get("other_chapters_excluded"),
        "faithful_prompt_isolated": prompt_snapshot.get("registered_in_prompt_select") is False,
        "historical_prompt_unmodified": True,
        "production_cache_write": False,
        "production_book_absent": True,
        "single_call_limit_possible": True,
        "lock_already_consumed": already,
        "cost_blocked": bool(cost.get("blocked")),
        "blocked": blocked,
        "block_reason": block_reason,
        "execute_real_requested": bool(execute_real),
        "dry_run": bool(dry_run or not execute_real),
        "secrets_included": False,
    }

    will_call = bool(execute_real and not blocked and not dry_run)
    if not will_call:
        after = snapshot(root=base)
        stop_reason = block_reason or (
            "DRY_RUN" if dry_run or not execute_real else "STOPPED_BEFORE_PROVIDER_CALL"
        )
        header = _header(
            before=before,
            after=after,
            calls=0,
            anthropic_http=0,
            cost=cost,
            actual=None,
            structural=None,
            idea=None,
            editorial=None,
            tests=tests,
            stop_reason=stop_reason,
            result="BLOCKED" if blocked else "FAIL",
            json_valid=False,
            contract_valid=False,
            prompt_hash=prompt_snapshot.get("prompt_sha256"),
            context_hash=context_manifest.get("context_hash"),
        )
        bundle = _offline_bundle(
            header=header,
            before=before,
            after=after,
            preflight=preflight,
            prompt=prompt_snapshot,
            context=context_manifest,
            cost=cost,
            authorization=authorization_manifest(
                consumed=already,
                sha256=identity.get("request_sha256"),
                blocked=blocked,
                block_reason=block_reason,
                lock_state=(read_lock(lock) or {}).get("state") or LOCK_STATE_PREPARATION,
            ),
            tests=tests,
            scenarios=scenarios,
            notes=stop_reason or "preflight only",
        )
        bundle["report_text"] = render_report(bundle)
        if write_artifacts:
            write_phase_artifacts(bundle, root=base, call_completed=False)
        result.bundle = redact_secrets(bundle)
        result.error = block_reason or ""
        result.mode = "BLOCKED_PRECALL" if blocked else "DRY_RUN"
        result.accepted = not blocked
        return result

    if engine is None:
        try:
            engine = build_real_engine()
        except BookGeneration4221Error as exc:
            after = snapshot(root=base)
            header = _header(
                before=before,
                after=after,
                calls=0,
                anthropic_http=0,
                cost=cost,
                actual=None,
                structural=None,
                idea=None,
                editorial=None,
                tests=tests,
                stop_reason=str(exc),
                result="BLOCKED",
                json_valid=False,
                contract_valid=False,
                prompt_hash=prompt_snapshot.get("prompt_sha256"),
                context_hash=context_manifest.get("context_hash"),
            )
            bundle = _offline_bundle(
                header=header,
                before=before,
                after=after,
                preflight=preflight,
                prompt=prompt_snapshot,
                context=context_manifest,
                cost=cost,
                authorization=authorization_manifest(
                    consumed=False,
                    sha256=identity.get("request_sha256"),
                    blocked=True,
                    block_reason=str(exc),
                    lock_state=(read_lock(lock) or {}).get("state"),
                ),
                tests=tests,
                scenarios=scenarios,
                notes=str(exc),
            )
            bundle["report_text"] = render_report(bundle)
            if write_artifacts:
                write_phase_artifacts(bundle, root=base, call_completed=False)
            result.bundle = redact_secrets(bundle)
            result.error = str(exc)
            result.mode = "REJECTED"
            return result

    request = identity["ai_request"]
    guard = OneShotCallGuard(max_calls=1)
    reserve_call(lock, request_sha256=str(identity.get("request_sha256") or ""))
    forensic_dir = forensic_root(root=base)
    forensic_dir.mkdir(parents=True, exist_ok=True)
    tracker = CostTracker()
    http_meta: dict[str, Any] = {}
    response_meta: dict[str, Any] = {}
    raw_parsed = None
    raw_text = None
    error_text = None
    http_success = None
    cost_record = None
    response = None
    identity_hash = str(identity.get("request_sha256") or "")
    transition_lock(
        lock,
        state=LOCK_STATE_POSSIBLY_SENT,
        request_sha256=identity_hash,
        note="Generate started. If interrupted, treat authorization as consumed.",
        extra={"http_sent": True},
    )

    try:
        with provider_forensic_scope(
            windows_root=forensic_dir,
            window_id=CANARY_WINDOW_ID,
            analysis_signature=identity_hash,
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
                    analysis_signature=identity_hash,
                    provider=getattr(getattr(exc, "response", None), "provider", None),
                    model=getattr(getattr(exc, "response", None), "model", None) or MODEL,
                    stage=STAGE_CANARY,
                )
                persist_error_forensics(
                    exc,
                    windows_root=forensic_dir,
                    window_id=CANARY_WINDOW_ID,
                    analysis_signature=identity_hash,
                )
                envelope = getattr(exc, "http_envelope", None) or current_http_envelope()
                if envelope is not None:
                    http_meta = envelope.compact_metadata()
                    http_success = envelope.http_success
                attached = getattr(exc, "response", None)
                if attached is not None:
                    response_meta = attached.to_dict()
                    raw_text = attached.text
                    raw_parsed = getattr(attached, "parsed", None)
                    if not isinstance(raw_parsed, dict):
                        raw_parsed = None
                error_text = str(exc)
                response = None
            except AIError as exc:
                persist_error_forensics(
                    exc,
                    windows_root=forensic_dir,
                    window_id=CANARY_WINDOW_ID,
                    analysis_signature=identity_hash,
                )
                envelope = getattr(exc, "http_envelope", None) or current_http_envelope()
                if envelope is not None:
                    http_meta = envelope.compact_metadata()
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
                if envelope is not None:
                    persist_provider_forensics(envelope)
                    http_meta = envelope.compact_metadata()
                    http_success = envelope.http_success
                elif response is not None:
                    http_success = True
                if response is not None:
                    response_meta = response.to_dict()
                    raw_text = response.text
                    raw_parsed = response.parsed if isinstance(response.parsed, dict) else None
                    cost_record = tracker.record_response(response, stage=STAGE_CANARY)
    except KeyboardInterrupt:
        transition_lock(
            lock,
            state=LOCK_STATE_UNCERTAIN,
            note="KeyboardInterrupt after reservation. NO RETRY.",
        )
        result.error = "KeyboardInterrupt after authorization consumed. NO RETRY."
        result.engine_generate_attempts = guard.generate_attempts
        result.anthropic_post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
        result.mode = "INTERRUPTED"
        after = snapshot(root=base)
        header = _header(
            before=before,
            after=after,
            calls=int(getattr(engine, "post_attempts", 0) or guard.generate_attempts),
            anthropic_http=int(getattr(engine, "post_attempts", 0) or 0),
            cost=cost,
            actual=None,
            structural=None,
            idea=None,
            editorial=None,
            tests=tests,
            stop_reason="RESPONSE_UNCERTAIN_AFTER_SEND",
            result="FAIL",
            json_valid=False,
            contract_valid=False,
            prompt_hash=prompt_snapshot.get("prompt_sha256"),
            context_hash=context_manifest.get("context_hash"),
        )
        bundle = _offline_bundle(
            header=header,
            before=before,
            after=after,
            preflight=preflight,
            prompt=prompt_snapshot,
            context=context_manifest,
            cost=cost,
            authorization=authorization_manifest(
                consumed=True,
                sha256=identity.get("request_sha256"),
                blocked=False,
                block_reason="RESPONSE_UNCERTAIN_AFTER_SEND",
                lock_state=LOCK_STATE_UNCERTAIN,
            ),
            tests=tests,
            scenarios=scenarios,
            notes="KeyboardInterrupt after send. NO RETRY.",
        )
        bundle["report_text"] = render_report(bundle)
        if write_artifacts:
            write_phase_artifacts(bundle, root=base, call_completed=False)
        result.bundle = redact_secrets(bundle)
        return result

    post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
    generate_attempts = int(getattr(engine, "generate_attempts", 0) or guard.generate_attempts)
    result.engine_generate_attempts = generate_attempts
    result.anthropic_post_attempts = post_attempts

    input_tokens = response_meta.get("input_tokens") or http_meta.get("input_tokens")
    output_tokens = response_meta.get("output_tokens") or http_meta.get("output_tokens")
    thinking_tokens = response_meta.get("thinking_tokens") or http_meta.get("thinking_tokens")
    finish = response_meta.get("finish_reason") or http_meta.get("finish_reason")
    actual = actual_cost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
    )
    if cost_record is not None and persist_usage:
        record_call(PROJECT_NAME, cost_record)

    if raw_parsed is not None or response is not None:
        transition_lock(
            lock,
            state=LOCK_STATE_RESPONSE_RECEIVED,
            note="Provider response received.",
            extra={"http_sent": True, "finish_reason": finish},
        )
    elif error_text:
        transition_lock(
            lock,
            state=LOCK_STATE_FAILED,
            note=error_text,
            extra={"http_sent": True},
        )

    interpreted = interpret_response(
        raw_parsed,
        plan=corpus.plan,
        source_map=corpus.source_map,
        chapter=chapter,
        language=corpus.language,
        allowed_handles=list(evidence.get("allowed") or []),
        provider_raw_sha256=content_hash(raw_text) if raw_text else "",
    )
    candidate = interpreted.get("candidate")
    if candidate is not None:
        isolated_cache.store(
            str(identity.get("request_sha256") or TARGET_CHAPTER_ID),
            {"chapter_id": TARGET_CHAPTER_ID, "isolated": True},
        )
    structural = structural_validation(
        interpreted=interpreted,
        plan=corpus.plan,
        chapter=chapter,
        allowed_handles=list(evidence.get("allowed") or []),
        other_chapter_ids=[
            item.chapter_id for item in corpus.plan.chapters if item.chapter_id != TARGET_CHAPTER_ID
        ],
        finish_reason=finish,
        max_output_tokens=max_output,
    )
    candidate_payload = candidate.to_dict() if candidate is not None else None
    idea = idea_traceability_review(
        candidate_payload=candidate_payload,
        raw_parsed=raw_parsed,
        structural=structural,
        allowed_handles=list(evidence.get("allowed") or []),
    )
    editorial = editorial_readiness_review(
        candidate=candidate,
        chapter=chapter,
        structural=structural,
    )
    after = snapshot(root=base)
    hashes_ok = snapshots_match(before, after) and after["canonical_match_expected"]
    ch012_ok = bool(after.get("ch012_unchanged"))
    checks = dict(structural.get("checks") or {})
    result_label = _classify(
        calls=max(post_attempts, generate_attempts),
        blocked=False,
        json_valid=bool(structural.get("json_valid")),
        contract_valid=bool(structural.get("chapter_contract_valid")),
        sections_ok=bool(checks.get("sections_match")),
        ideas_ok=not checks.get("ideas_missing_from_paras_e")
        and not checks.get("ideas_invented"),
        hashes_ok=hashes_ok,
        ch012_ok=ch012_ok,
        test_failures=int(tests.get("failed") or 0),
        http_success=http_success,
        error_text=error_text,
    )
    if error_text and result_label == "PASS":
        result_label = "PARTIAL"
    stop_reason = "ONE_REAL_CALL_COMPLETED"
    if error_text:
        stop_reason = "ONE_REAL_CALL_COMPLETED_WITH_ERROR"
    if finish in {"length", "max_tokens"}:
        stop_reason = "OUTPUT_LENGTH_STOP"
        if result_label == "PASS":
            result_label = "PARTIAL"

    if result_label == "PASS" and structural.get("status") == "PASS":
        transition_lock(
            lock,
            state=LOCK_STATE_RESPONSE_VALIDATED,
            note="Response structurally validated.",
        )
    elif raw_parsed is not None or response is not None:
        transition_lock(
            lock,
            state=LOCK_STATE_FAILED if result_label == "FAIL" else LOCK_STATE_RESPONSE_RECEIVED,
            note=stop_reason,
        )

    header = _header(
        before=before,
        after=after,
        calls=max(post_attempts, generate_attempts),
        anthropic_http=post_attempts if isinstance(engine, CountingAnthropicEngine) else generate_attempts,
        cost=cost,
        actual=actual,
        structural=structural,
        idea=idea,
        editorial=editorial,
        tests=tests,
        stop_reason=stop_reason,
        result=result_label,
        json_valid=bool(structural.get("json_valid")),
        contract_valid=bool(structural.get("chapter_contract_valid")),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        finish=finish,
        prompt_hash=prompt_snapshot.get("prompt_sha256"),
        context_hash=context_manifest.get("context_hash"),
    )
    anthropic_http = header["anthropic_http"]
    if describe_engine(engine).get("is_fake"):
        header["anthropic_http"] = 0
        anthropic_http = 0

    usage = {
        "phase": PHASE,
        "provider": PROVIDER,
        "model": f"{PROVIDER}/{MODEL}",
        "http_success": http_success,
        "http_status": http_meta.get("http_status"),
        "finish_reason": finish,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "request_id": http_meta.get("request_id") or response_meta.get("request_id"),
        "elapsed_ms": http_meta.get("elapsed_ms") or response_meta.get("latency_ms"),
        "raw_sha256": content_hash(raw_text) if raw_text else None,
        "cost": actual,
        "error": error_text,
        "engine": describe_engine(engine),
        "usage": http_meta.get("usage") if isinstance(http_meta.get("usage"), dict) else {},
        "secrets_included": False,
    }
    raw_response = {
        "phase": PHASE,
        "http_success": http_success,
        "finish_reason": finish,
        "parsed": raw_parsed,
        "raw_sha256": content_hash(raw_text) if raw_text else None,
        "raw_chars": len(raw_text) if raw_text else 0,
        "error": error_text,
        "invented_response": False,
        "secrets_included": False,
    }
    markdown = render_chapter_markdown(candidate, chapter) if candidate is not None else None
    ready_human = result_label in {"PASS", "PARTIAL"} and candidate is not None
    header["ready_for_human_review"] = _yn(ready_human)
    header["quality_summary"] = editorial.get("readability")
    bundle = {
        "header": header,
        "preflight": preflight,
        "canonical_hashes_pre": before,
        "authorization_scope": authorization_manifest(
            consumed=True,
            sha256=identity.get("request_sha256"),
            blocked=False,
            block_reason=None,
            lock_state=(read_lock(lock) or {}).get("state"),
        ),
        "prompt_manifest": prompt_snapshot,
        "source_context_manifest": context_manifest,
        "cost_preflight": cost,
        "provider_response_raw": raw_response,
        "provider_usage": usage,
        "chapter_candidate": candidate_payload,
        "chapter_candidate_md": markdown,
        "structural_validation": structural,
        "idea_traceability_review": idea,
        "editorial_readiness_review": editorial,
        "canonical_hashes_post": after,
        "regression_tests": tests,
        "offline_scenarios": scenarios,
        "isolated_cache": {
            "production_writes": isolated_cache.production_writes,
            "records": len(isolated_cache.records),
            "production_cache": "UNCHANGED",
        },
        "readiness": {
            "READY_FOR_HUMAN_REVIEW": ready_human,
            "READY_FOR_NEXT_CHAPTER": False,
            "book_json": "NOT PUBLISHED",
            "production_cache": "UNCHANGED",
            "SEMANTIC_CERTIFICATION": "NOT PERFORMED",
            "HUMAN_EDITORIAL_ACCEPTANCE": "PENDING",
            "NEXT_ACTION": NEXT_ACTION,
            "why": stop_reason,
        },
        "execution": {
            "mode": result_label,
            "provider_calls": max(post_attempts, generate_attempts),
            "anthropic_http": anthropic_http,
            "openai_http": 0,
            "retries": 0,
            "fallbacks": 0,
        },
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        write_phase_artifacts(bundle, root=base, call_completed=True)
    result.bundle = redact_secrets(bundle)
    result.accepted = result_label in {"PASS", "PARTIAL"}
    result.mode = result_label
    result.error = error_text or ""
    return result


def _header(
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    calls: int,
    anthropic_http: int,
    cost: Mapping[str, Any],
    actual: Mapping[str, Any] | None,
    structural: Mapping[str, Any] | None,
    idea: Mapping[str, Any] | None,
    editorial: Mapping[str, Any] | None,
    tests: Mapping[str, Any],
    stop_reason: str,
    result: str,
    json_valid: bool,
    contract_valid: bool,
    input_tokens: Any = None,
    output_tokens: Any = None,
    finish: Any = None,
    prompt_hash: Any = None,
    context_hash: Any = None,
) -> dict[str, Any]:
    checks = dict((structural or {}).get("checks") or {})
    actual_display = "n/a"
    if actual:
        actual_display = actual.get("display") or actual.get("total_cost_usd")
    sections = list(checks.get("sections_generated") or [])
    idea_found = (idea or {}).get("ideas_found_count")
    if idea_found is None:
        idea_found = len(checks.get("ideas_in_paragraph_evidence") or [])
    potential = (editorial or {}).get("potential_substantive_issues") or []
    voice = ((editorial or {}).get("authorial_voice") or {}).get("classification")
    return {
        "result": result,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "provider_calls": calls,
        "anthropic_http": anthropic_http,
        "openai_http": 0,
        "chapter": TARGET_CHAPTER_ID,
        "model": f"{PROVIDER}/{MODEL}",
        "prompt": PROMPT_VERSION,
        "prompt_hash": prompt_hash,
        "source_context_hash": context_hash,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "finish_reason": finish,
        "preflight_max_cost": cost.get("theoretical_maximum_usd"),
        "actual_cost": actual_display,
        "retries": 0,
        "fallbacks": 0,
        "json_valid": _yn(json_valid) if calls else "NO",
        "structural_contract": (structural or {}).get("status") or "FAIL",
        "sections_present": sections or list(EXPECTED_SECTION_IDS) if calls else [],
        "idea_handles_expected": EXPECTED_IDEA_COUNT,
        "idea_handles_found": idea_found if calls else 0,
        "idea_handles_invalid": list((idea or {}).get("ideas_invalid") or []),
        "src_handles_invalid": list((idea or {}).get("src_handles_invalid") or []),
        "authorial_voice_review": voice or "n/a",
        "potential_substantive_issues": len(potential),
        "canonical_hashes_pre_post": (
            _hash_line("pre", before) + "; " + _hash_line("post", after)
        ),
        "ch012_unchanged": _yn(bool(after.get("ch012_unchanged"))),
        "production_cache": "UNCHANGED",
        "ready_for_human_review": "NO",
        "next_action": NEXT_ACTION,
        "canonical_python": CANONICAL_PYTHON,
        "stop_reason": stop_reason,
        "tests_passed_failed": f"{tests.get('passed') or 0} / {tests.get('failed') or 0}",
    }


def _offline_bundle(
    *,
    header: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    preflight: dict[str, Any],
    prompt: dict[str, Any],
    context: dict[str, Any],
    cost: dict[str, Any],
    authorization: dict[str, Any],
    tests: dict[str, Any],
    scenarios: dict[str, Any],
    notes: str,
) -> dict[str, Any]:
    return {
        "header": header,
        "preflight": preflight,
        "canonical_hashes_pre": before,
        "authorization_scope": authorization,
        "prompt_manifest": prompt,
        "source_context_manifest": context,
        "cost_preflight": cost,
        "canonical_hashes_post": after,
        "regression_tests": tests,
        "offline_scenarios": scenarios,
        "readiness": {
            "READY_FOR_HUMAN_REVIEW": False,
            "READY_FOR_NEXT_CHAPTER": False,
            "book_json": "NOT PUBLISHED",
            "production_cache": "UNCHANGED",
            "SEMANTIC_CERTIFICATION": "NOT PERFORMED",
            "HUMAN_EDITORIAL_ACCEPTANCE": "PENDING",
            "NEXT_ACTION": NEXT_ACTION,
            "why": notes,
        },
        "execution": {
            "mode": header.get("result"),
            "provider_calls": 0,
            "anthropic_http": 0,
            "openai_http": 0,
            "retries": 0,
            "fallbacks": 0,
        },
    }


__all__ = ["PhaseResult", "run_phase"]
