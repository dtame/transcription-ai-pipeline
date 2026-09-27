"""
Orchestration du Source Analyzer global CLEAN — Phase 3B Final.

Dry-run : charge le transcript DERIVED, construit le payload, S'ARRÊTE
avant HTTP.
Real call : un seul generate(), max_attempts=1, aucun fallback.

Le transport est préservé AVANT decoder / validator.
La publication de analysis/source_map.json n'a lieu qu'après la chaîne
locale complète.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.cost import CostTracker
from app.ai.errors import AIError, AITimeoutError
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.registry import get_ai_engine
from app.ai.retry import RetryPolicy
from app.ai.settings import resolve_stage_settings
from app.ai.usage_store import record_call
from app.cleanup_application.writer import audit_path, clean_json_path
from app.file_utils import content_hash
from app.project_state import load_project_state, save_project_state
from app.report_service import build_project_report
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis import cache as cache_module
from app.source_analysis import prompt as production_prompt
from app.source_analysis import state as state_module
from app.source_analysis import writer as writer_module
from app.source_analysis.analyzer import is_truncated_finish_reason
from app.source_analysis.compact_schema import build_compact_response_schema
from app.source_analysis.context_strategy import plan_context
from app.source_analysis.guard import RealCallGuard
from app.source_analysis.models import (
    SOURCE_MAP_SCHEMA_VERSION,
    STRATEGY_GLOBAL,
    AnalysisProvenance,
)
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.real_run import GuardedEngine, anthropic_credential_available
from app.source_analysis.schema import build_response_schema, schema_fingerprint
from app.source_analysis.transcript_input import (
    TranscriptInputMode,
    load_transcript_input,
)
from app.source_analysis.ultra_compact_schema import (
    SEMANTIC_TRANSPORT_VERSION,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.writer import transcripts_dir
from app.source_analysis_global_clean import integrity as integrity_module
from app.source_analysis_global_clean import writer as artifact_writer
from app.source_analysis_global_clean.constants import (
    CANARY_SIGNATURE_MARKS,
    CLASS_PRE_CALL_CREDENTIAL_MISSING,
    CLASS_PRE_CALL_EXISTING_MAP,
    CLASS_PRE_CALL_NOT_GLOBAL,
    CLASS_PRE_CALL_OUTPUT_CAPACITY,
    CLASS_PRE_CALL_PARITY,
    CLASS_PRE_CALL_SCHEMA_DRIFT,
    CLASS_PRE_CALL_UNEXPECTED_CACHE,
    EXPECTED_MODEL,
    EXPECTED_MODEL_MAX_OUTPUT,
    EXPECTED_PROMPT_VERSION,
    EXPECTED_PROVIDER,
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
    MAX_ATTEMPTS,
    MAX_REAL_CALLS,
    OUTCOME_FAIL,
    OUTCOME_PARTIAL,
    OUTCOME_PASS,
    PURPOSE,
    REFERENCE_3B44_PROMPT_SHA256,
    SCHEMA_VERSION,
    STAGE,
    STOP_AFTER_CALL,
    STOP_CACHE_HIT,
    STOP_EXISTING_MAP,
    STOP_PRE_CALL,
    STOP_TRANSPORT_WRITE,
    STOP_TRUNCATED,
    TRANSPORT_VERSION,
)
from app.source_analysis_global_clean.errors import (
    ExistingSourceMapStop,
    PreCallFailure,
    SchemaDriftError,
    TransportPreserveError,
    UnexpectedCacheHit,
)
from app.source_analysis_ultra_compact_canary import architecture as architecture_module
from app.source_analysis_ultra_compact_canary import classify as classify_module
from app.source_analysis_ultra_compact_canary import pipeline as pipeline_module
from app.source_analysis_ultra_compact_canary.errors import SchemaRegressionError
from app.source_analysis_vocabulary_compliance_canary import decoder_integrity
from app.source_analysis_vocabulary_compliance_canary import observe as observe_module
from app.source_analysis_vocabulary_compliance_canary import preflight as preflight_module
from app.source_analysis_vocabulary_compliance_canary.errors import VocabularyParityError

_SRC_RE = re.compile(r"SRC\d{6}")
_EMPTY_NETWORK = {
    "anthropic": 0,
    "openai": 0,
    "whisper": 0,
    "ollama": 0,
    "lm_studio": 0,
    "other_ai": 0,
}
_ACCEPTABLE_FINISH = frozenset({"end_turn", "stop", "end_turn\n"})


@dataclass
class GlobalCleanResult:
    project_name: str
    dry_run: bool
    outcome: str = OUTCOME_FAIL
    pipeline_result: str = "not_started"
    provider_generation: str = "N/A"
    source_map_published: bool = False
    stop_reason: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    classification: str | None = None
    protected_before: dict[str, str] = field(default_factory=dict)
    protected_after: dict[str, str] = field(default_factory=dict)
    protected_unchanged: bool | None = None
    architecture: dict = field(default_factory=dict)
    complexity: dict = field(default_factory=dict)
    local_audit: dict = field(default_factory=dict)
    decoder_integrity: dict = field(default_factory=dict)
    transcript_id: str = ""
    mode: str = "DERIVED"
    segment_count: int | None = None
    word_count: int | None = None
    duration_seconds: float | None = None
    transcript_sha256: str = ""
    original_transcript_sha256: str = ""
    provenance_verified: bool | None = None
    provenance: dict | None = None
    present_src_count: int | None = None
    clean_source_set_count: int | None = None
    removed_src_count: int | None = None
    sparse_src_preserved: bool | None = None
    original_not_selected: bool | None = None
    provider: str = EXPECTED_PROVIDER
    model: str = EXPECTED_MODEL
    prompt_version: str = ""
    prompt_sha256: str = ""
    vocabulary_parity: str = "N/A"
    vocabulary_contract_sha256: str = ""
    missing_from_prompt: list[str] = field(default_factory=list)
    extra_in_prompt: list[str] = field(default_factory=list)
    raw_generation_c_sha256: str = ""
    anthropic_generation_c_sha256: str = ""
    uses_production_generation_c: bool | None = None
    generation_c_unchanged: bool | None = None
    generation_a_absent_from_payload: bool | None = None
    generation_b_absent_from_payload: bool | None = None
    output_format_type: str = ""
    local_compatibility: str = ""
    provider_enums: int | None = None
    strategy: str = ""
    estimated_tokens: int | None = None
    usable_input_budget: int | None = None
    remaining_margin: int | None = None
    estimation_method: str = ""
    model_max_output: int | None = None
    configured_max_output: int | None = None
    request_max_output: int | None = None
    resolved_max_output: int | None = None
    max_output_coherent: bool | None = None
    credential_available: bool | None = None
    signature: str = ""
    cache_hit: bool = False
    cache_isolated_from_canaries: bool | None = None
    cache_status: str = "none"
    cache_written: bool = False
    would_call_ai: bool = False
    dry_run_pass: bool | None = None
    dry_run_sha256: str = ""
    dry_run_sha256_run1: str = ""
    dry_run_sha256_run2: str = ""
    dry_run_deterministic: bool | None = None
    real_call_executed: bool = False
    max_real_calls: int = MAX_REAL_CALLS
    actual_real_calls: int = 0
    max_attempts: int = MAX_ATTEMPTS
    retry: bool = False
    fallback: str | None = None
    http_status: int | None = None
    finish_reason: str | None = None
    request_id: str | None = None
    request_id_present: bool | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    usage_source: str = ""
    input_cost: Any = None
    output_cost: Any = None
    total_cost: Any = None
    cost_status: str = ""
    cost_currency: str = ""
    transport_preserved: str = "N/A"
    transport_sha256: str = ""
    transport_parse: str = "N/A"
    vocabulary_compliance: str = "N/A"
    source_refs: str = "N/A"
    links: str = "N/A"
    decoder: str = "N/A"
    reconstruction: str = "N/A"
    normalization: str = "N/A"
    canonical_validation: str = "N/A"
    editorial_leakage: str = "N/A"
    determinism: str = "N/A"
    determinism_sha_run1: str = ""
    determinism_sha_run2: str = ""
    controlled_tokens_observed: list[dict] = field(default_factory=list)
    invalid_tokens: list[dict] = field(default_factory=list)
    topic_ids: list[str] = field(default_factory=list)
    idea_ids: list[str] = field(default_factory=list)
    example_ids: list[str] = field(default_factory=list)
    reference_ids: list[str] = field(default_factory=list)
    uncertainty_ids: list[str] = field(default_factory=list)
    repetition_ids: list[str] = field(default_factory=list)
    topic_count: int | None = None
    idea_count: int | None = None
    example_count: int | None = None
    reference_count: int | None = None
    uncertainty_count: int | None = None
    repetition_count: int | None = None
    coverage_ratio: float | None = None
    referenced_source_count: int | None = None
    all_refs_in_clean: bool | None = None
    any_removed_referenced: bool | None = None
    main_theme_present: bool | None = None
    voice_profile_present: bool | None = None
    author_intent_kinds: list[str] = field(default_factory=list)
    target_audience_kinds: list[str] = field(default_factory=list)
    source_map_path: str = ""
    source_map_sha256: str = ""
    source_map_stats: dict = field(default_factory=dict)
    project_state_status: str = ""
    report_json_updated: bool | None = None
    writer_called_before_validation: bool = False
    phase4_invoked: bool = False
    network: dict[str, int] = field(default_factory=lambda: dict(_EMPTY_NETWORK))
    files_created: list[str] = field(default_factory=list)
    attempt_number: int = 1
    effective_connect_timeout_seconds: float | None = None
    effective_read_timeout_seconds: float | None = None
    connect_source: str = ""
    read_source: str = ""
    requests_timeout_tuple: list[float] | None = None
    timeout_kind: str | None = None
    elapsed_ms: int | None = None
    policy_match: str = "N/A"
    third_global_timeout_escalation_allowed: bool = False
    other_stages_isolated: bool | None = None
    timeout_env_injected: bool | None = None
    timeout_injection_method: str = ""
    next_action: str = ""
    project_state_before: str = ""

    def to_result_artifact(self) -> dict[str, Any]:
        if self.attempt_number == 2:
            return self.to_attempt2_result_artifact()
        return {
            "schema_version": SCHEMA_VERSION,
            "purpose": PURPOSE,
            "input": {
                "transcript_id": self.transcript_id,
                "mode": self.mode,
                "segments": self.segment_count,
                "words": self.word_count,
                "duration_seconds": self.duration_seconds,
                "transcript_sha256": self.transcript_sha256,
                "provenance": "VERIFIED" if self.provenance_verified else "FAIL",
            },
            "prompt": {
                "version": self.prompt_version,
                "sha256": self.prompt_sha256,
                "vocabulary_parity": self.vocabulary_parity,
            },
            "transport": {
                "version": TRANSPORT_VERSION,
                "generation_c_raw_sha256": self.raw_generation_c_sha256,
                "generation_c_anthropic_sha256": self.anthropic_generation_c_sha256,
                "provider_enums": self.provider_enums if self.provider_enums is not None else 0,
            },
            "preflight": {
                "strategy": self.strategy,
                "estimated_tokens": self.estimated_tokens,
                "usable_input_budget": self.usable_input_budget,
                "remaining_margin": self.remaining_margin,
            },
            "execution": {
                "provider": self.provider,
                "model": self.model,
                "max_real_calls": self.max_real_calls,
                "actual_real_calls": self.actual_real_calls,
                "max_attempts": self.max_attempts,
                "retry": self.retry,
                "fallback": self.fallback,
            },
            "provider": {
                "http_status": self.http_status,
                "finish_reason": self.finish_reason,
                "request_id_present": self.request_id_present,
                "latency_ms": self.latency_ms,
            },
            "pipeline": {
                "transport_preserved": self.transport_preserved,
                "transport_parse": self.transport_parse,
                "vocabulary_compliance": self.vocabulary_compliance,
                "source_refs": self.source_refs,
                "links": self.links,
                "decoder": self.decoder,
                "canonical_reconstruction": self.reconstruction,
                "normalization": self.normalization,
                "canonical_validation": self.canonical_validation,
                "editorial_leakage": self.editorial_leakage,
                "determinism": self.determinism,
            },
            "source_map": {
                "published": self.source_map_published,
                "path": self.source_map_path if self.source_map_published else None,
                "sha256": self.source_map_sha256 or None,
                "stats": dict(self.source_map_stats),
            },
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens,
                "usage_source": self.usage_source or None,
                "estimated_input_tokens": self.estimated_tokens,
            },
            "cost": {
                "input_cost": self.input_cost,
                "output_cost": self.output_cost,
                "total_cost": self.total_cost,
                "status": self.cost_status or None,
                "currency": self.cost_currency or None,
            },
            "network": dict(self.network),
        }

    def to_attempt2_result_artifact(self) -> dict[str, Any]:
        elapsed = self.elapsed_ms if self.elapsed_ms is not None else self.latency_ms
        return {
            "schema_version": SCHEMA_VERSION,
            "phase": "3B_FINAL",
            "attempt_number": 2,
            "policy": {
                "connect_timeout_seconds": 30,
                "read_timeout_seconds": 7200,
                "third_global_timeout_escalation_allowed": False,
            },
            "input": {
                "transcript_id": self.transcript_id,
                "mode": self.mode,
                "segments": self.segment_count,
                "words": self.word_count,
                "duration_seconds": self.duration_seconds,
                "sha256": self.transcript_sha256,
                "present_src_count": self.present_src_count,
                "provenance": "VERIFIED" if self.provenance_verified else "FAIL",
            },
            "prompt": {
                "version": self.prompt_version,
                "sha256": self.prompt_sha256,
                "vocabulary_parity": self.vocabulary_parity,
            },
            "transport_schema": {
                "version": TRANSPORT_VERSION,
                "generation_c_raw_sha256": self.raw_generation_c_sha256,
                "generation_c_anthropic_sha256": self.anthropic_generation_c_sha256,
            },
            "preflight": {
                "strategy": self.strategy,
                "estimated_input_tokens": self.estimated_tokens,
                "usable_input_budget": self.usable_input_budget,
                "remaining_margin": self.remaining_margin,
                "max_output_tokens": self.resolved_max_output,
            },
            "execution": {
                "provider": self.provider,
                "model": self.model,
                "max_real_calls": self.max_real_calls,
                "actual_real_calls": self.actual_real_calls,
                "max_attempts": self.max_attempts,
                "retry": self.retry,
                "fallback": self.fallback,
                "effective_connect_timeout_seconds": self.effective_connect_timeout_seconds,
                "effective_read_timeout_seconds": self.effective_read_timeout_seconds,
            },
            "provider": {
                "http_status": self.http_status,
                "finish_reason": self.finish_reason,
                "timeout_kind": self.timeout_kind,
                "elapsed_ms": elapsed,
                "request_id_present": self.request_id_present,
            },
            "pipeline": {
                "transport_persisted": self.transport_preserved,
                "transport_parse": self.transport_parse,
                "vocabulary": self.vocabulary_compliance,
                "source_refs": self.source_refs,
                "links": self.links,
                "decoder": self.decoder,
                "reconstruction": self.reconstruction,
                "normalization": self.normalization,
                "canonical_validation": self.canonical_validation,
                "editorial_leakage": self.editorial_leakage,
                "determinism": self.determinism,
            },
            "source_map": {
                "published": self.source_map_published,
                "path": self.source_map_path if self.source_map_published else None,
                "sha256": self.source_map_sha256 or None,
                "stats": dict(self.source_map_stats),
            },
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens,
                "usage_source": self.usage_source or None,
                "estimated_input_tokens": self.estimated_tokens,
            },
            "cost": {
                "input_cost": self.input_cost,
                "output_cost": self.output_cost,
                "total_cost": self.total_cost,
                "status": self.cost_status or None,
                "currency": self.cost_currency or None,
            },
            "next_action": self.next_action,
            "network": dict(self.network),
        }

    def to_dry_run_artifact(self) -> dict[str, Any]:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "purpose": PURPOSE,
            "would_call_ai": True,
            "actual_real_calls": 0,
            "provider": self.provider,
            "model": self.model,
            "strategy": self.strategy,
            "prompt": EXPECTED_PROMPT_VERSION,
            "prompt_sha256": self.prompt_sha256,
            "transport": TRANSPORT_VERSION,
            "generation_c": True,
            "provider_enums": 0,
            "vocabulary_parity": self.vocabulary_parity,
            "native_structured_output": True,
            "derived_provenance": "PASS" if self.provenance_verified else "FAIL",
            "output_config_format_type": self.output_format_type,
            "uses_production_generation_c": self.uses_production_generation_c,
            "generation_a_absent_from_payload": self.generation_a_absent_from_payload,
            "generation_b_absent_from_payload": self.generation_b_absent_from_payload,
            "generation_c_unchanged": self.generation_c_unchanged,
            "raw_generation_c_sha256": self.raw_generation_c_sha256,
            "anthropic_generation_c_sha256": self.anthropic_generation_c_sha256,
            "retry": False,
            "fallback": None,
            "max_real_calls": MAX_REAL_CALLS,
            "max_attempts": MAX_ATTEMPTS,
            "input": {
                "transcript_id": self.transcript_id,
                "mode": self.mode,
                "segments": self.segment_count,
                "words": self.word_count,
                "duration_seconds": self.duration_seconds,
                "transcript_sha256": self.transcript_sha256,
                "present_src_count": self.present_src_count,
                "provenance": "VERIFIED" if self.provenance_verified else "FAIL",
            },
            "preflight": {
                "strategy": self.strategy,
                "estimated_tokens": self.estimated_tokens,
                "usable_input_budget": self.usable_input_budget,
                "remaining_margin": self.remaining_margin,
                "model_max_output": self.model_max_output,
                "configured_max_output": self.configured_max_output,
                "resolved_max_output": self.resolved_max_output,
                "max_output_coherent": self.max_output_coherent,
            },
            "credential_available": self.credential_available,
            "cache_status": self.cache_status,
            "cache_isolated_from_canaries": self.cache_isolated_from_canaries,
            "signature": self.signature,
            "network": dict(_EMPTY_NETWORK),
            "call_guard": {
                "max_real_calls": MAX_REAL_CALLS,
                "max_attempts": MAX_ATTEMPTS,
                "retry": False,
                "fallback": None,
            },
        }
        if self.attempt_number == 2:
            payload["attempt_number"] = 2
            payload["phase"] = "3B_FINAL"
            payload["generation_c_raw_sha256"] = self.raw_generation_c_sha256
            payload["generation_c_anthropic_sha256"] = self.anthropic_generation_c_sha256
            payload["schema_metrics"] = {
                "provider_enums": self.provider_enums if self.provider_enums is not None else 0,
            }
            payload["effective_connect_timeout_seconds"] = (
                self.effective_connect_timeout_seconds
            )
            payload["connect_source"] = self.connect_source
            payload["effective_read_timeout_seconds"] = (
                self.effective_read_timeout_seconds
            )
            payload["read_source"] = self.read_source
            payload["requests_timeout"] = list(self.requests_timeout_tuple or [])
            payload["third_global_timeout_escalation_allowed"] = False
            payload["policy_match"] = self.policy_match
            payload["other_stages_isolated"] = self.other_stages_isolated
            payload["timeout_injection"] = {
                "method": self.timeout_injection_method or "process_scoped_os_environ",
                "injected": self.timeout_env_injected,
                "real_dotenv_modified": False,
            }
        return payload


def _artifact_writer(attempt_number: int):
    if attempt_number == 2:
        from app.source_analysis_global_clean_attempt2 import writer as attempt2_writer

        return attempt2_writer
    return artifact_writer


def _integrity_module(attempt_number: int):
    if attempt_number == 2:
        from app.source_analysis_global_clean_attempt2 import integrity as attempt2_integrity

        return attempt2_integrity
    return integrity_module


def run_global_clean_source_analysis(
    project_name: str,
    *,
    dry_run: bool,
    engine=None,
    sortie_dir: Path | None = None,
    require_protected: bool = True,
    require_credential: bool | None = None,
    write_artifacts: bool = True,
    lock_production_route: bool | None = None,
    attempt_number: int = 1,
    inject_timeout_env: bool | None = None,
) -> GlobalCleanResult:
    """
    Préflight + au plus un appel réel Anthropic sur le transcript clean.

    `engine` est réservé aux tests (FakeAIEngine). Sans injection, le moteur
    est Anthropic / claude-sonnet-5, retry désactivé. Les timeouts connect
    et read viennent de la résolution standard (étape / env / défauts),
    plus d'un scalaire REAL_CALL_TIMEOUT_SECONDS.
    """
    result = GlobalCleanResult(
        project_name=project_name,
        dry_run=dry_run,
        attempt_number=int(attempt_number),
    )
    if result.attempt_number == 2:
        result.third_global_timeout_escalation_allowed = False
    need_credential = engine is None if require_credential is None else require_credential
    lock_route = engine is None if lock_production_route is None else lock_production_route
    should_inject = (
        result.attempt_number == 2 if inject_timeout_env is None else inject_timeout_env
    )

    try:
        _execute(
            result,
            project_name,
            dry_run=dry_run,
            engine=engine,
            sortie_dir=sortie_dir,
            require_protected=require_protected,
            require_credential=need_credential,
            write_artifacts=write_artifacts,
            lock_production_route=lock_route,
            inject_timeout_env=should_inject,
        )
    except Exception as exc:
        if result.stop_reason is None:
            result.stop_reason = (
                STOP_AFTER_CALL if result.real_call_executed else STOP_PRE_CALL
            )
        result.error_type = result.error_type or type(exc).__name__
        result.error_message = result.error_message or str(exc)
        if result.pipeline_result == "not_started":
            result.pipeline_result = "FAIL" if result.real_call_executed else "N/A"
        result.outcome = _decide_outcome(result)
        _assign_next_action(result)
        if write_artifacts:
            _write_terminal_artifacts(result, project_name, sortie_dir)
        _safe_post_snapshot(result, project_name, sortie_dir, require_protected)
        return result

    result.outcome = _decide_outcome(result)
    _assign_next_action(result)
    if write_artifacts:
        _write_terminal_artifacts(result, project_name, sortie_dir)
    _safe_post_snapshot(result, project_name, sortie_dir, require_protected)
    return result


def _execute(
    result: GlobalCleanResult,
    project_name: str,
    *,
    dry_run: bool,
    engine,
    sortie_dir: Path | None,
    require_protected: bool,
    require_credential: bool,
    write_artifacts: bool,
    lock_production_route: bool,
    inject_timeout_env: bool = False,
) -> None:
    writer = _artifact_writer(result.attempt_number)
    integ = _integrity_module(result.attempt_number)

    if result.attempt_number == 2 and inject_timeout_env:
        from app.source_analysis_global_clean_attempt2.timeouts import (
            inject_attempt2_timeout_env,
        )

        injection = inject_attempt2_timeout_env()
        result.timeout_env_injected = True
        result.timeout_injection_method = injection["injection"]
    elif result.attempt_number == 2:
        result.timeout_env_injected = False

    if result.attempt_number == 2:
        snapshot = integ.snapshot_attempt2_protected(
            project_name,
            sortie_dir=sortie_dir,
            require_all=require_protected,
        )
    else:
        snapshot = integ.snapshot_final_protected(
            project_name,
            sortie_dir=sortie_dir,
            require_all=require_protected,
        )
    result.protected_before = snapshot.to_dict()

    if result.attempt_number == 2:
        from app.source_analysis_long_run_policy.audit import inspect_project_state
        from app.source_analysis_global_clean_attempt2.errors import UnexpectedProjectState

        prior_state = inspect_project_state(project_name)
        result.project_state_before = str(prior_state.get("status") or "")
        if require_protected:
            status = str(prior_state.get("status") or "").lower()
            if status in {"completed", "success"}:
                result.classification = "PRE_CALL_PROJECT_STATE_UNEXPECTED"
                raise UnexpectedProjectState(
                    "source_analysis est déjà SUCCESS. STOP : l'essai #2 "
                    "n'écrase pas un état réussi."
                )

    map_path = writer.production_source_map_path(
        project_name, sortie_dir=sortie_dir
    )
    result.source_map_path = map_path.as_posix()
    map_existed = map_path.exists()
    if map_existed:
        result.classification = CLASS_PRE_CALL_EXISTING_MAP
        result.stop_reason = STOP_EXISTING_MAP
        raise ExistingSourceMapStop(
            f"{map_path} existe déjà. STOP avant réseau : aucun écrasement."
        )

    try:
        result.architecture = architecture_module.verify_generation_c_architecture()
        result.complexity = architecture_module.audit_generation_c_complexity()
        result.local_audit = architecture_module.audit_local_anthropic_generation_c()
    except SchemaRegressionError as exc:
        result.classification = CLASS_PRE_CALL_SCHEMA_DRIFT
        raise SchemaDriftError(str(exc)) from exc

    result.local_compatibility = result.local_audit.get("compatibility", "")
    result.raw_generation_c_sha256 = result.local_audit["raw_sha256"]
    result.anthropic_generation_c_sha256 = result.local_audit["anthropic_sha256"]
    result.provider_enums = int(result.local_audit.get("provider_enums") or 0)
    result.generation_c_unchanged = True
    result.decoder_integrity = decoder_integrity.verify_decoder_integrity()

    result.prompt_version = preflight_module.verify_prompt_version()

    clean_path = clean_json_path(project_name, sortie_dir=sortie_dir)
    provenance_path = audit_path(project_name, sortie_dir=sortie_dir)
    original_path = transcripts_dir(project_name, sortie_dir=sortie_dir) / "transcript_data.json"
    result.original_not_selected = Path(clean_path).resolve() != Path(original_path).resolve()
    if not result.original_not_selected:
        raise PreCallFailure(
            "Le Source Analyzer a sélectionné le transcript original non nettoyé."
        )

    from app.source_analysis.provenance import validate_derived_provenance

    proven = validate_derived_provenance(
        derived_path=clean_path,
        provenance_path=provenance_path,
        original_transcript_path=original_path,
    )
    result.provenance = proven.to_dict()
    result.provenance_verified = True
    result.removed_src_count = proven.removed_count
    result.sparse_src_preserved = (
        proven.removed_set_matches is True and proven.survivors_unchanged is True
    )

    transcript = load_transcript_input(
        clean_path,
        project_name=project_name,
        mode=TranscriptInputMode.DERIVED,
        provenance_path=provenance_path,
        original_transcript_path=original_path,
    )
    result.transcript_id = transcript.transcript_id
    result.segment_count = transcript.segment_count
    result.word_count = transcript.word_count
    result.duration_seconds = transcript.duration_seconds
    result.transcript_sha256 = sha256_of_file(clean_path)
    result.original_transcript_sha256 = sha256_of_file(original_path)
    clean_srcs = set(transcript.src_ids())
    result.present_src_count = len(clean_srcs)
    result.clean_source_set_count = len(clean_srcs)
    if not result.sparse_src_preserved:
        raise PreCallFailure("Intégrité SRC sparse / provenance échouée.")

    settings = resolve_stage_settings(STAGE)
    if lock_production_route:
        if settings.provider != EXPECTED_PROVIDER or settings.model != EXPECTED_MODEL:
            raise PreCallFailure(
                f"Routage verrouillé : attendu {EXPECTED_PROVIDER}/"
                f"{EXPECTED_MODEL}, obtenu {settings.provider}/{settings.model}."
            )
    result.provider = settings.provider
    result.model = settings.model or EXPECTED_MODEL

    system_prompt = production_prompt.build_system_prompt(transcript.primary_language)
    user_prompt = production_prompt.build_user_prompt(transcript)
    try:
        preflight_module.verify_vocabulary_contract_included(system_prompt)
        preflight_module.verify_protocol_token_rules(system_prompt)
        preflight_module.verify_fallbacks(system_prompt)
        parity = preflight_module.verify_vocabulary_parity(system_prompt)
    except VocabularyParityError as exc:
        result.classification = CLASS_PRE_CALL_PARITY
        raise PreCallFailure(str(exc)) from exc

    result.missing_from_prompt = list(parity["missing_from_prompt"])
    result.extra_in_prompt = list(parity["extra_in_prompt"])
    result.vocabulary_parity = "PASS"
    result.vocabulary_contract_sha256 = preflight_module.vocabulary_contract_sha256()
    result.prompt_sha256 = cache_module.prompt_fingerprint(system_prompt, user_prompt)
    if require_protected and result.prompt_sha256 != REFERENCE_3B44_PROMPT_SHA256:
        raise PreCallFailure(
            "Prompt 1.3 SHA ≠ diagnostic 3B.4.4 / 3B.4.5. "
            f"recalculé={result.prompt_sha256}"
        )

    generation_c = architecture_module.production_generation_c_schema()
    result.uses_production_generation_c = (
        ultra_compact_schema_fingerprint(generation_c) == result.raw_generation_c_sha256
    )
    if not result.uses_production_generation_c:
        result.classification = CLASS_PRE_CALL_SCHEMA_DRIFT
        raise SchemaDriftError("Le run n'utilise pas Generation C de production.")
    if TRANSPORT_VERSION != SEMANTIC_TRANSPORT_VERSION:
        raise PreCallFailure("transport_version inattendu.")
    if SOURCE_ANALYZER_PROMPT_VERSION != EXPECTED_PROMPT_VERSION:
        raise PreCallFailure("Prompt version incohérente au moment de l'AIRequest.")

    request = AIRequest(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model=EXPECTED_MODEL,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
        response_schema=generation_c,
        metadata={"stage": STAGE, "project": project_name, "final_global_clean": True},
    )

    inspector = AnthropicEngine(model=EXPECTED_MODEL, api_key="final-inspect-unused")
    payload = inspector.build_payload(request, EXPECTED_MODEL)
    fmt = (payload.get("output_config") or {}).get("format") or {}
    result.output_format_type = str(fmt.get("type") or "")
    payload_schema = fmt.get("schema") or {}
    payload_schema_sha = schema_fingerprint(payload_schema)
    old_adapted_sha = schema_fingerprint(
        inspector.build_payload(
            replace(request, response_schema=build_response_schema()),
            EXPECTED_MODEL,
        )
        .get("output_config", {})
        .get("format", {})
        .get("schema")
        or {}
    )
    compact_adapted_sha = schema_fingerprint(
        inspector.build_payload(
            replace(request, response_schema=build_compact_response_schema()),
            EXPECTED_MODEL,
        )
        .get("output_config", {})
        .get("format", {})
        .get("schema")
        or {}
    )
    result.generation_a_absent_from_payload = (
        payload_schema_sha != old_adapted_sha
        and not architecture_module.payload_contains_ab_schema(payload_schema)
    )
    result.generation_b_absent_from_payload = payload_schema_sha != compact_adapted_sha
    if result.output_format_type != "json_schema":
        raise PreCallFailure(
            f"output_config.format.type = {result.output_format_type!r}, "
            "attendu json_schema."
        )
    if payload_schema_sha != result.anthropic_generation_c_sha256:
        result.classification = CLASS_PRE_CALL_SCHEMA_DRIFT
        raise SchemaDriftError(
            "Le schéma adapté du payload n'est pas Generation C Anthropic."
        )
    if not result.generation_a_absent_from_payload:
        raise PreCallFailure("Generation A est encore identifiable dans le payload.")
    if not result.generation_b_absent_from_payload:
        raise PreCallFailure("Generation B est encore identifiable dans le payload.")

    capabilities = inspector.capabilities(EXPECTED_MODEL)
    result.model_max_output = capabilities.max_output_tokens
    result.configured_max_output = settings.max_output_tokens
    result.request_max_output = request.max_output_tokens
    result.resolved_max_output = inspector.resolve_max_output_tokens(request)
    result.max_output_coherent = (
        result.resolved_max_output == result.model_max_output
        and result.resolved_max_output == EXPECTED_MODEL_MAX_OUTPUT
        and (
            result.configured_max_output is None
            or result.configured_max_output == EXPECTED_MODEL_MAX_OUTPUT
        )
    )
    if not result.max_output_coherent:
        result.classification = CLASS_PRE_CALL_OUTPUT_CAPACITY
        raise PreCallFailure(
            "Plafond de sortie incohérent : "
            f"model={result.model_max_output} configured={result.configured_max_output} "
            f"resolved={result.resolved_max_output}."
        )

    plan = plan_context(
        transcript,
        capabilities,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        safety_ratio=settings.context_safety_ratio,
    )
    result.strategy = plan.strategy
    result.estimated_tokens = plan.estimated_input_tokens
    result.usable_input_budget = plan.usable_input_context
    result.remaining_margin = int(plan.usable_input_context) - int(plan.estimated_input_tokens)
    result.estimation_method = plan.estimation_method
    if plan.strategy != STRATEGY_GLOBAL:
        result.classification = CLASS_PRE_CALL_NOT_GLOBAL
        raise PreCallFailure(
            "Stratégie ≠ global : "
            f"{plan.strategy}. La consolidation multi-fenêtres n'est pas autorisée."
        )

    prompt_srcs = set(_SRC_RE.findall(user_prompt))
    removed = set(proven.removed_source_refs)
    if prompt_srcs != clean_srcs or not prompt_srcs.isdisjoint(removed):
        raise PreCallFailure(
            "Le prompt ne préserve pas exactement les SRC du clean."
        )

    result.signature = cache_module.build_signature(
        cache_module.SignatureInputs(
            transcript_sha256=transcript.content_sha256,
            transcript_id=transcript.transcript_id,
            prompt_version=SOURCE_ANALYZER_PROMPT_VERSION,
            prompt_sha256=result.prompt_sha256,
            schema_version=SOURCE_MAP_SCHEMA_VERSION,
            response_schema_sha256=ultra_compact_schema_fingerprint(generation_c),
            provider=settings.provider,
            model=settings.model or "",
            temperature=settings.temperature,
            max_output_tokens=settings.max_output_tokens,
            context_safety_ratio=float(settings.context_safety_ratio),
            output_language=transcript.primary_language,
        )
    )
    result.cache_isolated_from_canaries = result.signature not in CANARY_SIGNATURE_MARKS
    if not result.cache_isolated_from_canaries:
        raise PreCallFailure("Collision de signature avec un cache canary.")

    published = writer_module.read_source_map_payload(map_path)
    state = load_project_state(project_name)
    state_block = state_module.load_state_block(state)
    cache_valid = cache_module.is_cache_valid(
        signature=result.signature,
        state_block=state_block,
        published_payload=published,
    )
    if cache_valid:
        result.cache_hit = True
        result.cache_status = "unexpected_hit"
        result.classification = CLASS_PRE_CALL_UNEXPECTED_CACHE
        result.stop_reason = STOP_CACHE_HIT
        raise UnexpectedCacheHit(
            "Cache hit inattendu sur le premier run global Prompt 1.3 / "
            "Generation C. STOP PRE_CALL : aucun canary n'est un cache global."
        )
    result.cache_status = "miss"
    result.cache_hit = False

    result.would_call_ai = True
    result.credential_available = anthropic_credential_available()
    _record_resolved_timeouts(result, request, inspector)
    if result.attempt_number == 2:
        _enforce_attempt2_timeout_and_policy(
            result,
            project_name,
            sortie_dir=sortie_dir,
            require_protected=require_protected,
            request=request,
            inspector=inspector,
        )

    dry_payload = result.to_dry_run_artifact()
    encoded = (json.dumps(dry_payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    result.dry_run_sha256_run1 = content_hash(encoded.decode("utf-8"))
    result.dry_run_sha256_run2 = content_hash(
        json.dumps(result.to_dry_run_artifact(), ensure_ascii=False, indent=2) + "\n"
    )
    result.dry_run_deterministic = result.dry_run_sha256_run1 == result.dry_run_sha256_run2
    result.dry_run_sha256 = result.dry_run_sha256_run1
    if not result.dry_run_deterministic:
        raise PreCallFailure("Dry-run non déterministe : SHA run1 ≠ run2.")

    if write_artifacts:
        writer.write_bytes_atomic(
            writer.dry_run_path(project_name, sortie_dir=sortie_dir),
            dry_payload,
        )
        result.files_created.append(writer.DRY_RUN_ARTIFACT_NAME)

    if dry_run:
        result.pipeline_result = "DRY_RUN"
        result.actual_real_calls = 0
        result.real_call_executed = False
        result.dry_run_pass = True
        result.outcome = OUTCOME_PASS
        writer.assert_no_new_production_source_map(
            project_name, sortie_dir=sortie_dir, existed_before=map_existed
        )
        return

    result.dry_run_pass = True
    if require_credential and not result.credential_available:
        result.classification = CLASS_PRE_CALL_CREDENTIAL_MISSING
        raise PreCallFailure("Credential Anthropic indisponible. STOP : 0 appel.")

    if result.attempt_number == 2:
        _enforce_attempt2_timeout_and_policy(
            result,
            project_name,
            sortie_dir=sortie_dir,
            require_protected=require_protected,
            request=request,
            inspector=inspector,
        )

    retry = RetryPolicy(max_attempts=MAX_ATTEMPTS, base_delay_seconds=0.0)
    if engine is None:
        inner = get_ai_engine(
            EXPECTED_PROVIDER,
            model=EXPECTED_MODEL,
            retry_policy=retry,
        )
        if inner.provider_name != EXPECTED_PROVIDER or inner.resolve_model() != EXPECTED_MODEL:
            raise PreCallFailure(
                f"Moteur résolu {inner.provider_name}/{inner.resolve_model()} "
                f"≠ {EXPECTED_PROVIDER}/{EXPECTED_MODEL}."
            )
    else:
        inner = engine
        inner._retry_policy = retry

    guard = RealCallGuard(max_calls=MAX_REAL_CALLS)
    guarded = GuardedEngine(inner, guard)
    tracker = CostTracker()

    try:
        response = guarded.generate(request)
    except Exception as exc:
        result.actual_real_calls = guard.call_count
        result.real_call_executed = guard.call_count > 0
        result.network["anthropic"] = guard.call_count
        result.stop_reason = STOP_AFTER_CALL if guard.call_count else STOP_PRE_CALL
        attached = getattr(exc, "response", None)
        if attached is not None:
            _fill_usage(result, attached, tracker, failed=True, error=exc, persist=True)
            _preserve_transport(
                result,
                project_name,
                sortie_dir,
                write_artifacts=write_artifacts,
                parsed=getattr(attached, "parsed", None),
                raw_text=getattr(attached, "text", None),
            )
            if attached.has_usage or attached.request_id or attached.parsed is not None:
                result.provider_generation = "PASS"
                result.http_status = result.http_status or 200
            else:
                result.provider_generation = "FAIL"
                result.http_status = classify_module.extract_http_status(exc)
        else:
            result.provider_generation = "FAIL"
            result.http_status = classify_module.extract_http_status(exc)
            if isinstance(exc, AIError):
                record = tracker.record_failure(
                    provider=EXPECTED_PROVIDER,
                    model=EXPECTED_MODEL,
                    stage=STAGE,
                    error=exc,
                    response=None,
                )
                record_call(project_name, record)
                cost = record.cost
                result.cost_status = cost.status or "unavailable"
                result.input_cost = (
                    None if cost.input_cost is None else str(cost.input_cost)
                )
                result.output_cost = (
                    None if cost.output_cost is None else str(cost.output_cost)
                )
                result.total_cost = (
                    None if cost.total_cost is None else str(cost.total_cost)
                )
                result.cost_currency = cost.currency or ""
            if result.input_tokens is None and result.output_tokens is None:
                result.cost_status = result.cost_status or "unavailable"
        result.error_type = classify_module.extract_error_type(exc) or type(exc).__name__
        result.error_message = classify_module.truncate_error_message(exc)
        if isinstance(exc, AITimeoutError):
            result.timeout_kind = exc.timeout_kind or "unknown"
            if exc.elapsed_ms is not None:
                result.elapsed_ms = exc.elapsed_ms
                result.latency_ms = exc.elapsed_ms
            if exc.connect_timeout_seconds is not None:
                result.effective_connect_timeout_seconds = exc.connect_timeout_seconds
            if exc.read_timeout_seconds is not None:
                result.effective_read_timeout_seconds = exc.read_timeout_seconds
        result.pipeline_result = "FAIL" if result.provider_generation == "PASS" else "N/A"
        _record_failed_state(result, project_name, plan)
        writer.assert_no_new_production_source_map(
            project_name, sortie_dir=sortie_dir, existed_before=map_existed
        )
        return

    result.actual_real_calls = guard.call_count
    result.real_call_executed = True
    result.network["anthropic"] = guard.call_count
    result.provider_generation = "PASS"
    result.http_status = 200
    result.provider = response.provider
    result.model = response.model
    result.finish_reason = response.finish_reason
    result.request_id = response.request_id
    result.request_id_present = bool(response.request_id)
    result.elapsed_ms = getattr(response, "latency_ms", None)
    _fill_usage(result, response, tracker, failed=False, persist=True)

    try:
        _preserve_transport(
            result,
            project_name,
            sortie_dir,
            write_artifacts=write_artifacts,
            parsed=response.parsed,
            raw_text=response.text,
        )
    except Exception as exc:
        result.stop_reason = STOP_TRANSPORT_WRITE
        result.pipeline_result = "FAIL"
        result.error_type = type(exc).__name__
        result.error_message = str(exc)
        _record_failed_state(result, project_name, plan)
        raise TransportPreserveError(
            "Préservation du transport échouée. Publication interdite."
        ) from exc

    if _output_truncated(response.finish_reason):
        result.pipeline_result = "FAIL"
        result.stop_reason = STOP_TRUNCATED
        result.error_type = "SourceMapTruncatedError"
        result.error_message = f"finish_reason={response.finish_reason}"
        _record_failed_state(result, project_name, plan)
        writer.assert_no_new_production_source_map(
            project_name, sortie_dir=sortie_dir, existed_before=map_existed
        )
        return

    parsed = response.parsed
    if isinstance(parsed, dict):
        result.controlled_tokens_observed = observe_module.observe_controlled_tokens(parsed)
        result.invalid_tokens = observe_module.invalid_controlled_tokens(
            result.controlled_tokens_observed
        )
        result.vocabulary_compliance = observe_module.vocabulary_compliance_status(
            result.controlled_tokens_observed
        )
    else:
        result.vocabulary_compliance = "FAIL"
        result.invalid_tokens = [{"vocabulary": "root", "actual_token": type(parsed).__name__, "allowed_values": []}]

    provenance = AnalysisProvenance(
        prompt_version=SOURCE_ANALYZER_PROMPT_VERSION,
        schema_version=SOURCE_MAP_SCHEMA_VERSION,
        provider=response.provider,
        model=response.model,
        strategy=STRATEGY_GLOBAL,
        signature=result.signature,
    )
    first = pipeline_module.run_local_pipeline(
        parsed,
        transcript,
        transcript.segments,
        provenance=provenance,
    )
    _apply_pipeline(result, first)

    if result.vocabulary_compliance != "PASS" or result.invalid_tokens:
        result.vocabulary_compliance = "FAIL"
        result.pipeline_result = "FAIL"
        _write_failed_candidates(result, project_name, sortie_dir, first, write_artifacts)
        _record_failed_state(result, project_name, plan)
        writer.assert_no_new_production_source_map(
            project_name, sortie_dir=sortie_dir, existed_before=map_existed
        )
        return

    second = pipeline_module.run_local_pipeline(
        parsed,
        transcript,
        transcript.segments,
        provenance=provenance,
    )
    if first.source_map is not None and second.source_map is not None:
        sha1 = content_hash(writer_module.render_source_map(first.source_map.to_dict()))
        sha2 = content_hash(writer_module.render_source_map(second.source_map.to_dict()))
        result.determinism_sha_run1 = sha1
        result.determinism_sha_run2 = sha2
        result.determinism = "PASS" if sha1 == sha2 else "FAIL"
    else:
        result.determinism = "FAIL"

    pipeline_ok = _pipeline_passed(result)
    if not pipeline_ok:
        result.pipeline_result = "FAIL"
        _write_failed_candidates(result, project_name, sortie_dir, first, write_artifacts)
        _record_failed_state(result, project_name, plan)
        writer.assert_no_new_production_source_map(
            project_name, sortie_dir=sortie_dir, existed_before=map_existed
        )
        return

    source_map = first.source_map
    payload = source_map.to_dict()
    referenced = set(source_map.all_source_refs())
    result.all_refs_in_clean = referenced <= clean_srcs
    result.any_removed_referenced = bool(referenced & removed)
    result.referenced_source_count = len(referenced)
    result.coverage_ratio = (
        round(len(referenced) / transcript.segment_count, 4)
        if transcript.segment_count
        else 0.0
    )
    if not result.all_refs_in_clean or result.any_removed_referenced:
        result.source_refs = "FAIL"
        result.pipeline_result = "FAIL"
        _write_failed_candidates(result, project_name, sortie_dir, first, write_artifacts)
        _record_failed_state(result, project_name, plan)
        writer.assert_no_new_production_source_map(
            project_name, sortie_dir=sortie_dir, existed_before=map_existed
        )
        return

    writer_module.write_source_map(map_path, payload)
    if not map_path.exists():
        raise PreCallFailure("Publication atomique : source_map.json absent après write.")
    leftover = writer_module.partial_path(map_path)
    if leftover.exists():
        raise PreCallFailure("Fichier .partial abandonné après publication.")

    result.source_map_published = True
    result.source_map_sha256 = sha256_of_file(map_path)
    result.source_map_stats = dict(payload.get("stats") or {})
    result.files_created.append("analysis/source_map.json")
    result.pipeline_result = "PASS"
    result.cache_written = True

    _write_completed_state(
        project_name,
        path=map_path,
        signature=result.signature,
        provider=response.provider,
        model=response.model,
        plan=plan,
        stats=payload["stats"],
    )
    result.project_state_status = "completed"
    try:
        build_project_report(project_name)
        result.report_json_updated = True
        result.files_created.append("report.json")
    except Exception as exc:
        result.report_json_updated = False
        result.error_message = f"report.json : {exc}"
    result.files_created.append("project_state.json")


def _record_resolved_timeouts(
    result: GlobalCleanResult,
    request: AIRequest,
    inspector: AnthropicEngine,
) -> dict:
    timeouts = inspector.resolve_timeouts(request)
    connect, read = timeouts.as_requests_timeout()
    result.effective_connect_timeout_seconds = timeouts.connect_seconds
    result.effective_read_timeout_seconds = timeouts.read_seconds
    result.connect_source = timeouts.connect_source
    result.read_source = timeouts.read_source
    result.requests_timeout_tuple = [connect, read]
    return {
        "connect_seconds": timeouts.connect_seconds,
        "connect_source": timeouts.connect_source,
        "read_seconds": timeouts.read_seconds,
        "read_source": timeouts.read_source,
        "requests_timeout": [connect, read],
        "requests_timeout_shape": "tuple",
        "scalar_timeout_used": False,
        "total_wall_clock_timeout": False,
    }


def _enforce_attempt2_timeout_and_policy(
    result: GlobalCleanResult,
    project_name: str,
    *,
    sortie_dir: Path | None,
    require_protected: bool,
    request: AIRequest,
    inspector: AnthropicEngine,
) -> None:
    from app.source_analysis_global_clean_attempt2.constants import (
        CLASS_PRE_CALL_POLICY_MISMATCH,
        CLASS_PRE_CALL_TIMEOUT_MISMATCH,
    )
    from app.source_analysis_global_clean_attempt2.policy import (
        effective_policy_view,
        match_attempt2_policy,
    )
    from app.source_analysis_global_clean_attempt2.timeouts import (
        assert_attempt2_timeouts,
        assert_other_stages_isolated,
        diagnose_other_stages,
        resolve_attempt2_timeouts,
        third_timeout_escalation_prohibited,
    )

    third_timeout_escalation_prohibited()
    result.third_global_timeout_escalation_allowed = False
    independent = resolve_attempt2_timeouts(request=request, engine=inspector)
    recorded = _record_resolved_timeouts(result, request, inspector)
    if independent != {
        "connect_seconds": recorded["connect_seconds"],
        "connect_source": recorded["connect_source"],
        "read_seconds": recorded["read_seconds"],
        "read_source": recorded["read_source"],
        "requests_timeout": recorded["requests_timeout"],
        "requests_timeout_shape": recorded["requests_timeout_shape"],
        "scalar_timeout_used": recorded["scalar_timeout_used"],
        "total_wall_clock_timeout": recorded["total_wall_clock_timeout"],
    }:
        result.classification = CLASS_PRE_CALL_TIMEOUT_MISMATCH
        raise PreCallFailure(
            "Résolution timeout inspecteur ≠ résolution indépendante."
        )
    try:
        assert_attempt2_timeouts(recorded)
        stages = diagnose_other_stages()
        result.other_stages_isolated = assert_other_stages_isolated(stages)
    except Exception:
        result.classification = CLASS_PRE_CALL_TIMEOUT_MISMATCH
        raise
    try:
        match = match_attempt2_policy(
            project_name,
            sortie_dir=sortie_dir,
            effective=effective_policy_view(
                connect_seconds=result.effective_connect_timeout_seconds or 0,
                read_seconds=result.effective_read_timeout_seconds or 0,
                max_real_calls=result.max_real_calls,
                max_attempts=result.max_attempts,
                retry=result.retry,
                fallback=result.fallback,
                attempt_number=result.attempt_number,
                third_escalation=result.third_global_timeout_escalation_allowed,
            ),
            require_file=require_protected,
        )
        result.policy_match = match["status"]
    except Exception:
        result.classification = CLASS_PRE_CALL_POLICY_MISMATCH
        raise


def _assign_next_action(result: GlobalCleanResult) -> None:
    if result.attempt_number != 2:
        return
    from app.source_analysis_global_clean_attempt2.constants import (
        NEXT_PHASE_ON_FAIL,
        NEXT_PHASE_ON_PARTIAL,
        NEXT_PHASE_ON_PASS,
        NEXT_PHASE_ON_TIMEOUT,
    )

    if result.outcome == OUTCOME_PASS and result.source_map_published:
        result.next_action = NEXT_PHASE_ON_PASS
        return
    if result.error_type == "AITimeoutError" or result.timeout_kind:
        result.next_action = NEXT_PHASE_ON_TIMEOUT
        return
    if result.outcome == OUTCOME_PARTIAL:
        result.next_action = NEXT_PHASE_ON_PARTIAL
        return
    result.next_action = NEXT_PHASE_ON_FAIL


def _output_truncated(finish_reason: str | None) -> bool:
    if is_truncated_finish_reason(finish_reason):
        return True
    value = str(finish_reason or "").strip().lower()
    return value in {"truncated", "max_output_tokens"}


def _preserve_transport(
    result: GlobalCleanResult,
    project_name: str,
    sortie_dir: Path | None,
    *,
    write_artifacts: bool,
    parsed: Any,
    raw_text: str | None,
) -> None:
    if not write_artifacts:
        result.transport_preserved = "SKIPPED"
        return
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "transport_version": TRANSPORT_VERSION,
        "purpose": PURPOSE,
    }
    if isinstance(parsed, dict):
        body["transport"] = dict(parsed)
    elif raw_text:
        body["raw_text"] = raw_text
        body["transport"] = None
    else:
        body["transport"] = None
        body["note"] = "no_provider_body"
    writer = _artifact_writer(result.attempt_number)
    path = writer.transport_path(project_name, sortie_dir=sortie_dir)
    writer.write_bytes_atomic(path, body)
    result.transport_preserved = "PASS"
    result.transport_sha256 = sha256_of_file(path)
    if writer.TRANSPORT_ARTIFACT_NAME not in result.files_created:
        result.files_created.append(writer.TRANSPORT_ARTIFACT_NAME)


def _apply_pipeline(result: GlobalCleanResult, local) -> None:
    result.transport_parse = local.transport_parse
    result.source_refs = local.source_refs_in_canary
    result.links = local.link_validation
    result.decoder = local.decoder
    result.reconstruction = local.reconstruction
    result.normalization = local.normalization
    result.canonical_validation = local.canonical_validation
    result.editorial_leakage = local.editorial_leakage
    result.topic_ids = list(local.topic_ids or [])
    result.idea_ids = list(local.idea_ids or [])
    result.example_ids = list(local.example_ids or [])
    result.reference_ids = list(local.reference_ids or [])
    result.uncertainty_ids = list(local.uncertainty_ids or [])
    result.repetition_ids = list(local.repetition_ids or [])
    result.topic_count = len(result.topic_ids)
    result.idea_count = len(result.idea_ids)
    result.example_count = len(result.example_ids)
    result.reference_count = len(result.reference_ids)
    result.uncertainty_count = len(result.uncertainty_ids)
    result.repetition_count = len(result.repetition_ids)
    if local.source_map is not None:
        analysis = local.source_map.source_analysis
        result.main_theme_present = bool(str(getattr(analysis, "main_theme", "") or "").strip())
        voice = local.source_map.author_voice_profile
        result.voice_profile_present = voice is not None
        intent = getattr(analysis, "author_intent", None)
        audience = getattr(analysis, "target_audience", None)
        result.author_intent_kinds = list(getattr(intent, "kinds", None) or [])
        result.target_audience_kinds = list(getattr(audience, "kinds", None) or [])
        stats = local.source_map.stats
        result.source_map_stats = {
            "topic_count": stats.topic_count,
            "idea_count": stats.idea_count,
            "example_count": stats.example_count,
            "reference_count": stats.reference_count,
            "uncertainty_count": stats.uncertainty_count,
            "repetition_count": stats.repetition_count,
            "source_coverage_ratio": stats.source_coverage_ratio,
            "referenced_source_segments": stats.referenced_source_segments,
        }
    if local.errors:
        result.error_message = " | ".join(local.errors)
        result.error_type = result.error_type or "LocalPipelineError"


def _pipeline_passed(result: GlobalCleanResult) -> bool:
    steps = (
        result.transport_parse,
        result.vocabulary_compliance,
        result.source_refs,
        result.links,
        result.decoder,
        result.reconstruction,
        result.normalization,
        result.canonical_validation,
        result.editorial_leakage,
        result.determinism,
    )
    return all(step == "PASS" for step in steps) and not result.invalid_tokens


def _write_failed_candidates(
    result: GlobalCleanResult,
    project_name: str,
    sortie_dir: Path | None,
    local,
    write_artifacts: bool,
) -> None:
    if not write_artifacts:
        return
    writer = _artifact_writer(result.attempt_number)
    if local.raw_canonical is not None:
        writer.write_bytes_atomic(
            writer.failed_raw_path(project_name, sortie_dir=sortie_dir),
            {
                "status": "FAILED_CANDIDATE",
                "not_production": True,
                "purpose": "offline_diagnosis",
                "canonical_raw": local.raw_canonical,
            },
        )
        result.files_created.append(writer.FAILED_RAW_NAME)
    if local.source_map is not None:
        writer.write_bytes_atomic(
            writer.failed_normalized_path(project_name, sortie_dir=sortie_dir),
            {
                "status": "FAILED_CANDIDATE",
                "not_production": True,
                "purpose": "offline_diagnosis",
                "source_map": local.source_map.to_dict(),
            },
        )
        result.files_created.append(writer.FAILED_NORMALIZED_NAME)


def _fill_usage(
    result: GlobalCleanResult,
    response,
    tracker: CostTracker,
    *,
    failed: bool,
    error=None,
    persist: bool = False,
) -> None:
    result.input_tokens = getattr(response, "input_tokens", None)
    result.output_tokens = getattr(response, "output_tokens", None)
    result.total_tokens = getattr(response, "total_tokens", None)
    result.usage_source = (
        response.usage_source if getattr(response, "has_usage", False) else ""
    )
    result.latency_ms = getattr(response, "latency_ms", None)
    result.request_id = getattr(response, "request_id", None)
    result.request_id_present = bool(result.request_id)
    result.finish_reason = getattr(response, "finish_reason", None)
    if failed:
        record = tracker.record_failure(
            provider=getattr(response, "provider", EXPECTED_PROVIDER),
            model=getattr(response, "model", EXPECTED_MODEL),
            stage=STAGE,
            error=error,
            response=response,
        )
    else:
        record = tracker.record_response(response, stage=STAGE)
    cost = record.cost
    result.input_cost = None if cost.input_cost is None else str(cost.input_cost)
    result.output_cost = None if cost.output_cost is None else str(cost.output_cost)
    result.total_cost = None if cost.total_cost is None else str(cost.total_cost)
    result.cost_status = cost.status
    result.cost_currency = cost.currency or ""
    if persist:
        record_call(result.project_name, record)


def _write_completed_state(project_name, *, path, signature, provider, model, plan, stats):
    state = load_project_state(project_name)
    state[state_module.STATE_KEY] = state_module.build_completed_block(
        signature=signature,
        path=str(path),
        provider=provider,
        model=model,
        strategy=plan.strategy,
        prompt_version=SOURCE_ANALYZER_PROMPT_VERSION,
        schema_version=SOURCE_MAP_SCHEMA_VERSION,
        cached=False,
        stats=stats,
        updated_at=datetime.now().isoformat(timespec="seconds"),
    )
    save_project_state(project_name, state)


def _record_failed_state(result: GlobalCleanResult, project_name: str, plan) -> None:
    state = load_project_state(project_name)
    previous = state_module.load_state_block(state)
    state[state_module.STATE_KEY] = state_module.build_failed_block(
        signature=result.signature,
        provider=result.provider,
        model=result.model,
        strategy=plan.strategy if plan is not None else result.strategy,
        prompt_version=SOURCE_ANALYZER_PROMPT_VERSION,
        schema_version=SOURCE_MAP_SCHEMA_VERSION,
        error_type=result.error_type or "GlobalCleanError",
        updated_at=datetime.now().isoformat(timespec="seconds"),
        previous=previous,
    )
    save_project_state(project_name, state)
    result.project_state_status = "failed"
    result.files_created.append("project_state.json")


def _decide_outcome(result: GlobalCleanResult) -> str:
    if result.dry_run and result.actual_real_calls == 0 and result.would_call_ai:
        if result.stop_reason in {STOP_PRE_CALL, STOP_EXISTING_MAP, STOP_CACHE_HIT}:
            return OUTCOME_FAIL
        return OUTCOME_PASS
    if result.actual_real_calls == 0:
        return OUTCOME_FAIL
    if (
        result.provider_generation == "PASS"
        and result.pipeline_result == "PASS"
        and result.source_map_published
        and result.project_state_status == "completed"
        and result.transport_preserved == "PASS"
        and not result.invalid_tokens
        and result.phase4_invoked is False
    ):
        return OUTCOME_PASS
    if result.provider_generation == "PASS":
        return OUTCOME_PARTIAL
    return OUTCOME_FAIL


def _safe_post_snapshot(
    result: GlobalCleanResult,
    project_name: str,
    sortie_dir: Path | None,
    require_protected: bool,
) -> None:
    try:
        integ = _integrity_module(result.attempt_number)
        if result.attempt_number == 2:
            after = integ.snapshot_attempt2_protected(
                project_name,
                sortie_dir=sortie_dir,
                require_all=require_protected,
            )
        else:
            after = integ.snapshot_final_protected(
                project_name,
                sortie_dir=sortie_dir,
                require_all=require_protected,
            )
        result.protected_after = after.to_dict()
        before = type(after)(hashes=result.protected_before)
        integ.assert_protected_unchanged(before, after)
        result.protected_unchanged = True
    except Exception:
        result.protected_unchanged = False


def _write_terminal_artifacts(
    result: GlobalCleanResult,
    project_name: str,
    sortie_dir: Path | None,
) -> None:
    if result.attempt_number == 2:
        from app.source_analysis_global_clean_attempt2.report import (
            render_attempt2_report,
        )

        render = render_attempt2_report
    else:
        from app.source_analysis_global_clean.report import render_final_report

        render = render_final_report

    if result.dry_run and not result.stop_reason:
        return

    writer = _artifact_writer(result.attempt_number)
    writer.write_bytes_atomic(
        writer.result_path(project_name, sortie_dir=sortie_dir),
        result.to_result_artifact(),
    )
    if writer.RESULT_ARTIFACT_NAME not in result.files_created:
        result.files_created.append(writer.RESULT_ARTIFACT_NAME)

    writer.write_bytes_atomic(
        writer.report_path(project_name, sortie_dir=sortie_dir),
        render(result),
    )
    if writer.REPORT_NAME not in result.files_created:
        result.files_created.append(writer.REPORT_NAME)
