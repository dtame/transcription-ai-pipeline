"""
Runner Phase 4B.2.23.

Preflight, hashes, CH012/CH018 integrity, BATCH-01 hydration, cost bound,
then at most one Anthropic call per chapter and four calls for the lot.
No retry. No fallback. No Terra. No publication. No BATCH-02.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from decimal import Decimal
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
from app.book_generation_4b223.authorization import authorization_manifest
from app.book_generation_4b223.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_CHAPTER_IDS,
    BATCH_ID,
    BUDGET_CAP_USD,
    CANARY_WINDOW_ID,
    CANONICAL_PYTHON,
    LOCK_RESUME_WITHOUT_RECALL,
    LOCK_STATE_FAILED,
    LOCK_STATE_MAY_HAVE_BEEN_SENT,
    LOCK_STATE_PREFLIGHT,
    LOCK_STATE_RESPONSE_RECEIVED,
    LOCK_STATE_RESPONSE_VALIDATED,
    LOCK_STATE_UNCERTAIN,
    LOCK_STOP_STATES,
    MODEL,
    NEXT_ACTION,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    STAGE_CANARY,
)
from app.book_generation_4b223.context import (
    build_chapter_context,
    load_corpus,
    source_context_manifest,
)
from app.book_generation_4b223.costing import actual_cost, remaining_budget, reserve_chapter_budget
from app.book_generation_4b223.editorial import editorial_readiness_review
from app.book_generation_4b223.engine import (
    CountingAnthropicEngine,
    build_real_engine,
    credential_available,
    describe_engine,
)
from app.book_generation_4b223.guard import (
    BatchCallGuard,
    BookGeneration4223Error,
    OneShotCallGuard,
    assert_no_publication,
    validate_authorization_scope,
)
from app.book_generation_4b223.hashes import (
    assert_canonical,
    assert_ch012_unchanged,
    assert_ch018_unchanged,
    snapshot,
    snapshots_match,
)
from app.book_generation_4b223.inventory import ChapterSpec, chapter_from_plan, load_batch01_specs
from app.book_generation_4b223.ledger import empty_ledger, update_ledger
from app.book_generation_4b223.lock import (
    lock_already_consumed,
    persist_preflight,
    read_lock,
    reserve_call,
    transition_lock,
)
from app.book_generation_4b223.paths import (
    batch_lock_path,
    forensic_root,
    lock_path,
    production_book_path,
    repo_root,
    venv_python_path,
)
from app.book_generation_4b223.report import render_report
from app.book_generation_4b223.request import request_identity
from app.book_generation_4b223.scenarios import evaluate_offline_scenarios
from app.book_generation_4b223.traceability import (
    ex_ref_traceability_review,
    idea_traceability_review,
)
from app.book_generation_4b223.validation import (
    interpret_response,
    render_chapter_markdown,
    structural_validation,
)
from app.book_generation_4b223.writer import write_batch_artifacts, write_chapter_artifacts
from app.file_utils import content_hash
from app.source_analysis.errors import MaxRealCallsExceededError


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _run_focused_tests(*, root: Path) -> dict[str, Any]:
    tests = [
        "app/tests/test_book_generation_4b223.py",
        "app/tests/test_book_batch_preparation_4b222.py",
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


def _money(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(value)


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    engine_generate_attempts: int = 0
    anthropic_post_attempts: int = 0


def _classify_batch(
    *,
    calls: int,
    blocked: bool,
    chapters_generated: int,
    hashes_ok: bool,
    accepted_ok: bool,
    test_failures: int,
    stop_reason: str | None,
) -> str:
    if blocked and calls == 0:
        return "BLOCKED"
    if calls == 0:
        return "FAIL"
    if not hashes_ok or not accepted_ok:
        return "FAIL"
    if chapters_generated == 4 and not test_failures and not stop_reason:
        return "PASS"
    if chapters_generated == 4 and not stop_reason:
        return "PASS" if not test_failures else "PARTIAL"
    if chapters_generated:
        return "PARTIAL"
    return "FAIL"


def _prepare_chapter(
    *,
    spec: ChapterSpec,
    corpus,
    remaining: Decimal,
) -> dict[str, Any]:
    chapter = chapter_from_plan(corpus.plan, spec.chapter_id)
    built = build_chapter_context(spec, corpus=corpus)
    evidence = built["evidence"]
    idea_count = len(evidence.get("ideas") or [])
    section_count = len(evidence.get("sections") or [])
    output_probe = reserve_chapter_budget(
        {
            "payload": {"system": "", "messages": [{"role": "user", "content": ""}]},
            "local_input_token_estimate": {"tokens": 0},
            "thinking_mode": "disabled",
        },
        chapter_id=spec.chapter_id,
        idea_count=idea_count,
        section_count=section_count,
        remaining_budget=remaining,
    )
    max_output = int(output_probe["max_output_tokens"])
    identity = request_identity(
        evidence, chapter_id=spec.chapter_id, max_output_tokens=max_output
    )
    cost = reserve_chapter_budget(
        identity,
        chapter_id=spec.chapter_id,
        idea_count=idea_count,
        section_count=section_count,
        remaining_budget=remaining,
    )
    max_output = int(cost["max_output_tokens"])
    identity = request_identity(
        evidence, chapter_id=spec.chapter_id, max_output_tokens=max_output
    )
    cost = reserve_chapter_budget(
        identity,
        chapter_id=spec.chapter_id,
        idea_count=idea_count,
        section_count=section_count,
        remaining_budget=remaining,
    )
    return {
        "spec": spec,
        "chapter": chapter,
        "built": built,
        "evidence": evidence,
        "identity": identity,
        "cost": cost,
        "context_manifest": source_context_manifest(built, spec),
        "max_output": int(cost["max_output_tokens"]),
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
    except BookGeneration4223Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = snapshot(root=base)
    try:
        assert_canonical(before)
        assert_ch012_unchanged(before)
        assert_ch018_unchanged(before)
        corpus = load_corpus()
        batch_specs = load_batch01_specs(corpus=corpus, root=base)
    except Exception as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        after = snapshot(root=base)
        bundle = _blocked_bundle(
            before=before,
            after=after,
            tests={"passed": 0, "failed": 0},
            stop_reason=str(exc),
            result_label="BLOCKED",
        )
        if write_artifacts:
            write_batch_artifacts(bundle, root=base)
        result.bundle = redact_secrets(bundle)
        return result

    prepared: dict[str, dict[str, Any]] = {}
    lot_max = Decimal("0")
    try:
        for chapter_id in AUTHORIZED_CHAPTER_IDS:
            spec = batch_specs["specs"][chapter_id]
            prepared[chapter_id] = _prepare_chapter(
                spec=spec,
                corpus=corpus,
                remaining=BUDGET_CAP_USD,
            )
            theoretical = Decimal(
                str(prepared[chapter_id]["cost"]["theoretical_maximum_decimal"])
            )
            lot_max += theoretical
    except Exception as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        after = snapshot(root=base)
        bundle = _blocked_bundle(
            before=before,
            after=after,
            tests={"passed": 0, "failed": 0},
            stop_reason=str(exc),
            result_label="BLOCKED",
        )
        if write_artifacts:
            write_batch_artifacts(bundle, root=base)
        result.bundle = redact_secrets(bundle)
        return result

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

    batch_lock = batch_lock_path(root=base)
    blocked = False
    block_reason = None
    if lot_max > BUDGET_CAP_USD:
        blocked = True
        block_reason = "COST_MAXIMUM_EXCEEDS_CAP"
    elif any(item["cost"].get("blocked") for item in prepared.values()):
        blocked = True
        block_reason = next(
            item["cost"].get("block_reason")
            for item in prepared.values()
            if item["cost"].get("blocked")
        )
    elif any(not item["identity"].get("deterministic") for item in prepared.values()):
        blocked = True
        block_reason = "REQUEST_NOT_DETERMINISTIC"
    elif any(item["identity"].get("model") != MODEL for item in prepared.values()):
        blocked = True
        block_reason = "MODEL_UNAVAILABLE"
    elif any(item["context_manifest"].get("context_truncated") for item in prepared.values()):
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
    elif lock_already_consumed(batch_lock) and read_lock(batch_lock) and str(
        (read_lock(batch_lock) or {}).get("state") or ""
    ) in LOCK_STOP_STATES:
        blocked = True
        block_reason = "BATCH_LOCK_ALREADY_CONSUMED"

    if not lock_already_consumed(batch_lock):
        persist_preflight(batch_lock)

    first_prompt = (next(iter(prepared.values()))["identity"].get("prompt_snapshot") or {})
    preflight = {
        "phase": PHASE,
        "authorization_scope": scope,
        "batch_id": BATCH_ID,
        "chapter_ids": list(AUTHORIZED_CHAPTER_IDS),
        "model": f"{PROVIDER}/{MODEL}",
        "prompt_version": PROMPT_VERSION,
        "canonical_hashes_ok": before["canonical_match_expected"],
        "ch012_unchanged": before["ch012_unchanged"],
        "ch018_unchanged": before["ch018_unchanged"],
        "lot_theoretical_maximum_usd": float(lot_max),
        "authorized_cap_usd": float(BUDGET_CAP_USD),
        "lot_within_cap": lot_max <= BUDGET_CAP_USD,
        "faithful_prompt_isolated": first_prompt.get("registered_in_prompt_select") is False,
        "historical_prompt_unmodified": True,
        "production_cache_write": False,
        "production_book_absent": True,
        "single_call_per_chapter": True,
        "retries": 0,
        "fallbacks": 0,
        "blocked": blocked,
        "block_reason": block_reason,
        "execute_real_requested": bool(execute_real),
        "dry_run": bool(dry_run or not execute_real),
        "secrets_included": False,
    }

    ledger = empty_ledger()
    for chapter_id, item in prepared.items():
        ledger = update_ledger(
            ledger,
            chapter_id=chapter_id,
            status="PREFLIGHT_VALIDATED",
            theoretical_maximum_usd=item["cost"].get("theoretical_maximum_usd"),
        )
        chapter_lock = lock_path(chapter_id, root=base)
        if not lock_already_consumed(chapter_lock):
            persist_preflight(chapter_lock, chapter_id=chapter_id)
        if write_artifacts:
            write_chapter_artifacts(
                chapter_id,
                {
                    "preflight": {
                        "phase": PHASE,
                        "chapter_id": chapter_id,
                        "title": item["spec"].title,
                        "model": f"{PROVIDER}/{MODEL}",
                        "prompt_version": PROMPT_VERSION,
                        "prompt_sha256": (item["identity"].get("prompt_snapshot") or {}).get(
                            "prompt_sha256"
                        ),
                        "blocked": blocked,
                        "block_reason": block_reason,
                    },
                    "prompt_manifest": item["identity"].get("prompt_snapshot"),
                    "source_context_manifest": item["context_manifest"],
                    "cost_preflight": item["cost"],
                    "readiness": {
                        "READY_FOR_HUMAN_REVIEW": False,
                        "chapter_id": chapter_id,
                        "why": block_reason or "preflight",
                    },
                },
                root=base,
                call_completed=False,
            )

    will_call = bool(execute_real and not blocked and not dry_run)
    if not will_call:
        after = snapshot(root=base)
        stop_reason = block_reason or (
            "DRY_RUN" if dry_run or not execute_real else "STOPPED_BEFORE_PROVIDER_CALL"
        )
        bundle = _final_bundle(
            before=before,
            after=after,
            tests=tests,
            scenarios=scenarios,
            ledger=ledger,
            prepared=prepared,
            chapter_results=[],
            isolated_cache=isolated_cache,
            calls=0,
            anthropic_http=0,
            stop_reason=stop_reason,
            result_label="BLOCKED" if blocked else "FAIL",
            lot_max=lot_max,
        )
        if write_artifacts:
            write_batch_artifacts(bundle, root=base)
        result.bundle = redact_secrets(bundle)
        result.error = block_reason or ""
        result.mode = "BLOCKED_PRECALL" if blocked else "DRY_RUN"
        result.accepted = not blocked
        return result

    batch_guard = BatchCallGuard(max_calls=4)
    chapter_results: list[dict[str, Any]] = []
    shared_engine = engine
    stop_reason = None

    for chapter_id in AUTHORIZED_CHAPTER_IDS:
        item = prepared[chapter_id]
        spec = item["spec"]
        chapter_lock = lock_path(chapter_id, root=base)
        existing = read_lock(chapter_lock) or {}
        existing_state = str(existing.get("state") or "")
        if existing_state in LOCK_RESUME_WITHOUT_RECALL:
            chapter_results.append(
                {
                    "chapter_id": chapter_id,
                    "status": "RESUME_SKIPPED_ALREADY_VALIDATED",
                    "cost": "n/a",
                    "structural": "PASS",
                    "ideas_missing": [],
                    "src_invalid": [],
                    "editorial": "n/a",
                    "notes": "lock already RESPONSE_VALIDATED; no second call",
                    "provider_calls": 0,
                    "anthropic_http": 0,
                }
            )
            continue
        if existing_state in LOCK_STOP_STATES:
            stop_reason = f"{chapter_id}_LOCK_{existing_state}"
            break

        remaining = remaining_budget(
            accumulated_actual=Decimal(str(ledger["accumulated_actual_usd"])),
            reserved_or_uncertain=Decimal(str(ledger["reserved_or_uncertain_usd"])),
        )
        live = _prepare_chapter(spec=spec, corpus=corpus, remaining=remaining)
        item.update(live)
        prompt_hash = (live["identity"].get("prompt_snapshot") or {}).get("prompt_sha256")
        if prompt_hash != first_prompt.get("prompt_sha256"):
            stop_reason = "PROMPT_HASH_DIVERGED"
            break
        if live["identity"].get("model") != MODEL:
            stop_reason = "MODEL_UNAVAILABLE"
            break
        if live["cost"].get("blocked"):
            stop_reason = str(live["cost"].get("block_reason") or "COST_BLOCK")
            break
        if live["context_manifest"].get("context_truncated"):
            stop_reason = "SOURCE_CONTEXT_TRUNCATED"
            break

        chapter_engine = shared_engine
        if chapter_engine is None:
            try:
                chapter_engine = build_real_engine()
            except BookGeneration4223Error as exc:
                stop_reason = str(exc)
                break

        request = live["identity"]["ai_request"]
        guard = OneShotCallGuard(max_calls=1)
        identity_hash = str(live["identity"].get("request_sha256") or "")
        reserve_call(chapter_lock, request_sha256=identity_hash, chapter_id=chapter_id)
        ledger = update_ledger(
            ledger,
            chapter_id=chapter_id,
            status="CALL_RESERVED",
            theoretical_maximum_usd=live["cost"].get("theoretical_maximum_usd"),
        )
        forensic_dir = forensic_root(chapter_id, root=base)
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
        transition_lock(
            chapter_lock,
            state=LOCK_STATE_MAY_HAVE_BEEN_SENT,
            chapter_id=chapter_id,
            request_sha256=identity_hash,
            note="Generate started. If interrupted, treat authorization as consumed.",
            extra={"http_sent": True},
        )
        ledger = update_ledger(
            ledger,
            chapter_id=chapter_id,
            status="CALL_MAY_HAVE_BEEN_SENT",
            theoretical_maximum_usd=live["cost"].get("theoretical_maximum_usd"),
        )

        try:
            with provider_forensic_scope(
                windows_root=forensic_dir,
                window_id=f"{CANARY_WINDOW_ID}_{chapter_id}",
                analysis_signature=identity_hash,
                provider=PROVIDER,
                model=MODEL,
            ):
                try:
                    batch_guard.register()
                    response = guard.guarded_generate(chapter_engine, request)
                except KeyboardInterrupt:
                    persist_interrupt_forensics()
                    raise
                except AIStructuredOutputError as exc:
                    persist_structured_output_forensics(
                        error=exc,
                        windows_root=forensic_dir,
                        window_id=f"{CANARY_WINDOW_ID}_{chapter_id}",
                        analysis_signature=identity_hash,
                        provider=getattr(getattr(exc, "response", None), "provider", None),
                        model=getattr(getattr(exc, "response", None), "model", None) or MODEL,
                        stage=f"{STAGE_CANARY}_{chapter_id.lower()}",
                    )
                    persist_error_forensics(
                        exc,
                        windows_root=forensic_dir,
                        window_id=f"{CANARY_WINDOW_ID}_{chapter_id}",
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
                        window_id=f"{CANARY_WINDOW_ID}_{chapter_id}",
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
                        cost_record = tracker.record_response(
                            response, stage=f"{STAGE_CANARY}_{chapter_id.lower()}"
                        )
        except KeyboardInterrupt:
            transition_lock(
                chapter_lock,
                state=LOCK_STATE_UNCERTAIN,
                chapter_id=chapter_id,
                note="KeyboardInterrupt after reservation. NO RETRY.",
            )
            ledger = update_ledger(
                ledger,
                chapter_id=chapter_id,
                status="UNCERTAIN",
                theoretical_maximum_usd=live["cost"].get("theoretical_maximum_usd"),
            )
            result.error = "KeyboardInterrupt after authorization consumed. NO RETRY."
            result.mode = "INTERRUPTED"
            stop_reason = "RESPONSE_UNCERTAIN_AFTER_SEND"
            chapter_results.append(
                {
                    "chapter_id": chapter_id,
                    "status": "UNCERTAIN",
                    "cost": "UNCERTAIN",
                    "structural": "FAIL",
                    "ideas_missing": "n/a",
                    "src_invalid": "n/a",
                    "editorial": "UNDETERMINED",
                    "notes": "KeyboardInterrupt after send. NO RETRY.",
                    "provider_calls": 1,
                    "anthropic_http": int(getattr(chapter_engine, "post_attempts", 0) or 0),
                }
            )
            break

        post_attempts = int(getattr(chapter_engine, "post_attempts", 0) or 0)
        generate_attempts = int(
            getattr(chapter_engine, "generate_attempts", 0) or guard.generate_attempts
        )
        result.engine_generate_attempts += generate_attempts
        result.anthropic_post_attempts += post_attempts
        if describe_engine(chapter_engine).get("is_fake"):
            post_attempts = 0

        input_tokens = response_meta.get("input_tokens") or http_meta.get("input_tokens")
        output_tokens = response_meta.get("output_tokens") or http_meta.get("output_tokens")
        thinking_tokens = response_meta.get("thinking_tokens") or http_meta.get(
            "thinking_tokens"
        )
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
                chapter_lock,
                state=LOCK_STATE_RESPONSE_RECEIVED,
                chapter_id=chapter_id,
                note="Provider response received.",
                extra={"http_sent": True, "finish_reason": finish},
            )
        elif error_text:
            transition_lock(
                chapter_lock,
                state=LOCK_STATE_FAILED,
                chapter_id=chapter_id,
                note=error_text,
                extra={"http_sent": True},
            )

        interpreted = interpret_response(
            raw_parsed,
            plan=corpus.plan,
            source_map=corpus.source_map,
            chapter=live["chapter"],
            language=corpus.language,
            allowed_handles=list(live["evidence"].get("allowed") or []),
            provider_raw_sha256=content_hash(raw_text) if raw_text else "",
        )
        candidate = interpreted.get("candidate")
        if candidate is not None:
            isolated_cache.store(
                str(live["identity"].get("request_sha256") or chapter_id),
                {"chapter_id": chapter_id, "isolated": True},
            )
        structural = structural_validation(
            interpreted=interpreted,
            plan=corpus.plan,
            chapter=live["chapter"],
            spec=spec,
            allowed_handles=list(live["evidence"].get("allowed") or []),
            other_chapter_ids=[
                item.chapter_id
                for item in corpus.plan.chapters
                if item.chapter_id != chapter_id
            ],
            finish_reason=finish,
            max_output_tokens=live["max_output"],
        )
        candidate_payload = candidate.to_dict() if candidate is not None else None
        idea = idea_traceability_review(
            spec=spec,
            candidate_payload=candidate_payload,
            raw_parsed=raw_parsed,
            structural=structural,
            allowed_handles=list(live["evidence"].get("allowed") or []),
        )
        ex_ref = ex_ref_traceability_review(
            spec=spec,
            candidate_payload=candidate_payload,
            raw_parsed=raw_parsed,
            allowed_handles=list(live["evidence"].get("allowed") or []),
        )
        editorial = editorial_readiness_review(
            candidate=candidate,
            chapter=live["chapter"],
            spec=spec,
            structural=structural,
        )

        checks = dict(structural.get("checks") or {})
        blocking = False
        chapter_stop = None
        if actual.get("status") == "UNKNOWN" or actual.get("display") == "UNKNOWN":
            blocking = True
            chapter_stop = "COST_UNKNOWN"
        theoretical = Decimal(str(live["cost"].get("theoretical_maximum_decimal") or "0"))
        actual_total = actual.get("total_cost_usd")
        if actual_total is not None and Decimal(str(actual_total)) > theoretical:
            blocking = True
            chapter_stop = "ACTUAL_COST_EXCEEDS_THEORETICAL_MAXIMUM"
        if not structural.get("json_valid"):
            blocking = True
            chapter_stop = chapter_stop or "INVALID_JSON"
        if not structural.get("chapter_contract_valid"):
            blocking = True
            chapter_stop = chapter_stop or "INVALID_CONTRACT"
        if checks.get("ideas_missing_from_paras_e"):
            blocking = True
            chapter_stop = chapter_stop or "UNTRACED_REQUIRED_IDEAS"
        if checks.get("ideas_invented"):
            blocking = True
            chapter_stop = chapter_stop or "INVALID_PROVENANCE"
        if checks.get("invalid_src"):
            blocking = True
            chapter_stop = chapter_stop or "INVALID_SRC"
        if checks.get("detectable_truncation"):
            blocking = True
            chapter_stop = chapter_stop or "TRUNCATED_RESPONSE"
        if error_text and raw_parsed is None:
            blocking = True
            chapter_stop = chapter_stop or "PROVIDER_ERROR"
        if editorial.get("blocking_substantive_issue_established"):
            blocking = True
            chapter_stop = chapter_stop or "SUBSTANTIVE_EDITORIAL_ISSUE"

        if blocking and chapter_stop == "COST_UNKNOWN":
            ledger = update_ledger(
                ledger,
                chapter_id=chapter_id,
                status="UNCERTAIN",
                theoretical_maximum_usd=live["cost"].get("theoretical_maximum_usd"),
                actual=actual,
            )
            transition_lock(
                chapter_lock,
                state=LOCK_STATE_UNCERTAIN,
                chapter_id=chapter_id,
                note=chapter_stop,
            )
        elif blocking:
            ledger = update_ledger(
                ledger,
                chapter_id=chapter_id,
                status="FAILED",
                theoretical_maximum_usd=live["cost"].get("theoretical_maximum_usd"),
                actual=actual,
            )
            transition_lock(
                chapter_lock,
                state=LOCK_STATE_FAILED,
                chapter_id=chapter_id,
                note=chapter_stop or error_text or "chapter failed",
            )
        else:
            ledger = update_ledger(
                ledger,
                chapter_id=chapter_id,
                status="RESPONSE_VALIDATED",
                theoretical_maximum_usd=live["cost"].get("theoretical_maximum_usd"),
                actual=actual,
            )
            transition_lock(
                chapter_lock,
                state=LOCK_STATE_RESPONSE_VALIDATED,
                chapter_id=chapter_id,
                note="Response structurally validated.",
            )

        markdown = render_chapter_markdown(candidate, live["chapter"]) if candidate is not None else None
        chapter_bundle = {
            "preflight": {
                "phase": PHASE,
                "chapter_id": chapter_id,
                "title": spec.title,
                "model": f"{PROVIDER}/{MODEL}",
                "prompt_version": PROMPT_VERSION,
                "blocked": blocking,
                "block_reason": chapter_stop,
            },
            "prompt_manifest": live["identity"].get("prompt_snapshot"),
            "source_context_manifest": live["context_manifest"],
            "cost_preflight": live["cost"],
            "provider_response_raw": {
                "phase": PHASE,
                "chapter_id": chapter_id,
                "http_success": http_success,
                "finish_reason": finish,
                "parsed": raw_parsed,
                "raw_sha256": content_hash(raw_text) if raw_text else None,
                "raw_chars": len(raw_text) if raw_text else 0,
                "error": error_text,
                "invented_response": False,
                "secrets_included": False,
            },
            "provider_usage": {
                "phase": PHASE,
                "chapter_id": chapter_id,
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
                "engine": describe_engine(chapter_engine),
                "usage": http_meta.get("usage") if isinstance(http_meta.get("usage"), dict) else {},
                "secrets_included": False,
            },
            "chapter_candidate": candidate_payload,
            "chapter_candidate_md": markdown,
            "structural_validation": structural,
            "idea_traceability_review": idea,
            "ex_ref_traceability_review": ex_ref,
            "editorial_readiness_review": editorial,
            "readiness": {
                "READY_FOR_HUMAN_REVIEW": candidate is not None and not blocking,
                "chapter_id": chapter_id,
                "why": chapter_stop or "ONE_REAL_CALL_COMPLETED",
            },
        }
        if write_artifacts:
            write_chapter_artifacts(
                chapter_id, chapter_bundle, root=base, call_completed=True
            )
        chapter_results.append(
            {
                "chapter_id": chapter_id,
                "status": "GENERATED" if not blocking else (chapter_stop or "FAILED"),
                "cost": actual.get("display") or actual.get("total_cost_usd") or "UNKNOWN",
                "structural": structural.get("status"),
                "ideas_missing": list(idea.get("ideas_missing_from_paras_e") or []),
                "src_invalid": list(idea.get("src_handles_invalid") or []),
                "editorial": editorial.get("overall_classification"),
                "notes": chapter_stop or error_text or "",
                "provider_calls": max(generate_attempts, 1),
                "anthropic_http": post_attempts if not describe_engine(chapter_engine).get("is_fake") else 0,
                "bundle": chapter_bundle,
                "blocking": blocking,
            }
        )
        if blocking:
            stop_reason = chapter_stop
            break

    after = snapshot(root=base)
    hashes_ok = snapshots_match(before, after) and after["canonical_match_expected"]
    accepted_ok = bool(after.get("ch012_unchanged")) and bool(after.get("ch018_unchanged"))
    generated = [
        row["chapter_id"]
        for row in chapter_results
        if row.get("status") == "GENERATED"
    ]
    attempted = [row["chapter_id"] for row in chapter_results]
    calls = sum(int(row.get("provider_calls") or 0) for row in chapter_results)
    anthropic_http = sum(int(row.get("anthropic_http") or 0) for row in chapter_results)
    if stop_reason is None and len(generated) == 4:
        stop_reason = "BATCH01_COMPLETED"
        result_label = "PASS"
        if int(tests.get("failed") or 0):
            result_label = "PARTIAL"
    else:
        result_label = _classify_batch(
            calls=calls,
            blocked=False,
            chapters_generated=len(generated),
            hashes_ok=hashes_ok,
            accepted_ok=accepted_ok,
            test_failures=int(tests.get("failed") or 0),
            stop_reason=None if stop_reason == "BATCH01_COMPLETED" else stop_reason,
        )
        if stop_reason is None:
            stop_reason = "BATCH_STOPPED"
    if result_label == "PASS" and stop_reason == "BATCH01_COMPLETED":
        transition_lock(
            batch_lock,
            state=LOCK_STATE_RESPONSE_VALIDATED,
            note="BATCH-01 structurally completed.",
        )
    elif calls:
        transition_lock(
            batch_lock,
            state=LOCK_STATE_FAILED if result_label == "FAIL" else LOCK_STATE_RESPONSE_RECEIVED,
            note=stop_reason or "batch stopped",
        )

    bundle = _final_bundle(
        before=before,
        after=after,
        tests=tests,
        scenarios=scenarios,
        ledger=ledger,
        prepared=prepared,
        chapter_results=chapter_results,
        isolated_cache=isolated_cache,
        calls=calls,
        anthropic_http=anthropic_http,
        stop_reason=stop_reason or "STOPPED",
        result_label=result_label,
        lot_max=lot_max,
    )
    if write_artifacts:
        write_batch_artifacts(bundle, root=base)
    result.bundle = redact_secrets(bundle)
    result.accepted = result_label in {"PASS", "PARTIAL"}
    result.mode = result_label
    result.error = "" if result_label == "PASS" else (stop_reason or "")
    return result


def _blocked_bundle(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    tests: Mapping[str, Any],
    stop_reason: str,
    result_label: str,
) -> dict[str, Any]:
    header = {
        "result": result_label,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "batch": BATCH_ID,
        "chapters_attempted": [],
        "chapters_generated": [],
        "chapters_not_generated": list(AUTHORIZED_CHAPTER_IDS),
        "provider_calls": 0,
        "anthropic_http": 0,
        "openai_http": 0,
        "model": f"{PROVIDER}/{MODEL}",
        "prompt": PROMPT_VERSION,
        "prompt_hash": None,
        "preflight_max_cost": None,
        "actual_cost_by_chapter": {},
        "actual_total_cost": "n/a",
        "reserved_or_uncertain_cost": "n/a",
        "remaining_budget": str(BUDGET_CAP_USD),
        "retries": 0,
        "fallbacks": 0,
        "structural_by_chapter": {},
        "idea_coverage_by_chapter": {},
        "src_validation_by_chapter": {},
        "ex_ref_traceability": "n/a",
        "authorial_voice_review": "n/a",
        "potential_substantive_issues": 0,
        "canonical_hashes_pre_post": _hash_line("pre", before) + "; " + _hash_line("post", after),
        "ch012_unchanged": _yn(bool(after.get("ch012_unchanged"))),
        "ch018_unchanged": _yn(bool(after.get("ch018_unchanged"))),
        "production_cache": "UNCHANGED",
        "ready_for_human_review": "NO",
        "next_action": NEXT_ACTION,
        "canonical_python": CANONICAL_PYTHON,
        "stop_reason": stop_reason,
    }
    bundle = {
        "header": header,
        "canonical_hashes_pre": before,
        "canonical_hashes_post": after,
        "authorization_scope": authorization_manifest(
            consumed_calls=0,
            sha256=None,
            blocked=True,
            block_reason=stop_reason,
        ),
        "batch_budget_ledger": empty_ledger(),
        "batch_progress": {
            "phase": PHASE,
            "batch_id": BATCH_ID,
            "state": "BLOCKED",
            "chapters": list(AUTHORIZED_CHAPTER_IDS),
        },
        "batch_summary": {"result": result_label, "stop_reason": stop_reason},
        "batch_manifest": {
            "phase": PHASE,
            "batch_id": BATCH_ID,
            "chapters": list(AUTHORIZED_CHAPTER_IDS),
        },
        "regression_tests": tests,
        "readiness": {
            "READY_FOR_HUMAN_REVIEW": False,
            "READY_FOR_BATCH02": False,
            "book_json": "NOT PUBLISHED",
            "production_cache": "UNCHANGED",
            "SEMANTIC_CERTIFICATION": "NOT PERFORMED",
            "HUMAN_EDITORIAL_ACCEPTANCE": "PENDING",
            "NEXT_ACTION": NEXT_ACTION,
            "why": stop_reason,
        },
        "chapter_rows": [],
    }
    bundle["report_text"] = render_report(bundle)
    return bundle


def _final_bundle(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    tests: Mapping[str, Any],
    scenarios: Mapping[str, Any],
    ledger: Mapping[str, Any],
    prepared: Mapping[str, Any],
    chapter_results: list[dict[str, Any]],
    isolated_cache: IsolatedChapterCache,
    calls: int,
    anthropic_http: int,
    stop_reason: str,
    result_label: str,
    lot_max: Decimal,
) -> dict[str, Any]:
    generated = [
        row["chapter_id"] for row in chapter_results if row.get("status") == "GENERATED"
    ]
    attempted = [row["chapter_id"] for row in chapter_results]
    not_generated = [
        chapter_id for chapter_id in AUTHORIZED_CHAPTER_IDS if chapter_id not in generated
    ]
    actual_by_chapter = {
        row["chapter_id"]: row.get("cost") for row in chapter_results
    }
    structural_by = {
        row["chapter_id"]: row.get("structural") for row in chapter_results
    }
    idea_by = {
        row["chapter_id"]: {
            "missing": row.get("ideas_missing"),
        }
        for row in chapter_results
    }
    src_by = {row["chapter_id"]: row.get("src_invalid") for row in chapter_results}
    voice_by = {row["chapter_id"]: row.get("editorial") for row in chapter_results}
    potential = 0
    for row in chapter_results:
        bundle = row.get("bundle") or {}
        editorial = bundle.get("editorial_readiness_review") or {}
        potential += len(editorial.get("potential_substantive_issues") or [])
    first_prompt = None
    if prepared:
        first_prompt = (
            next(iter(prepared.values())).get("identity", {}).get("prompt_snapshot") or {}
        )
    ready = bool(generated)
    header = {
        "result": result_label,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "batch": BATCH_ID,
        "chapters_attempted": attempted,
        "chapters_generated": generated,
        "chapters_not_generated": not_generated,
        "provider_calls": calls,
        "anthropic_http": anthropic_http,
        "openai_http": 0,
        "model": f"{PROVIDER}/{MODEL}",
        "prompt": PROMPT_VERSION,
        "prompt_hash": (first_prompt or {}).get("prompt_sha256"),
        "preflight_max_cost": float(lot_max),
        "actual_cost_by_chapter": actual_by_chapter,
        "actual_total_cost": ledger.get("accumulated_actual_usd"),
        "reserved_or_uncertain_cost": ledger.get("reserved_or_uncertain_usd"),
        "remaining_budget": ledger.get("remaining_budget_usd"),
        "retries": 0,
        "fallbacks": 0,
        "structural_by_chapter": structural_by,
        "idea_coverage_by_chapter": idea_by,
        "src_validation_by_chapter": src_by,
        "ex_ref_traceability": "documented_without_auto_omission",
        "authorial_voice_review": voice_by,
        "potential_substantive_issues": potential,
        "canonical_hashes_pre_post": _hash_line("pre", before)
        + "; "
        + _hash_line("post", after),
        "ch012_unchanged": _yn(bool(after.get("ch012_unchanged"))),
        "ch018_unchanged": _yn(bool(after.get("ch018_unchanged"))),
        "production_cache": "UNCHANGED",
        "ready_for_human_review": _yn(ready),
        "next_action": NEXT_ACTION,
        "canonical_python": CANONICAL_PYTHON,
        "stop_reason": stop_reason,
        "tests_passed_failed": f"{tests.get('passed') or 0} / {tests.get('failed') or 0}",
    }
    progress = {
        "phase": PHASE,
        "batch_id": BATCH_ID,
        "state": result_label,
        "chapters": {
            row["chapter_id"]: row.get("status") for row in chapter_results
        },
        "stop_reason": stop_reason,
    }
    bundle = {
        "header": header,
        "preflight": {
            "phase": PHASE,
            "lot_theoretical_maximum_usd": float(lot_max),
            "authorized_cap_usd": float(BUDGET_CAP_USD),
        },
        "canonical_hashes_pre": before,
        "authorization_scope": authorization_manifest(
            consumed_calls=calls,
            sha256=None,
            blocked=result_label == "BLOCKED",
            block_reason=stop_reason if result_label != "PASS" else None,
        ),
        "batch_budget_ledger": ledger,
        "batch_progress": progress,
        "batch_summary": {
            "result": result_label,
            "chapters_generated": generated,
            "chapters_not_generated": not_generated,
            "provider_calls": calls,
            "anthropic_http": anthropic_http,
            "actual_total_cost": ledger.get("accumulated_actual_usd"),
            "stop_reason": stop_reason,
        },
        "batch_manifest": {
            "phase": PHASE,
            "batch_id": BATCH_ID,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "chapters": list(AUTHORIZED_CHAPTER_IDS),
            "model": f"{PROVIDER}/{MODEL}",
            "prompt": PROMPT_VERSION,
            "max_calls": 4,
            "max_calls_per_chapter": 1,
            "retries": 0,
            "fallbacks": 0,
            "publication": False,
        },
        "canonical_hashes_post": after,
        "regression_tests": tests,
        "offline_scenarios": scenarios,
        "isolated_cache": {
            "production_writes": isolated_cache.production_writes,
            "records": len(isolated_cache.records),
            "production_cache": "UNCHANGED",
        },
        "readiness": {
            "READY_FOR_HUMAN_REVIEW": ready,
            "READY_FOR_BATCH02": False,
            "book_json": "NOT PUBLISHED",
            "production_cache": "UNCHANGED",
            "SEMANTIC_CERTIFICATION": "NOT PERFORMED",
            "HUMAN_EDITORIAL_ACCEPTANCE": "PENDING",
            "NEXT_ACTION": NEXT_ACTION,
            "why": stop_reason,
        },
        "execution": {
            "mode": result_label,
            "provider_calls": calls,
            "anthropic_http": anthropic_http,
            "openai_http": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "chapter_rows": [
            {
                "chapter_id": row["chapter_id"],
                "status": row.get("status"),
                "cost": row.get("cost"),
                "structural": row.get("structural"),
                "ideas_missing": row.get("ideas_missing"),
                "src_invalid": row.get("src_invalid"),
                "editorial": row.get("editorial"),
                "notes": row.get("notes"),
            }
            for row in chapter_results
        ],
    }
    bundle["report_text"] = render_report(bundle)
    return bundle


__all__ = ["PhaseResult", "run_phase"]
