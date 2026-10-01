"""
Runner Phase 4A.1.

Défaut : pré-appel only, 0 POST.
Réel : --execute-real + scope exact. Une tentative. Pas de retry.
"""

from __future__ import annotations

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
from app.editorial_planner_canary_4a1.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_WINDOW_ID,
    MAX_ANTHROPIC_POST,
    MAX_ENGINE_GENERATE,
    MODEL,
    PHASE,
    PHASE_4A_ADAPTED_SCHEMA_BYTES,
    PHASE_4A_ADAPTED_SCHEMA_SHA256,
    PHASE_4A_CONSERVATIVE_OUTPUT_TOKENS,
    PHASE_4A_EXPECTED_OUTPUT_TOKENS,
    PHASE_4A_HARD_OUTPUT_TOKENS,
    PHASE_4A_RAW_SCHEMA_BYTES,
    PHASE_4A_RAW_SCHEMA_SHA256,
    PRODUCTION_OUTPUT_BUDGET_REVIEW_REQUIRED,
    PRODUCTION_PROPOSED_MAX_OUTPUT,
    PROMPT_VERSION,
    PROVIDER,
    RETRIES,
    STAGE_CANARY,
    TRANSPORT_VERSION,
)
from app.editorial_planner_canary_4a1.costing import actual_cost
from app.editorial_planner_canary_4a1.engine import (
    CountingAnthropicEngine,
    build_real_canary_engine,
    credential_available,
    describe_engine,
)
from app.editorial_planner_canary_4a1.fixture import (
    build_synthetic_source_map,
    fixture_audit,
)
from app.editorial_planner_canary_4a1.guard import (
    OneShotCallGuard,
    PlannerCanaryError,
    assert_synthetic_source_map,
    validate_authorization_scope,
)
from app.editorial_planner_canary_4a1.identity import (
    precall_identity,
    require_precall_identity,
)
from app.editorial_planner_canary_4a1.payload import (
    build_canary_request,
    canary_settings,
    payload_audit,
)
from app.editorial_planner_canary_4a1.paths import (
    canary_lock_path,
    forensic_root,
    production_editorial_plan_path,
    production_source_map_path,
)
from app.editorial_planner_canary_4a1.report import render_report
from app.editorial_planner_canary_4a1.semantic import review_semantics
from app.editorial_planner_canary_4a1.validate import interpret_canary_response
from app.editorial_planning.pipeline import signature_for_source_map
from app.editorial_planning.prompt import prompt_bundle
from app.editorial_planning.schema import schema_identity
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


def _source_map_bytes(source_map) -> tuple[bytes, str]:
    raw = json.dumps(source_map.to_dict(), ensure_ascii=False, sort_keys=True).encode(
        "utf-8"
    )
    return raw, content_hash(raw.decode("utf-8"))


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


def production_budget_status() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "expected_output_tokens": PHASE_4A_EXPECTED_OUTPUT_TOKENS,
        "conservative_output_tokens": PHASE_4A_CONSERVATIVE_OUTPUT_TOKENS,
        "hard_output_tokens": PHASE_4A_HARD_OUTPUT_TOKENS,
        "proposed_max_output": PRODUCTION_PROPOSED_MAX_OUTPUT,
        "PRODUCTION_OUTPUT_BUDGET_REVIEW_REQUIRED": (
            "YES" if PRODUCTION_OUTPUT_BUDGET_REVIEW_REQUIRED else "NO"
        ),
        "reason": (
            f"hard estimate {PHASE_4A_HARD_OUTPUT_TOKENS} > "
            f"proposed max_output {PRODUCTION_PROPOSED_MAX_OUTPUT}"
        ),
        "canary_max_output_tokens": CANARY_MAX_OUTPUT_TOKENS,
        "canary_max_is_not_production_max": True,
        "do_not_authorize_production_from_canary": True,
        "do_not_extrapolate_production_cost_from_canary": True,
    }


def cache_signature_audit(source_map_sha256: str) -> dict[str, Any]:
    prompt = prompt_bundle()
    schema = schema_identity()
    settings = canary_settings()
    signature, inputs = signature_for_source_map(
        source_map_sha256,
        prompt["prompt_sha256"],
        schema["raw_schema_sha256"],
        settings,
    )
    signature2, _ = signature_for_source_map(
        source_map_sha256,
        prompt["prompt_sha256"],
        schema["raw_schema_sha256"],
        settings,
    )
    production_settings_token = PRODUCTION_PROPOSED_MAX_OUTPUT
    return {
        "signature": signature,
        "deterministic": signature == signature2,
        "inputs": inputs.to_dict(),
        "canary_max_output_tokens": settings.max_output_tokens,
        "production_max_output_tokens": production_settings_token,
        "distinct_from_production_max": (
            settings.max_output_tokens != production_settings_token
        ),
        "cache_populated_for_production": False,
        "note": (
            "Synthetic canary signature includes canary max_output=4096 and "
            "synthetic SourceMap hash. It must not be stored as a production "
            "pastoral planning cache hit."
        ),
    }


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


def build_offline_bundle() -> dict[str, Any]:
    source_map = build_synthetic_source_map()
    assert_synthetic_source_map(source_map)
    fixture = fixture_audit(source_map)
    identity = precall_identity()
    payload = payload_audit(source_map)
    raw, digest = _source_map_bytes(source_map)
    cache = cache_signature_audit(digest)
    budget = production_budget_status()
    blocked = bool(identity.get("blocked_precall"))
    return {
        "source_map": source_map,
        "source_map_bytes": raw,
        "source_map_sha256": digest,
        "precall": {
            "phase": PHASE,
            "blocked_precall": blocked,
            **identity,
            "payload_keys": payload.get("payload_keys"),
            "thinking_present_in_payload": payload.get("thinking_present"),
            "effort_present_in_payload": payload.get("effort_present"),
            "temperature_present_in_payload": payload.get("temperature_present"),
            "max_tokens": payload.get("max_tokens"),
            "model": payload.get("model"),
            "cache": cache,
            "production_source_map_path_exists": production_source_map_path().is_file(),
            "production_source_map_included_in_request": False,
        },
        "fixture": fixture,
        "payload_audit": payload,
        "budget": budget,
        "cache": cache,
    }


def _classify(
    *,
    blocked_precall: bool,
    generate_attempts: int,
    post_attempts: int,
    http_success: bool | None,
    contract: Mapping[str, Any],
    semantic: Mapping[str, Any],
    retries: int,
    production_sent: bool,
    test_failures: int,
) -> str:
    if blocked_precall and generate_attempts == 0:
        return "BLOCKED_PRECALL"
    if production_sent or retries != 0 or generate_attempts > 1 or post_attempts > 1:
        return "FAIL"
    grammar = http_success is True and contract.get("structured_parse") == "PASS"
    validator = contract.get("editorial_plan_validator")
    validator_ok = validator in {"PASS", "REVIEW"} and not contract.get(
        "validator_hard_fail"
    )
    contract_ok = (
        grammar
        and contract.get("transport_decoder") == "PASS"
        and contract.get("handle_validation") == "PASS"
        and contract.get("canonical_reconstruction") == "PASS"
        and contract.get("canonical_ids") == "PASS"
        and contract.get("hierarchy") == "PASS"
        and contract.get("traceability") == "PASS"
        and contract.get("invention_boundary") == "PASS"
        and contract.get("uncertainty_preservation") == "PASS"
        and contract.get("deterministic_replay") == "PASS"
        and bool((contract.get("idea_coverage") or {}).get("coverage_complete"))
        and (contract.get("idea_coverage") or {}).get("silent_omissions") == 0
        and all(
            int((contract.get("unknown_refs") or {}).get(key) or 0) == 0
            for key in (
                "unknown_idea_refs",
                "unknown_topic_refs",
                "unknown_example_refs",
                "unknown_reference_refs",
                "unknown_uncertainty_refs",
            )
        )
        and validator_ok
        and semantic.get("status") == "PASS"
        and test_failures == 0
    )
    if generate_attempts != 1:
        return "FAIL"
    if not grammar:
        return "FAIL"
    if contract_ok:
        return "PASS"
    if http_success:
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
    except PlannerCanaryError as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        return result

    if execute_real and dry_run:
        result.error = "--dry-run and --execute-real are exclusive."
        result.mode = "REJECTED"
        return result

    offline = build_offline_bundle()
    identity = offline["precall"]
    source_map = offline["source_map"]
    blocked = bool(identity.get("blocked_precall"))

    header_base = {
        "authorized_provider_calls": 1,
        "actual_provider_calls": 0,
        "retries": RETRIES,
        "production_data_sent": "NO",
        "real_editorial_planning": "NO",
        "provider": "Anthropic",
        "model": MODEL,
        "prompt": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "schema_raw_adapted": f"{PHASE_4A_RAW_SCHEMA_BYTES} / {PHASE_4A_ADAPTED_SCHEMA_BYTES}",
        "schema_hash": PHASE_4A_ADAPTED_SCHEMA_SHA256,
        "schema_identity": identity.get("schema_identity"),
        "thinking_mode": "provider_default",
        "effort": "none",
        "budget_tokens": "none",
        "canary_max_output": CANARY_MAX_OUTPUT_TOKENS,
        "production_expected_output": PHASE_4A_EXPECTED_OUTPUT_TOKENS,
        "production_conservative_output": PHASE_4A_CONSERVATIVE_OUTPUT_TOKENS,
        "production_hard_output": PHASE_4A_HARD_OUTPUT_TOKENS,
        "proposed_production_max_output": PRODUCTION_PROPOSED_MAX_OUTPUT,
        "production_output_budget_review_required": "YES",
        "tests": tests,
        "new_failures": new_failures,
        "ready_for_real_editorial_planner_call": "NO",
    }

    if blocked or not execute_real:
        verdict = "BLOCKED_PRECALL" if blocked else "DRY_RUN"
        header = {
            **header_base,
            "result": verdict if blocked else "DRY_RUN",
            "http_status": None,
            "finish": None,
            "request_id": None,
            "input_tokens": None,
            "output_tokens": None,
            "thinking_tokens": None,
            "opus5_thinking_observed": "NOT_EXPOSED",
            "elapsed": None,
            "cost": None,
            "structured_parse": "n/a",
            "transport_decoder": "n/a",
            "handle_validation": "n/a",
            "canonical_reconstruction": "n/a",
            "canonical_ids": "n/a",
            "hierarchy": "n/a",
            "chapters": None,
            "sections": None,
            "synthetic_ideas": offline["fixture"]["inventory"]["ideas"],
            "idea_coverage": "n/a",
            "silent_omissions": "n/a",
            "assigned": None,
            "deferred": None,
            "excluded": None,
            "reused": None,
            "unknown_idea_refs": "n/a",
            "unknown_topic_refs": "n/a",
            "unknown_example_refs": "n/a",
            "unknown_reference_refs": "n/a",
            "unknown_uncertainty_refs": "n/a",
            "traceability": "n/a",
            "invention_boundary": "n/a",
            "uncertainty_preservation": "n/a",
            "editorial_plan_validator": "n/a",
            "deterministic_replay": "n/a",
            "semantic_canary_review": "n/a",
            "grammar_proof": "n/a" if blocked else "NOT_RUN",
            "contract_canary": "n/a" if blocked else "NOT_RUN",
            "ready_for_production_preflight": "NO",
            "notes": identity.get("block_reason") or "offline pre-call only",
        }
        readiness = {
            "EDITORIAL_PLANNER_GRAMMAR_PROOF": header["grammar_proof"],
            "EDITORIAL_PLANNER_CONTRACT_CANARY": header["contract_canary"],
            "READY_FOR_EDITORIAL_PLANNER_PRODUCTION_PREFLIGHT": False,
            "READY_FOR_REAL_EDITORIAL_PLANNER_CALL": False,
            "NEXT_ACTION": "HUMAN REVIEW",
        }
        bundle = {
            "header": header,
            "precall": identity,
            "fixture": offline["fixture"],
            "request_payload": {
                "secrets_included": False,
                **{k: v for k, v in offline["payload_audit"].items() if k != "payload"},
                "payload": offline["payload_audit"].get("payload"),
            },
            "budget": offline["budget"],
            "readiness": readiness,
            "execution": {
                "mode": result.mode,
                "actual_provider_calls": 0,
                "retries": 0,
            },
            "report_text": render_report({"header": header}),
        }
        if write_artifacts:
            from app.editorial_planner_canary_4a1.writer import write_canary_artifacts

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

    request = build_canary_request(source_map)
    payload = offline["payload_audit"]
    forensic_dir = forensic_root(root=root)
    forensic_dir.mkdir(parents=True, exist_ok=True)
    guard = OneShotCallGuard(max_calls=MAX_ENGINE_GENERATE)
    identity_hash = (offline["cache"] or {}).get("signature") or content_hash(
        offline["source_map_sha256"]
    )
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
                    model=getattr(getattr(exc, "response", None), "model", None)
                    or MODEL,
                    stage=request.stage,
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
                    forensic_path = envelope.forensic_path
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
                    analysis_signature=identity_hash,
                )
                envelope = getattr(exc, "http_envelope", None) or current_http_envelope()
                if envelope is not None:
                    http_meta = envelope.compact_metadata()
                    forensic_path = envelope.forensic_path
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
                    forensic_path = envelope.forensic_path
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
    observed = _thinking_observed(thinking_tokens, content_metadata if isinstance(content_metadata, dict) else None)
    cost = actual_cost(input_tokens=input_tokens, output_tokens=output_tokens)
    if cost_record is not None:
        cost["call_record"] = cost_record.to_dict()

    contract = interpret_canary_response(
        raw_parsed,
        source_map=source_map,
        source_map_sha256=offline["source_map_sha256"],
        source_map_bytes=len(offline["source_map_bytes"]),
        raw_text=raw_text,
    )
    semantic = review_semantics(
        contract.get("plan"),
        source_map,
        contract=contract,
    )
    coverage = dict(contract.get("idea_coverage") or {})
    refs = dict(contract.get("unknown_refs") or {})
    grammar_proof = (
        "PASS"
        if http_success is True and contract.get("structured_parse") == "PASS"
        else "FAIL"
    )
    contract_canary = (
        "PASS"
        if (
            grammar_proof == "PASS"
            and contract.get("transport_decoder") == "PASS"
            and contract.get("canonical_reconstruction") == "PASS"
            and contract.get("deterministic_replay") == "PASS"
            and coverage.get("coverage_complete")
            and semantic.get("status") == "PASS"
            and not contract.get("validator_hard_fail")
        )
        else "FAIL"
    )
    verdict = _classify(
        blocked_precall=False,
        generate_attempts=guard.generate_attempts,
        post_attempts=post_attempts,
        http_success=http_success,
        contract=contract,
        semantic=semantic,
        retries=0,
        production_sent=False,
        test_failures=int(new_failures),
    )
    if error_text and http_success is not True:
        verdict = "FAIL"
        grammar_proof = "FAIL"
        contract_canary = "FAIL"

    ready_preflight = verdict == "PASS"
    elapsed = http_meta.get("elapsed_ms") or response_meta.get("latency_ms")
    request_id = http_meta.get("request_id") or response_meta.get("request_id")
    http_status = http_meta.get("http_status")
    raw_response_hash = content_hash(raw_text) if raw_text else None

    thinking_audit = {
        "phase": PHASE,
        "request_configuration": {
            "thinking_mode": "provider_default",
            "effort": None,
            "thinking_budget_tokens": None,
            "thinking_key_in_payload": payload.get("thinking_present"),
            "effort_key_in_payload": payload.get("effort_present"),
            "temperature_in_payload": payload.get("temperature_present"),
            "max_tokens": payload.get("max_tokens"),
            "model": payload.get("model"),
            "sonnet5_thinking_disabled_copied": False,
        },
        "response": {
            "thinking_tokens": thinking_tokens,
            "thinking_tokens_reported": thinking_tokens is not None,
            "output_tokens": output_tokens,
            "finish_reason": finish,
            "content_metadata": content_metadata,
            "raw_usage": usage,
        },
        "OPUS5_PROVIDER_DEFAULT_THINKING_OBSERVED": observed,
        "THINKING_TOKENS": thinking_tokens if thinking_tokens is not None else "unknown",
        "do_not_infer_support": True,
        "no_retry_on_thinking_observation": True,
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
        "airesponse": response_meta,
        "secrets_included": False,
        "forensic_path": forensic_path,
        "error": error_text,
    }
    header = {
        **header_base,
        "result": verdict,
        "actual_provider_calls": post_attempts,
        "http_status": http_status,
        "finish": finish,
        "request_id": request_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens if thinking_tokens is not None else "unknown",
        "opus5_thinking_observed": observed,
        "elapsed": elapsed,
        "cost": cost.get("display"),
        "structured_parse": contract.get("structured_parse"),
        "transport_decoder": contract.get("transport_decoder"),
        "handle_validation": contract.get("handle_validation"),
        "canonical_reconstruction": contract.get("canonical_reconstruction"),
        "canonical_ids": contract.get("canonical_ids"),
        "hierarchy": contract.get("hierarchy"),
        "chapters": contract.get("chapters"),
        "sections": contract.get("sections"),
        "synthetic_ideas": coverage.get("synthetic_ideas"),
        "idea_coverage": coverage.get("idea_coverage"),
        "silent_omissions": coverage.get("silent_omissions"),
        "assigned": coverage.get("assigned"),
        "deferred": coverage.get("deferred"),
        "excluded": coverage.get("excluded"),
        "reused": coverage.get("reused"),
        "unknown_idea_refs": refs.get("unknown_idea_refs"),
        "unknown_topic_refs": refs.get("unknown_topic_refs"),
        "unknown_example_refs": refs.get("unknown_example_refs"),
        "unknown_reference_refs": refs.get("unknown_reference_refs"),
        "unknown_uncertainty_refs": refs.get("unknown_uncertainty_refs"),
        "traceability": contract.get("traceability"),
        "invention_boundary": contract.get("invention_boundary"),
        "uncertainty_preservation": contract.get("uncertainty_preservation"),
        "editorial_plan_validator": contract.get("editorial_plan_validator"),
        "deterministic_replay": contract.get("deterministic_replay"),
        "semantic_canary_review": semantic.get("status"),
        "grammar_proof": grammar_proof,
        "contract_canary": contract_canary,
        "ready_for_production_preflight": "YES" if ready_preflight else "NO",
        "notes": error_text or "",
        "schema_raw_sha256": PHASE_4A_RAW_SCHEMA_SHA256,
        "editorial_plan_json": "NOT PUBLISHED",
        "production_plan_absent": not production_editorial_plan_path().is_file(),
    }
    readiness = {
        "EDITORIAL_PLANNER_GRAMMAR_PROOF": grammar_proof,
        "EDITORIAL_PLANNER_CONTRACT_CANARY": contract_canary,
        "READY_FOR_EDITORIAL_PLANNER_PRODUCTION_PREFLIGHT": ready_preflight,
        "READY_FOR_REAL_EDITORIAL_PLANNER_CALL": False,
        "PRODUCTION_OUTPUT_BUDGET_REVIEW_REQUIRED": True,
        "NEXT_ACTION": "HUMAN REVIEW",
        "why_no_real_call": (
            f"Production output budget unresolved: hard={PHASE_4A_HARD_OUTPUT_TOKENS} "
            f"> proposed max={PRODUCTION_PROPOSED_MAX_OUTPUT}."
        ),
    }
    bundle = {
        "header": header,
        "precall": identity,
        "fixture": offline["fixture"],
        "request_payload": {
            "secrets_included": False,
            **{k: v for k, v in payload.items() if k != "payload"},
            "payload": payload.get("payload"),
        },
        "raw_response": {
            "parsed": raw_parsed,
            "text": raw_text,
            "sha256": raw_response_hash,
            "repaired": False,
        },
        "response_identity": response_identity,
        "thinking": thinking_audit,
        "contract": contract,
        "semantic": semantic,
        "budget": offline["budget"],
        "readiness": readiness,
        "reconstructed_plan": contract.get("plan"),
        "execution": {
            "result": verdict,
            "engine": describe_engine(engine),
            "engine_generate_attempts": guard.generate_attempts,
            "anthropic_post_attempts": post_attempts,
            "retries": 0,
            "error": error_text,
            "forensic_path": forensic_path,
            "production_data_sent": False,
            "editorial_plan_json": "NOT PUBLISHED",
            "book_generator": "NOT STARTED",
        },
        "report_text": None,
    }
    bundle["report_text"] = render_report(bundle)
    if write_artifacts:
        from app.editorial_planner_canary_4a1.writer import write_canary_artifacts

        write_canary_artifacts(bundle, root=root)
    result.bundle = bundle
    result.accepted = verdict == "PASS"
    result.error = error_text
    result.mode = "EXECUTE"
    return result


__all__ = [
    "CanaryRunResult",
    "build_offline_bundle",
    "production_budget_status",
    "run_canary",
]
