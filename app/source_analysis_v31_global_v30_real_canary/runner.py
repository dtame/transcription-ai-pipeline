"""Runner A.46. Défaut dry-run. Réel : une tentative, pas de retry, pas de publication."""

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
from app.file_utils import content_hash
from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis_v31_global_grammar_canary.costing import actual_cost
from app.source_analysis_v31_global_v30_real_canary.constants import (
    A38_ELAPSED_BEFORE_MAX_TOKENS,
    A45_CONSERVATIVE_COST_USD,
    A45_CONSERVATIVE_OUTPUT,
    A45_ESTIMATED_INPUT,
    A45_EXPECTED_COST_USD,
    A45_EXPECTED_OUTPUT,
    A45_HARD_COST_USD,
    A45_HARD_OUTPUT,
    A45_NORMALIZED_INPUT_HASH,
    A45_REQUEST_HASH,
    AUTHORIZATION_SCOPE,
    CONNECT_TIMEOUT_SECONDS,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MAX_ANTHROPIC_POST,
    MAX_ATTEMPTS,
    MAX_ENGINE_GENERATE,
    MODE,
    MODEL,
    NORMAL_FINISH_REASONS,
    PHASE,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY,
    READY_WINDOWS,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_VERSION,
    THINKING_CONTRACT,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v30_real_canary.engine import (
    CountingAnthropicEngine,
    build_real_canary_engine,
    credential_available,
    describe_engine,
)
from app.source_analysis_v31_global_v30_real_canary.evidence import persist_raw_provider_evidence
from app.source_analysis_v31_global_v30_real_canary.guard import (
    GlobalRealCanaryError,
    OneShotCallGuard,
    reject_publication_path,
    validate_authorization_scope,
)
from app.source_analysis_v31_global_v30_real_canary.paths import (
    canary_lock_path,
    canary_windows_root,
    candidate_source_map_path,
    production_source_map_present,
)
from app.source_analysis_v31_global_v30_real_canary.preflight import run_preflight
from app.source_analysis_v31_global_v30_real_canary.semantic import review_semantics
from app.source_analysis_v31_global_v30_real_canary.validate import (
    interpret_production_response,
    technical_pass,
)
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic


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
            "semantic": self.semantic,
        }


def _consume_lock(project_name: str, *, sortie_dir: Path | None) -> None:
    path = canary_lock_path(project_name, sortie_dir=sortie_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise GlobalRealCanaryError(
            "Canary real-call lock already present — authorization consumed. NO RETRY."
        )
    path.write_text(
        f"{PHASE}\n{AUTHORIZATION_SCOPE}\nconsumed=1\n",
        encoding="utf-8",
    )


def _safe_preflight(preflight: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in preflight.items()
        if key not in {"normalized", "loaded", "built", "transcript", "inventory_runtime"}
    }


def dry_run_canary(
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
        "transport": TRANSPORT_VERSION,
        "max_output_tokens": PRODUCTION_MAX_OUTPUT_TOKENS,
        "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": READ_TIMEOUT_SECONDS,
        "max_attempts": MAX_ATTEMPTS,
        "max_engine_generate": MAX_ENGINE_GENERATE,
        "max_anthropic_post": MAX_ANTHROPIC_POST,
        "retry": False,
        "fallback": False,
        "auto_continue": False,
        "request_identity": audit.get("request_identity"),
        "normalized_input_hash": audit.get("normalized_input_hash"),
        "a45_normalized_input_hash": A45_NORMALIZED_INPUT_HASH,
        "a45_request_hash": A45_REQUEST_HASH,
        "request_identity_match": preflight.get("request_identity"),
        "schema_hash": audit.get("schema_hash"),
        "payload_audit": audit,
        "schema_metrics": preflight.get("schema_metrics"),
        "estimated_input": preflight.get("estimated_input"),
        "expected_output": preflight.get("expected_output"),
        "conservative_output": preflight.get("conservative_output"),
        "hard_output": preflight.get("hard_output"),
        "cost": preflight.get("cost"),
        "credential_available": credential_available(),
        "engine_generate": False,
        "actual_real_provider_calls": 0,
        "anthropic_post_attempts": 0,
        "ready_windows": list(READY_WINDOWS),
        "source_map_present": production_source_map_present(
            project_name, sortie_dir=sortie_dir
        ),
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "a45_ready": READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY,
        "preflight": _safe_preflight(preflight),
        "dry_run_identity": (
            audit.get("normalized_input_hash"),
            audit.get("request_identity"),
            audit.get("schema_hash"),
            audit.get("model"),
            audit.get("max_tokens"),
        ),
    }


def _classify(
    *,
    generate_attempts: int,
    post_attempts: int,
    http_success: bool | None,
    finish_reason: str | None,
    thinking_tokens: int | None,
    tech_ok: bool,
    semantic_status: str,
    publication_eligible: bool,
    source_map_published: bool,
    error: str | None,
) -> str:
    if source_map_published or generate_attempts > 1 or post_attempts > 1:
        return "FAIL"
    if generate_attempts == 0:
        return "BLOCKED_PRECALL"
    if http_success is not True or error:
        return "FAIL"
    finish_ok = str(finish_reason or "") in NORMAL_FINISH_REASONS
    if thinking_tokens != 0 or not finish_ok:
        return "FAIL"
    if not tech_ok:
        return "FAIL"
    if semantic_status == "FAIL":
        return "FAIL"
    if semantic_status == "REVIEW_REQUIRED" or not publication_eligible:
        return "PARTIAL"
    if semantic_status == "PASS" and publication_eligible:
        return "PASS"
    return "PARTIAL"


def run_global_v30_real_canary(
    project_name: str = PROJECT_NAME,
    *,
    dry_run: bool = True,
    execute_real: bool = False,
    authorization_scope: str | None = None,
    allow_real_provider: bool = False,
    engine=None,
    sortie_dir: Path | None = None,
    write_artifacts: bool = False,
    persist_evidence: bool = True,
) -> CanaryRunResult:
    result = CanaryRunResult(
        mode="DRY_RUN" if (dry_run or not execute_real) else "EXECUTE",
        project_name=project_name,
        authorization_scope=str(authorization_scope or ""),
    )
    try:
        scope = validate_authorization_scope(authorization_scope)
        result.authorization_scope = scope
    except GlobalRealCanaryError as exc:
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
        dry_a = dry_run_canary(
            project_name, authorization_scope=scope, sortie_dir=sortie_dir
        )
        dry_b = dry_run_canary(
            project_name, authorization_scope=scope, sortie_dir=sortie_dir
        )
    except (GlobalRealCanaryError, Exception) as exc:
        result.error = str(exc)
        result.mode = "BLOCKED_PRECALL"
        result.blocked_precall = True
        return result

    if dry_a.get("dry_run_identity") != dry_b.get("dry_run_identity"):
        result.error = "BLOCKED_PRECALL: dry-run request identity is not deterministic."
        result.mode = "BLOCKED_PRECALL"
        result.blocked_precall = True
        result.dry_run = dry_a
        return result

    result.dry_run = dry_a
    result.preflight = dry_a.get("preflight") or {}
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
        except GlobalRealCanaryError as exc:
            result.accepted = False
            result.error = str(exc)
            result.mode = "BLOCKED_PRECALL"
            result.blocked_precall = True
            return result

    try:
        preflight = run_preflight(
            project_name,
            authorization_scope=scope,
            sortie_dir=sortie_dir,
            require_credential=isinstance(engine, CountingAnthropicEngine),
        )
    except GlobalRealCanaryError as exc:
        result.accepted = False
        result.error = str(exc)
        result.mode = "BLOCKED_PRECALL"
        result.blocked_precall = True
        return result

    result.preflight = _safe_preflight(preflight)
    built = preflight["built"]
    request = built["request"]
    identity = str(built["audit"]["request_identity"])
    inventory = preflight["inventory_runtime"]
    forensic_root = canary_windows_root(project_name, sortie_dir=sortie_dir)
    forensic_root.mkdir(parents=True, exist_ok=True)
    if persist_evidence:
        from app.source_analysis_v31_global_v30_real_canary.writer import (
            write_precall_manifest,
        )

        write_precall_manifest(project_name, preflight, sortie_dir=sortie_dir)
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
        except GlobalRealCanaryError as exc:
            result.accepted = False
            result.error = str(exc)
            result.mode = "REJECTED"
            result.blocked_precall = True
            return result

    try:
        with provider_forensic_scope(
            windows_root=forensic_root,
            window_id="GLOBAL_A46",
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
                    window_id="GLOBAL_A46",
                    analysis_signature=identity,
                    provider=getattr(getattr(exc, "response", None), "provider", None),
                    model=getattr(getattr(exc, "response", None), "model", None) or MODEL,
                    stage=(request.metadata or {}).get("stage"),
                )
                persist_error_forensics(
                    exc,
                    windows_root=forensic_root,
                    window_id="GLOBAL_A46",
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
                error_text = str(exc)
                response = None
            except AIError as exc:
                persist_error_forensics(
                    exc,
                    windows_root=forensic_root,
                    window_id="GLOBAL_A46",
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
    except KeyboardInterrupt:
        result.error = "KeyboardInterrupt"
        result.engine_generate_attempts = guard.generate_attempts
        result.anthropic_post_attempts = int(getattr(engine, "post_attempts", 0) or 0)
        return result

    if persist_evidence:
        persist_raw_provider_evidence(
            project_name,
            raw_text=raw_text,
            parsed=parsed,
            http_meta=http_meta,
            response_meta=response_meta,
            sortie_dir=sortie_dir,
        )

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
    finish_reason = response_meta.get("finish_reason") or http_meta.get("finish_reason")
    if str(finish_reason or "") == "max_tokens":
        error_text = error_text or "controlled FAIL: finish=max_tokens. No repair. No retry."
    cost = actual_cost(input_tokens=input_tokens, output_tokens=output_tokens)
    raw_chars = len(raw_text or "")
    raw_bytes = len((raw_text or "").encode("utf-8"))
    raw_hash = content_hash(raw_text or "") if raw_text else ""
    validation = interpret_production_response(
        parsed,
        inventory=inventory,
        raw_text=raw_text,
        signature=identity,
    )
    reconstruction = validation.get("reconstruction") or {}
    candidate_payload = reconstruction.get("payload") if reconstruction.get("ok") else None
    if candidate_payload and persist_evidence:
        reject_publication_path(str(candidate_source_map_path(project_name, sortie_dir=sortie_dir)))
        write_bytes_atomic(
            candidate_source_map_path(project_name, sortie_dir=sortie_dir),
            candidate_payload,
        )
    semantic = review_semantics(
        validation.get("transport"),
        inventory,
        accountability=str(validation.get("idea_accountability") or ""),
        missing=int(validation.get("missing_members") or 0),
        candidate_payload=candidate_payload,
    )
    result.semantic = semantic
    source_map_published = production_source_map_present(project_name, sortie_dir=sortie_dir)
    tech_ok = technical_pass(validation)
    provider_ok = (
        bool(http_success)
        and int(http_meta.get("http_status") or 0) == 200
        and str(finish_reason or "") in NORMAL_FINISH_REASONS
        and int(thinking_tokens or -1) == 0
    )
    publication_eligible = bool(
        provider_ok
        and tech_ok
        and semantic.get("publication_semantic_ok") is True
        and semantic.get("status") == "PASS"
        and not source_map_published
    )
    verdict = _classify(
        generate_attempts=guard.generate_attempts,
        post_attempts=post_attempts,
        http_success=http_success,
        finish_reason=finish_reason,
        thinking_tokens=thinking_tokens,
        tech_ok=tech_ok and provider_ok,
        semantic_status=str(semantic.get("status") or "FAIL"),
        publication_eligible=publication_eligible,
        source_map_published=source_map_published,
        error=error_text,
    )
    local_est = built["audit"].get("local_input_estimate_tokens")
    a45_input = A45_ESTIMATED_INPUT
    input_error = None
    if isinstance(input_tokens, int):
        input_error = {
            "absolute": input_tokens - a45_input,
            "percent": round(100.0 * (input_tokens - a45_input) / a45_input, 2),
        }
    output_band = "unknown"
    if isinstance(output_tokens, int):
        if output_tokens <= A45_EXPECTED_OUTPUT:
            output_band = "at_or_below_expected"
        elif output_tokens <= A45_CONSERVATIVE_OUTPUT:
            output_band = "between_expected_and_conservative"
        elif output_tokens <= A45_HARD_OUTPUT:
            output_band = "between_conservative_and_hard"
        else:
            output_band = "above_hard"
    utilization = None
    headroom = None
    chars_per_token = None
    if isinstance(output_tokens, int):
        utilization = round(output_tokens / PRODUCTION_MAX_OUTPUT_TOKENS, 4)
        headroom = PRODUCTION_MAX_OUTPUT_TOKENS - output_tokens
        if output_tokens and raw_chars:
            chars_per_token = raw_chars / output_tokens
    actual_cost_value = (cost or {}).get("total_cost")
    cost_position = "unknown"
    if isinstance(actual_cost_value, (int, float)):
        if actual_cost_value <= A45_EXPECTED_COST_USD:
            cost_position = "at_or_below_expected"
        elif actual_cost_value <= A45_CONSERVATIVE_COST_USD:
            cost_position = "between_expected_and_conservative"
        elif actual_cost_value <= A45_HARD_COST_USD:
            cost_position = "between_conservative_and_hard"
        else:
            cost_position = "above_hard"
    elapsed_ms = http_meta.get("elapsed_ms") or response_meta.get("latency_ms")
    elapsed_s = (elapsed_ms / 1000.0) if isinstance(elapsed_ms, (int, float)) else None
    inventory_counts = validation.get("inventory") or {}
    membership = validation.get("membership") or {}
    ready_review = "YES" if verdict == "PASS" and publication_eligible else "NO"
    result.error = error_text
    result.execution = {
        "result": verdict,
        "authorization_scope": scope,
        "provider": PROVIDER,
        "model": MODEL,
        "thinking_mode": THINKING_MODE,
        "engine": describe_engine(engine),
        "engine_generate_attempts": guard.generate_attempts,
        "anthropic_post_attempts": post_attempts,
        "authorized_calls": 1,
        "actual_calls": post_attempts or guard.generate_attempts,
        "successful_calls": 1 if http_success else 0,
        "failed_calls": 0 if http_success else 1,
        "retry_calls": 0,
        "http": http_meta,
        "http_status": http_meta.get("http_status"),
        "request_id": http_meta.get("request_id") or response_meta.get("request_id"),
        "http_success": http_success,
        "provider_elapsed_ms": elapsed_ms,
        "elapsed_seconds": elapsed_s,
        "a38_elapsed_seconds": A38_ELAPSED_BEFORE_MAX_TOKENS,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "finish_reason": finish_reason,
        "raw_text_chars": raw_chars,
        "raw_text_bytes": raw_bytes,
        "raw_response_hash": raw_hash,
        "schema_hash": built["audit"].get("schema_hash"),
        "schema_raw_bytes": built["audit"].get("raw_bytes"),
        "schema_adapted_bytes": built["audit"].get("adapted_bytes"),
        "prompt_version": PROMPT_VERSION,
        "transport_version": TRANSPORT_VERSION,
        "normalized_input_hash": built["audit"].get("normalized_input_hash"),
        "request_hash": built["audit"].get("request_identity"),
        "request_identity": preflight.get("request_identity"),
        "local_input_estimate": local_est,
        "a45_estimated_input": a45_input,
        "input_estimate_error": input_error,
        "a45_expected_output": A45_EXPECTED_OUTPUT,
        "a45_conservative_output": A45_CONSERVATIVE_OUTPUT,
        "a45_hard_output": A45_HARD_OUTPUT,
        "output_band": output_band,
        "output_utilization": utilization,
        "output_headroom": headroom,
        "actual_chars_per_token": chars_per_token,
        "cost": cost,
        "actual_cost": actual_cost_value,
        "actual_cost_position": cost_position,
        "structured_parse": validation.get("structured_parse"),
        "transport_decoder": validation.get("decoder"),
        "handle_validation": validation.get("handle_validation"),
        "inventory": inventory_counts,
        "membership": membership,
        "global_ideas": inventory_counts.get("ideas"),
        "reuse_ideas": validation.get("single_member_global_ideas"),
        "synthesized_merges": validation.get("multi_member_global_ideas"),
        "dropped_ideas": validation.get("drop_count"),
        "SINGLE_MEMBER_WITH_V": validation.get("SINGLE_MEMBER_WITH_V"),
        "MULTI_MEMBER_WITHOUT_V": validation.get("MULTI_MEMBER_WITHOUT_V"),
        "NON_IDEA_IN_MEMBERS": validation.get("NON_IDEA_IN_MEMBERS"),
        "NON_IDEA_IN_DROP": validation.get("NON_IDEA_IN_DROP"),
        "unknown_members": validation.get("unknown_members"),
        "duplicate_members": validation.get("duplicate_members"),
        "missing_members": validation.get("missing_members"),
        "member_drop_overlap": validation.get("member_drop_overlap"),
        "idea_accountability": validation.get("idea_accountability"),
        "keep_count": validation.get("keep_count"),
        "merge_equivalent_count": validation.get("merge_equivalent_count"),
        "drop_count": validation.get("drop_count"),
        "other_count": validation.get("other_count"),
        "link_related": validation.get("link_related_count"),
        "derived_src_union": validation.get("derived_src_union"),
        "topics": inventory_counts.get("topics"),
        "examples": inventory_counts.get("examples"),
        "references": inventory_counts.get("references"),
        "uncertainties": inventory_counts.get("uncertainties"),
        "global_validator": validation.get("global_validator"),
        "canonical_reconstruction": validation.get("canonical_reconstruction"),
        "canonical_validation": validation.get("canonical_validation"),
        "deterministic_replay": validation.get("deterministic_replay"),
        "empty_relations_valid": validation.get("empty_relations_valid"),
        "reuse_synthesis": validation.get("reuse_synthesis"),
        "type_boundary": validation.get("type_boundary"),
        "semantic_review": semantic.get("status"),
        "merge_semantic_review": (semantic.get("merges") or {}).get("status"),
        "drop_semantic_review": (semantic.get("drops") or {}).get("status"),
        "topic_semantic_review": (semantic.get("topics") or {}).get("status"),
        "metadata_semantic_review": (semantic.get("metadata") or {}).get("status"),
        "uncertainty_preservation": (semantic.get("uncertainty") or {}).get("status"),
        "completeness": (semantic.get("completeness") or {}).get("status"),
        "no_editorial_structure": (semantic.get("editorial") or {}).get("status"),
        "publication_eligible": "YES" if publication_eligible else "NO",
        "ready_for_source_map_publication_review": ready_review,
        "candidate_source_map": (
            str(candidate_source_map_path(project_name, sortie_dir=sortie_dir))
            if candidate_payload
            else "NOT_CREATED"
        ),
        "source_map": "NOT PUBLISHED",
        "source_map_published": source_map_published,
        "validation": {
            key: value
            for key, value in validation.items()
            if key not in {"transport", "source_map"}
        },
        "forensic_path": str(forensic_path) if forensic_path else None,
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "ready_windows": list(READY_WINDOWS),
        "phase_3b": "INCOMPLETE",
        "retry": False,
        "technical_pass": tech_ok and provider_ok,
    }
    if write_artifacts:
        from app.source_analysis_v31_global_v30_real_canary.writer import (
            write_canary_artifacts,
        )

        write_canary_artifacts(project_name, result, sortie_dir=sortie_dir)
    return result


__all__ = ["CanaryRunResult", "dry_run_canary", "run_global_v30_real_canary"]
