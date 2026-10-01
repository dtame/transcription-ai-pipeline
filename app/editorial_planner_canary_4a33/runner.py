"""
Runner Phase 4A.3.3.

Default: pre-call only, 0 POST.
Real: --execute-real + exact scope. One attempt. No retry.
"""

from __future__ import annotations

import hashlib
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
from app.editorial_planner_canary_4a3.review import chapter_review, section_review
from app.editorial_planner_canary_4a33.constants import (
    A3_CANDIDATE_SHA256,
    A32_ESTIMATED_COST_DISPLAY,
    AUTHORIZATION_SCOPE,
    AUTHORIZED_PROVIDER_CALLS,
    BOOK_GENERATOR,
    CANARY_WINDOW_ID,
    CANONICAL_LANGUAGE_SOURCE,
    CONNECT_TIMEOUT_SECONDS,
    EXPECTED_CANONICAL_DOCUMENT_LANGUAGE,
    EXPECTED_IDEA_COUNT,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    MODEL,
    NEXT_ACTION,
    PHASE,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    RAW_SCHEMA_BYTES,
    ADAPTED_SCHEMA_BYTES,
    ADAPTED_SCHEMA_SHA256,
    READ_TIMEOUT_SECONDS,
    RETRIES,
    STAGE_CANARY,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.editorial_planner_canary_4a33.costing import actual_cost, budget_calibration
from app.editorial_planner_canary_4a33.engine import (
    CountingAnthropicEngine,
    build_real_canary_engine,
    describe_engine,
)
from app.editorial_planner_canary_4a33.guard import (
    OneShotCallGuard,
    PlannerCanaryError,
    assert_no_book_generator,
    assert_no_publication,
    assert_phase3b_untouched,
    validate_authorization_scope,
)
from app.editorial_planner_canary_4a33.identity import (
    precall_identity,
    require_precall_identity,
)
from app.editorial_planner_canary_4a33.language import language_audit
from app.editorial_planner_canary_4a33.paths import (
    a3_candidate_path,
    canary_lock_path,
    forensic_root,
    production_editorial_plan_path,
    production_source_map_path,
)
from app.editorial_planner_canary_4a33.report import render_report
from app.editorial_planner_canary_4a33.semantic import review_semantics
from app.editorial_planner_canary_4a33.validate import interpret_production_response
from app.editorial_planner_language_policy_4a32.identity import file_sha256
from app.editorial_planner_language_policy_4a32.payload import build_production_request
from app.editorial_planning.pipeline import load_published_source_map
from app.file_utils import content_hash
from app.source_analysis.errors import MaxRealCallsExceededError


def _consume_lock(*, root: Path | None) -> None:
    path = canary_lock_path(root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise PlannerCanaryError(
            "Canary real-call lock already present — authorization consumed. "
            "NO RETRY."
        )
    path.write_text(
        f"{PHASE}\n{AUTHORIZATION_SCOPE}\nconsumed=1\n",
        encoding="utf-8",
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _thinking_observed(thinking_tokens: Any, content_metadata: Mapping | None) -> str:
    blocks = []
    if isinstance(content_metadata, dict):
        blocks = list(content_metadata.get("block_types") or [])
    thinking_blocks = any(str(item).lower() == "thinking" for item in blocks)
    if thinking_tokens is None and not thinking_blocks:
        return "NOT_EXPOSED"
    try:
        value = int(thinking_tokens) if thinking_tokens is not None else 0
    except (TypeError, ValueError):
        return "YES" if thinking_blocks else "NOT_EXPOSED"
    if value > 0 or thinking_blocks:
        return "YES"
    return "NO"


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


@dataclass
class CanaryRunResult:
    mode: str
    authorization_scope: str
    accepted: bool = False
    error: str | None = None
    engine_generate_attempts: int = 0
    anthropic_post_attempts: int = 0
    bundle: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": PHASE,
            "mode": self.mode,
            "authorization_scope": self.authorization_scope,
            "accepted": self.accepted,
            "error": self.error,
            "engine_generate_attempts": self.engine_generate_attempts,
            "anthropic_post_attempts": self.anthropic_post_attempts,
            "bundle_header": (self.bundle.get("header") or {}),
        }


def _header_base(identity: Mapping[str, Any], *, tests: str, new_failures: int) -> dict[str, Any]:
    return {
        "authorized_provider_calls": AUTHORIZED_PROVIDER_CALLS,
        "actual_provider_calls": 0,
        "retries": RETRIES,
        "source_map_sha256_pre": identity.get("source_map_sha256"),
        "source_map_sha256_post": None,
        "source_map_unchanged": "n/a",
        "canonical_language_source": CANONICAL_LANGUAGE_SOURCE,
        "canonical_document_language": identity.get("canonical_document_language"),
        "prompt": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "schema_raw_adapted": f"{RAW_SCHEMA_BYTES} / {ADAPTED_SCHEMA_BYTES}",
        "schema_hash": ADAPTED_SCHEMA_SHA256,
        "schema_identity": identity.get("schema_identity"),
        "expected_request_sha256": EXPECTED_REQUEST_SHA256,
        "actual_request_sha256": identity.get("actual_request_sha256"),
        "request_identity": identity.get("request_identity"),
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "connect_timeout": CONNECT_TIMEOUT_SECONDS,
        "read_timeout": READ_TIMEOUT_SECONDS,
        "a32_estimated_cost": A32_ESTIMATED_COST_DISPLAY,
        "editorial_language_expected": EXPECTED_CANONICAL_DOCUMENT_LANGUAGE,
        "tests": tests,
        "new_failures": new_failures,
        "editorial_plan_json": "NOT PUBLISHED",
        "book_generator": BOOK_GENERATOR,
        "next_action": NEXT_ACTION,
    }


def _offline_header(identity: Mapping[str, Any], *, tests: str, new_failures: int, result: str) -> dict[str, Any]:
    post = identity.get("source_map_sha256")
    return {
        **_header_base(identity, tests=tests, new_failures=new_failures),
        "result": result,
        "source_map_sha256_post": post,
        "source_map_unchanged": _yn(post == EXPECTED_SOURCE_MAP_SHA256),
        "http_status": None,
        "finish": None,
        "request_id": None,
        "input_tokens": None,
        "output_tokens": None,
        "thinking_tokens": None,
        "output_utilization": None,
        "elapsed": None,
        "cost": None,
        "structured_parse": "n/a",
        "transport_decoder": "n/a",
        "handle_validation": "n/a",
        "canonical_reconstruction": "n/a",
        "canonical_candidate_sha256": None,
        "chapters": None,
        "sections": None,
        "idea_coverage": "n/a",
        "silent_omissions": "n/a",
        "assigned": None,
        "deferred": None,
        "excluded": None,
        "reused": None,
        "unknown_refs_total": "n/a",
        "editorial_language_result": "n/a",
        "traceability": "n/a",
        "invention_boundary": "n/a",
        "uncertainty_preservation": "n/a",
        "title_review": "n/a",
        "book_concept_review": "n/a",
        "chapter_review": "n/a",
        "section_review": "n/a",
        "editorial_plan_validator": "n/a",
        "deterministic_replay": "n/a",
        "semantic_review": "n/a",
        "publication_eligible": "NO",
        "ready_for_controlled_editorial_plan_publication": "NO",
        "notes": identity.get("block_reason") or "offline pre-call only",
    }


def _publication_eligible(
    *,
    http_success: bool | None,
    finish: Any,
    contract: Mapping[str, Any],
    semantic: Mapping[str, Any],
    language: Mapping[str, Any],
    replay: str,
    post_hash: str,
    generate_attempts: int,
    post_attempts: int,
    test_failures: int,
) -> bool:
    coverage = dict(contract.get("idea_coverage") or {})
    refs = dict(contract.get("unknown_refs") or {})
    validator = contract.get("editorial_plan_validator")
    validator_ok = validator in {"PASS", "REVIEW"} and not contract.get("validator_hard_fail")
    finish_ok = str(finish or "") in {"end_turn", "stop"}
    unknown_ok = all(int(refs.get(key) or 0) == 0 for key in refs)
    language_ok = language.get("editorial_language_match") == "PASS"
    return (
        http_success is True
        and finish_ok
        and generate_attempts == 1
        and post_attempts == 1
        and contract.get("structured_parse") == "PASS"
        and contract.get("transport_decoder") == "PASS"
        and contract.get("handle_validation") == "PASS"
        and contract.get("canonical_reconstruction") == "PASS"
        and contract.get("hierarchy") == "PASS"
        and bool(coverage.get("coverage_complete"))
        and coverage.get("silent_omissions") == 0
        and unknown_ok
        and language_ok
        and contract.get("traceability") == "PASS"
        and contract.get("invention_boundary") == "PASS"
        and contract.get("uncertainty_preservation") == "PASS"
        and validator_ok
        and replay == "PASS"
        and semantic.get("status") == "PASS"
        and post_hash == EXPECTED_SOURCE_MAP_SHA256
        and test_failures == 0
    )


def _classify(
    *,
    blocked_precall: bool,
    generate_attempts: int,
    post_attempts: int,
    http_success: bool | None,
    finish: Any,
    contract: Mapping[str, Any],
    semantic: Mapping[str, Any],
    eligible: bool,
    test_failures: int,
) -> str:
    if blocked_precall and generate_attempts == 0:
        return "BLOCKED_PRECALL"
    if generate_attempts > 1 or post_attempts > 1:
        return "FAIL"
    if generate_attempts != 1:
        return "FAIL"
    if str(finish or "") == "max_tokens":
        return "FAIL"
    if http_success is not True:
        return "FAIL"
    if eligible and test_failures == 0:
        return "PASS"
    if (
        http_success is True
        and contract.get("structured_parse") == "PASS"
        and contract.get("canonical_reconstruction") == "PASS"
        and semantic.get("status") == "REVIEW_REQUIRED"
    ):
        return "PARTIAL"
    return "FAIL"


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
    tests: str = "not-run-yet",
    new_failures: int = 0,
) -> CanaryRunResult:
    result = CanaryRunResult(
        mode="DRY_RUN" if (dry_run or not execute_real) else "EXECUTE",
        authorization_scope=str(authorization_scope or ""),
    )
    try:
        scope = validate_authorization_scope(authorization_scope)
        result.authorization_scope = scope
        assert_phase3b_untouched()
        assert_no_book_generator()
        assert_no_publication(production_editorial_plan_path())
    except PlannerCanaryError as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if execute_real and dry_run:
        result.error = "--dry-run and --execute-real are exclusive."
        result.mode = "REJECTED"
        return result

    identity = precall_identity()
    blocked = bool(identity.get("blocked_precall"))
    language_code = str(identity.get("canonical_document_language") or "")

    if blocked or not execute_real:
        verdict = "BLOCKED_PRECALL" if blocked else "DRY_RUN"
        header = _offline_header(
            identity, tests=tests, new_failures=new_failures, result=verdict
        )
        readiness = {
            "READY_FOR_CONTROLLED_EDITORIAL_PLAN_PUBLICATION": False,
            "PUBLICATION_ELIGIBLE": False,
            "BOOK_GENERATOR": BOOK_GENERATOR,
            "NEXT_ACTION": NEXT_ACTION,
            "why": identity.get("block_reason") or "pre-call only; provider not called",
        }
        bundle = {
            "header": header,
            "precall": identity,
            "readiness": readiness,
            "publication": {
                "PUBLICATION_ELIGIBLE": False,
                "editorial_plan_json": "NOT PUBLISHED",
            },
            "execution": {
                "mode": result.mode,
                "actual_provider_calls": 0,
                "retries": 0,
            },
        }
        bundle["report_text"] = render_report(bundle)
        if write_artifacts:
            from app.editorial_planner_canary_4a33.writer import write_canary_artifacts

            write_canary_artifacts(bundle, root=root)
        result.bundle = bundle
        result.accepted = not blocked
        if blocked:
            result.error = str(identity.get("block_reason"))
        return result

    try:
        require_precall_identity(identity)
    except PlannerCanaryError as exc:
        result.error = str(exc)
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
        except PlannerCanaryError as exc:
            result.accepted = False
            result.error = str(exc)
            result.mode = "REJECTED"
            return result

    source_map, raw_map, digest, path = load_published_source_map(PROJECT_NAME)
    request = build_production_request(
        source_map,
        canonical_document_language=language_code,
        max_output_tokens=PRODUCTION_MAX_OUTPUT_TOKENS,
    )
    forensic_dir = forensic_root(root=root)
    forensic_dir.mkdir(parents=True, exist_ok=True)
    guard = OneShotCallGuard(max_calls=1)
    identity_hash = digest
    if isinstance(engine, CountingAnthropicEngine):
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
                    stage=request.stage or STAGE_CANARY,
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
        result.anthropic_post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
        return result

    post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
    if post_attempts == 0:
        post_attempts = int(getattr(engine, "call_count", 0) or 0)
    result.engine_generate_attempts = guard.generate_attempts
    result.anthropic_post_attempts = post_attempts

    usage = http_meta.get("usage") if isinstance(http_meta.get("usage"), dict) else {}
    thinking_tokens = response_meta.get("thinking_tokens")
    if thinking_tokens is None:
        thinking_tokens = extract_thinking_tokens_from_usage(usage)
    input_tokens = response_meta.get("input_tokens")
    output_tokens = response_meta.get("output_tokens")
    if input_tokens is None:
        input_tokens = http_meta.get("input_tokens")
    if output_tokens is None:
        output_tokens = http_meta.get("output_tokens")
    finish = response_meta.get("finish_reason") or http_meta.get("finish_reason")
    content_metadata = http_meta.get("content_metadata")
    observed = _thinking_observed(
        thinking_tokens,
        content_metadata if isinstance(content_metadata, dict) else None,
    )
    cost = actual_cost(input_tokens=input_tokens, output_tokens=output_tokens)
    if cost_record is not None:
        cost["call_record"] = cost_record.to_dict()
        if persist_usage:
            record_call(PROJECT_NAME, cost_record)

    elapsed = http_meta.get("elapsed_ms") or response_meta.get("latency_ms")
    request_id = http_meta.get("request_id") or response_meta.get("request_id")
    http_status = http_meta.get("http_status")
    raw_response_hash = content_hash(raw_text) if raw_text else None
    utilization = (
        round(float(output_tokens) / float(PRODUCTION_MAX_OUTPUT_TOKENS), 6)
        if output_tokens is not None
        else None
    )

    raw_response = {
        "parsed": raw_parsed,
        "text": raw_text,
        "sha256": raw_response_hash,
        "repaired": False,
        "truncated": False,
        "manually_edited": False,
        "translated": False,
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
        "cost": cost,
        "raw_structured_response_sha256": raw_response_hash,
        "raw_text_chars": len(raw_text or ""),
        "provider_metadata": http_meta,
        "airesponse": {k: v for k, v in response_meta.items() if k not in {"text", "parsed"}},
        "secrets_included": False,
        "forensic_path": forensic_path,
        "error": error_text,
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
    }
    if write_artifacts:
        from app.editorial_planner_canary_4a33.writer import persist_raw_evidence

        persist_raw_evidence(
            {
                "raw_response": raw_response,
                "provider_evidence": provider_evidence,
                "response_identity": response_identity,
            },
            root=root,
        )

    source_path = production_source_map_path()
    post_hash = _file_sha256(source_path) if source_path.is_file() else ""
    source_unchanged = post_hash == EXPECTED_SOURCE_MAP_SHA256 and post_hash == digest
    historical_candidate = a3_candidate_path()
    historical_hash = (
        file_sha256(historical_candidate) if historical_candidate.is_file() else ""
    )
    historical_untouched = historical_hash == A3_CANDIDATE_SHA256

    contract = interpret_production_response(
        raw_parsed,
        source_map=source_map,
        source_map_sha256=digest,
        source_map_bytes=len(raw_map),
        source_map_path_value=str(path).replace("\\", "/"),
        raw_text=raw_text,
        canonical_document_language=language_code,
    )
    language = language_audit(
        contract.get("plan"),
        canonical_document_language=language_code,
    )
    chapter_audit = chapter_review(contract.get("plan"), source_map, contract=contract)
    section_audit = section_review(contract.get("plan"), source_map, contract=contract)
    semantic = review_semantics(
        contract.get("plan"),
        source_map,
        contract=contract,
        chapter_audit=chapter_audit,
        section_audit=section_audit,
        language=language,
    )
    planning_estimate = None
    input_budget = identity.get("input_budget") or {}
    if isinstance(input_budget, dict):
        planning_estimate = input_budget.get("planning_input_estimate")
    budget = budget_calibration(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
        actual=cost,
        planning_input_estimate=int(planning_estimate)
        if planning_estimate is not None
        else None,
    )
    thinking_audit = {
        "phase": PHASE,
        "request_configuration": {
            "thinking_mode": THINKING_MODE,
            "effort": None,
            "thinking_budget_tokens": None,
            "thinking_key_in_payload": identity.get("thinking_present_in_payload"),
            "effort_key_in_payload": identity.get("effort_present_in_payload"),
            "temperature_in_payload": identity.get("temperature_present_in_payload"),
            "max_tokens": identity.get("max_tokens"),
            "model": identity.get("model"),
            "thinking_disabled": False,
        },
        "response": {
            "thinking_tokens": thinking_tokens,
            "thinking_tokens_reported": thinking_tokens is not None,
            "thinking_block_present": observed == "YES",
            "output_tokens": output_tokens,
            "finish_reason": finish,
            "content_metadata": content_metadata,
            "raw_usage": usage,
        },
        "OPUS5_PROVIDER_DEFAULT_THINKING_OBSERVED": observed,
        "THINKING_TOKENS": thinking_tokens if thinking_tokens is not None else "unknown",
        "do_not_infer_from_a1_or_a3": True,
        "no_retry_on_thinking_observation": True,
        "historical_a1_synthetic_thinking": 158,
        "historical_a3_production_thinking": 6443,
    }

    coverage = dict(contract.get("idea_coverage") or {})
    refs = dict(contract.get("unknown_refs") or {})
    reuse = dict(contract.get("reuse") or {})
    eligible = _publication_eligible(
        http_success=http_success,
        finish=finish,
        contract=contract,
        semantic=semantic,
        language=language,
        replay=str(contract.get("deterministic_replay") or "FAIL"),
        post_hash=post_hash,
        generate_attempts=guard.generate_attempts,
        post_attempts=post_attempts,
        test_failures=int(new_failures),
    )
    verdict = _classify(
        blocked_precall=False,
        generate_attempts=guard.generate_attempts,
        post_attempts=post_attempts,
        http_success=http_success,
        finish=finish,
        contract=contract,
        semantic=semantic,
        eligible=eligible,
        test_failures=int(new_failures),
    )
    if error_text and http_success is not True:
        verdict = "FAIL"
        eligible = False
    if str(finish or "") == "max_tokens":
        verdict = "FAIL"
        eligible = False
    if language.get("editorial_language_match") != "PASS":
        eligible = False

    validator_status = contract.get("editorial_plan_validator")
    technical = {
        k: v for k, v in contract.items() if k not in {"plan", "transport"}
    }
    coverage_audit = {
        "idea_coverage": coverage.get("idea_coverage"),
        "coverage_complete": coverage.get("coverage_complete"),
        "silent_omissions": coverage.get("silent_omissions"),
        "assigned": coverage.get("assigned"),
        "deferred": coverage.get("deferred"),
        "excluded": coverage.get("excluded"),
        "reused": coverage.get("reused"),
        "extra_section_assignments": coverage.get("extra_section_assignments"),
        "missing_idea_ids": coverage.get("missing_idea_ids"),
        "unknown_refs": refs,
        "reuse": reuse,
        "disposition_reasons": contract.get("disposition_reasons"),
        "dispositions": coverage.get("dispositions"),
        "expected_ideas": EXPECTED_IDEA_COUNT,
        "historical_286_assigned_not_assumed": True,
    }
    publication = {
        "PUBLICATION_ELIGIBLE": eligible,
        "EDITORIAL_LANGUAGE_MATCH": language.get("editorial_language_match"),
        "semantic_review": semantic.get("status"),
        "technical_result": verdict,
        "editorial_plan_json": "NOT PUBLISHED",
        "automatic_publication": False,
        "candidate_written": bool(
            contract.get("plan") and contract.get("canonical_reconstruction") == "PASS"
        ),
        "candidate_is_not_production_publication": True,
        "historical_a3_candidate_untouched": historical_untouched,
        "final_title_approved": False,
        "why": (
            "All technical, language, and semantic gates passed. A.3.3 still does not publish."
            if eligible
            else "Not eligible for publication. No retry. No translation. Preserve candidate."
        ),
    }
    readiness = {
        "READY_FOR_CONTROLLED_EDITORIAL_PLAN_PUBLICATION": eligible,
        "PUBLICATION_ELIGIBLE": eligible,
        "BOOK_GENERATOR": BOOK_GENERATOR,
        "NEXT_ACTION": NEXT_ACTION,
        "NEXT_PHASE_IF_PASS": (
            "PHASE 4A.4 — EDITORIAL PLAN CONTROLLED PUBLICATION + PHASE 4 FREEZE"
            if eligible
            else "HUMAN REVIEW"
        ),
        "why": publication["why"],
    }
    unknown_total = sum(int(refs.get(key) or 0) for key in refs)
    header = {
        **_header_base(identity, tests=tests, new_failures=new_failures),
        "result": verdict,
        "actual_provider_calls": post_attempts,
        "source_map_sha256_post": post_hash,
        "source_map_unchanged": _yn(source_unchanged),
        "http_status": http_status,
        "finish": finish,
        "request_id": request_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens if thinking_tokens is not None else "unknown",
        "output_utilization": utilization,
        "elapsed": elapsed,
        "cost": cost.get("display"),
        "structured_parse": contract.get("structured_parse"),
        "transport_decoder": contract.get("transport_decoder"),
        "handle_validation": contract.get("handle_validation"),
        "canonical_reconstruction": contract.get("canonical_reconstruction"),
        "canonical_candidate_sha256": contract.get("plan_sha256"),
        "chapters": contract.get("chapters"),
        "sections": contract.get("sections"),
        "idea_coverage": coverage.get("idea_coverage"),
        "silent_omissions": coverage.get("silent_omissions"),
        "assigned": coverage.get("assigned"),
        "deferred": coverage.get("deferred"),
        "excluded": coverage.get("excluded"),
        "reused": coverage.get("reused"),
        "unknown_refs_total": unknown_total,
        "unknown_idea_refs": refs.get("unknown_idea_refs"),
        "editorial_language_result": language.get("editorial_language_match"),
        "traceability": contract.get("traceability"),
        "invention_boundary": contract.get("invention_boundary"),
        "uncertainty_preservation": contract.get("uncertainty_preservation"),
        "title_review": semantic.get("primary_question"),
        "book_concept_review": semantic.get("author_intent"),
        "chapter_review": chapter_audit.get("status"),
        "section_review": section_audit.get("status"),
        "editorial_plan_validator": validator_status,
        "deterministic_replay": contract.get("deterministic_replay"),
        "semantic_review": semantic.get("status"),
        "publication_eligible": _yn(eligible),
        "ready_for_controlled_editorial_plan_publication": _yn(eligible),
        "notes": error_text or "",
    }
    candidate = None
    if contract.get("plan") and contract.get("canonical_reconstruction") == "PASS":
        candidate = {
            "plan": contract.get("plan"),
            "sha256": contract.get("plan_sha256"),
            "bytes": contract.get("plan_bytes"),
            "chars": contract.get("plan_chars"),
            "not_production_publication": True,
        }
    bundle = {
        "header": header,
        "precall": identity,
        "raw_response": raw_response,
        "provider_evidence": provider_evidence,
        "response_identity": response_identity,
        "thinking": thinking_audit,
        "budget": budget,
        "language": language,
        "technical": technical,
        "coverage_audit": coverage_audit,
        "chapter_review": chapter_audit,
        "section_review": section_audit,
        "semantic": semantic,
        "publication": publication,
        "readiness": readiness,
        "candidate": candidate,
        "execution": {
            "result": verdict,
            "engine": describe_engine(engine),
            "engine_generate_attempts": guard.generate_attempts,
            "anthropic_post_attempts": post_attempts,
            "retries": 0,
            "error": error_text,
            "forensic_path": forensic_path,
            "editorial_plan_json": "NOT PUBLISHED",
            "book_generator": BOOK_GENERATOR,
            "source_map_unchanged": source_unchanged,
            "historical_a3_candidate_untouched": historical_untouched,
        },
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        from app.editorial_planner_canary_4a33.writer import write_canary_artifacts

        write_canary_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.error = error_text
    result.mode = "EXECUTE"
    return result


__all__ = ["CanaryRunResult", "run_canary"]
