"""Runner canary A.35. Défaut dry-run. Réel : une tentative, pas de retry."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.errors import AIError, AIStructuredOutputError
from app.ai.provider_forensics import (
    current_http_envelope,
    persist_error_forensics,
    persist_interrupt_forensics,
    persist_provider_forensics,
    provider_forensic_scope,
)
from app.ai.structured_forensics import persist_structured_output_forensics
from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis_v31_global_grammar_canary.constants import (
    AUTHORIZATION_SCOPE,
    CANARY_CONNECT_TIMEOUT_SECONDS,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_READ_TIMEOUT_SECONDS,
    CANARY_VERSION,
    CANARY_WINDOW_ID,
    GLOBAL_PROMPT_VERSION,
    GLOBAL_TRANSPORT_VERSION,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MAX_ANTHROPIC_POST,
    MAX_ATTEMPTS,
    MAX_ENGINE_GENERATE,
    MODE,
    MODEL,
    NORMAL_FINISH_REASONS,
    PHASE,
    PRODUCTION_ESTIMATED_COST_USD,
    PRODUCTION_LOCAL_ESTIMATE_TOKENS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PRODUCTION_NORMALIZED_CHARS,
    PRODUCTION_OUTPUT_HEADROOM_TOKENS,
    PRODUCTION_PROVIDER_ADJUSTED_TOKENS,
    PRODUCTION_WORST_CASE_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROVIDER,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_VERSION,
    THINKING_CONTRACT,
    THINKING_MODE,
)
from app.source_analysis_v31_global_grammar_canary.costing import actual_cost
from app.source_analysis_v31_global_grammar_canary.engine import (
    CountingAnthropicEngine,
    build_real_canary_engine,
    credential_available,
    describe_engine,
)
from app.source_analysis_v31_global_grammar_canary.fixture import build_synthetic_fixture
from app.source_analysis_v31_global_grammar_canary.guard import (
    GlobalGrammarCanaryError,
    OneShotCallGuard,
    validate_authorization_scope,
)
from app.source_analysis_v31_global_grammar_canary.identity import verify_schema_identity
from app.source_analysis_v31_global_grammar_canary.paths import (
    canary_lock_path,
    canary_windows_root,
    production_source_map_present,
)
from app.source_analysis_v31_global_grammar_canary.payload import build_audited_request
from app.source_analysis_v31_global_grammar_canary.validate import interpret_canary_response


@dataclass
class CanaryRunResult:
    mode: str
    project_name: str
    authorization_scope: str
    accepted: bool = False
    blocked_precall: bool = False
    error: str | None = None
    engine_generate_attempts: int = 0
    anthropic_post_attempts: int = 0
    dry_run: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    payload_audit: dict[str, Any] = field(default_factory=dict)
    schema_metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "phase": PHASE,
            "mode": self.mode,
            "project_name": self.project_name,
            "authorization_scope": self.authorization_scope,
            "accepted": self.accepted,
            "blocked_precall": self.blocked_precall,
            "error": self.error,
            "engine_generate_attempts": self.engine_generate_attempts,
            "anthropic_post_attempts": self.anthropic_post_attempts,
            "dry_run": self.dry_run,
            "execution": self.execution,
            "payload_audit": self.payload_audit,
            "schema_metrics": self.schema_metrics,
        }


def _consume_lock(project_name: str, *, sortie_dir: Path | None) -> None:
    path = canary_lock_path(project_name, sortie_dir=sortie_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise GlobalGrammarCanaryError(
            "Canary real-call lock already present — authorization consumed. "
            "NO RETRY."
        )
    path.write_text(
        f"{PHASE}\n{AUTHORIZATION_SCOPE}\nconsumed=1\n",
        encoding="utf-8",
    )


def dry_run_canary(
    project_name: str = PROJECT_NAME,
    *,
    authorization_scope: str = AUTHORIZATION_SCOPE,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    validate_authorization_scope(authorization_scope)
    fixture = build_synthetic_fixture()
    built = build_audited_request(
        fixture, project_name=project_name, sortie_dir=sortie_dir
    )
    audit = built["audit"]
    return {
        "mode": "DRY_RUN",
        "authorization_scope": authorization_scope,
        "canary_version": CANARY_VERSION,
        "phase": PHASE,
        "runner_mode": MODE,
        "provider": PROVIDER,
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "thinking_contract": THINKING_CONTRACT,
        "effort": None,
        "prompt_version": GLOBAL_PROMPT_VERSION,
        "prompt_hash": audit.get("prompt_hash"),
        "transport": GLOBAL_TRANSPORT_VERSION,
        "max_output_tokens": CANARY_MAX_OUTPUT_TOKENS,
        "production_max_output_tokens": PRODUCTION_MAX_OUTPUT_TOKENS,
        "connect_timeout_seconds": CANARY_CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": CANARY_READ_TIMEOUT_SECONDS,
        "max_attempts": MAX_ATTEMPTS,
        "max_engine_generate": MAX_ENGINE_GENERATE,
        "max_anthropic_post": MAX_ANTHROPIC_POST,
        "retry": False,
        "fallback": False,
        "auto_continue": False,
        "request_identity": audit["request_identity"],
        "schema_hash": audit["schema_hash"],
        "schema_raw_bytes": audit.get("raw_bytes"),
        "schema_adapted_bytes": audit.get("adapted_bytes"),
        "schema_identity": built["schema_metrics"].get("schema_identity"),
        "synthetic_fixture_hash": audit["synthetic_input_hash"],
        "payload_audit": audit,
        "schema_metrics": built["schema_metrics"],
        "fixture": fixture.to_safe_dict(),
        "local_input_estimate_tokens": audit.get("local_input_estimate_tokens"),
        "credential_available": credential_available(),
        "credential_secret_printed": False,
        "engine_generate": False,
        "actual_real_provider_calls": 0,
        "anthropic_post_attempts": 0,
        "secrets_included": False,
        "pastoral_content_sent": False,
        "real_consolidation_executed": False,
        "source_map_present": production_source_map_present(
            project_name, sortie_dir=sortie_dir
        ),
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "production_input_chars": PRODUCTION_NORMALIZED_CHARS,
        "production_local_estimate": PRODUCTION_LOCAL_ESTIMATE_TOKENS,
        "production_provider_adjusted": PRODUCTION_PROVIDER_ADJUSTED_TOKENS,
        "production_worst_case_output": PRODUCTION_WORST_CASE_OUTPUT_TOKENS,
        "production_output_headroom": PRODUCTION_OUTPUT_HEADROOM_TOKENS,
        "estimated_real_consolidation_cost": PRODUCTION_ESTIMATED_COST_USD,
    }


def _classify(
    *,
    generate_attempts: int,
    post_attempts: int,
    http_success: bool | None,
    finish_reason: str | None,
    thinking_tokens: int | None,
    structured: str,
    decoder: str,
    handles: str,
    coverage: float,
    silent_drops: int,
    traceability: str,
    global_validator: str,
    no_drop: str,
    relation: str,
    reconstruction: str,
    canonical: str,
    replay: str,
    semantic: str,
    pastoral: bool,
    source_map_published: bool,
    error: str | None,
) -> str:
    if pastoral or generate_attempts > 1 or post_attempts > 1 or source_map_published:
        return "FAIL"
    if generate_attempts == 0:
        return "BLOCKED_PRECALL"
    pipeline = (
        structured,
        decoder,
        handles,
        traceability,
        global_validator,
        no_drop,
        relation,
        reconstruction,
        canonical,
        replay,
        semantic,
    )
    thinking_ok = thinking_tokens == 0
    finish_ok = str(finish_reason or "") in NORMAL_FINISH_REASONS
    coverage_ok = float(coverage or 0) >= 100.0
    silent_ok = int(silent_drops or 0) == 0
    if http_success is not True or error:
        return "FAIL"
    if not thinking_ok or not finish_ok:
        return "FAIL"
    if any(status != "PASS" for status in pipeline) or not coverage_ok or not silent_ok:
        return "FAIL"
    if generate_attempts != 1 or post_attempts > 1:
        return "FAIL"
    return "PASS"


def run_global_grammar_canary(
    project_name: str = PROJECT_NAME,
    *,
    dry_run: bool = True,
    execute_real: bool = False,
    authorization_scope: str | None = None,
    allow_real_provider: bool = False,
    engine=None,
    sortie_dir: Path | None = None,
    write_artifacts: bool = False,
) -> CanaryRunResult:
    result = CanaryRunResult(
        mode="DRY_RUN" if (dry_run or not execute_real) else "EXECUTE",
        project_name=project_name,
        authorization_scope=str(authorization_scope or ""),
    )
    try:
        scope = validate_authorization_scope(authorization_scope)
        result.authorization_scope = scope
    except GlobalGrammarCanaryError as exc:
        result.error = str(exc)
        result.mode = "REJECTED"
        result.blocked_precall = True
        return result

    if execute_real and dry_run:
        result.error = "--dry-run and --execute-real are exclusive."
        result.mode = "REJECTED"
        result.blocked_precall = True
        return result

    try:
        dry = dry_run_canary(
            project_name,
            authorization_scope=scope,
            sortie_dir=sortie_dir,
        )
    except GlobalGrammarCanaryError as exc:
        result.error = str(exc)
        result.mode = "BLOCKED_PRECALL"
        result.blocked_precall = True
        return result

    result.dry_run = dry
    result.payload_audit = dry["payload_audit"]
    result.schema_metrics = dry["schema_metrics"]
    result.accepted = True

    if dry_run or not execute_real:
        return result

    if engine is None and not allow_real_provider:
        result.accepted = False
        result.error = "exécution réelle refusée : allow_real_provider=false."
        result.mode = "REJECTED"
        result.blocked_precall = True
        return result

    if engine is None:
        try:
            engine = build_real_canary_engine()
        except GlobalGrammarCanaryError as exc:
            result.accepted = False
            result.error = str(exc)
            result.mode = "BLOCKED_PRECALL"
            result.blocked_precall = True
            return result

    try:
        verify_schema_identity(project_name, sortie_dir=sortie_dir)
    except GlobalGrammarCanaryError as exc:
        result.accepted = False
        result.error = str(exc)
        result.mode = "BLOCKED_PRECALL"
        result.blocked_precall = True
        return result

    fixture = build_synthetic_fixture()
    built = build_audited_request(
        fixture, project_name=project_name, sortie_dir=sortie_dir
    )
    request = built["request"]
    identity = built["audit"]["request_identity"]
    forensic_root = canary_windows_root(project_name, sortie_dir=sortie_dir)
    forensic_root.mkdir(parents=True, exist_ok=True)
    guard = OneShotCallGuard(max_calls=MAX_ENGINE_GENERATE)
    forensic_path = None
    http_meta: dict[str, Any] = {}
    validation: dict[str, Any] = {}
    response_meta: dict[str, Any] = {}
    error_text: str | None = None
    http_success: bool | None = None
    raw_text: str | None = None
    parsed: dict[str, Any] | None = None

    if isinstance(engine, CountingAnthropicEngine):
        try:
            _consume_lock(project_name, sortie_dir=sortie_dir)
        except GlobalGrammarCanaryError as exc:
            result.accepted = False
            result.error = str(exc)
            result.mode = "REJECTED"
            result.blocked_precall = True
            return result

    try:
        with provider_forensic_scope(
            windows_root=forensic_root,
            window_id=CANARY_WINDOW_ID,
            analysis_signature=identity,
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
                    windows_root=forensic_root,
                    window_id=CANARY_WINDOW_ID,
                    analysis_signature=identity,
                    provider=getattr(getattr(exc, "response", None), "provider", None),
                    model=getattr(getattr(exc, "response", None), "model", None) or MODEL,
                    stage=request.stage,
                )
                persist_error_forensics(
                    exc,
                    windows_root=forensic_root,
                    window_id=CANARY_WINDOW_ID,
                    analysis_signature=identity,
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
                    parsed = attached.parsed if isinstance(attached.parsed, dict) else None
                    validation = interpret_canary_response(
                        parsed,
                        fixture=fixture,
                        raw_text=raw_text,
                        signature=identity,
                    )
                error_text = str(exc)
                response = None
            except AIError as exc:
                persist_error_forensics(
                    exc,
                    windows_root=forensic_root,
                    window_id=CANARY_WINDOW_ID,
                    analysis_signature=identity,
                )
                envelope = getattr(exc, "http_envelope", None) or current_http_envelope()
                if envelope is not None:
                    http_meta = envelope.compact_metadata()
                    forensic_path = envelope.forensic_path
                    http_success = envelope.http_success
                error_text = str(exc)
                response = None
            except MaxRealCallsExceededError as exc:
                error_text = str(exc)
                response = None
            else:
                envelope = current_http_envelope() or getattr(response, "http_envelope", None)
                if envelope is None and isinstance(getattr(response, "metadata", None), dict):
                    http_meta = dict(response.metadata.get("provider_http") or {})
                    http_success = http_meta.get("http_success")
                if envelope is not None:
                    persist_provider_forensics(envelope)
                    http_meta = envelope.compact_metadata()
                    forensic_path = envelope.forensic_path
                    http_success = envelope.http_success
                response_meta = response.to_dict()
                raw_text = response.text
                parsed = response.parsed if isinstance(response.parsed, dict) else None
                validation = interpret_canary_response(
                    parsed,
                    fixture=fixture,
                    raw_text=raw_text,
                    signature=identity,
                )
    except KeyboardInterrupt:
        result.error = "KeyboardInterrupt"
        result.engine_generate_attempts = guard.generate_attempts
        result.anthropic_post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
        return result

    post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
    result.engine_generate_attempts = guard.generate_attempts
    result.anthropic_post_attempts = post_attempts
    thinking_tokens = response_meta.get("thinking_tokens") if response_meta else None
    if thinking_tokens is None and http_meta.get("usage"):
        usage = http_meta["usage"]
        details = usage.get("output_tokens_details") if isinstance(usage, dict) else None
        if isinstance(details, dict) and "thinking_tokens" in details:
            thinking_tokens = details.get("thinking_tokens")
        elif isinstance(usage, dict) and "thinking_tokens" in usage:
            thinking_tokens = usage.get("thinking_tokens")

    input_tokens = response_meta.get("input_tokens")
    output_tokens = response_meta.get("output_tokens")
    if input_tokens is None:
        input_tokens = http_meta.get("input_tokens")
    if output_tokens is None:
        output_tokens = http_meta.get("output_tokens")

    cost = actual_cost(input_tokens=input_tokens, output_tokens=output_tokens)
    local_est = built["audit"].get("local_input_estimate_tokens")
    ratio = None
    if isinstance(local_est, int) and local_est and isinstance(input_tokens, int):
        ratio = input_tokens / local_est
    finish_reason = response_meta.get("finish_reason") or http_meta.get("finish_reason")
    source_map_published = production_source_map_present(
        project_name, sortie_dir=sortie_dir
    )
    grammar_accepted = "YES" if http_success else "NO"
    thinking_accepted = "YES" if http_success else "NO"
    if error_text and http_success is not True:
        grammar_accepted = "NO"
        thinking_accepted = "NO"

    verdict = _classify(
        generate_attempts=guard.generate_attempts,
        post_attempts=post_attempts,
        http_success=http_success,
        finish_reason=finish_reason,
        thinking_tokens=thinking_tokens,
        structured=validation.get("structured_parse", "FAIL"),
        decoder=validation.get("decoder", "FAIL"),
        handles=validation.get("handle_validation", "FAIL"),
        coverage=float(validation.get("idea_disposition_coverage") or 0),
        silent_drops=int(validation.get("silent_drops") or 0),
        traceability=validation.get("traceability", "FAIL"),
        global_validator=validation.get("global_validator", "FAIL"),
        no_drop=validation.get("no_drop_validator", "FAIL"),
        relation=validation.get("relation_validator", "FAIL"),
        reconstruction=validation.get("canonical_reconstruction", "FAIL"),
        canonical=validation.get("canonical_validation", "FAIL"),
        replay=validation.get("deterministic_replay", "FAIL"),
        semantic=validation.get("semantic_review", {}).get("status", "FAIL"),
        pastoral=False,
        source_map_published=source_map_published,
        error=error_text,
    )
    ready = verdict == "PASS"
    result.error = error_text
    result.execution = {
        "result": verdict,
        "authorization_scope": scope,
        "provider": PROVIDER,
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "effort": "omitted",
        "manual_budget": "absent",
        "task_budget": "absent",
        "engine": describe_engine(engine),
        "engine_generate_attempts": guard.generate_attempts,
        "anthropic_post_attempts": post_attempts,
        "authorized_calls": 1,
        "actual_calls": post_attempts,
        "successful_calls": 1 if http_success else 0,
        "failed_calls": 0 if http_success else 1,
        "retry_calls": 0,
        "http": http_meta,
        "http_status": http_meta.get("http_status"),
        "request_id": http_meta.get("request_id") or response_meta.get("request_id"),
        "response_received": http_meta.get("response_received"),
        "http_success": http_success,
        "provider_elapsed_ms": http_meta.get("elapsed_ms") or response_meta.get("latency_ms"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "thinking_tokens_reported": thinking_tokens is not None,
        "finish_reason": finish_reason,
        "usage_source": response_meta.get("usage_source"),
        "airesponse_created": bool(response_meta),
        "raw_text_chars": len(raw_text or ""),
        "schema_identity": built["schema_metrics"].get("schema_identity"),
        "schema_hash": built["schema_metrics"].get("hash"),
        "schema_raw_bytes": built["schema_metrics"].get("raw_bytes"),
        "schema_adapted_bytes": built["schema_metrics"].get("adapted_bytes"),
        "max_output_canary": CANARY_MAX_OUTPUT_TOKENS,
        "local_input_estimate": local_est,
        "provider_input": input_tokens,
        "input_ratio": ratio,
        "structured_parse": validation.get("structured_parse"),
        "transport_decoder": validation.get("decoder"),
        "handle_validation": validation.get("handle_validation"),
        "inventory": validation.get("inventory"),
        "idea_disposition_coverage": validation.get("idea_disposition_coverage"),
        "silent_drops": validation.get("silent_drops"),
        "traceability": validation.get("traceability"),
        "global_validator": validation.get("global_validator"),
        "no_drop_validator": validation.get("no_drop_validator"),
        "relation_validator": validation.get("relation_validator"),
        "canonical_reconstruction": validation.get("canonical_reconstruction"),
        "canonical_validation": validation.get("canonical_validation"),
        "deterministic_replay": validation.get("deterministic_replay"),
        "semantic_fixture_review": (validation.get("semantic_review") or {}).get("status"),
        "theme_present": validation.get("theme_present"),
        "intent_present": validation.get("intent_present"),
        "audience_present": validation.get("audience_present"),
        "voice_present": validation.get("voice_present"),
        "validation_errors": validation.get("errors") or [],
        "handles": validation.get("handles"),
        "dispositions": validation.get("dispositions"),
        "reconstruction": validation.get("reconstruction"),
        "replay": validation.get("replay"),
        "semantic_review": validation.get("semantic_review"),
        "server_grammar_accepted": grammar_accepted,
        "thinking_disabled_accepted": thinking_accepted,
        "cost": cost,
        "forensic_path": str(forensic_path) if forensic_path else None,
        "canary_artifact_isolated": True,
        "pastoral_content_sent": False,
        "real_consolidation_executed": False,
        "source_map": "NOT PUBLISHED",
        "source_map_published": source_map_published,
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "ready_for_real_global_consolidation_canary": "YES" if ready else "NO",
        "phase_3b": "INCOMPLETE",
        "retry": False,
        "classifications": {
            "GRAMMAR_ACCEPTED": grammar_accepted == "YES",
            "TRANSPORT_VALID": validation.get("decoder") == "PASS",
            "VALIDATOR_VALID": validation.get("global_validator") == "PASS",
            "CANONICAL_RECONSTRUCTION_VALID": validation.get("canonical_reconstruction")
            == "PASS",
            "SEMANTIC_FIXTURE_REASONABLE": (validation.get("semantic_review") or {}).get(
                "status"
            )
            == "PASS",
        },
    }
    if write_artifacts:
        from app.source_analysis_v31_global_grammar_canary.writer import (
            write_canary_artifacts,
        )

        write_canary_artifacts(project_name, result, sortie_dir=sortie_dir)
    return result


__all__ = [
    "CanaryRunResult",
    "dry_run_canary",
    "run_global_grammar_canary",
]
