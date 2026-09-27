"""
Orchestration du canary 3B.4.1.

Dry-run : charge, sélectionne, construit le payload, S'ARRÊTE avant réseau.
Real call : un seul generate(), max_attempts=1, aucun fallback.

N'appelle jamais analyze_source() / write_source_map / save_project_state /
record_call / build_project_report.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.cost import CostTracker
from app.ai.errors import AIError
from app.ai.estimation import estimate_request_tokens
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.registry import get_ai_engine
from app.ai.retry import RetryPolicy
from app.ai.settings import resolve_stage_settings
from app.cleanup_application.writer import audit_path, clean_json_path
from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis import cache as cache_module
from app.source_analysis.analyzer import is_truncated_finish_reason
from app.source_analysis.compact_schema import compact_schema_fingerprint
from app.source_analysis.guard import RealCallGuard
from app.source_analysis.models import (
    SOURCE_MAP_SCHEMA_VERSION,
    AnalysisProvenance,
)
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.real_run import (
    GuardedEngine,
    anthropic_credential_available,
)
from app.source_analysis.schema import build_response_schema, schema_fingerprint
from app.source_analysis.transcript_input import (
    TranscriptInputMode,
    load_transcript_input,
)
from app.source_analysis.writer import transcripts_dir
from app.source_analysis_schema_canary import architecture as architecture_module
from app.source_analysis_schema_canary import classify as classify_module
from app.source_analysis_schema_canary import integrity as integrity_module
from app.source_analysis_schema_canary import pipeline as pipeline_module
from app.source_analysis_schema_canary import prompt as prompt_module
from app.source_analysis_schema_canary import selection as selection_module
from app.source_analysis_schema_canary import writer as writer_module
from app.source_analysis_schema_canary.constants import (
    CANARY_SCHEMA_VERSION,
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    GLOBAL_ESTIMATED_TOKENS_REFERENCE,
    GRAMMAR_ACCEPTANCE_UNKNOWN,
    GRAMMAR_ACCEPTANCE_VERIFIED,
    MAX_ATTEMPTS,
    MAX_ESTIMATED_INPUT_TOKENS,
    MAX_REAL_CALLS,
    MAX_WORDS,
    OUTCOME_FAIL,
    OUTCOME_PARTIAL,
    OUTCOME_PASS,
    REAL_CALL_TIMEOUT_SECONDS,
    SELECTION_RULE,
    STAGE,
    STOP_PRE_CALL,
)
from app.source_analysis_schema_canary.errors import PreCallFailure, SchemaCanaryError

_EMPTY_NETWORK = {
    "anthropic": 0,
    "openai": 0,
    "whisper": 0,
    "ollama": 0,
    "lm_studio": 0,
    "other": 0,
}


@dataclass
class SchemaCanaryResult:
    project_name: str
    dry_run: bool
    outcome: str = OUTCOME_FAIL
    pipeline_result: str = "not_started"
    server_grammar_result: str = GRAMMAR_ACCEPTANCE_UNKNOWN
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
    transcript_id: str = ""
    transcript_sha256: str = ""
    selection_rule: str = SELECTION_RULE
    selected_source_ids: list[str] = field(default_factory=list)
    selected_segment_count: int | None = None
    selected_word_count: int | None = None
    selected_texts: list[dict] = field(default_factory=list)
    real_src_ids_preserved: bool | None = None
    text_unchanged: bool | None = None
    provider: str = EXPECTED_PROVIDER
    model: str = EXPECTED_MODEL
    prompt_version: str = ""
    prompt_sha256: str = ""
    compact_schema_sha256: str = ""
    anthropic_schema_sha256: str = ""
    old_schema_sha256: str = ""
    uses_production_compact: bool | None = None
    old_schema_absent_from_payload: bool | None = None
    output_format_type: str = ""
    local_compatibility: str = ""
    credential_available: bool | None = None
    estimated_input_tokens: int | None = None
    estimated_output_budget: int | None = None
    estimation_method: str = ""
    would_call_ai: bool = False
    real_call_executed: bool = False
    max_real_calls: int = MAX_REAL_CALLS
    actual_real_calls: int = 0
    max_attempts: int = MAX_ATTEMPTS
    retry_disabled: bool = True
    fallback_disabled: bool = True
    request_accepted: bool | None = None
    http_status: int | None = None
    finish_reason: str | None = None
    request_id: str | None = None
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
    compact_parse: str = "N/A"
    compact_semantic: str = "N/A"
    source_refs_in_canary: str = "N/A"
    index_validation: str = "N/A"
    reconstruction: str = "N/A"
    normalization: str = "N/A"
    canonical_validation: str = "N/A"
    topic_ids: list[str] = field(default_factory=list)
    idea_ids: list[str] = field(default_factory=list)
    example_ids: list[str] = field(default_factory=list)
    reference_ids: list[str] = field(default_factory=list)
    uncertainty_ids: list[str] = field(default_factory=list)
    repetition_ids: list[str] = field(default_factory=list)
    production_source_map_created: bool = False
    global_source_analysis_success: bool = False
    report_json_global_success: bool = False
    network: dict[str, int] = field(default_factory=lambda: dict(_EMPTY_NETWORK))
    files_created: list[str] = field(default_factory=list)
    tests_before: str = ""
    tests_after: str = ""
    remaining_anomaly: str = ""

    def to_result_artifact(self) -> dict[str, Any]:
        return {
            "schema_version": CANARY_SCHEMA_VERSION,
            "input": {
                "transcript_id": self.transcript_id,
                "selected_source_ids": list(self.selected_source_ids),
                "segment_count": self.selected_segment_count,
                "word_count": self.selected_word_count,
                "input_sha256": self.transcript_sha256,
            },
            "provider": {"name": self.provider, "model": self.model},
            "schema": {
                "compact_sha256": self.compact_schema_sha256,
                "anthropic_sha256": self.anthropic_schema_sha256,
                "local_compatibility": self.local_compatibility,
            },
            "execution": {
                "max_real_calls": self.max_real_calls,
                "actual_real_calls": self.actual_real_calls,
                "max_attempts": self.max_attempts,
                "dry_run": self.dry_run,
                "retry_disabled": self.retry_disabled,
                "fallback_disabled": self.fallback_disabled,
            },
            "server": {
                "request_accepted": self.request_accepted,
                "grammar_acceptance": self.server_grammar_result,
                "http_status": self.http_status,
                "error_type": self.error_type,
                "error_message": self.error_message,
                "finish_reason": self.finish_reason,
                "classification": self.classification,
            },
            "pipeline": {
                "compact_parse": self.compact_parse,
                "reconstruction": self.reconstruction,
                "normalization": self.normalization,
                "canonical_validation": self.canonical_validation,
                "compact_semantic": self.compact_semantic,
                "source_refs_in_canary": self.source_refs_in_canary,
                "index_validation": self.index_validation,
            },
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens,
                "usage_source": self.usage_source or None,
                "latency_ms": self.latency_ms,
            },
            "cost": {
                "input_cost": self.input_cost,
                "output_cost": self.output_cost,
                "total_cost": self.total_cost,
                "currency": self.cost_currency or None,
                "status": self.cost_status or None,
            },
            "network": dict(self.network),
        }


def run_schema_canary(
    project_name: str,
    *,
    dry_run: bool = True,
    engine=None,
    sortie_dir: Path | None = None,
    require_protected: bool = True,
    require_credential: bool | None = None,
    write_artifacts: bool = True,
) -> SchemaCanaryResult:
    """
    Dry-run (défaut) ou unique appel réel.

    `engine` est réservé aux tests (FakeAIEngine). Sans injection, le moteur
    est Anthropic / claude-sonnet-5, retry désactivé.
    """
    result = SchemaCanaryResult(project_name=project_name, dry_run=dry_run)
    need_credential = engine is None if require_credential is None else require_credential

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
        )
    except Exception as exc:
        if result.stop_reason is None:
            result.stop_reason = (
                STOP_PRE_CALL if result.actual_real_calls == 0 else "POST_CALL_FAILURE"
            )
        result.error_type = result.error_type or type(exc).__name__
        result.error_message = result.error_message or classify_module.truncate_error_message(exc)
        if result.pipeline_result == "not_started":
            result.pipeline_result = (
                STOP_PRE_CALL if result.actual_real_calls == 0 else "FAIL"
            )
        result.outcome = _decide_outcome(result)
        result.remaining_anomaly = result.error_message or type(exc).__name__
        _safe_post_snapshot(result, project_name, sortie_dir, require_protected)
        if write_artifacts:
            _write_terminal_artifacts(result, project_name, sortie_dir)
        if isinstance(exc, SchemaCanaryError) or result.actual_real_calls:
            return result
        if dry_run:
            return result
        raise

    result.outcome = _decide_outcome(result)
    _safe_post_snapshot(result, project_name, sortie_dir, require_protected)
    if write_artifacts:
        _write_terminal_artifacts(result, project_name, sortie_dir)
    return result


def _execute(
    result: SchemaCanaryResult,
    project_name: str,
    *,
    dry_run: bool,
    engine,
    sortie_dir: Path | None,
    require_protected: bool,
    require_credential: bool,
    write_artifacts: bool,
) -> None:
    snapshot = integrity_module.snapshot_canary_protected(
        project_name,
        sortie_dir=sortie_dir,
        require_all=require_protected,
    )
    result.protected_before = snapshot.to_dict()

    map_path = writer_module.production_source_map_path(
        project_name, sortie_dir=sortie_dir
    )
    map_existed = map_path.exists()

    result.architecture = architecture_module.verify_3b4_architecture()
    result.complexity = architecture_module.audit_complexity()
    result.local_audit = architecture_module.audit_local_anthropic_schema()
    result.local_compatibility = result.local_audit.get("compatibility", "")
    result.compact_schema_sha256 = result.local_audit["compact_sha256"]
    result.anthropic_schema_sha256 = result.local_audit["anthropic_sha256"]
    result.old_schema_sha256 = result.architecture["old_schema_sha256"]

    clean_path = clean_json_path(project_name, sortie_dir=sortie_dir)
    provenance_path = audit_path(project_name, sortie_dir=sortie_dir)
    original_path = transcripts_dir(project_name, sortie_dir=sortie_dir) / "transcript_data.json"

    transcript = load_transcript_input(
        clean_path,
        project_name=project_name,
        mode=TranscriptInputMode.DERIVED,
        provenance_path=provenance_path,
        original_transcript_path=original_path,
    )
    result.transcript_id = transcript.transcript_id
    result.transcript_sha256 = sha256_of_file(clean_path)

    chosen = selection_module.select_canary_segments(transcript.segments)
    result.selected_source_ids = list(chosen.source_ids)
    result.selected_segment_count = chosen.segment_count
    result.selected_word_count = chosen.word_count
    result.selected_texts = [
        {"source_id": segment.src_id, "text": segment.text}
        for segment in chosen.segments
    ]
    original_by_id = {segment.src_id: segment.text for segment in transcript.segments}
    result.text_unchanged = chosen.texts_unchanged(original_by_id)
    result.real_src_ids_preserved = set(chosen.source_ids) <= set(transcript.src_ids())
    if not result.text_unchanged or not result.real_src_ids_preserved:
        raise PreCallFailure(
            "La sélection a altéré le texte ou les identifiants SRC."
        )
    if chosen.word_count > MAX_WORDS:
        raise PreCallFailure(
            f"Canary trop gros : {chosen.word_count} mots > {MAX_WORDS}."
        )

    settings = resolve_stage_settings("source_analysis")
    system_prompt = prompt_module.build_canary_system_prompt(transcript.primary_language)
    user_prompt = prompt_module.build_canary_user_prompt(transcript, chosen.segments)
    compact = architecture_module.production_compact_schema()
    result.prompt_version = SOURCE_ANALYZER_PROMPT_VERSION
    result.prompt_sha256 = cache_module.prompt_fingerprint(system_prompt, user_prompt)
    result.uses_production_compact = (
        compact_schema_fingerprint(compact) == result.compact_schema_sha256
    )
    if not result.uses_production_compact:
        raise PreCallFailure("Le canary n'utilise pas le schéma compact de production.")

    request = AIRequest(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model=EXPECTED_MODEL,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
        response_schema=compact,
        metadata={"stage": STAGE, "project": project_name, "canary": True},
    )

    inspector = AnthropicEngine(model=EXPECTED_MODEL, api_key="canary-inspect-unused")
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
    result.old_schema_absent_from_payload = payload_schema_sha != old_adapted_sha
    if result.output_format_type != "json_schema":
        raise PreCallFailure(
            f"output_config.format.type = {result.output_format_type!r}, "
            "attendu json_schema."
        )
    if payload_schema_sha != result.anthropic_schema_sha256:
        raise PreCallFailure(
            "Le schéma adapté du payload n'est pas le compact Anthropic de production."
        )
    if not result.old_schema_absent_from_payload:
        raise PreCallFailure("L'ancien gros schéma est encore dans le payload.")

    estimate = estimate_request_tokens(request)
    result.estimated_input_tokens = estimate.tokens
    result.estimation_method = estimate.method
    result.estimated_output_budget = request.max_output_tokens
    if result.estimated_output_budget is None:
        result.estimated_output_budget = inspector.resolve_max_output_tokens(request)
    if estimate.tokens > MAX_ESTIMATED_INPUT_TOKENS:
        raise PreCallFailure(
            f"Canary trop gros : {estimate.tokens} tokens estimés "
            f"> {MAX_ESTIMATED_INPUT_TOKENS}."
        )
    if estimate.tokens >= GLOBAL_ESTIMATED_TOKENS_REFERENCE:
        raise PreCallFailure(
            "Le canary n'est pas plus petit que l'appel Source Analyzer global."
        )

    leaked = _src_ids_in_text(user_prompt) - set(chosen.source_ids) - _instruction_example_srcs()
    if leaked:
        raise PreCallFailure(
            f"Le prompt cite des SRC hors extrait : {sorted(leaked)}."
        )

    input_artifact = _build_input_artifact(result, compact)
    if write_artifacts:
        writer_module.write_bytes_atomic(
            writer_module.input_path(project_name, sortie_dir=sortie_dir),
            input_artifact,
        )
        result.files_created.append(writer_module.INPUT_ARTIFACT_NAME)

    result.would_call_ai = True
    result.credential_available = anthropic_credential_available()

    if dry_run:
        result.pipeline_result = "DRY_RUN"
        result.actual_real_calls = 0
        result.real_call_executed = False
        result.request_accepted = None
        result.server_grammar_result = GRAMMAR_ACCEPTANCE_UNKNOWN
        result.outcome = OUTCOME_PASS
        if write_artifacts:
            writer_module.write_bytes_atomic(
                writer_module.dry_run_path(project_name, sortie_dir=sortie_dir),
                _build_dry_run_artifact(result),
            )
            result.files_created.append(writer_module.DRY_RUN_ARTIFACT_NAME)
        writer_module.assert_no_production_source_map(
            project_name, sortie_dir=sortie_dir, existed_before=map_existed
        )
        return

    if require_credential and not result.credential_available:
        raise PreCallFailure(
            "Credential Anthropic indisponible. STOP : 0 appel."
        )

    retry = RetryPolicy(max_attempts=MAX_ATTEMPTS, base_delay_seconds=0.0)
    if engine is None:
        inner = get_ai_engine(
            EXPECTED_PROVIDER,
            model=EXPECTED_MODEL,
            retry_policy=retry,
            timeout_seconds=REAL_CALL_TIMEOUT_SECONDS,
        )
        if inner.provider_name != EXPECTED_PROVIDER or inner.resolve_model() != EXPECTED_MODEL:
            raise PreCallFailure(
                f"Moteur résolu {inner.provider_name}/{inner.resolve_model()} "
                f"≠ {EXPECTED_PROVIDER}/{EXPECTED_MODEL}. Aucun fallback."
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
        result.request_accepted = False
        classification, grammar, status = classify_module.classify_server_error(exc)
        result.classification = classification
        result.server_grammar_result = grammar
        result.http_status = status
        result.error_type = classify_module.extract_error_type(exc) or type(exc).__name__
        result.error_message = classify_module.truncate_error_message(exc)
        attached = getattr(exc, "response", None)
        if attached is not None:
            _fill_usage(result, attached, tracker, failed=True, error=exc)
            if attached.has_usage or attached.request_id:
                result.request_accepted = True
                result.server_grammar_result = GRAMMAR_ACCEPTANCE_VERIFIED
        elif isinstance(exc, AIError):
            tracker.record_failure(
                provider=EXPECTED_PROVIDER,
                model=EXPECTED_MODEL,
                stage=STAGE,
                error=exc,
                response=None,
            )
        result.pipeline_result = "FAIL"
        result.stop_reason = "POST_CALL_FAILURE" if guard.call_count else STOP_PRE_CALL
        writer_module.assert_no_production_source_map(
            project_name, sortie_dir=sortie_dir, existed_before=map_existed
        )
        return

    result.actual_real_calls = guard.call_count
    result.real_call_executed = True
    result.network["anthropic"] = guard.call_count
    result.request_accepted = True
    result.server_grammar_result = GRAMMAR_ACCEPTANCE_VERIFIED
    result.http_status = 200
    result.provider = response.provider
    result.model = response.model
    result.finish_reason = response.finish_reason
    result.request_id = response.request_id
    _fill_usage(result, response, tracker, failed=False)

    if is_truncated_finish_reason(response.finish_reason):
        result.pipeline_result = "FAIL"
        result.stop_reason = "TRUNCATED"
        result.error_type = "SourceMapTruncatedError"
        result.error_message = f"finish_reason={response.finish_reason}"
        writer_module.assert_no_production_source_map(
            project_name, sortie_dir=sortie_dir, existed_before=map_existed
        )
        return

    provenance = AnalysisProvenance(
        prompt_version=SOURCE_ANALYZER_PROMPT_VERSION,
        schema_version=SOURCE_MAP_SCHEMA_VERSION,
        provider=response.provider,
        model=response.model,
        strategy="global",
        signature="schema-canary-3b41",
    )
    local = pipeline_module.run_local_pipeline(
        response.parsed,
        transcript,
        chosen.segments,
        provenance=provenance,
    )
    result.compact_parse = local.compact_parse
    result.compact_semantic = local.compact_semantic
    result.source_refs_in_canary = local.source_refs_in_canary
    result.index_validation = local.index_validation
    result.reconstruction = local.reconstruction
    result.normalization = local.normalization
    result.canonical_validation = local.canonical_validation
    result.topic_ids = list(local.topic_ids or [])
    result.idea_ids = list(local.idea_ids or [])
    result.example_ids = list(local.example_ids or [])
    result.reference_ids = list(local.reference_ids or [])
    result.uncertainty_ids = list(local.uncertainty_ids or [])
    result.repetition_ids = list(local.repetition_ids or [])
    if local.errors:
        result.error_message = " | ".join(local.errors)
        result.error_type = result.error_type or "CanaryPipelineError"

    pipeline_steps = (
        local.compact_parse,
        local.compact_semantic,
        local.source_refs_in_canary,
        local.index_validation,
        local.reconstruction,
        local.normalization,
        local.canonical_validation,
    )
    result.pipeline_result = "PASS" if all(step == "PASS" for step in pipeline_steps) else "FAIL"

    if write_artifacts and local.source_map is not None:
        writer_module.write_bytes_atomic(
            writer_module.canary_sourcemap_path(project_name, sortie_dir=sortie_dir),
            local.source_map.to_dict(),
        )
        result.files_created.append(writer_module.CANARY_SOURCEMAP_NAME)

    writer_module.assert_no_production_source_map(
        project_name, sortie_dir=sortie_dir, existed_before=map_existed
    )
    result.production_source_map_created = map_path.exists() and not map_existed


def _src_ids_in_text(text: str) -> set[str]:
    import re

    return set(re.findall(r"SRC\d{6}", text or ""))


def _instruction_example_srcs() -> set[str]:
    """IDs éventuellement cités comme exemple dans le prompt de production."""
    return {"SRC000001"}


def _fill_usage(result: SchemaCanaryResult, response, tracker: CostTracker, *, failed: bool, error=None) -> None:
    result.input_tokens = response.input_tokens
    result.output_tokens = response.output_tokens
    result.total_tokens = response.total_tokens
    result.usage_source = response.usage_source if response.has_usage else ""
    result.latency_ms = response.latency_ms
    result.request_id = response.request_id
    result.finish_reason = response.finish_reason
    if failed:
        record = tracker.record_failure(
            provider=response.provider,
            model=response.model,
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


def _build_input_artifact(result: SchemaCanaryResult, compact: dict) -> dict:
    return {
        "schema_version": CANARY_SCHEMA_VERSION,
        "source_transcript_id": result.transcript_id,
        "source_transcript_sha256": result.transcript_sha256,
        "selection_rule": result.selection_rule,
        "selected_source_ids": list(result.selected_source_ids),
        "selected_segment_count": result.selected_segment_count,
        "selected_word_count": result.selected_word_count,
        "selected_sources": list(result.selected_texts),
        "compact_schema_sha256": result.compact_schema_sha256,
        "anthropic_schema_sha256": result.anthropic_schema_sha256,
        "compact_schema_fingerprint_check": compact_schema_fingerprint(compact),
    }


def _build_dry_run_artifact(result: SchemaCanaryResult) -> dict:
    return {
        "schema_version": CANARY_SCHEMA_VERSION,
        "would_call_ai": True,
        "actual_real_calls": 0,
        "provider": result.provider,
        "model": result.model,
        "output_config_format_type": result.output_format_type,
        "uses_production_compact": result.uses_production_compact,
        "old_schema_absent_from_payload": result.old_schema_absent_from_payload,
        "local_compatibility": result.local_compatibility,
        "retry_disabled": True,
        "fallback_disabled": True,
        "max_real_calls": MAX_REAL_CALLS,
        "max_attempts": MAX_ATTEMPTS,
        "selected_segment_count": result.selected_segment_count,
        "selected_word_count": result.selected_word_count,
        "selected_source_ids": list(result.selected_source_ids),
        "estimated_input_tokens": result.estimated_input_tokens,
        "estimated_output_budget": result.estimated_output_budget,
        "network": dict(_EMPTY_NETWORK),
        "credential_available": result.credential_available,
    }


def _decide_outcome(result: SchemaCanaryResult) -> str:
    if result.dry_run and result.actual_real_calls == 0 and result.would_call_ai:
        if result.stop_reason == STOP_PRE_CALL:
            return OUTCOME_FAIL
        return OUTCOME_PASS
    if result.actual_real_calls == 0:
        return OUTCOME_FAIL
    if result.server_grammar_result != GRAMMAR_ACCEPTANCE_VERIFIED:
        return OUTCOME_FAIL
    if result.pipeline_result == "PASS":
        return OUTCOME_PASS
    return OUTCOME_PARTIAL


def _safe_post_snapshot(
    result: SchemaCanaryResult,
    project_name: str,
    sortie_dir: Path | None,
    require_protected: bool,
) -> None:
    try:
        after = integrity_module.snapshot_canary_protected(
            project_name,
            sortie_dir=sortie_dir,
            require_all=require_protected,
        )
        result.protected_after = after.to_dict()
        before = type(after)(hashes=result.protected_before)
        integrity_module.assert_protected_unchanged(before, after)
        result.protected_unchanged = True
    except Exception:
        result.protected_unchanged = False


def _write_terminal_artifacts(
    result: SchemaCanaryResult,
    project_name: str,
    sortie_dir: Path | None,
) -> None:
    from app.source_analysis_schema_canary.report import render_canary_report

    if not result.dry_run or result.stop_reason == STOP_PRE_CALL:
        writer_module.write_bytes_atomic(
            writer_module.result_path(project_name, sortie_dir=sortie_dir),
            result.to_result_artifact(),
        )
        if writer_module.RESULT_ARTIFACT_NAME not in result.files_created:
            result.files_created.append(writer_module.RESULT_ARTIFACT_NAME)

    writer_module.write_bytes_atomic(
        writer_module.report_path(project_name, sortie_dir=sortie_dir),
        render_canary_report(result),
    )
    if writer_module.REPORT_NAME not in result.files_created:
        result.files_created.append(writer_module.REPORT_NAME)
