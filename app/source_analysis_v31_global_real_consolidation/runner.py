"""Runner A.38. Défaut dry-run. Réel : une tentative, pas de retry."""

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
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_v31_global_grammar_canary.costing import actual_cost
from app.source_analysis_v31_global_real_consolidation.constants import (
    AUTHORIZATION_SCOPE,
    CONNECT_TIMEOUT_SECONDS,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MAX_ANTHROPIC_POST,
    MAX_ATTEMPTS,
    MAX_ENGINE_GENERATE,
    MAX_OUTPUT_TOKENS,
    MODE,
    MODEL,
    NORMAL_FINISH_REASONS,
    OUTPUT_HEADROOM_LABEL,
    OUTPUT_HEADROOM_PERCENT,
    PHASE,
    PRODUCTION_ESTIMATED_COST_USD,
    PRODUCTION_LOCAL_ESTIMATE_TOKENS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PRODUCTION_NORMALIZED_CHARS,
    PRODUCTION_OUTPUT_HEADROOM_TOKENS,
    PRODUCTION_PROVIDER_ADJUSTED_TOKENS,
    PRODUCTION_WORST_CASE_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    READY_WINDOWS,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_VERSION,
    THINKING_CONTRACT,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_real_consolidation.engine import (
    CountingAnthropicEngine,
    build_real_consolidation_engine,
    credential_available,
    describe_engine,
)
from app.source_analysis_v31_global_real_consolidation.guard import (
    GlobalRealConsolidationError,
    OneShotCallGuard,
    reject_publication_path,
    validate_authorization_scope,
)
from app.source_analysis_v31_global_real_consolidation.paths import (
    canary_lock_path,
    canary_windows_root,
    candidate_source_map_path,
    production_source_map_present,
)
from app.source_analysis_v31_global_real_consolidation.payload import dry_run_identity_tuple
from app.source_analysis_v31_global_real_consolidation.preflight import run_preflight
from app.source_analysis_v31_global_real_consolidation.semantic import review_semantics
from app.source_analysis_v31_global_real_consolidation.validate import interpret_real_response


@dataclass
class ConsolidationRunResult:
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
    preflight: dict[str, Any] = field(default_factory=dict)
    semantic: dict[str, Any] = field(default_factory=dict)

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
            "preflight": {
                key: value
                for key, value in self.preflight.items()
                if key not in {"normalized", "loaded", "built"}
            },
            "semantic": self.semantic,
        }


def _consume_lock(project_name: str, *, sortie_dir: Path | None) -> None:
    path = canary_lock_path(project_name, sortie_dir=sortie_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise GlobalRealConsolidationError(
            "Canary real-call lock already present — authorization consumed. NO RETRY."
        )
    path.write_text(
        f"{PHASE}\n{AUTHORIZATION_SCOPE}\nconsumed=1\n",
        encoding="utf-8",
    )


def dry_run_consolidation(
    project_name: str = PROJECT_NAME,
    *,
    authorization_scope: str = AUTHORIZATION_SCOPE,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    preflight = run_preflight(
        project_name,
        authorization_scope=authorization_scope,
        sortie_dir=sortie_dir,
        require_credential=False,
    )
    audit = preflight["payload_audit"]
    return {
        "mode": "DRY_RUN",
        "authorization_scope": authorization_scope,
        "phase": PHASE,
        "runner_mode": MODE,
        "provider": PROVIDER,
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "thinking_contract": THINKING_CONTRACT,
        "effort": None,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": audit.get("prompt_hash"),
        "transport": TRANSPORT_VERSION,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": READ_TIMEOUT_SECONDS,
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
        "schema_identity": preflight["schema"].get("schema_identity"),
        "input_hash": audit.get("input_hash"),
        "payload_audit": audit,
        "inventory": preflight["inventory"],
        "ready_windows": list(READY_WINDOWS),
        "local_input_estimate_tokens": audit.get("local_input_estimate_tokens"),
        "credential_available": credential_available(),
        "credential_secret_printed": False,
        "engine_generate": False,
        "actual_real_provider_calls": 0,
        "anthropic_post_attempts": 0,
        "secrets_included": False,
        "raw_transcript_sent": False,
        "real_consolidation_executed": False,
        "source_map_present": False,
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "production_input_chars": PRODUCTION_NORMALIZED_CHARS,
        "production_local_estimate": PRODUCTION_LOCAL_ESTIMATE_TOKENS,
        "production_provider_adjusted": PRODUCTION_PROVIDER_ADJUSTED_TOKENS,
        "production_worst_case_output": PRODUCTION_WORST_CASE_OUTPUT_TOKENS,
        "production_output_headroom": PRODUCTION_OUTPUT_HEADROOM_TOKENS,
        "production_output_headroom_percent": OUTPUT_HEADROOM_PERCENT,
        "production_output_headroom_label": OUTPUT_HEADROOM_LABEL,
        "estimated_real_consolidation_cost": PRODUCTION_ESTIMATED_COST_USD,
        "dry_run_identity": dry_run_identity_tuple(audit),
        "preflight": preflight,
    }


def _classify(
    *,
    generate_attempts: int,
    post_attempts: int,
    http_success: bool | None,
    finish_reason: str | None,
    thinking_tokens: int | None,
    validation: Mapping[str, Any],
    semantic: Mapping[str, Any],
    source_map_published: bool,
    error: str | None,
) -> str:
    if generate_attempts > 1 or post_attempts > 1 or source_map_published:
        return "FAIL"
    if generate_attempts == 0:
        return "BLOCKED_PRECALL"
    thinking_ok = thinking_tokens == 0
    finish_ok = str(finish_reason or "") in NORMAL_FINISH_REASONS
    coverage_ok = float(validation.get("idea_disposition_coverage") or 0) >= 100.0
    silent_ok = int(validation.get("silent_drops") or 0) == 0
    technical = (
        validation.get("structured_parse"),
        validation.get("decoder"),
        validation.get("handle_validation"),
        validation.get("traceability"),
        validation.get("global_validator"),
        validation.get("no_drop_validator"),
        validation.get("canonical_reconstruction"),
        validation.get("canonical_validation"),
        validation.get("deterministic_replay"),
        validation.get("d_o_enum"),
        validation.get("d_w_enum"),
        validation.get("operation_reason_matrix"),
        validation.get("merge_source_union"),
    )
    if http_success is not True or error:
        return "FAIL"
    if not thinking_ok or not finish_ok:
        return "FAIL"
    if any(status != "PASS" for status in technical) or not coverage_ok or not silent_ok:
        return "FAIL"
    if int(validation.get("free_text_drop_reason") or 0) != 0:
        return "FAIL"
    if int(validation.get("link_related_count") or 0) != 0:
        return "FAIL"
    if generate_attempts != 1 or post_attempts > 1:
        return "FAIL"
    quality = str(semantic.get("semantic_quality") or "")
    if semantic.get("status") != "PASS":
        return "FAIL"
    if quality == "ACCEPTABLE_WITH_REVIEW_ITEMS":
        return "PARTIAL"
    if quality == "ACCEPTABLE_FOR_SOURCE_MAP_CANDIDATE":
        return "PASS"
    if quality == "INADEQUATE_FOR_SOURCE_MAP":
        return "FAIL"
    return "PARTIAL"


def run_real_global_consolidation(
    project_name: str = PROJECT_NAME,
    *,
    dry_run: bool = True,
    execute_real: bool = False,
    authorization_scope: str | None = None,
    allow_real_provider: bool = False,
    engine=None,
    sortie_dir: Path | None = None,
    write_artifacts: bool = False,
) -> ConsolidationRunResult:
    result = ConsolidationRunResult(
        mode="DRY_RUN" if (dry_run or not execute_real) else "EXECUTE",
        project_name=project_name,
        authorization_scope=str(authorization_scope or ""),
    )
    try:
        scope = validate_authorization_scope(authorization_scope)
        result.authorization_scope = scope
    except GlobalRealConsolidationError as exc:
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
        dry = dry_run_consolidation(
            project_name,
            authorization_scope=scope,
            sortie_dir=sortie_dir,
        )
    except GlobalRealConsolidationError as exc:
        result.error = str(exc)
        result.mode = "BLOCKED_PRECALL"
        result.blocked_precall = True
        return result

    result.dry_run = {key: value for key, value in dry.items() if key != "preflight"}
    result.preflight = dry["preflight"]
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
            engine = build_real_consolidation_engine()
        except GlobalRealConsolidationError as exc:
            result.accepted = False
            result.error = str(exc)
            result.mode = "BLOCKED_PRECALL"
            result.blocked_precall = True
            return result

    preflight = dry["preflight"]
    built = preflight["built"]
    normalized = preflight["normalized"]
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
    semantic: dict[str, Any] = {}

    if isinstance(engine, CountingAnthropicEngine):
        try:
            _consume_lock(project_name, sortie_dir=sortie_dir)
        except GlobalRealConsolidationError as exc:
            result.accepted = False
            result.error = str(exc)
            result.mode = "REJECTED"
            result.blocked_precall = True
            return result

    try:
        transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    except Exception as exc:  # noqa: BLE001
        result.accepted = False
        result.error = f"BLOCKED_PRECALL: CLEAN transcript unavailable ({exc})."
        result.mode = "BLOCKED_PRECALL"
        result.blocked_precall = True
        return result

    try:
        with provider_forensic_scope(
            windows_root=forensic_root,
            window_id="GLOBAL",
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
                    window_id="GLOBAL",
                    analysis_signature=identity,
                    provider=getattr(getattr(exc, "response", None), "provider", None),
                    model=getattr(getattr(exc, "response", None), "model", None) or MODEL,
                    stage=(getattr(request, "metadata", None) or {}).get("stage")
                    or "source_analysis_v31_global_real_consolidation",
                )
                persist_error_forensics(
                    exc,
                    windows_root=forensic_root,
                    window_id="GLOBAL",
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
                    validation = interpret_real_response(
                        parsed,
                        normalized=normalized,
                        transcript=transcript,
                        raw_text=raw_text,
                        signature=identity,
                        finish_reason=response_meta.get("finish_reason"),
                    )
                error_text = str(exc)
                response = None
            except AIError as exc:
                persist_error_forensics(
                    exc,
                    windows_root=forensic_root,
                    window_id="GLOBAL",
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
                validation = interpret_real_response(
                    parsed,
                    normalized=normalized,
                    transcript=transcript,
                    raw_text=raw_text,
                    signature=identity,
                    finish_reason=response_meta.get("finish_reason")
                    or http_meta.get("finish_reason"),
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
    if validation.get("transport") and validation.get("global_validator") == "PASS":
        semantic = review_semantics(validation["transport"], normalized, transcript)
    elif validation.get("transport"):
        semantic = review_semantics(validation["transport"], normalized, transcript)
        semantic["technical_gate"] = "FAIL"
    else:
        semantic = {"status": "FAIL", "semantic_quality": "UNDETERMINABLE"}

    inventory = validation.get("inventory") or {}
    by_kind = inventory.get("by_kind") or inventory
    verdict = _classify(
        generate_attempts=guard.generate_attempts,
        post_attempts=post_attempts,
        http_success=http_success,
        finish_reason=finish_reason,
        thinking_tokens=thinking_tokens,
        validation=validation,
        semantic=semantic,
        source_map_published=source_map_published,
        error=error_text,
    )
    output_headroom = None
    output_headroom_pct = None
    if isinstance(output_tokens, int):
        output_headroom = MAX_OUTPUT_TOKENS - output_tokens
        output_headroom_pct = round(100.0 * output_headroom / MAX_OUTPUT_TOKENS, 1)
    candidate_created = (
        verdict in {"PASS", "PARTIAL"}
        and validation.get("canonical_reconstruction") == "PASS"
    )
    candidate_path = (
        str(candidate_source_map_path(project_name, sortie_dir=sortie_dir))
        if candidate_created
        else None
    )
    if candidate_path:
        reject_publication_path(candidate_path)
    result.error = error_text
    result.semantic = semantic
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
        "prompt_version": PROMPT_VERSION,
        "transport_version": TRANSPORT_VERSION,
        "max_output": MAX_OUTPUT_TOKENS,
        "local_input_estimate": local_est,
        "provider_input": input_tokens,
        "input_ratio": ratio,
        "output_headroom_tokens": output_headroom,
        "output_headroom_percent": output_headroom_pct,
        "structured_parse": validation.get("structured_parse"),
        "transport_decoder": validation.get("decoder"),
        "handle_validation": validation.get("handle_validation"),
        "inventory": inventory,
        "global_topics": by_kind.get("TOPIC"),
        "global_ideas": by_kind.get("IDEA"),
        "global_relations": inventory.get("relations"),
        "global_examples": by_kind.get("EXAMPLE"),
        "global_references": by_kind.get("REFERENCE"),
        "global_uncertainties": by_kind.get("UNCERTAINTY"),
        "global_repetitions": by_kind.get("REPETITION"),
        "idea_disposition_coverage": validation.get("idea_disposition_coverage"),
        "silent_drops": validation.get("silent_drops"),
        "traceability": validation.get("traceability"),
        "global_validator": validation.get("global_validator"),
        "canonical_reconstruction": validation.get("canonical_reconstruction"),
        "canonical_validation": validation.get("canonical_validation"),
        "deterministic_replay": validation.get("deterministic_replay"),
        "d_o_enum": validation.get("d_o_enum"),
        "d_w_enum": validation.get("d_w_enum"),
        "free_text_drop_reason": validation.get("free_text_drop_reason"),
        "link_related": validation.get("link_related_count"),
        "operation_reason_matrix": validation.get("operation_reason_matrix"),
        "merge_source_union": validation.get("merge_source_union"),
        "keep_count": validation.get("keep_count"),
        "merge_equivalent_count": validation.get("merge_equivalent_count"),
        "drop_count": validation.get("drop_count"),
        "other_count": validation.get("other_count"),
        "observed_dw_tokens": validation.get("observed_dw_tokens"),
        "validation_errors": validation.get("errors") or [],
        "handles": validation.get("handles"),
        "dispositions": validation.get("validator"),
        "enum_audit": validation.get("enum_audit"),
        "reconstruction": validation.get("reconstruction"),
        "replay": validation.get("replay"),
        "transport": validation.get("transport"),
        "semantic_quality": semantic.get("semantic_quality"),
        "semantic_status": semantic.get("status"),
        "cost": cost,
        "forensic_path": str(forensic_path) if forensic_path else None,
        "canary_artifact_isolated": True,
        "raw_transcript_sent": False,
        "real_consolidation_executed": True,
        "source_map": "NOT PUBLISHED",
        "source_map_published": source_map_published,
        "candidate_source_map": "CREATED" if candidate_created else "NOT_CREATED",
        "candidate_path": candidate_path,
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "phase_3b": "INCOMPLETE",
        "retry": False,
    }
    if write_artifacts:
        from app.source_analysis_v31_global_real_consolidation.writer import (
            write_consolidation_artifacts,
        )

        write_consolidation_artifacts(project_name, result, sortie_dir=sortie_dir)
    return result


__all__ = [
    "ConsolidationRunResult",
    "dry_run_consolidation",
    "run_real_global_consolidation",
]
