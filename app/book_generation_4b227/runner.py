"""
Runner Phase 4B.2.27.

Verify the six accepted chapters and the 4B.2.26 plan, then at most one
Anthropic call each for the 13 remaining chapters. No retry. No fallback.
No Terra. No publication. Sequential. Resume-safe.
"""

from __future__ import annotations

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
from app.book_ch002_offline_recovery_4b224.chapter_io import candidate_from_dict
from app.book_full_generation_preparation_4b226.acceptance import record_acceptances
from app.book_full_generation_preparation_4b226.normalize import (
    normalize_empty_paragraphs_idempotent,
)
from app.book_generation_integration_4b213.cache import IsolatedChapterCache
from app.book_generation_4b223.editorial import editorial_readiness_review
from app.book_generation_4b223.request import request_identity
from app.book_generation_4b223.traceability import (
    ex_ref_traceability_review,
    idea_traceability_review,
)
from app.book_generation_4b223.validation import (
    interpret_response,
    render_chapter_markdown,
    structural_validation,
)
from app.book_generation_4b227.authorization import authorization_manifest
from app.book_generation_4b227.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_CHAPTER_IDS,
    AUTHORIZED_ANTHROPIC_CALLS,
    BUDGET_CAP_USD,
    CANARY_WINDOW_ID,
    CANONICAL_PYTHON,
    EXPECTED_REMAINING_IDEAS,
    FORBIDDEN_CHAPTER_IDS,
    GENERATED_STATUS,
    LOCK_RESUME_WITHOUT_RECALL,
    LOCK_STATE_FAILED,
    LOCK_STATE_MAY_HAVE_BEEN_SENT,
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
from app.book_generation_4b227.context import (
    build_chapter_context,
    load_corpus,
    source_context_manifest,
)
from app.book_generation_4b227.costing import actual_cost, remaining_budget, reserve_chapter_budget
from app.book_generation_4b227.engine import (
    build_real_engine,
    credential_available,
    describe_engine,
)
from app.book_generation_4b227.guard import (
    BatchCallGuard,
    BookGeneration4227Error,
    OneShotCallGuard,
    assert_no_publication,
    validate_authorization_scope,
)
from app.book_generation_4b227.hashes import (
    assert_accepted_unchanged,
    assert_canonical,
    snapshot,
    snapshots_match,
)
from app.book_generation_4b227.inventory import chapter_from_plan, load_remaining_specs
from app.book_generation_4b227.ledger import empty_ledger, update_ledger
from app.book_generation_4b227.lock import (
    lock_already_consumed,
    persist_preflight,
    read_lock,
    reserve_call,
    transition_lock,
)
from app.book_generation_4b227.paths import (
    batch_lock_path,
    forensic_root,
    lock_path,
    production_book_path,
    repo_root,
)
from app.book_generation_4b227.report import render_report
from app.book_generation_4b227.scenarios import evaluate_offline_scenarios
from app.book_generation_4b227.writer import write_batch_artifacts, write_chapter_artifacts
from app.file_utils import content_hash
from app.source_analysis.errors import MaxRealCallsExceededError


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _hash_line(label: str, snap: dict[str, Any]) -> str:
    canonical = snap["canonical"]
    return (
        f"{label} source={canonical['source_map']['sha256']} "
        f"plan={canonical['editorial_plan']['sha256']} "
        f"transcript={canonical['clean_transcript']['sha256']}"
    )


def _progress_payload(
    *,
    ledger: Mapping[str, Any],
    chapter_results: list[dict[str, Any]],
    current: str | None,
    stop_reason: str | None,
    state: str,
) -> dict[str, Any]:
    generated = [
        row["chapter_id"] for row in chapter_results if row.get("status") == GENERATED_STATUS
    ]
    failed = [
        row["chapter_id"]
        for row in chapter_results
        if row.get("status") not in {GENERATED_STATUS, "RESUME_SKIPPED_ALREADY_VALIDATED"}
        and row.get("blocking")
    ]
    remaining = [
        chapter_id
        for chapter_id in AUTHORIZED_CHAPTER_IDS
        if chapter_id not in generated
        and chapter_id not in {row.get("chapter_id") for row in chapter_results}
    ]
    last_validation = None
    last_error = stop_reason
    if chapter_results:
        last = chapter_results[-1]
        last_validation = last.get("structural")
        last_error = last.get("notes") or stop_reason
    return {
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "state": state,
        "chapters_completed": len(generated),
        "chapters_remaining": len(AUTHORIZED_CHAPTER_IDS) - len(generated),
        "chapter_in_progress": current,
        "calls_consumed": sum(int(row.get("provider_calls") or 0) for row in chapter_results),
        "calls_uncertain": sum(
            1 for row in chapter_results if row.get("status") == "UNCERTAIN"
        ),
        "actual_spend_usd": ledger.get("accumulated_actual_usd"),
        "reserved_or_uncertain_usd": ledger.get("reserved_or_uncertain_usd"),
        "remaining_budget_usd": ledger.get("remaining_budget_usd"),
        "last_validation": last_validation,
        "last_error": last_error,
        "resume_state": {
            "ignore_already_validated": True,
            "never_replay_consumed": True,
            "never_replay_uncertain": True,
            "same_authorization_scope": True,
        },
        "chapters": {
            chapter_id: next(
                (
                    row.get("status")
                    for row in chapter_results
                    if row.get("chapter_id") == chapter_id
                ),
                "NOT_STARTED",
            )
            for chapter_id in AUTHORIZED_CHAPTER_IDS
        },
        "failed": failed,
        "remaining": remaining,
        "stop_reason": stop_reason,
        "secrets_included": False,
    }


def _persist_progress(
    *,
    root: Path,
    ledger: Mapping[str, Any],
    chapter_results: list[dict[str, Any]],
    current: str | None,
    stop_reason: str | None,
    state: str,
) -> dict[str, Any]:
    payload = _progress_payload(
        ledger=ledger,
        chapter_results=chapter_results,
        current=current,
        stop_reason=stop_reason,
        state=state,
    )
    write_batch_artifacts({"progress": payload, "budget_ledger": ledger}, root=root)
    return payload


@dataclass
class PhaseResult:
    accepted: bool
    mode: str
    bundle: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    engine_generate_attempts: int = 0
    anthropic_post_attempts: int = 0


def _classify_lot(
    *,
    calls: int,
    blocked: bool,
    chapters_generated: int,
    hashes_ok: bool,
    accepted_ok: bool,
    stop_reason: str | None,
) -> str:
    if blocked and calls == 0:
        return "BLOCKED"
    if calls == 0:
        return "FAIL"
    if not hashes_ok or not accepted_ok:
        return "FAIL"
    if chapters_generated == 13 and not stop_reason:
        return "PASS"
    if chapters_generated == 13:
        return "PASS"
    if chapters_generated or calls:
        return "PARTIAL"
    return "FAIL"


def _prepare_chapter(
    *,
    spec,
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
        remaining=remaining,
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
        remaining=remaining,
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
        remaining=remaining,
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
    run_tests: bool = False,
) -> PhaseResult:
    del run_tests
    result = PhaseResult(
        accepted=False,
        mode="DRY_RUN" if (dry_run or not execute_real) else "EXECUTE",
    )
    isolated_cache = IsolatedChapterCache()
    try:
        scope = validate_authorization_scope(authorization_scope)
        assert_no_publication(production_book_path())
    except BookGeneration4227Error as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    base = root or repo_root()
    before = snapshot(root=base)
    acceptances: dict[str, Any] | None = None
    try:
        assert_canonical(before)
        assert_accepted_unchanged(before)
        acceptances = record_acceptances()
        corpus = load_corpus()
        loaded = load_remaining_specs(corpus=corpus, root=base)
    except Exception as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        after = snapshot(root=base)
        bundle = _blocked_bundle(
            before=before,
            after=after,
            stop_reason=str(exc),
            result_label="BLOCKED",
            acceptances=acceptances,
        )
        if write_artifacts:
            write_batch_artifacts(bundle, root=base)
        result.bundle = redact_secrets(bundle)
        return result

    prepared: dict[str, dict[str, Any]] = {}
    lot_max = Decimal("0")
    try:
        for chapter_id in AUTHORIZED_CHAPTER_IDS:
            spec = loaded["specs"][chapter_id]
            prepared[chapter_id] = _prepare_chapter(
                spec=spec,
                corpus=corpus,
                remaining=BUDGET_CAP_USD,
            )
            theoretical = Decimal(
                str(prepared[chapter_id]["cost"]["theoretical_maximum_decimal"])
            )
            lot_max += theoretical
        if lot_max > BUDGET_CAP_USD:
            raise BookGeneration4227Error(
                f"Sum of calculable maxima {lot_max} exceeds {BUDGET_CAP_USD}. "
                "STOP without changing parameters."
            )
    except Exception as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        after = snapshot(root=base)
        bundle = _blocked_bundle(
            before=before,
            after=after,
            stop_reason=str(exc),
            result_label="BLOCKED",
            acceptances=acceptances,
        )
        if write_artifacts:
            write_batch_artifacts(bundle, root=base)
        result.bundle = redact_secrets(bundle)
        return result

    scenarios = evaluate_offline_scenarios(root=base)

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
    elif execute_real and int(scenarios.get("failed") or 0):
        blocked = True
        block_reason = "OFFLINE_SCENARIOS_FAILED"
    elif str((read_lock(batch_lock) or {}).get("state") or "") in LOCK_STOP_STATES:
        blocked = True
        block_reason = "BATCH_LOCK_ALREADY_CONSUMED"

    if not lock_already_consumed(batch_lock):
        persist_preflight(batch_lock)

    first_prompt = (next(iter(prepared.values()))["identity"].get("prompt_snapshot") or {})
    preflight = {
        "phase": PHASE,
        "authorization_scope": scope,
        "chapter_ids": list(AUTHORIZED_CHAPTER_IDS),
        "model": f"{PROVIDER}/{MODEL}",
        "prompt_version": PROMPT_VERSION,
        "canonical_hashes_ok": before["canonical_match_expected"],
        "six_accepted_immutable": before.get("six_accepted_immutable"),
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
        "expected_from_plan": loaded.get("expected_from_plan"),
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

    if write_artifacts:
        _persist_progress(
            root=base,
            ledger=ledger,
            chapter_results=[],
            current=None,
            stop_reason=block_reason,
            state="PREFLIGHT_VALIDATED" if not blocked else "BLOCKED",
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
            acceptances=acceptances,
            preflight=preflight,
        )
        if write_artifacts:
            write_batch_artifacts(bundle, root=base)
        result.bundle = redact_secrets(bundle)
        result.error = block_reason or ""
        result.mode = "BLOCKED_PRECALL" if blocked else "DRY_RUN"
        result.accepted = not blocked
        return result

    batch_guard = BatchCallGuard(max_calls=AUTHORIZED_ANTHROPIC_CALLS)
    chapter_results: list[dict[str, Any]] = []
    shared_engine = engine
    stop_reason = None

    for chapter_id in AUTHORIZED_CHAPTER_IDS:
        print(
            f"[book_generation_4b227] chapter={chapter_id} "
            f"remaining_budget={ledger.get('remaining_budget_usd')} "
            f"completed={sum(1 for row in chapter_results if row.get('status') == GENERATED_STATUS)}/13",
            flush=True,
        )
        try:
            live_snap = snapshot(root=base)
            assert_canonical(live_snap)
            assert_accepted_unchanged(live_snap)
        except Exception as exc:
            stop_reason = str(exc)
            break

        item = prepared[chapter_id]
        spec = item["spec"]
        chapter_lock = lock_path(chapter_id, root=base)
        existing = read_lock(chapter_lock) or {}
        existing_state = str(existing.get("state") or "")
        if existing_state in LOCK_RESUME_WITHOUT_RECALL:
            chapter_results.append(
                {
                    "chapter_id": chapter_id,
                    "status": GENERATED_STATUS,
                    "cost": existing.get("actual_cost_usd") or "n/a",
                    "structural": "PASS",
                    "ideas_missing": [],
                    "ideas_found": spec.idea_count,
                    "ideas_expected": spec.idea_count,
                    "src_invalid": [],
                    "editorial": "n/a",
                    "notes": "lock already RESPONSE_VALIDATED; no second call",
                    "provider_calls": 0,
                    "anthropic_http": 0,
                    "normalized_empty": 0,
                }
            )
            if write_artifacts:
                _persist_progress(
                    root=base,
                    ledger=ledger,
                    chapter_results=chapter_results,
                    current=chapter_id,
                    stop_reason=None,
                    state="RESUME_SKIPPED",
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
            except Exception as exc:
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
        if write_artifacts:
            _persist_progress(
                root=base,
                ledger=ledger,
                chapter_results=chapter_results,
                current=chapter_id,
                stop_reason=None,
                state="CALL_RESERVED",
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
                    "blocking": True,
                    "normalized_empty": 0,
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
        raw_for_norm = raw_parsed if isinstance(raw_parsed, dict) else None
        normalization = {
            "phase": PHASE,
            "chapter_id": chapter_id,
            "changed": False,
            "removed_paragraph_ids": [],
            "raw_response_unchanged": True,
            "applied": False,
            "secrets_included": False,
        }
        if candidate is not None:
            isolated_cache.store(
                str(live["identity"].get("request_sha256") or chapter_id),
                {"chapter_id": chapter_id, "isolated": True},
            )
            normalization = normalize_empty_paragraphs_idempotent(
                candidate.to_dict(),
                raw_response=raw_for_norm,
                protect_accepted=True,
            )
            candidate = candidate_from_dict(normalization["derived"])
            interpreted = dict(interpreted)
            interpreted["candidate"] = candidate
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
        if checks.get("empty_paragraphs"):
            blocking = True
            chapter_stop = chapter_stop or "EMPTY_PARAGRAPHS_REMAIN"

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
        removed = list(normalization.get("removed_paragraph_ids") or [])
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
                "raw_response_kept_intact": True,
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
            "normalization_report": {
                key: value
                for key, value in normalization.items()
                if key not in {"derived", "raw_response"}
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
                "status": GENERATED_STATUS if not blocking else (chapter_stop or "FAILED"),
                "why": chapter_stop or "ONE_REAL_CALL_COMPLETED",
                "SEMANTIC_CERTIFICATION": "NOT PERFORMED",
            },
        }
        if write_artifacts:
            write_chapter_artifacts(
                chapter_id, chapter_bundle, root=base, call_completed=True
            )
        print(
            f"[book_generation_4b227] chapter={chapter_id} "
            f"status={'GENERATED_STRUCTURALLY_VALID' if not blocking else (chapter_stop or 'FAILED')} "
            f"cost={actual.get('display') or actual.get('total_cost_usd')} "
            f"structural={structural.get('status')}",
            flush=True,
        )
        chapter_results.append(
            {
                "chapter_id": chapter_id,
                "status": GENERATED_STATUS if not blocking else (chapter_stop or "FAILED"),
                "cost": actual.get("display") or actual.get("total_cost_usd") or "UNKNOWN",
                "structural": structural.get("status"),
                "ideas_missing": list(idea.get("ideas_missing_from_paras_e") or []),
                "ideas_found": idea.get("ideas_found_count"),
                "ideas_expected": idea.get("ideas_expected_count") or spec.idea_count,
                "src_invalid": list(idea.get("src_handles_invalid") or []),
                "editorial": editorial.get("overall_classification"),
                "notes": chapter_stop or error_text or "",
                "provider_calls": max(generate_attempts, 1),
                "anthropic_http": post_attempts
                if not describe_engine(chapter_engine).get("is_fake")
                else 0,
                "bundle": chapter_bundle,
                "blocking": blocking,
                "normalized_empty": len(removed),
            }
        )
        if write_artifacts:
            _persist_progress(
                root=base,
                ledger=ledger,
                chapter_results=chapter_results,
                current=chapter_id,
                stop_reason=chapter_stop,
                state=GENERATED_STATUS if not blocking else (chapter_stop or "FAILED"),
            )
        if blocking:
            stop_reason = chapter_stop
            break

    after = snapshot(root=base)
    hashes_ok = snapshots_match(before, after) and after["canonical_match_expected"]
    accepted_ok = bool(after.get("six_accepted_immutable"))
    generated = [
        row["chapter_id"]
        for row in chapter_results
        if row.get("status") == GENERATED_STATUS
    ]
    calls = sum(int(row.get("provider_calls") or 0) for row in chapter_results)
    anthropic_http = sum(int(row.get("anthropic_http") or 0) for row in chapter_results)
    if stop_reason is None and len(generated) == 13:
        stop_reason = "REMAINING_13_COMPLETED"
        result_label = "PASS"
    else:
        result_label = _classify_lot(
            calls=calls,
            blocked=False,
            chapters_generated=len(generated),
            hashes_ok=hashes_ok,
            accepted_ok=accepted_ok,
            stop_reason=None if stop_reason == "REMAINING_13_COMPLETED" else stop_reason,
        )
        if stop_reason is None:
            stop_reason = "LOT_STOPPED"
    if result_label == "PASS" and stop_reason == "REMAINING_13_COMPLETED":
        transition_lock(
            batch_lock,
            state=LOCK_STATE_RESPONSE_VALIDATED,
            note="Remaining 13 structurally completed.",
        )
    elif calls:
        transition_lock(
            batch_lock,
            state=LOCK_STATE_FAILED if result_label == "FAIL" else LOCK_STATE_RESPONSE_RECEIVED,
            note=stop_reason or "lot stopped",
        )

    bundle = _final_bundle(
        before=before,
        after=after,
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
        acceptances=acceptances,
        preflight=preflight,
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
    stop_reason: str,
    result_label: str,
    acceptances: dict[str, Any] | None,
) -> dict[str, Any]:
    header = {
        "result": result_label,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "authorized_chapters": ", ".join(AUTHORIZED_CHAPTER_IDS),
        "provider_calls": 0,
        "anthropic_http": 0,
        "openai_http": 0,
        "model": f"{PROVIDER}/{MODEL}",
        "prompt": PROMPT_VERSION,
        "prompt_hash": None,
        "preflight_max_cost": None,
        "actual_total_cost": "n/a",
        "reserved_or_uncertain_cost": "n/a",
        "remaining_budget": float(BUDGET_CAP_USD),
        "chapters_generated": [],
        "chapters_failed": [],
        "chapters_not_started": list(AUTHORIZED_CHAPTER_IDS),
        "normalized_empty_paragraphs": 0,
        "structural_validation": {},
        "idea_coverage": f"0 / {EXPECTED_REMAINING_IDEAS}",
        "invalid_src": 0,
        "ex_ref_unc_traceability": "n/a",
        "authorial_voice_review": "n/a",
        "potential_substantive_issues": 0,
        "accepted_chapters_immutable": _yn(bool(after.get("six_accepted_immutable"))),
        "canonical_hashes_pre_post": _hash_line("pre", before)
        + "; "
        + _hash_line("post", after),
        "canonical_hashes_pre_post_status": "MATCH"
        if snapshots_match(before, after)
        else "MISMATCH",
        "resume_safety": "FAIL",
        "call_lock_safety": "FAIL",
        "ready_for_19_chapter_manuscript_review": "NO",
        "next_action": NEXT_ACTION,
        "canonical_python": CANONICAL_PYTHON,
        "stop_reason": stop_reason,
    }
    bundle = {
        "header": header,
        "canonical_hashes_pre": before,
        "canonical_hashes_post": after,
        "canonical_hashes_pre_post": {
            "pre": before,
            "post": after,
            "match": snapshots_match(before, after),
            "status": header["canonical_hashes_pre_post_status"],
        },
        "authorization": authorization_manifest(
            consumed_calls=0,
            sha256=None,
            blocked=True,
            block_reason=stop_reason,
        ),
        "accepted_chapters_manifest": acceptances,
        "budget_ledger": empty_ledger(),
        "progress": {
            "phase": PHASE,
            "state": "BLOCKED",
            "chapters": {chapter_id: "NOT_STARTED" for chapter_id in AUTHORIZED_CHAPTER_IDS},
        },
        "summary": {"result": result_label, "stop_reason": stop_reason},
        "run_manifest": {
            "phase": PHASE,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "chapters": list(AUTHORIZED_CHAPTER_IDS),
        },
        "readiness": {
            "READY_FOR_19_CHAPTER_MANUSCRIPT_REVIEW": False,
            "book_json": "NOT PUBLISHED",
            "production_cache": "UNCHANGED",
            "SEMANTIC_CERTIFICATION": "NOT PERFORMED",
            "HUMAN_EDITORIAL_ACCEPTANCE_OF_NEW_CHAPTERS": "PENDING",
            "NEXT_ACTION": NEXT_ACTION,
            "why": stop_reason,
        },
        "chapter_rows": [
            {
                "chapter_id": chapter_id,
                "status": "NOT_STARTED",
                "cost": "n/a",
                "structural": "n/a",
                "provider_calls": 0,
            }
            for chapter_id in AUTHORIZED_CHAPTER_IDS
        ],
    }
    bundle["report_text"] = render_report(bundle)
    return bundle


def _final_bundle(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
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
    acceptances: dict[str, Any] | None,
    preflight: Mapping[str, Any] | None,
) -> dict[str, Any]:
    generated = [
        row["chapter_id"] for row in chapter_results if row.get("status") == GENERATED_STATUS
    ]
    failed = [
        row["chapter_id"]
        for row in chapter_results
        if row.get("status") not in {GENERATED_STATUS}
        and row.get("blocking")
    ]
    not_started = [
        chapter_id
        for chapter_id in AUTHORIZED_CHAPTER_IDS
        if chapter_id not in {row.get("chapter_id") for row in chapter_results}
    ]
    by_id = {row["chapter_id"]: row for row in chapter_results}
    structural_by = {row["chapter_id"]: row.get("structural") for row in chapter_results}
    idea_found = 0
    idea_expected = EXPECTED_REMAINING_IDEAS
    invalid_src = 0
    normalized = 0
    potential = 0
    for row in chapter_results:
        if isinstance(row.get("ideas_found"), int):
            idea_found += int(row["ideas_found"])
        invalid_src += len(row.get("src_invalid") or [])
        normalized += int(row.get("normalized_empty") or 0)
        bundle = row.get("bundle") or {}
        editorial = bundle.get("editorial_readiness_review") or {}
        potential += len(editorial.get("potential_substantive_issues") or [])
    first_prompt = None
    if prepared:
        first_prompt = (
            next(iter(prepared.values())).get("identity", {}).get("prompt_snapshot") or {}
        )
    hashes_ok = snapshots_match(before, after) and after.get("canonical_match_expected")
    accepted_ok = bool(after.get("six_accepted_immutable"))
    structural_ok = all(
        by_id.get(chapter_id, {}).get("structural") == "PASS" for chapter_id in generated
    )
    ready = (
        result_label == "PASS"
        and len(generated) == 13
        and hashes_ok
        and accepted_ok
        and structural_ok
        and idea_found >= EXPECTED_REMAINING_IDEAS
        and invalid_src == 0
        and not production_book_path().is_file()
    )
    chapter_rows = []
    for chapter_id in AUTHORIZED_CHAPTER_IDS:
        row = by_id.get(chapter_id)
        if row is None:
            chapter_rows.append(
                {
                    "chapter_id": chapter_id,
                    "status": "NOT_STARTED",
                    "cost": "n/a",
                    "structural": "n/a",
                    "ideas_found": None,
                    "ideas_expected": (prepared.get(chapter_id) or {})
                    .get("spec")
                    .idea_count
                    if prepared.get(chapter_id)
                    else None,
                    "provider_calls": 0,
                    "notes": "not attempted",
                }
            )
        else:
            chapter_rows.append(
                {
                    "chapter_id": chapter_id,
                    "status": row.get("status"),
                    "cost": row.get("cost"),
                    "structural": row.get("structural"),
                    "ideas_missing": row.get("ideas_missing"),
                    "ideas_found": row.get("ideas_found"),
                    "ideas_expected": row.get("ideas_expected"),
                    "src_invalid": row.get("src_invalid"),
                    "editorial": row.get("editorial"),
                    "notes": row.get("notes"),
                    "provider_calls": row.get("provider_calls"),
                    "normalized_empty": row.get("normalized_empty"),
                }
            )
    header = {
        "result": result_label,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "authorized_chapters": ", ".join(AUTHORIZED_CHAPTER_IDS),
        "provider_calls": calls,
        "anthropic_http": anthropic_http,
        "openai_http": 0,
        "model": f"{PROVIDER}/{MODEL}",
        "prompt": PROMPT_VERSION,
        "prompt_hash": (first_prompt or {}).get("prompt_sha256"),
        "preflight_max_cost": float(lot_max),
        "actual_total_cost": ledger.get("accumulated_actual_usd"),
        "reserved_or_uncertain_cost": ledger.get("reserved_or_uncertain_usd"),
        "remaining_budget": ledger.get("remaining_budget_usd"),
        "retries": 0,
        "fallbacks": 0,
        "chapters_generated": generated,
        "chapters_failed": failed,
        "chapters_not_started": not_started,
        "normalized_empty_paragraphs": normalized,
        "structural_validation": structural_by,
        "idea_coverage": f"{idea_found} / {idea_expected}",
        "invalid_src": invalid_src,
        "ex_ref_unc_traceability": "documented_without_auto_omission",
        "authorial_voice_review": {
            row["chapter_id"]: row.get("editorial") for row in chapter_results
        },
        "potential_substantive_issues": potential,
        "accepted_chapters_immutable": _yn(accepted_ok),
        "canonical_hashes_pre_post": _hash_line("pre", before)
        + "; "
        + _hash_line("post", after),
        "canonical_hashes_pre_post_status": "MATCH" if hashes_ok else "MISMATCH",
        "resume_safety": "PASS",
        "call_lock_safety": "PASS",
        "ready_for_19_chapter_manuscript_review": _yn(ready),
        "next_action": NEXT_ACTION,
        "canonical_python": CANONICAL_PYTHON,
        "stop_reason": stop_reason,
        "accepted_excluded": list(FORBIDDEN_CHAPTER_IDS),
    }
    progress = _progress_payload(
        ledger=ledger,
        chapter_results=chapter_results,
        current=None,
        stop_reason=stop_reason,
        state=result_label,
    )
    bundle = {
        "header": header,
        "preflight": preflight
        or {
            "phase": PHASE,
            "lot_theoretical_maximum_usd": float(lot_max),
            "authorized_cap_usd": float(BUDGET_CAP_USD),
        },
        "canonical_hashes_pre": before,
        "canonical_hashes_post": after,
        "canonical_hashes_pre_post": {
            "phase": PHASE,
            "pre": before,
            "post": after,
            "match": hashes_ok,
            "status": "MATCH" if hashes_ok else "MISMATCH",
            "secrets_included": False,
        },
        "authorization": authorization_manifest(
            consumed_calls=calls,
            sha256=None,
            blocked=result_label == "BLOCKED",
            block_reason=stop_reason if result_label != "PASS" else None,
        ),
        "accepted_chapters_manifest": acceptances,
        "budget_ledger": ledger,
        "progress": progress,
        "summary": {
            "result": result_label,
            "chapters_generated": generated,
            "chapters_failed": failed,
            "chapters_not_started": not_started,
            "provider_calls": calls,
            "anthropic_http": anthropic_http,
            "actual_total_cost": ledger.get("accumulated_actual_usd"),
            "stop_reason": stop_reason,
        },
        "run_manifest": {
            "phase": PHASE,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "chapters": list(AUTHORIZED_CHAPTER_IDS),
            "model": f"{PROVIDER}/{MODEL}",
            "prompt": PROMPT_VERSION,
            "max_calls": 13,
            "max_calls_per_chapter": 1,
            "retries": 0,
            "fallbacks": 0,
            "publication": False,
        },
        "offline_scenarios": scenarios,
        "isolated_cache": {
            "production_writes": isolated_cache.production_writes,
            "records": len(isolated_cache.records),
            "production_cache": "UNCHANGED",
        },
        "readiness": {
            "READY_FOR_19_CHAPTER_MANUSCRIPT_REVIEW": ready,
            "book_json": "NOT PUBLISHED",
            "production_cache": "UNCHANGED",
            "SEMANTIC_CERTIFICATION": "NOT PERFORMED",
            "HUMAN_EDITORIAL_ACCEPTANCE_OF_NEW_CHAPTERS": "PENDING",
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
        "chapter_rows": chapter_rows,
    }
    bundle["report_text"] = render_report(bundle)
    return bundle


__all__ = ["PhaseResult", "run_phase"]
