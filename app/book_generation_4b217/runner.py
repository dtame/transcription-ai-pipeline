"""
Runner Phase 4B.2.17.

Preflight, hashes, hydration, cost bound, then at most one Anthropic call.
No retry. No fallback. No Terra. No publication.
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
from app.book_editorial_alignment_4b216.policy import editorial_policy
from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation_integration_4b213.cache import IsolatedChapterCache
from app.book_generation_4b217.authorization import authorization_manifest
from app.book_generation_4b217.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_WINDOW_ID,
    CANONICAL_PYTHON,
    EDITORIAL_POLICY_VERSION,
    EXPECTED_SECTION_COUNT,
    HISTORICAL_4B210_STATUS,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_4B212_STATUS,
    HISTORICAL_4B213_STATUS,
    HISTORICAL_4B214_STATUS,
    HISTORICAL_4B215_STATUS,
    HISTORICAL_4B216_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    MODEL,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    STAGE_CANARY,
    TARGET_CHAPTER_ID,
)
from app.book_generation_4b217.context import (
    build_ch012_evidence,
    chapter_context_manifest,
    chapter_from_plan,
    hydrated_source_manifest,
    load_canonical_corpus,
)
from app.book_generation_4b217.costing import actual_cost, reserve_budget
from app.book_generation_4b217.coverage import assess_chapter_coverage
from app.book_generation_4b217.engine import (
    CountingAnthropicEngine,
    build_real_engine,
    credential_available,
    describe_engine,
)
from app.book_generation_4b217.guard import (
    BookGeneration4217Error,
    OneShotCallGuard,
    assert_no_publication,
    consume_remote_lock,
    lock_already_consumed,
    validate_authorization_scope,
)
from app.book_generation_4b217.hashes import assert_canonical, snapshot, snapshots_match
from app.book_generation_4b217.paths import (
    forensic_root,
    lock_path,
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_generation_4b217.report import render_report
from app.book_generation_4b217.request import request_identity
from app.book_generation_4b217.risks import editorial_risk_flags
from app.book_generation_4b217.scenarios import evaluate_offline_scenarios
from app.book_generation_4b217.terra_prep import prepare_terra_manifest
from app.book_generation_4b217.validation import (
    interpret_response,
    render_chapter_markdown,
    structural_validation,
)
from app.book_generation_4b217.writer import write_phase_artifacts
from app.file_utils import content_hash
from app.source_analysis.errors import MaxRealCallsExceededError


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_generation_4b217.py",
        "app/tests/test_book_editorial_alignment_4b216.py",
        "app/tests/test_book_generation_4b1.py",
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


def _strip_request(identity: Mapping[str, Any]) -> dict[str, Any]:
    skip = {"payload", "ai_request"}
    return {key: value for key, value in identity.items() if key not in skip}


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
    test_failures: int,
    http_success: bool | None,
    error_text: str | None,
) -> str:
    if blocked and calls == 0:
        return "FAIL"
    if calls == 0:
        return "FAIL"
    if error_text and http_success is not True and not json_valid:
        return "FAIL"
    if not hashes_ok:
        return "FAIL"
    if not json_valid or not contract_valid or not sections_ok or not ideas_ok:
        return "PARTIAL"
    if test_failures:
        return "PARTIAL"
    return "PASS"


def _editorial_summary(*, candidate, coverage: Mapping[str, Any], risks: Mapping[str, Any]) -> dict[str, Any]:
    if candidate is None:
        return {
            "reading_quality": "No chapter candidate was produced.",
            "thematic_organization": "n/a",
            "passages_to_examine": "n/a",
            "uncertain_references": "UNC029 Isaiah 26 versus 28 remains unresolved.",
            "possible_omissions": "entire chapter",
            "interpretive_transitions": "n/a",
        }
    missing = list(coverage.get("important_missing") or [])
    flag_codes = [row.get("code") for row in risks.get("flags") or []]
    paragraphs = sum(len(section.paragraphs) for section in candidate.sections)
    return {
        "reading_quality": (
            f"{paragraphs} paragraphs across {len(candidate.sections)} sections. "
            "Offline readability only; not a fidelity certificate."
        ),
        "thematic_organization": (
            "Four EditorialPlan sections were requested: Bavardage Is Not Prayer, "
            "The Refreshing, He Told Me I Was Tired, Pouring on the Thirsty."
        ),
        "passages_to_examine": (
            "SEC048 refreshing / Isaiah material; SEC049 tiredness example; "
            "cross-recording grouping of AUDIO003 and AUDIO004."
        ),
        "uncertain_references": (
            "UNC029 Isaiah 26 versus 28; REF037 Jude v.20 partial; "
            "SEC048 references without shared SRC (REF044, REF047, REF037)."
        ),
        "possible_omissions": ", ".join(missing) if missing else "none flagged by the offline heuristic",
        "interpretive_transitions": (
            "INTERPRETIVE_TRANSITION" if "INTERPRETIVE_TRANSITION" in flag_codes else "none flagged"
        ),
    }


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
    except BookGeneration4217Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = snapshot(root=base)
    try:
        assert_canonical(before)
        inputs, index, language = load_canonical_corpus()
        chapter = chapter_from_plan(inputs.plan)
        evidence = build_ch012_evidence(
            inputs.plan,
            inputs.source_map,
            chapter,
            language=language,
            transcript_index=index,
        )
    except Exception as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        after = snapshot(root=base)
        bundle = {
            "header": {
                "result": "FAIL",
                "provider_calls": 0,
                "anthropic_http": 0,
                "openai_http": 0,
                "stop_reason": str(exc),
            },
            "canonical_hashes_pre": before,
            "canonical_hashes_post": after,
            "regression_tests": evaluate_offline_scenarios(root=base),
            "readiness": {
                "READY_FOR_HUMAN_CHAPTER_REVIEW": False,
                "READY_FOR_TERRA_VALIDATION": False,
                "READY_FOR_FULL_BOOK_GENERATION": False,
                "why": str(exc),
            },
        }
        bundle["report_text"] = render_report(bundle)
        if write_artifacts:
            write_phase_artifacts(bundle, root=base)
        result.bundle = redact_secrets(bundle)
        return result

    idea_count = len(assigned_idea_ids_for_chapter(chapter))
    section_count = len(chapter.sections)
    output_probe = reserve_budget(
        {
            "payload": {"system": "", "messages": [{"role": "user", "content": ""}]},
            "local_input_token_estimate": {"tokens": 0},
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
    context_manifest = chapter_context_manifest(
        inputs.plan, inputs.source_map, chapter, evidence
    )
    hydrated = hydrated_source_manifest(evidence)
    policy = editorial_policy()
    policy_snapshot = dict(policy)
    policy_snapshot["phase"] = PHASE
    policy_snapshot["used_for_isolated_ch012_only"] = True
    policy_snapshot["activated_in_production"] = False

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
    elif execute_real and not (allow_real_provider or engine is not None):
        blocked = True
        block_reason = "REAL_PROVIDER_NOT_ALLOWED"
    elif execute_real and engine is None and not credential_available():
        blocked = True
        block_reason = "MODEL_UNAVAILABLE"

    preflight = {
        "phase": PHASE,
        "authorization_scope": scope,
        "chapter_id": TARGET_CHAPTER_ID,
        "model": f"{PROVIDER} / {MODEL}",
        "prompt_version": PROMPT_VERSION,
        "canonical_hashes_ok": before["canonical_match_expected"],
        "sources_available": bool(hydrated.get("hydrated_count")),
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
        "historical_statuses": {
            "h01": HISTORICAL_H01_STATUS,
            "h02": HISTORICAL_H02_STATUS,
            "h11": HISTORICAL_H11_STATUS,
            "4B.2.10": HISTORICAL_4B210_STATUS,
            "4B.2.11": HISTORICAL_4B211_STATUS,
            "4B.2.12": HISTORICAL_4B212_STATUS,
            "4B.2.13": HISTORICAL_4B213_STATUS,
            "4B.2.14": HISTORICAL_4B214_STATUS,
            "4B.2.15": HISTORICAL_4B215_STATUS,
            "4B.2.16": HISTORICAL_4B216_STATUS,
        },
        "secrets_included": False,
    }

    request_hash = {
        "phase": PHASE,
        "algorithm": "sha256",
        "request_sha256": identity.get("request_sha256"),
        "request_sha256_repeat": identity.get("request_sha256_repeat"),
        "deterministic": identity.get("deterministic"),
        "model": identity.get("model"),
        "max_tokens": identity.get("max_tokens"),
        "prompt_version": PROMPT_VERSION,
        "chapter_id": TARGET_CHAPTER_ID,
        "http_sent": False,
        "secrets_included": False,
    }

    will_call = bool(execute_real and not blocked and not dry_run)
    if not will_call:
        after = snapshot(root=base)
        stop_reason = block_reason or ("DRY_RUN" if dry_run or not execute_real else "STOPPED_BEFORE_PROVIDER_CALL")
        header = _header(
            before=before,
            after=after,
            calls=0,
            anthropic_http=0,
            cost=cost,
            actual=None,
            structural=None,
            coverage=None,
            terra=None,
            tests=tests,
            stop_reason=stop_reason,
            result="FAIL" if blocked else "FAIL",
            authorization="BLOCKED" if blocked else "NOT_CONSUMED",
            json_valid=False,
            contract_valid=False,
        )
        if not execute_real and not blocked:
            header["result"] = "FAIL"
            header["stop_reason"] = "DRY_RUN_NO_PROVIDER_CALL"
        bundle = _offline_bundle(
            header=header,
            before=before,
            after=after,
            preflight=preflight,
            policy=policy_snapshot,
            prompt=prompt_snapshot,
            context=context_manifest,
            hydrated=hydrated,
            cost=cost,
            authorization=authorization_manifest(
                consumed=False,
                sha256=identity.get("request_sha256"),
                blocked=blocked,
                block_reason=block_reason,
            ),
            request_hash=request_hash,
            tests=tests,
            scenarios=scenarios,
            notes=stop_reason or "preflight only",
        )
        bundle["report_text"] = render_report(bundle)
        if write_artifacts:
            write_phase_artifacts(bundle, root=base)
        result.bundle = redact_secrets(bundle)
        result.error = block_reason or ""
        result.mode = "BLOCKED_PRECALL" if blocked else "DRY_RUN"
        result.accepted = not blocked
        return result

    if engine is None:
        try:
            engine = build_real_engine()
        except BookGeneration4217Error as exc:
            result.error = str(exc)
            result.mode = "REJECTED"
            after = snapshot(root=base)
            header = _header(
                before=before,
                after=after,
                calls=0,
                anthropic_http=0,
                cost=cost,
                actual=None,
                structural=None,
                coverage=None,
                terra=None,
                tests=tests,
                stop_reason=str(exc),
                result="FAIL",
                authorization="NOT_CONSUMED",
                json_valid=False,
                contract_valid=False,
            )
            bundle = _offline_bundle(
                header=header,
                before=before,
                after=after,
                preflight=preflight,
                policy=policy_snapshot,
                prompt=prompt_snapshot,
                context=context_manifest,
                hydrated=hydrated,
                cost=cost,
                authorization=authorization_manifest(
                    consumed=False,
                    sha256=identity.get("request_sha256"),
                    blocked=True,
                    block_reason=str(exc),
                ),
                request_hash=request_hash,
                tests=tests,
                scenarios=scenarios,
                notes=str(exc),
            )
            bundle["report_text"] = render_report(bundle)
            if write_artifacts:
                write_phase_artifacts(bundle, root=base)
            result.bundle = redact_secrets(bundle)
            return result

    request = identity["ai_request"]
    guard = OneShotCallGuard(max_calls=1)
    consume_remote_lock(path=lock, phase=PHASE, scope=AUTHORIZATION_SCOPE)
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
                    if isinstance(raw_parsed, dict):
                        pass
                    else:
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
            coverage=None,
            terra=None,
            tests=tests,
            stop_reason="RESPONSE_UNCERTAIN_AFTER_SEND",
            result="FAIL",
            authorization="CONSUMED",
            json_valid=False,
            contract_valid=False,
        )
        bundle = _offline_bundle(
            header=header,
            before=before,
            after=after,
            preflight=preflight,
            policy=policy_snapshot,
            prompt=prompt_snapshot,
            context=context_manifest,
            hydrated=hydrated,
            cost=cost,
            authorization=authorization_manifest(
                consumed=True,
                sha256=identity.get("request_sha256"),
                blocked=False,
                block_reason="RESPONSE_UNCERTAIN_AFTER_SEND",
            ),
            request_hash={**request_hash, "http_sent": True},
            tests=tests,
            scenarios=scenarios,
            notes="KeyboardInterrupt after send. NO RETRY.",
        )
        bundle["report_text"] = render_report(bundle)
        if write_artifacts:
            write_phase_artifacts(bundle, root=base)
        result.bundle = redact_secrets(bundle)
        return result

    post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
    generate_attempts = int(getattr(engine, "generate_attempts", 0) or guard.generate_attempts)
    result.engine_generate_attempts = generate_attempts
    result.anthropic_post_attempts = post_attempts
    if post_attempts == 0 and generate_attempts and not describe_engine(engine).get("is_fake"):
        # Fake engines have no POST; real engines must have one if generate ran.
        if isinstance(engine, CountingAnthropicEngine) and response is None and not error_text:
            error_text = "RESPONSE_UNCERTAIN_AFTER_SEND"

    input_tokens = response_meta.get("input_tokens") or http_meta.get("input_tokens")
    output_tokens = response_meta.get("output_tokens") or http_meta.get("output_tokens")
    finish = response_meta.get("finish_reason") or http_meta.get("finish_reason")
    actual = actual_cost(input_tokens=input_tokens, output_tokens=output_tokens)
    if cost_record is not None and persist_usage:
        record_call(PROJECT_NAME, cost_record)

    interpreted = interpret_response(
        raw_parsed,
        plan=inputs.plan,
        source_map=inputs.source_map,
        chapter=chapter,
        language=language,
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
        plan=inputs.plan,
        chapter=chapter,
        allowed_handles=list(evidence.get("allowed") or []),
        other_chapter_ids=[
            item.chapter_id for item in inputs.plan.chapters if item.chapter_id != TARGET_CHAPTER_ID
        ],
    )
    coverage = assess_chapter_coverage(candidate=candidate, evidence=evidence)
    risks = editorial_risk_flags(candidate=candidate, evidence=evidence, coverage=coverage)
    terra = prepare_terra_manifest(candidate=candidate, structural=structural)
    after = snapshot(root=base)
    hashes_ok = snapshots_match(before, after) and after["canonical_match_expected"]
    checks = dict(structural.get("checks") or {})
    result_label = _classify(
        calls=max(post_attempts, generate_attempts),
        blocked=False,
        json_valid=bool(structural.get("json_valid")),
        contract_valid=bool(structural.get("chapter_contract_valid")),
        sections_ok=bool(checks.get("sections_match")),
        ideas_ok=not checks.get("ideas_missing_from_metadata"),
        hashes_ok=hashes_ok,
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

    header = _header(
        before=before,
        after=after,
        calls=max(post_attempts, generate_attempts),
        anthropic_http=post_attempts if isinstance(engine, CountingAnthropicEngine) else generate_attempts,
        cost=cost,
        actual=actual,
        structural=structural,
        coverage=coverage,
        terra=terra,
        tests=tests,
        stop_reason=stop_reason,
        result=result_label,
        authorization="CONSUMED",
        json_valid=bool(structural.get("json_valid")),
        contract_valid=bool(structural.get("chapter_contract_valid")),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        finish=finish,
    )
    anthropic_http = header["anthropic_http"]
    if describe_engine(engine).get("is_fake"):
        header["anthropic_http"] = 0
        anthropic_http = 0

    response_metadata = {
        "phase": PHASE,
        "http_success": http_success,
        "http_status": http_meta.get("http_status"),
        "finish_reason": finish,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": response_meta.get("thinking_tokens"),
        "request_id": http_meta.get("request_id") or response_meta.get("request_id"),
        "elapsed_ms": http_meta.get("elapsed_ms") or response_meta.get("latency_ms"),
        "raw_sha256": content_hash(raw_text) if raw_text else None,
        "error": error_text,
        "engine": describe_engine(engine),
        "usage": http_meta.get("usage") if isinstance(http_meta.get("usage"), dict) else {},
        "secrets_included": False,
    }
    candidate_payload = candidate.to_dict() if candidate is not None else None
    markdown = render_chapter_markdown(candidate, chapter)
    editorial = _editorial_summary(candidate=candidate, coverage=coverage, risks=risks)
    ready_human = result_label in {"PASS", "PARTIAL"} and candidate is not None
    bundle = {
        "header": header,
        "preflight": preflight,
        "canonical_hashes_pre": before,
        "editorial_policy_snapshot": policy_snapshot,
        "generator_prompt_snapshot": prompt_snapshot,
        "chapter_context_manifest": context_manifest,
        "hydrated_source_manifest": hydrated,
        "cost_preflight": cost,
        "provider_call_authorization": authorization_manifest(
            consumed=True,
            sha256=identity.get("request_sha256"),
            blocked=False,
            block_reason=None,
        ),
        "provider_request_hash": {**request_hash, "http_sent": True},
        "provider_response_metadata": response_metadata,
        "chapter_candidate": candidate_payload,
        "chapter_candidate_md": markdown,
        "structural_validation": structural,
        "source_coverage": coverage,
        "editorial_risk_flags": risks,
        "canonical_hashes_post": after,
        "regression_tests": tests,
        "offline_scenarios": scenarios,
        "terra_prep": terra,
        "editorial_summary": editorial,
        "isolated_cache": {
            "production_writes": isolated_cache.production_writes,
            "records": len(isolated_cache.records),
            "production_cache": "UNCHANGED",
        },
        "readiness": {
            "READY_FOR_HUMAN_CHAPTER_REVIEW": ready_human,
            "READY_FOR_TERRA_VALIDATION": False,
            "READY_FOR_FULL_BOOK_GENERATION": False,
            "book_json": "NOT PUBLISHED",
            "production_cache": "UNCHANGED",
            "NEXT_ACTION": "HUMAN REVIEW",
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
    bundle["header"]["ready_for_human_chapter_review"] = _yn(ready_human)
    bundle["header"]["ready_for_terra_validation"] = "NO"
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        write_phase_artifacts(bundle, root=base)
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
    coverage: Mapping[str, Any] | None,
    terra: Mapping[str, Any] | None,
    tests: Mapping[str, Any],
    stop_reason: str,
    result: str,
    authorization: str,
    json_valid: bool,
    contract_valid: bool,
    input_tokens: Any = None,
    output_tokens: Any = None,
    finish: Any = None,
) -> dict[str, Any]:
    checks = dict((structural or {}).get("checks") or {})
    coverage_line = "n/a"
    if coverage:
        by_kind = coverage.get("by_kind") or {}
        idea = by_kind.get("idea") or {}
        coverage_line = (
            f"identifier+heuristic ideas covered={idea.get('covered')} "
            f"identifier_only={idea.get('identifier_only')} "
            f"not_covered={idea.get('not_covered')} "
            "(not a semantic certificate)"
        )
    actual_display = "n/a"
    cost_source = "n/a"
    if actual:
        actual_display = actual.get("display") or actual.get("total_cost_usd")
        cost_source = actual.get("status") or "provider_usage"
    sections = (
        f"{EXPECTED_SECTION_COUNT} / {len(checks.get('sections_generated') or [])}"
        if structural
        else f"{EXPECTED_SECTION_COUNT} / 0"
    )
    ideas = (
        f"{len(checks.get('ideas_expected') or [])} / {len(checks.get('ideas_referenced') or [])}"
        if structural
        else "11 / 0"
    )
    return {
        "result": result,
        "provider_calls": calls,
        "anthropic_http": anthropic_http,
        "openai_http": 0,
        "model": f"{PROVIDER} / {MODEL}",
        "chapter": TARGET_CHAPTER_ID,
        "canonical_python": CANONICAL_PYTHON,
        "canonical_hashes_pre_post": (
            _hash_line("pre", before) + "; " + _hash_line("post", after)
        ),
        "editorial_policy": EDITORIAL_POLICY_VERSION,
        "generator_prompt": PROMPT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "real_call_authorization": authorization,
        "precall_maximum_cost": cost.get("theoretical_maximum_usd"),
        "real_cost": actual_display,
        "cost_source": cost_source,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "stop_reason": stop_reason,
        "chapter_json_valid": _yn(json_valid) if calls else "n/a",
        "chapter_contract_valid": _yn(contract_valid) if calls else "n/a",
        "sections_expected_generated": sections,
        "ideas_expected_referenced": ideas,
        "paragraphs_generated": checks.get("paragraphs_generated", 0 if calls else "n/a"),
        "source_coverage": coverage_line,
        "estimated_terra_calls": (terra or {}).get("estimated_terra_calls", "n/a"),
        "estimated_terra_cost": (terra or {}).get("estimated_terra_cost_usd", "n/a"),
        "ready_for_human_chapter_review": "NO",
        "ready_for_terra_validation": "NO",
        "tests_passed_failed": f"{tests.get('passed') or 0} / {tests.get('failed') or 0}",
        "finish_reason": finish,
        "historical_4b216": HISTORICAL_4B216_STATUS,
        "historical_4b215": HISTORICAL_4B215_STATUS,
    }


def _offline_bundle(
    *,
    header: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    preflight: dict[str, Any],
    policy: dict[str, Any],
    prompt: dict[str, Any],
    context: dict[str, Any],
    hydrated: dict[str, Any],
    cost: dict[str, Any],
    authorization: dict[str, Any],
    request_hash: dict[str, Any],
    tests: dict[str, Any],
    scenarios: dict[str, Any],
    notes: str,
) -> dict[str, Any]:
    return {
        "header": header,
        "preflight": preflight,
        "canonical_hashes_pre": before,
        "editorial_policy_snapshot": policy,
        "generator_prompt_snapshot": prompt,
        "chapter_context_manifest": context,
        "hydrated_source_manifest": hydrated,
        "cost_preflight": cost,
        "provider_call_authorization": authorization,
        "provider_request_hash": request_hash,
        "provider_response_metadata": {
            "phase": PHASE,
            "http_sent": False,
            "invented_response": False,
            "reason": notes,
            "secrets_included": False,
        },
        "chapter_candidate": None,
        "chapter_candidate_md": "# Prayer Corrected\n\n_No chapter candidate was produced._\n",
        "structural_validation": {
            "phase": PHASE,
            "status": "n/a",
            "reason": notes,
            "semantic_fidelity_validated": False,
        },
        "source_coverage": {
            "phase": PHASE,
            "status": "n/a",
            "reason": notes,
            "semantic_coverage_certified": False,
        },
        "editorial_risk_flags": {
            "phase": PHASE,
            "flags": [],
            "reason": notes,
            "semantic_fidelity_validated": False,
        },
        "canonical_hashes_post": after,
        "regression_tests": tests,
        "offline_scenarios": scenarios,
        "terra_prep": {
            "terra_calls_this_phase": 0,
            "estimated_terra_calls": "UNKNOWN",
            "estimated_terra_cost_usd": "UNKNOWN",
        },
        "editorial_summary": _editorial_summary(candidate=None, coverage={}, risks={}),
        "readiness": {
            "READY_FOR_HUMAN_CHAPTER_REVIEW": False,
            "READY_FOR_TERRA_VALIDATION": False,
            "READY_FOR_FULL_BOOK_GENERATION": False,
            "book_json": "NOT PUBLISHED",
            "production_cache": "UNCHANGED",
            "NEXT_ACTION": "HUMAN REVIEW",
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
