"""
Runner Phase 4B.2.2.

Default: pre-call only, 0 POST.
Real: --execute-real + exact scope. One attempt. No retry. No fallback.
"""

from __future__ import annotations

import hashlib
import json
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
from app.book_generation.payload import build_chapter_request, payload_audit
from app.book_generation.settings import frozen_production_settings
from app.book_generator_canary_4b22.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_PROVIDER_CALLS,
    CANARY_WINDOW_ID,
    CONNECT_TIMEOUT_SECONDS,
    EXPECTED_CLEAN_TRANSCRIPT_SHA256,
    EXPECTED_EDITORIAL_PLAN_SHA256,
    EXPECTED_MAX_OUTPUT,
    EXPECTED_REQUEST_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    FALLBACKS,
    HISTORICAL_4B2_STATUS,
    MAX_ENGINE_GENERATE,
    MODEL,
    NEXT_ACTION,
    PHASE,
    PRODUCTION_CACHE,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    READY_FOR_FULL_REAL_BOOK_GENERATION,
    RETRIES,
    SEMANTIC_STRATEGY,
    STAGE_CANARY,
    TARGET_CHAPTER_ID,
    THINKING_MODE,
    TRANSPORT_VERSION,
    VALIDATOR_VERSION,
)
from app.book_generator_canary_4b22.costing import actual_cost, cost_calibration
from app.book_generator_canary_4b22.engine import (
    CountingAnthropicEngine,
    build_real_canary_engine,
    describe_engine,
)
from app.book_generator_canary_4b22.guard import (
    BookGeneratorCanaryError,
    OneShotCallGuard,
    assert_no_publication,
    validate_authorization_scope,
)
from app.book_generator_canary_4b22.identity import (
    post_input_hashes,
    precall_identity,
    require_precall_identity,
)
from app.book_generator_canary_4b22.paths import (
    canary_lock_path,
    forensic_root,
    production_book_path,
)
from app.book_generator_canary_4b22.report import render_report
from app.book_generator_canary_4b22.review import (
    apply_human_review,
    connective_review,
    default_fidelity_review,
    default_quality_review,
    example_review,
    idea_coverage_review,
    paragraph_inventory,
    paragraph_provenance_review,
    reference_review,
)
from app.book_generator_canary_4b22.validate import interpret_production_response
from app.editorial_planning.pipeline import (
    load_published_editorial_plan,
    load_published_source_map,
)
from app.file_utils import content_hash
from app.source_analysis.errors import MaxRealCallsExceededError


def _consume_lock(*, root: Path | None) -> None:
    path = canary_lock_path(root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise BookGeneratorCanaryError(
            "Canary real-call lock already present — authorization consumed. "
            "NO RETRY."
        )
    path.write_text(
        f"{PHASE}\n{AUTHORIZATION_SCOPE}\nconsumed=1\n",
        encoding="utf-8",
    )


def _yn(value: bool) -> str:
    return "YES" if value else "NO"


def _thinking_observed(thinking_tokens: Any, content_metadata: Mapping | None) -> str:
    blocks = []
    if isinstance(content_metadata, dict):
        blocks = list(content_metadata.get("block_types") or [])
    thinking_blocks = any(str(item).lower() == "thinking" for item in blocks)
    if thinking_tokens is None and not thinking_blocks:
        return "NO"
    try:
        value = int(thinking_tokens) if thinking_tokens is not None else 0
    except (TypeError, ValueError):
        return "YES" if thinking_blocks else "NO"
    if value > 0 or thinking_blocks:
        return "YES"
    return "NO"


@dataclass
class CanaryRunResult:
    mode: str
    authorization_scope: str = ""
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
    hydration = dict(identity.get("hydration") or {})
    cache = dict(identity.get("cache") or {})
    estimate = dict(identity.get("cost_estimate") or {})
    return {
        "authorized_provider_calls": AUTHORIZED_PROVIDER_CALLS,
        "actual_provider_calls": 0,
        "retries": RETRIES,
        "fallbacks": FALLBACKS,
        "historical_4b2_status": HISTORICAL_4B2_STATUS,
        "target_chapter": TARGET_CHAPTER_ID,
        "source_map_sha256_pre": identity.get("source_map_sha256_pre"),
        "source_map_sha256_post": None,
        "editorial_plan_sha256_pre": identity.get("editorial_plan_sha256_pre"),
        "editorial_plan_sha256_post": None,
        "transcript_sha256_pre": identity.get("transcript_sha256_pre"),
        "transcript_sha256_post": None,
        "inputs_unchanged": "n/a",
        "canonical_language": identity.get("canonical_document_language"),
        "model": identity.get("model") or f"{PROVIDER} / {MODEL}",
        "prompt": PROMPT_VERSION,
        "validator": VALIDATOR_VERSION,
        "transport": TRANSPORT_VERSION,
        "schema_changed": "NO",
        "schema_raw_adapted": identity.get("schema_raw_adapted"),
        "schema_sha256": identity.get("schema_sha256"),
        "thinking": THINKING_MODE,
        "max_output": identity.get("recommended_max_output") or EXPECTED_MAX_OUTPUT,
        "expected_request_sha256": EXPECTED_REQUEST_SHA256,
        "request_sha256": identity.get("request_sha256"),
        "request_identity": identity.get("request_identity"),
        "request_determinism": (
            "PASS" if identity.get("request_determinism") else "FAIL"
        ),
        "cache_signature": cache.get("hardened"),
        "chapter_sections_expected": identity.get("expected_chapter_sections"),
        "chapter_ideas_expected": identity.get("expected_chapter_ideas"),
        "hydrated_src_count": hydration.get("hydrated_src_count"),
        "hydrated_chars": hydration.get("hydrated_chars"),
        "context_safety": (
            "PASS" if (identity.get("budget") or {}).get("context_safe") else "FAIL"
        ),
        "estimated_cost": estimate.get("total_cost_usd")
        or estimate.get("total_cost_display"),
        "tests": tests,
        "new_failures": new_failures,
        "book_json": "NOT PUBLISHED",
        "production_cache": PRODUCTION_CACHE,
        "ready_for_full_real_book_generation": "NO",
        "next_action": NEXT_ACTION,
        "semantic_strategy": SEMANTIC_STRATEGY,
    }


def _offline_header(
    identity: Mapping[str, Any], *, tests: str, new_failures: int, result: str
) -> dict[str, Any]:
    post = post_input_hashes()
    source_post = (post.get("source_map") or {}).get("sha256")
    plan_post = (post.get("editorial_plan") or {}).get("sha256")
    transcript_post = (post.get("clean_transcript") or {}).get("sha256")
    unchanged = (
        source_post == identity.get("source_map_sha256_pre")
        and plan_post == identity.get("editorial_plan_sha256_pre")
        and transcript_post == identity.get("transcript_sha256_pre")
        and source_post == EXPECTED_SOURCE_MAP_SHA256
        and plan_post == EXPECTED_EDITORIAL_PLAN_SHA256
        and transcript_post == EXPECTED_CLEAN_TRANSCRIPT_SHA256
    )
    return {
        **_header_base(identity, tests=tests, new_failures=new_failures),
        "result": result,
        "source_map_sha256_post": source_post,
        "editorial_plan_sha256_post": plan_post,
        "transcript_sha256_post": transcript_post,
        "inputs_unchanged": _yn(unchanged),
        "http_status": None,
        "finish": None,
        "request_id": None,
        "input_tokens": None,
        "output_tokens": None,
        "thinking_tokens": None,
        "elapsed": None,
        "actual_cost": None,
        "structured_parse": "n/a",
        "transport_decoder": "n/a",
        "reconstruction": "n/a",
        "local_validator": "n/a",
        "section_coverage": "n/a",
        "section_order": "n/a",
        "idea_coverage": "n/a",
        "silent_idea_omissions": "n/a",
        "unknown_idea_refs": "n/a",
        "unknown_src_refs": "n/a",
        "empty_paragraphs": "n/a",
        "whitespace_paragraphs": "n/a",
        "unsourced_substantive_paragraphs": "n/a",
        "connective_paragraphs": "n/a",
        "unsupported_connective_claims": "n/a",
        "example_like_elements": "n/a",
        "invented_examples": "n/a",
        "invented_references": "n/a",
        "questionable_support": "n/a",
        "unsupported_paragraphs": "n/a",
        "weak_ideas": "n/a",
        "missing_ideas": "n/a",
        "editorial_language": "n/a",
        "source_meaning": "n/a",
        "oral_to_written": "n/a",
        "author_voice": "n/a",
        "uncertainty_preservation": "n/a",
        "repetition_control": "n/a",
        "manuscript_quality": "n/a",
        "deterministic_replay": "n/a",
        "candidate_sha256": None,
        "candidate_file_sha256": None,
        "paragraphs": None,
        "words": None,
        "ready_for_book_generator_production_preflight": "NO",
        "ready_for_independent_semantic_gate_design": "NO",
        "notes": identity.get("block_reason") or "offline pre-call only",
    }


def _clean_pass(
    *,
    http_success: bool | None,
    finish: Any,
    contract: Mapping[str, Any],
    fidelity: Mapping[str, Any],
    quality: Mapping[str, Any],
    provenance: Mapping[str, Any],
    coverage: Mapping[str, Any],
    connective: Mapping[str, Any],
    examples: Mapping[str, Any],
    references: Mapping[str, Any],
    post: Mapping[str, Any],
    identity: Mapping[str, Any],
    generate_attempts: int,
    post_attempts: int,
    test_failures: int,
) -> bool:
    validator = dict(contract.get("local_validator") or {})
    language = dict(contract.get("language") or {})
    finish_ok = str(finish or "") in {"end_turn", "stop"}
    inputs_ok = (
        (post.get("source_map") or {}).get("sha256") == identity.get("source_map_sha256_pre")
        and (post.get("editorial_plan") or {}).get("sha256")
        == identity.get("editorial_plan_sha256_pre")
        and (post.get("clean_transcript") or {}).get("sha256")
        == identity.get("transcript_sha256_pre")
    )
    voice_ok = fidelity.get("author_voice") in {"STRONG", "ACCEPTABLE"}
    return (
        http_success is True
        and finish_ok
        and generate_attempts == 1
        and post_attempts == 1
        and identity.get("request_identity") == "MATCH"
        and contract.get("structured_parse") == "PASS"
        and contract.get("transport_decoder") == "PASS"
        and contract.get("canonical_reconstruction") == "PASS"
        and contract.get("section_coverage") == "PASS"
        and contract.get("section_order") == "PASS"
        and int(contract.get("silent_idea_omissions") or 0) == 0
        and int(contract.get("unknown_idea_refs") or 0) == 0
        and int(contract.get("unknown_src_refs") or 0) == 0
        and int(contract.get("empty_paragraphs") or 0) == 0
        and int(contract.get("whitespace_paragraphs") or 0) == 0
        and int(contract.get("unsourced_substantive_paragraphs") or 0) == 0
        and int(connective.get("unsupported_connective_claims") or 0) == 0
        and int(examples.get("invented_examples") or 0) == 0
        and int(references.get("invented_references") or 0) == 0
        and int(provenance.get("QUESTIONABLE_SUPPORT") or 0) == 0
        and int(provenance.get("UNSUPPORTED") or 0) == 0
        and int(coverage.get("WEAKLY_REPRESENTED") or 0) == 0
        and int(coverage.get("MISSING") or 0) == 0
        and language.get("status") == "PASS"
        and validator.get("status") == "PASS"
        and contract.get("deterministic_replay") == "PASS"
        and fidelity.get("source_meaning") == "PASS"
        and fidelity.get("oral_to_written") == "PASS"
        and voice_ok
        and fidelity.get("uncertainty_preservation") == "PASS"
        and fidelity.get("repetition_control") == "PASS"
        and quality.get("status") == "PASS"
        and inputs_ok
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
    fidelity: Mapping[str, Any],
    clean: bool,
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
    if clean:
        return "PASS"
    technical = (
        contract.get("structured_parse") == "PASS"
        and contract.get("transport_decoder") == "PASS"
        and contract.get("canonical_reconstruction") == "PASS"
        and contract.get("section_coverage") == "PASS"
        and (contract.get("local_validator") or {}).get("status") in {"PASS", "REVIEW"}
        and str((contract.get("language") or {}).get("status") or "") == "PASS"
        and int(contract.get("empty_paragraphs") or 0) == 0
        and int(contract.get("whitespace_paragraphs") or 0) == 0
    )
    if technical and fidelity.get("status") in {"REVIEW_REQUIRED", "REVIEW"}:
        return "PARTIAL"
    return "FAIL"


def _strip_payload(identity: Mapping[str, Any]) -> dict[str, Any]:
    request = dict(identity.get("request") or {})
    request.pop("local_input_token_estimate", None)
    return {
        "phase": PHASE,
        "target_chapter_id": identity.get("target_chapter_id"),
        "prompt_version": PROMPT_VERSION,
        "historical_prompt_version": identity.get("request", {}).get(
            "historical_prompt_version"
        ),
        "request_sha256": identity.get("request_sha256"),
        "request_sha256_repeat": (identity.get("request") or {}).get(
            "request_sha256_repeat"
        ),
        "determinism": identity.get("request_determinism"),
        "request_identity": identity.get("request_identity"),
        "expected_request_sha256": identity.get("expected_request_sha256"),
        "historical_request_sha256": identity.get("historical_request_sha256"),
        "future_differs_from_historical": identity.get("request_differs_from_historical"),
        "chars": (identity.get("request") or {}).get("chars"),
        "bytes": (identity.get("request") or {}).get("bytes"),
        "max_tokens": (identity.get("payload") or {}).get("max_tokens"),
        "model": (identity.get("payload") or {}).get("model"),
        "thinking_payload": (identity.get("payload") or {}).get("thinking"),
        "content_audit": identity.get("content_audit"),
        "cache": identity.get("cache"),
        "request": request,
        "secrets_included": False,
        "http_sent": False,
        "production_request_builder": True,
    }


def _offline_bundle(
    identity: Mapping[str, Any],
    *,
    result: CanaryRunResult,
    tests: str,
    new_failures: int,
    verdict: str,
) -> dict[str, Any]:
    header = _offline_header(
        identity, tests=tests, new_failures=new_failures, result=verdict
    )
    readiness = {
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": False,
        "READY_FOR_INDEPENDENT_SEMANTIC_GATE_DESIGN": False,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": READY_FOR_FULL_REAL_BOOK_GENERATION,
        "NEXT_ACTION": NEXT_ACTION,
        "why": identity.get("block_reason") or "pre-call only; provider not called",
        "cached_as_production": False,
        "book_json": "NOT PUBLISHED",
        "production_cache": PRODUCTION_CACHE,
        "validated_audit_candidate": False,
        "phase_5": False,
        "terra_called": False,
    }
    evidence = identity.get("evidence") or {}
    bundle = {
        "header": header,
        "precall": {k: v for k, v in identity.items() if k not in {"payload", "evidence"}},
        "evidence_bundle": evidence,
        "hydration": identity.get("hydration"),
        "request_identity": _strip_payload(identity),
        "readiness": readiness,
        "execution": {
            "mode": result.mode,
            "actual_provider_calls": 0,
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
    tests: str = "not-run-yet",
    new_failures: int = 0,
    fidelity_overlay: Mapping[str, Any] | None = None,
    quality_overlay: Mapping[str, Any] | None = None,
    human_review: Mapping[str, Any] | None = None,
) -> CanaryRunResult:
    result = CanaryRunResult(
        mode="DRY_RUN" if (dry_run or not execute_real) else "EXECUTE",
        authorization_scope=str(authorization_scope or ""),
    )
    try:
        scope = validate_authorization_scope(authorization_scope)
        result.authorization_scope = scope
        assert_no_publication(production_book_path())
    except BookGeneratorCanaryError as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if execute_real and dry_run:
        result.error = "--dry-run and --execute-real are exclusive."
        result.mode = "REJECTED"
        return result

    identity = precall_identity(root=root)
    blocked = bool(identity.get("blocked_precall"))

    if blocked or not execute_real:
        verdict = "BLOCKED_PRECALL" if blocked else "DRY_RUN"
        bundle = _offline_bundle(
            identity,
            result=result,
            tests=tests,
            new_failures=new_failures,
            verdict=verdict,
        )
        if write_artifacts:
            from app.book_generator_canary_4b22.writer import write_canary_artifacts

            write_canary_artifacts(bundle, root=root)
        result.bundle = bundle
        result.accepted = not blocked
        if blocked:
            result.error = str(identity.get("block_reason"))
        return result

    try:
        require_precall_identity(identity, root=root)
    except BookGeneratorCanaryError as exc:
        result.error = str(exc)
        result.mode = "BLOCKED_PRECALL"
        bundle = _offline_bundle(
            identity,
            result=result,
            tests=tests,
            new_failures=new_failures,
            verdict="BLOCKED_PRECALL",
        )
        if write_artifacts:
            from app.book_generator_canary_4b22.writer import write_canary_artifacts

            write_canary_artifacts(bundle, root=root)
        result.bundle = bundle
        return result

    if engine is None and not allow_real_provider:
        result.accepted = False
        result.error = "exécution réelle refusée : allow_real_provider=false."
        result.mode = "REJECTED"
        return result

    if engine is None:
        try:
            engine = build_real_canary_engine()
        except BookGeneratorCanaryError as exc:
            result.accepted = False
            result.error = str(exc)
            result.mode = "REJECTED"
            return result

    plan, _plan_raw, _plan_digest, _plan_path = load_published_editorial_plan(PROJECT_NAME)
    source_map, _map_raw, _map_digest, _map_path = load_published_source_map(PROJECT_NAME)
    chapter = next(item for item in plan.chapters if item.chapter_id == TARGET_CHAPTER_ID)
    evidence = dict(identity.get("evidence") or {})
    settings = frozen_production_settings()
    max_output = int(identity.get("recommended_max_output") or EXPECTED_MAX_OUTPUT)
    rebuilt = payload_audit(
        evidence,
        settings=settings,
        max_output_tokens=max_output,
        prompt_version=PROMPT_VERSION,
    )
    if rebuilt["payload_sha256"] != EXPECTED_REQUEST_SHA256:
        identity = dict(identity)
        identity["blocked_precall"] = True
        identity["block_reason"] = "request_sha256"
        identity["block_reasons"] = list(identity.get("block_reasons") or []) + [
            "request_sha256"
        ]
        result.error = "BLOCKED_PRECALL: rebuilt request SHA-256 mismatch"
        result.mode = "BLOCKED_PRECALL"
        bundle = _offline_bundle(
            identity,
            result=result,
            tests=tests,
            new_failures=new_failures,
            verdict="BLOCKED_PRECALL",
        )
        if write_artifacts:
            from app.book_generator_canary_4b22.writer import write_canary_artifacts

            write_canary_artifacts(bundle, root=root)
        result.bundle = bundle
        return result

    request = build_chapter_request(
        evidence,
        settings=settings,
        max_output_tokens=max_output,
        prompt_version=PROMPT_VERSION,
    )
    forensic_dir = forensic_root(root=root)
    forensic_dir.mkdir(parents=True, exist_ok=True)
    guard = OneShotCallGuard(max_calls=MAX_ENGINE_GENERATE)
    identity_hash = str(identity.get("request_sha256") or EXPECTED_REQUEST_SHA256)
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

    raw_response = {
        "parsed": raw_parsed,
        "text": raw_text,
        "sha256": raw_response_hash,
        "repaired": False,
        "truncated": False,
        "manually_edited": False,
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
        "thinking_block_present": observed,
        "cost": cost,
        "raw_structured_response_sha256": raw_response_hash,
        "raw_text_chars": len(raw_text or ""),
        "provider_metadata": http_meta,
        "airesponse": {
            k: v for k, v in response_meta.items() if k not in {"text", "parsed"}
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
        "thinking_block_present": observed,
        "cost": cost,
        "raw_response_sha256": raw_response_hash,
        "provider_metadata": http_meta,
        "secrets_included": False,
        "forensic_path": forensic_path,
        "error": error_text,
        "retries": 0,
        "fallbacks": 0,
        "stage": STAGE_CANARY,
    }
    raw_bundle = {
        "raw_response": raw_response,
        "provider_evidence": provider_evidence,
        "response_identity": response_identity,
    }
    if write_artifacts:
        from app.book_generator_canary_4b22.writer import persist_raw_evidence

        persist_raw_evidence(raw_bundle, root=root)

    post = post_input_hashes()
    source_unchanged = (
        (post.get("source_map") or {}).get("sha256")
        == identity.get("source_map_sha256_pre")
        == EXPECTED_SOURCE_MAP_SHA256
    )
    plan_unchanged = (
        (post.get("editorial_plan") or {}).get("sha256")
        == identity.get("editorial_plan_sha256_pre")
        == EXPECTED_EDITORIAL_PLAN_SHA256
    )
    transcript_unchanged = (
        (post.get("clean_transcript") or {}).get("sha256")
        == identity.get("transcript_sha256_pre")
        == EXPECTED_CLEAN_TRANSCRIPT_SHA256
    )
    inputs_unchanged = source_unchanged and plan_unchanged and transcript_unchanged

    contract = interpret_production_response(
        raw_parsed,
        plan=plan,
        source_map=source_map,
        chapter=chapter,
        language=str(identity.get("canonical_document_language") or "en"),
        allowed_handles=list(evidence.get("allowed") or []),
        raw_text=raw_text,
        provider_raw_sha256=raw_response_hash or "",
    )
    candidate_dict = contract.get("candidate")
    coverage = idea_coverage_review(candidate_dict or {}, chapter, evidence)
    provenance = paragraph_provenance_review(
        candidate_dict or {}, evidence, source_map
    )
    inventory = paragraph_inventory(candidate_dict, provenance=provenance)
    connective = connective_review(candidate_dict, evidence)
    examples = example_review(candidate_dict, evidence)
    references = reference_review(candidate_dict, evidence)
    fidelity = default_fidelity_review(
        candidate_dict,
        chapter=chapter,
        evidence=evidence,
        source_map=source_map,
        provenance=provenance,
        coverage=coverage,
        language=dict(contract.get("language") or {}),
    )
    if fidelity_overlay:
        fidelity = {**fidelity, **dict(fidelity_overlay)}
    quality = default_quality_review(
        candidate_dict, fidelity=fidelity, provenance=provenance
    )
    if quality_overlay:
        quality = {**quality, **dict(quality_overlay)}
    if human_review:
        applied = apply_human_review(
            inventory=inventory,
            connective=connective,
            examples=examples,
            references=references,
            coverage=coverage,
            fidelity=fidelity,
            quality=quality,
            overlay=human_review,
        )
        inventory = applied["inventory"]
        connective = applied["connective"]
        examples = applied["examples"]
        references = applied["references"]
        coverage = applied["coverage"]
        fidelity = applied["fidelity"]
        quality = applied["quality"]

    budget = cost_calibration(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
        actual=cost,
        estimate=identity.get("cost_estimate"),
        max_output=max_output,
    )
    clean = _clean_pass(
        http_success=http_success,
        finish=finish,
        contract=contract,
        fidelity=fidelity,
        quality=quality,
        provenance=provenance,
        coverage=coverage,
        connective=connective,
        examples=examples,
        references=references,
        post=post,
        identity=identity,
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
        fidelity=fidelity,
        clean=clean,
    )
    if error_text and http_success is not True:
        verdict = "FAIL"
        clean = False
    if str(finish or "") == "max_tokens":
        verdict = "FAIL"
        clean = False
    if int(contract.get("empty_paragraphs") or 0) > 0:
        verdict = "FAIL"
        clean = False

    ready_preflight = verdict == "PASS"
    readiness = {
        "READY_FOR_BOOK_GENERATOR_PRODUCTION_PREFLIGHT": ready_preflight,
        "READY_FOR_INDEPENDENT_SEMANTIC_GATE_DESIGN": ready_preflight,
        "READY_FOR_FULL_REAL_BOOK_GENERATION": False,
        "NEXT_ACTION": NEXT_ACTION,
        "why": (
            "Clean 4B.2.2 PASS. Next phase combines exact all-chapter "
            "production preflight, independent semantic-gate contract design, "
            "and a later decision on promoting this VALIDATED_AUDIT_CANDIDATE. "
            "Do not start 19 production calls."
            if ready_preflight
            else "Not ready for production preflight. Use saved evidence. No retry."
        ),
        "cached_as_production": False,
        "candidate_status": "VALIDATED_AUDIT_CANDIDATE" if ready_preflight else "NOT_ACCEPTED",
        "book_json": "NOT PUBLISHED",
        "production_cache": PRODUCTION_CACHE,
        "phase_5": False,
        "terra_called": False,
        "historical_4b2_status": HISTORICAL_4B2_STATUS,
        "semantic_strategy": SEMANTIC_STRATEGY,
    }
    structural = {
        k: v
        for k, v in contract.items()
        if k not in {"candidate", "transport"}
    }
    language_audit = dict(contract.get("language") or {})
    candidate_payload = None
    candidate_file_sha = None
    if candidate_dict and contract.get("canonical_reconstruction") == "PASS":
        rendered = json.dumps(candidate_dict, ensure_ascii=False, sort_keys=True)
        candidate_file_sha = hashlib.sha256(
            json.dumps(candidate_dict, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        candidate_payload = {
            "chapter": candidate_dict,
            "sha256": contract.get("candidate_sha256"),
            "file_sha256": candidate_file_sha,
            "bytes": contract.get("candidate_bytes"),
            "chars": contract.get("candidate_chars"),
            "paragraph_count": contract.get("paragraph_count"),
            "word_count": contract.get("word_count"),
            "not_production_cache": True,
            "global_paragraph_ids_not_assigned": True,
            "status": "VALIDATED_AUDIT_CANDIDATE" if ready_preflight else "AUDIT_ONLY",
            "canonical_chars": len(rendered),
        }
    header = {
        **_header_base(identity, tests=tests, new_failures=new_failures),
        "result": verdict,
        "actual_provider_calls": post_attempts,
        "source_map_sha256_post": (post.get("source_map") or {}).get("sha256"),
        "editorial_plan_sha256_post": (post.get("editorial_plan") or {}).get("sha256"),
        "transcript_sha256_post": (post.get("clean_transcript") or {}).get("sha256"),
        "inputs_unchanged": _yn(inputs_unchanged),
        "http_status": http_status,
        "finish": finish,
        "request_id": request_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens if thinking_tokens is not None else "unknown",
        "elapsed": elapsed,
        "actual_cost": cost.get("display"),
        "structured_parse": contract.get("structured_parse"),
        "transport_decoder": contract.get("transport_decoder"),
        "reconstruction": contract.get("canonical_reconstruction"),
        "local_validator": (contract.get("local_validator") or {}).get("status"),
        "section_coverage": contract.get("section_coverage"),
        "section_order": contract.get("section_order"),
        "idea_coverage": contract.get("idea_coverage"),
        "silent_idea_omissions": contract.get("silent_idea_omissions"),
        "unknown_idea_refs": contract.get("unknown_idea_refs"),
        "unknown_src_refs": contract.get("unknown_src_refs"),
        "empty_paragraphs": contract.get("empty_paragraphs"),
        "whitespace_paragraphs": contract.get("whitespace_paragraphs"),
        "unsourced_substantive_paragraphs": contract.get(
            "unsourced_substantive_paragraphs"
        ),
        "connective_paragraphs": contract.get("connective_paragraphs"),
        "unsupported_connective_claims": connective.get("unsupported_connective_claims"),
        "example_like_elements": examples.get("count"),
        "invented_examples": examples.get("invented_examples"),
        "invented_references": references.get("invented_references"),
        "questionable_support": provenance.get("QUESTIONABLE_SUPPORT"),
        "unsupported_paragraphs": provenance.get("UNSUPPORTED"),
        "weak_ideas": coverage.get("WEAKLY_REPRESENTED"),
        "missing_ideas": coverage.get("MISSING"),
        "editorial_language": language_audit.get("status"),
        "source_meaning": fidelity.get("source_meaning"),
        "oral_to_written": fidelity.get("oral_to_written"),
        "author_voice": fidelity.get("author_voice"),
        "uncertainty_preservation": fidelity.get("uncertainty_preservation"),
        "repetition_control": fidelity.get("repetition_control"),
        "manuscript_quality": quality.get("status"),
        "deterministic_replay": contract.get("deterministic_replay"),
        "candidate_sha256": contract.get("candidate_sha256"),
        "candidate_file_sha256": candidate_file_sha,
        "paragraphs": contract.get("paragraph_count"),
        "words": contract.get("word_count"),
        "ready_for_book_generator_production_preflight": _yn(ready_preflight),
        "ready_for_independent_semantic_gate_design": _yn(ready_preflight),
        "ready_for_full_real_book_generation": "NO",
        "notes": error_text or "",
        "thinking_block_present": observed,
        "connect_timeout": CONNECT_TIMEOUT_SECONDS,
        "read_timeout": READ_TIMEOUT_SECONDS,
    }
    bundle = {
        "header": header,
        "precall": {k: v for k, v in identity.items() if k not in {"payload", "evidence"}},
        "evidence_bundle": evidence,
        "hydration": identity.get("hydration"),
        "request_identity": _strip_payload(identity),
        "raw_response": raw_response,
        "provider_evidence": provider_evidence,
        "response_identity": response_identity,
        "structural": structural,
        "paragraph_inventory": inventory,
        "connective": connective,
        "examples": examples,
        "references": references,
        "coverage_audit": coverage,
        "provenance": provenance,
        "language": language_audit,
        "fidelity": fidelity,
        "quality": quality,
        "cost": budget,
        "readiness": readiness,
        "candidate": candidate_payload,
        "execution": {
            "result": verdict,
            "engine": describe_engine(engine),
            "engine_generate_attempts": guard.generate_attempts,
            "anthropic_post_attempts": post_attempts,
            "retries": 0,
            "fallbacks": 0,
            "error": error_text,
            "forensic_path": forensic_path,
            "book_json": "NOT PUBLISHED",
            "production_cache": PRODUCTION_CACHE,
            "inputs_unchanged": inputs_unchanged,
            "stage": STAGE_CANARY,
        },
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        from app.book_generator_canary_4b22.writer import write_canary_artifacts

        write_canary_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.error = error_text
    result.mode = "EXECUTE"
    return result


__all__ = ["CanaryRunResult", "run_canary"]
