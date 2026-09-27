"""
Orchestration du canary 3B.4.5.

Dry-run : charge, sélectionne l'extrait historique, construit le payload,
S'ARRÊTE avant réseau.
Real call : un seul generate(), max_attempts=1, aucun fallback.

N'appelle jamais analyze_source() / write_source_map / save_project_state /
record_call / build_project_report / cache production.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.cost import CostTracker
from app.ai.errors import AIError
from app.ai.estimation import estimate_request_tokens, estimate_tokens
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.registry import get_ai_engine
from app.ai.retry import RetryPolicy
from app.ai.settings import resolve_stage_settings
from app.cleanup_application.writer import audit_path, clean_json_path
from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.analyzer import is_truncated_finish_reason
from app.source_analysis.compact_schema import build_compact_response_schema
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
from app.source_analysis.schema import schema_fingerprint
from app.source_analysis.transcript_input import (
    TranscriptInputMode,
    load_transcript_input,
)
from app.source_analysis.ultra_compact_schema import (
    SEMANTIC_TRANSPORT_VERSION,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.writer import transcripts_dir
from app.source_analysis_ultra_compact_canary import architecture as architecture_module
from app.source_analysis_ultra_compact_canary import classify as classify_module
from app.source_analysis_ultra_compact_canary import pipeline as pipeline_module
from app.source_analysis_ultra_compact_canary import prompt as prompt_module
from app.source_analysis_ultra_compact_canary.errors import (
    SchemaRegressionError,
    UltraCompactCanaryError,
)
from app.source_analysis_vocabulary_compliance_canary import decoder_integrity
from app.source_analysis_vocabulary_compliance_canary import integrity as integrity_module
from app.source_analysis_vocabulary_compliance_canary import observe as observe_module
from app.source_analysis_vocabulary_compliance_canary import preflight as preflight_module
from app.source_analysis_vocabulary_compliance_canary import selection as selection_module
from app.source_analysis_vocabulary_compliance_canary import writer as writer_module
from app.source_analysis_vocabulary_compliance_canary import constants as canary_constants
from app.source_analysis_vocabulary_compliance_canary.constants import (
    CACHE_NAMESPACE,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_SCHEMA_VERSION,
    CLASS_PRE_CALL_CREDENTIAL_MISSING,
    CLASS_PRE_CALL_HISTORICAL_UNAVAILABLE,
    CLASS_PRE_CALL_PARITY,
    CLASS_PRE_CALL_SCHEMA_DRIFT,
    CLASS_SERVER_GRAMMAR_REGRESSION,
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    GLOBAL_ESTIMATED_TOKENS_REFERENCE,
    GRAMMAR_ACCEPTANCE_UNKNOWN,
    GRAMMAR_ACCEPTANCE_VERIFIED,
    GRAMMAR_UNKNOWN,
    MAX_ATTEMPTS,
    MAX_ESTIMATED_INPUT_TOKENS,
    MAX_REAL_CALLS,
    OBSERVED_3B43_INVALID_UNCERTAINTY_KINDS,
    OUTCOME_FAIL,
    OUTCOME_PARTIAL,
    OUTCOME_PASS,
    REAL_CALL_TIMEOUT_SECONDS,
    SIGNATURE_MARK,
    STAGE,
    STOP_PRE_CALL,
    TRANSPORT_VERSION,
    VOCAB_COMPLIANCE_NA,
    VOCAB_PROMPT_FAILED,
    VOCAB_PROMPT_UNVERIFIED,
    VOCAB_PROMPT_VERIFIED,
)
from app.source_analysis_vocabulary_compliance_canary.errors import (
    HistoricalInputUnavailable,
    PreCallFailure,
    VocabularyComplianceCanaryError,
    VocabularyParityError,
)

_EMPTY_NETWORK = {
    "anthropic": 0,
    "openai": 0,
    "whisper": 0,
    "ollama": 0,
    "lm_studio": 0,
    "other": 0,
}


@dataclass
class VocabularyComplianceCanaryResult:
    project_name: str
    dry_run: bool
    outcome: str = OUTCOME_FAIL
    pipeline_result: str = "not_started"
    server_grammar_result: str = GRAMMAR_UNKNOWN
    server_grammar_acceptance: str = GRAMMAR_ACCEPTANCE_UNKNOWN
    vocabulary_compliance: str = VOCAB_COMPLIANCE_NA
    vocabulary_prompt_compliance: str = VOCAB_PROMPT_UNVERIFIED
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
    prompt_preflight: dict = field(default_factory=dict)
    transcript_id: str = ""
    source_transcript_sha256: str = ""
    clean_transcript_sha256: str = ""
    input_sha256: str = ""
    input_sha256_run1: str = ""
    input_sha256_run2: str = ""
    input_deterministic: bool | None = None
    provenance_verified: bool | None = None
    selection_rule: str = ""
    selected_source_ids: list[str] = field(default_factory=list)
    selected_segment_count: int | None = None
    selected_word_count: int | None = None
    selected_texts: list[dict] = field(default_factory=list)
    selected_text: str = ""
    real_src_ids_preserved: bool | None = None
    text_unchanged: bool | None = None
    same_as_3b43_input: bool | None = None
    provider: str = EXPECTED_PROVIDER
    model: str = EXPECTED_MODEL
    prompt_version: str = ""
    prompt_sha256: str = ""
    production_prompt_sha256: str = ""
    vocabulary_contract_sha256: str = ""
    vocabulary_parity: str = "N/A"
    missing_from_prompt: list[str] = field(default_factory=list)
    extra_in_prompt: list[str] = field(default_factory=list)
    raw_generation_c_sha256: str = ""
    anthropic_generation_c_sha256: str = ""
    generation_a_sha256: str = ""
    generation_b_sha256: str = ""
    uses_production_generation_c: bool | None = None
    generation_a_absent_from_payload: bool | None = None
    generation_b_absent_from_payload: bool | None = None
    output_format_type: str = ""
    local_compatibility: str = ""
    credential_available: bool | None = None
    estimated_system_tokens: int | None = None
    estimated_user_tokens: int | None = None
    estimated_input_tokens: int | None = None
    estimated_output_budget: int | None = None
    estimation_method: str = ""
    would_call_ai: bool = False
    dry_run_pass: bool | None = None
    real_call_executed: bool = False
    max_real_calls: int = MAX_REAL_CALLS
    actual_real_calls: int = 0
    max_attempts: int = MAX_ATTEMPTS
    retry_disabled: bool = True
    fallback_disabled: bool = True
    cache_isolated: bool = True
    cache_used: bool = False
    request_accepted: bool | None = None
    provider_generation_occurred: bool | None = None
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
    transport_parse: str = "N/A"
    local_semantic: str = "N/A"
    source_refs_in_canary: str = "N/A"
    link_validation: str = "N/A"
    decoder: str = "N/A"
    reconstruction: str = "N/A"
    normalization: str = "N/A"
    canonical_validation: str = "N/A"
    editorial_leakage: str = "N/A"
    controlled_tokens_observed: list[dict] = field(default_factory=list)
    invalid_tokens: list[dict] = field(default_factory=list)
    reused_3b43_invalid_tokens: list[str] = field(default_factory=list)
    record_kinds: list[str] = field(default_factory=list)
    topic_ids: list[str] = field(default_factory=list)
    idea_ids: list[str] = field(default_factory=list)
    example_ids: list[str] = field(default_factory=list)
    reference_ids: list[str] = field(default_factory=list)
    uncertainty_ids: list[str] = field(default_factory=list)
    repetition_ids: list[str] = field(default_factory=list)
    production_source_map_created: bool = False
    canary_source_map_created: bool = False
    global_source_analysis_success: bool = False
    report_json_global_success: bool = False
    writer_production_called: bool = False
    network: dict[str, int] = field(default_factory=lambda: dict(_EMPTY_NETWORK))
    files_created: list[str] = field(default_factory=list)
    tests_before: str = ""
    tests_after: str = ""
    remaining_anomaly: str = ""

    def to_result_artifact(self) -> dict[str, Any]:
        gen_c = ((self.complexity.get("generation_c") or {}).get("metrics") or {})
        gen_ac = ((self.complexity.get("anthropic_generation_c") or {}).get("metrics") or {})
        return {
            "schema_version": CANARY_SCHEMA_VERSION,
            "transport_version": TRANSPORT_VERSION,
            "purpose": "canonical_vocabulary_compliance_canary",
            "input": {
                "transcript_id": self.transcript_id,
                "selected_source_ids": list(self.selected_source_ids),
                "segment_count": self.selected_segment_count,
                "word_count": self.selected_word_count,
                "sha256": self.input_sha256,
            },
            "prompt": {
                "version": self.prompt_version,
                "sha256": self.prompt_sha256,
                "production_sha256": self.production_prompt_sha256,
                "vocabulary_contract_sha256": self.vocabulary_contract_sha256,
                "parity": self.vocabulary_parity,
            },
            "schema": {
                "raw_sha256": self.raw_generation_c_sha256,
                "anthropic_sha256": self.anthropic_generation_c_sha256,
                "raw_metrics": dict(gen_c),
                "anthropic_metrics": dict(gen_ac),
                "server_acceptance_previous": "VERIFIED",
                "provider_enums": int(gen_c.get("enum_count") or 0),
                "local_compatibility": self.local_compatibility,
            },
            "execution": {
                "provider": self.provider,
                "model": self.model,
                "max_real_calls": self.max_real_calls,
                "actual_real_calls": self.actual_real_calls,
                "max_attempts": self.max_attempts,
                "retry": False,
                "fallback": None,
                "dry_run": self.dry_run,
            },
            "provider": {
                "http_status": self.http_status,
                "finish_reason": self.finish_reason,
                "generation_occurred": self.provider_generation_occurred,
                "request_accepted": self.request_accepted,
                "grammar_result": self.server_grammar_result,
                "grammar_acceptance": self.server_grammar_acceptance,
                "error_type": self.error_type,
                "classification": self.classification,
            },
            "vocabulary": {
                "controlled_tokens_observed": list(self.controlled_tokens_observed),
                "invalid_tokens": list(self.invalid_tokens),
                "reused_3b43_invalid_tokens": list(self.reused_3b43_invalid_tokens),
                "compliance": self.vocabulary_compliance,
                "prompt_compliance": self.vocabulary_prompt_compliance,
            },
            "pipeline": {
                "transport_parse": self.transport_parse,
                "source_refs": self.source_refs_in_canary,
                "links": self.link_validation,
                "decoder": self.decoder,
                "canonical_reconstruction": self.reconstruction,
                "normalization": self.normalization,
                "canonical_validation": self.canonical_validation,
                "editorial_leakage": self.editorial_leakage,
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


def run_vocabulary_compliance_canary(
    project_name: str,
    *,
    dry_run: bool = True,
    engine=None,
    sortie_dir: Path | None = None,
    require_protected: bool = True,
    require_credential: bool | None = None,
    write_artifacts: bool = True,
    tests_before: str = "",
    tests_after: str = "",
) -> VocabularyComplianceCanaryResult:
    """
    Dry-run (défaut) ou unique appel réel.

    `engine` est réservé aux tests (FakeAIEngine). Sans injection, le moteur
    est Anthropic / claude-sonnet-5, retry désactivé.
    """
    result = VocabularyComplianceCanaryResult(project_name=project_name, dry_run=dry_run)
    result.tests_before = tests_before
    result.tests_after = tests_after
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
        _annotate_precall_exception(result, exc)
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
        if isinstance(exc, (VocabularyComplianceCanaryError, UltraCompactCanaryError)) or result.actual_real_calls:
            return result
        if dry_run:
            return result
        raise

    result.outcome = _decide_outcome(result)
    _safe_post_snapshot(result, project_name, sortie_dir, require_protected)
    if write_artifacts:
        _write_terminal_artifacts(result, project_name, sortie_dir)
    return result


def _annotate_precall_exception(
    result: VocabularyComplianceCanaryResult,
    exc: BaseException,
) -> None:
    if isinstance(exc, SchemaRegressionError):
        result.classification = CLASS_PRE_CALL_SCHEMA_DRIFT
    elif isinstance(exc, HistoricalInputUnavailable):
        result.classification = CLASS_PRE_CALL_HISTORICAL_UNAVAILABLE
    elif isinstance(exc, VocabularyParityError):
        result.classification = CLASS_PRE_CALL_PARITY
    elif isinstance(exc, PreCallFailure) and "Credential" in str(exc):
        result.classification = CLASS_PRE_CALL_CREDENTIAL_MISSING


def _execute(
    result: VocabularyComplianceCanaryResult,
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

    try:
        result.architecture = architecture_module.verify_generation_c_architecture()
        result.complexity = architecture_module.audit_generation_c_complexity()
        result.local_audit = architecture_module.audit_local_anthropic_generation_c()
    except SchemaRegressionError:
        result.classification = CLASS_PRE_CALL_SCHEMA_DRIFT
        raise

    result.local_compatibility = result.local_audit.get("compatibility", "")
    result.raw_generation_c_sha256 = result.local_audit["raw_sha256"]
    result.anthropic_generation_c_sha256 = result.local_audit["anthropic_sha256"]
    result.generation_a_sha256 = result.architecture["generation_a_sha256"]
    result.generation_b_sha256 = result.architecture["generation_b_sha256"]
    result.decoder_integrity = decoder_integrity.verify_decoder_integrity()
    if not decoder_integrity.observed_3b43_tokens_still_rejected():
        raise PreCallFailure(
            "Les jetons 3B.4.3 ne sont plus rejetés par le decoder. STOP : 0 appel."
        )

    result.prompt_version = preflight_module.verify_prompt_version()

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
    result.clean_transcript_sha256 = sha256_of_file(clean_path)
    result.source_transcript_sha256 = sha256_of_file(original_path)
    result.provenance_verified = True

    first = selection_module.select_historical_canary_segments(transcript.segments)
    second = selection_module.select_historical_canary_segments(transcript.segments)
    if first.source_ids != second.source_ids:
        raise PreCallFailure("Sélection non déterministe : run1 ≠ run2.")

    chosen = first
    result.selection_rule = chosen.selection_rule
    result.selected_source_ids = list(chosen.source_ids)
    result.selected_segment_count = chosen.segment_count
    result.selected_word_count = chosen.word_count
    result.selected_texts = [
        {"source_id": segment.src_id, "text": segment.text}
        for segment in chosen.segments
    ]
    result.selected_text = "\n\n".join(segment.text for segment in chosen.segments)
    original_by_id = {segment.src_id: segment.text for segment in transcript.segments}
    result.text_unchanged = chosen.texts_unchanged(original_by_id)
    result.real_src_ids_preserved = set(chosen.source_ids) <= set(transcript.src_ids())
    result.same_as_3b43_input = _same_as_3b43_input(
        project_name,
        chosen,
        sortie_dir=sortie_dir,
    )
    if not result.text_unchanged or not result.real_src_ids_preserved:
        raise PreCallFailure(
            "La sélection a altéré le texte ou les identifiants SRC."
        )
    if list(chosen.source_ids) != list(canary_constants.HISTORICAL_SRC_IDS):
        raise HistoricalInputUnavailable(
            "Les SRC sélectionnés ne sont pas exactement SRC003799–SRC003808."
        )
    if require_protected and result.same_as_3b43_input is False:
        raise HistoricalInputUnavailable(
            "L'extrait n'est plus identique à l'input 3B.4.3. STOP pour revue."
        )

    settings = resolve_stage_settings("source_analysis")
    system_prompt = prompt_module.build_canary_system_prompt(transcript.primary_language)
    user_prompt = prompt_module.build_canary_user_prompt(transcript, chosen.segments)
    preflight_module.verify_vocabulary_contract_included(system_prompt)
    preflight_module.verify_protocol_token_rules(system_prompt)
    preflight_module.verify_fallbacks(system_prompt)
    parity = preflight_module.verify_vocabulary_parity(system_prompt)
    result.missing_from_prompt = list(parity["missing_from_prompt"])
    result.extra_in_prompt = list(parity["extra_in_prompt"])
    result.vocabulary_parity = "PASS"
    result.vocabulary_contract_sha256 = preflight_module.vocabulary_contract_sha256()
    result.production_prompt_sha256 = preflight_module.verify_production_prompt_sha(
        transcript,
        require_historical_match=require_protected,
    )
    generation_c = architecture_module.production_generation_c_schema()
    result.prompt_sha256 = preflight_module.canary_prompt_sha256(system_prompt, user_prompt)
    result.prompt_preflight = preflight_module.prompt_preflight_report(
        system_prompt,
        production_sha=result.production_prompt_sha256,
        canary_sha=result.prompt_sha256,
        parity=parity,
    )
    result.uses_production_generation_c = (
        ultra_compact_schema_fingerprint(generation_c) == result.raw_generation_c_sha256
    )
    if not result.uses_production_generation_c:
        raise PreCallFailure(
            "Le canary n'utilise pas le schéma Generation C de production."
        )
    if TRANSPORT_VERSION != SEMANTIC_TRANSPORT_VERSION:
        raise PreCallFailure("transport_version inattendu.")
    if SOURCE_ANALYZER_PROMPT_VERSION != result.prompt_version:
        raise PreCallFailure("Prompt version incohérente au moment de l'AIRequest.")

    request = AIRequest(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model=EXPECTED_MODEL,
        temperature=settings.temperature,
        max_output_tokens=CANARY_MAX_OUTPUT_TOKENS,
        response_schema=generation_c,
        metadata={
            "stage": STAGE,
            "project": project_name,
            "canary": True,
            "cache_namespace": CACHE_NAMESPACE,
            "cache_disabled": True,
            "signature": SIGNATURE_MARK,
        },
    )

    inspector = AnthropicEngine(model=EXPECTED_MODEL, api_key="canary-inspect-unused")
    payload = inspector.build_payload(request, EXPECTED_MODEL)
    fmt = (payload.get("output_config") or {}).get("format") or {}
    result.output_format_type = str(fmt.get("type") or "")
    payload_schema = fmt.get("schema") or {}
    payload_schema_sha = schema_fingerprint(payload_schema)

    from app.source_analysis.schema import build_response_schema

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
        raise PreCallFailure(
            "Le schéma adapté du payload n'est pas Generation C Anthropic de production."
        )
    if not result.generation_a_absent_from_payload:
        raise PreCallFailure("Generation A est encore identifiable dans le payload.")
    if not result.generation_b_absent_from_payload:
        raise PreCallFailure("Generation B est encore identifiable dans le payload.")

    system_estimate = estimate_tokens(system_prompt, model=EXPECTED_MODEL)
    user_estimate = estimate_tokens(user_prompt, model=EXPECTED_MODEL)
    estimate = estimate_request_tokens(request)
    result.estimated_system_tokens = system_estimate.tokens
    result.estimated_user_tokens = user_estimate.tokens
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

    input_artifact = _build_input_artifact(result)
    encoded = (json.dumps(input_artifact, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    result.input_sha256_run1 = content_hash(encoded.decode("utf-8"))
    result.input_sha256_run2 = content_hash(
        (json.dumps(_build_input_artifact(result), ensure_ascii=False, indent=2) + "\n")
    )
    result.input_deterministic = result.input_sha256_run1 == result.input_sha256_run2
    result.input_sha256 = result.input_sha256_run1
    if not result.input_deterministic:
        raise PreCallFailure("Input canary non déterministe : SHA run1 ≠ run2.")

    if write_artifacts:
        writer_module.write_bytes_atomic(
            writer_module.input_path(project_name, sortie_dir=sortie_dir),
            input_artifact,
        )
        result.files_created.append(writer_module.INPUT_ARTIFACT_NAME)

    result.would_call_ai = True
    result.credential_available = anthropic_credential_available()
    result.cache_isolated = True
    result.cache_used = False

    if dry_run:
        result.pipeline_result = "DRY_RUN"
        result.actual_real_calls = 0
        result.real_call_executed = False
        result.request_accepted = None
        result.server_grammar_result = GRAMMAR_UNKNOWN
        result.server_grammar_acceptance = GRAMMAR_ACCEPTANCE_UNKNOWN
        result.dry_run_pass = True
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

    result.dry_run_pass = True
    if require_credential and not result.credential_available:
        result.classification = CLASS_PRE_CALL_CREDENTIAL_MISSING
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
        result.provider_generation_occurred = False
        classification, grammar, acceptance, status = classify_module.classify_server_error(exc)
        if classification == "SERVER_GRAMMAR_REJECTED":
            result.classification = CLASS_SERVER_GRAMMAR_REGRESSION
        else:
            result.classification = classification
        result.server_grammar_result = grammar
        result.server_grammar_acceptance = acceptance
        result.http_status = status
        result.error_type = classify_module.extract_error_type(exc) or type(exc).__name__
        result.error_message = classify_module.truncate_error_message(exc)
        attached = getattr(exc, "response", None)
        if attached is not None:
            _fill_usage(result, attached, tracker, failed=True, error=exc)
            if attached.has_usage or attached.request_id:
                result.request_accepted = True
                result.provider_generation_occurred = True
                result.server_grammar_result = "ACCEPTED"
                result.server_grammar_acceptance = GRAMMAR_ACCEPTANCE_VERIFIED
        elif isinstance(exc, AIError):
            tracker.record_failure(
                provider=EXPECTED_PROVIDER,
                model=EXPECTED_MODEL,
                stage=STAGE,
                error=exc,
                response=None,
            )
            if result.input_tokens is None and result.output_tokens is None:
                result.cost_status = "unavailable"
        result.pipeline_result = (
            "N/A" if result.server_grammar_acceptance != GRAMMAR_ACCEPTANCE_VERIFIED else "FAIL"
        )
        result.stop_reason = "POST_CALL_FAILURE" if guard.call_count else STOP_PRE_CALL
        writer_module.assert_no_production_source_map(
            project_name, sortie_dir=sortie_dir, existed_before=map_existed
        )
        return

    result.actual_real_calls = guard.call_count
    result.real_call_executed = True
    result.network["anthropic"] = guard.call_count
    result.request_accepted = True
    result.provider_generation_occurred = True
    result.server_grammar_result = "ACCEPTED"
    result.server_grammar_acceptance = GRAMMAR_ACCEPTANCE_VERIFIED
    result.http_status = 200
    result.provider = response.provider
    result.model = response.model
    result.finish_reason = response.finish_reason
    result.request_id = response.request_id
    _fill_usage(result, response, tracker, failed=False)

    if write_artifacts and isinstance(response.parsed, dict):
        writer_module.write_bytes_atomic(
            writer_module.transport_path(project_name, sortie_dir=sortie_dir),
            {
                "schema_version": CANARY_SCHEMA_VERSION,
                "transport_version": TRANSPORT_VERSION,
                "canary": True,
                "not_production": True,
                "purpose": "canonical_vocabulary_compliance_canary",
                "transport": dict(response.parsed),
            },
        )
        result.files_created.append(writer_module.TRANSPORT_ARTIFACT_NAME)

    if is_truncated_finish_reason(response.finish_reason):
        result.pipeline_result = "FAIL"
        result.stop_reason = "TRUNCATED"
        result.error_type = "SourceMapTruncatedError"
        result.error_message = f"finish_reason={response.finish_reason}"
        writer_module.assert_no_production_source_map(
            project_name, sortie_dir=sortie_dir, existed_before=map_existed
        )
        return

    if isinstance(response.parsed, dict):
        result.controlled_tokens_observed = observe_module.observe_controlled_tokens(
            response.parsed
        )
        result.invalid_tokens = observe_module.invalid_controlled_tokens(
            result.controlled_tokens_observed
        )
        result.reused_3b43_invalid_tokens = observe_module.reused_3b43_invalid_tokens(
            result.controlled_tokens_observed
        )
        result.vocabulary_compliance = observe_module.vocabulary_compliance_status(
            result.controlled_tokens_observed
        )

    provenance = AnalysisProvenance(
        prompt_version=SOURCE_ANALYZER_PROMPT_VERSION,
        schema_version=SOURCE_MAP_SCHEMA_VERSION,
        provider=response.provider,
        model=response.model,
        strategy="global",
        signature=SIGNATURE_MARK,
    )
    local = pipeline_module.run_local_pipeline(
        response.parsed,
        transcript,
        chosen.segments,
        provenance=provenance,
    )
    result.transport_parse = local.transport_parse
    result.local_semantic = local.local_semantic
    result.source_refs_in_canary = local.source_refs_in_canary
    result.link_validation = local.link_validation
    result.decoder = local.decoder
    result.reconstruction = local.reconstruction
    result.normalization = local.normalization
    result.canonical_validation = local.canonical_validation
    result.editorial_leakage = local.editorial_leakage
    result.record_kinds = list(local.record_kinds or [])
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
        local.transport_parse,
        local.source_refs_in_canary,
        local.link_validation,
        local.decoder,
        local.reconstruction,
        local.normalization,
        local.canonical_validation,
        local.editorial_leakage,
    )
    result.pipeline_result = "PASS" if all(step == "PASS" for step in pipeline_steps) else "FAIL"
    if (
        result.pipeline_result == "PASS"
        and result.vocabulary_compliance == "PASS"
        and not result.invalid_tokens
    ):
        result.vocabulary_prompt_compliance = VOCAB_PROMPT_VERIFIED
    elif result.vocabulary_compliance == "FAIL" or result.invalid_tokens:
        result.vocabulary_prompt_compliance = VOCAB_PROMPT_FAILED
    else:
        result.vocabulary_prompt_compliance = VOCAB_PROMPT_UNVERIFIED

    if write_artifacts and local.source_map is not None:
        writer_module.write_bytes_atomic(
            writer_module.canary_sourcemap_path(project_name, sortie_dir=sortie_dir),
            {
                "canary": True,
                "partial_corpus": True,
                "not_production": True,
                "corpus_note": "CANARY / PARTIAL CORPUS / NOT PRODUCTION",
                "selected_source_ids": list(result.selected_source_ids),
                "source_map": local.source_map.to_dict(),
            },
        )
        result.files_created.append(writer_module.CANARY_SOURCEMAP_NAME)
        result.canary_source_map_created = True

    writer_module.assert_no_production_source_map(
        project_name, sortie_dir=sortie_dir, existed_before=map_existed
    )
    result.production_source_map_created = map_path.exists() and not map_existed
    result.writer_production_called = False
    result.global_source_analysis_success = False
    result.report_json_global_success = False


def _same_as_3b43_input(
    project_name: str,
    selection,
    *,
    sortie_dir: Path | None,
) -> bool | None:
    historical = (
        Path(audit_path(project_name, sortie_dir=sortie_dir)).parent
        / "source_analysis_ultra_compact_canary_input.json"
    )
    if not historical.is_file():
        return None
    payload = json.loads(historical.read_text(encoding="utf-8"))
    historical_ids = list(payload.get("selected_source_ids") or [])
    historical_sources = list(payload.get("selected_sources") or [])
    current_sources = [
        {"source_id": segment.src_id, "text": segment.text}
        for segment in selection.segments
    ]
    return (
        list(selection.source_ids) == historical_ids
        and current_sources == historical_sources
    )


def _src_ids_in_text(text: str) -> set[str]:
    import re

    return set(re.findall(r"SRC\d{6}", text or ""))


def _instruction_example_srcs() -> set[str]:
    return {"SRC000001"}


def _fill_usage(
    result: VocabularyComplianceCanaryResult,
    response,
    tracker: CostTracker,
    *,
    failed: bool,
    error=None,
) -> None:
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


def _build_input_artifact(result: VocabularyComplianceCanaryResult) -> dict:
    return {
        "schema_version": CANARY_SCHEMA_VERSION,
        "transport_version": TRANSPORT_VERSION,
        "transcript_id": result.transcript_id,
        "source_transcript_sha256": result.source_transcript_sha256,
        "clean_transcript_sha256": result.clean_transcript_sha256,
        "provenance_verified": result.provenance_verified,
        "selection_rule": result.selection_rule,
        "selected_source_ids": list(result.selected_source_ids),
        "selected_segment_count": result.selected_segment_count,
        "selected_word_count": result.selected_word_count,
        "selected_sources": list(result.selected_texts),
        "selected_text": result.selected_text,
        "prompt_version": result.prompt_version,
        "prompt_sha256": result.prompt_sha256,
        "vocabulary_contract_sha256": result.vocabulary_contract_sha256,
        "raw_generation_c_sha256": result.raw_generation_c_sha256,
        "anthropic_generation_c_sha256": result.anthropic_generation_c_sha256,
        "estimated_system_tokens": result.estimated_system_tokens,
        "estimated_user_tokens": result.estimated_user_tokens,
        "estimated_total_tokens": result.estimated_input_tokens,
        "max_output_tokens": result.estimated_output_budget,
    }


def _build_dry_run_artifact(result: VocabularyComplianceCanaryResult) -> dict:
    return {
        "schema_version": CANARY_SCHEMA_VERSION,
        "transport_version": TRANSPORT_VERSION,
        "would_call_ai": True,
        "actual_real_calls": 0,
        "provider": result.provider,
        "model": result.model,
        "output_config_format_type": result.output_format_type,
        "prompt_version": result.prompt_version,
        "vocabulary_parity": result.vocabulary_parity,
        "generation_c_selected": True,
        "generation_b_selected": False,
        "generation_a_selected": False,
        "native_structured_output": True,
        "uses_production_generation_c": result.uses_production_generation_c,
        "generation_a_absent_from_payload": result.generation_a_absent_from_payload,
        "generation_b_absent_from_payload": result.generation_b_absent_from_payload,
        "local_compatibility": result.local_compatibility,
        "provider_enums": 0,
        "retry_disabled": True,
        "fallback_disabled": True,
        "max_real_calls": MAX_REAL_CALLS,
        "max_attempts": MAX_ATTEMPTS,
        "selected_segment_count": result.selected_segment_count,
        "selected_word_count": result.selected_word_count,
        "selected_source_ids": list(result.selected_source_ids),
        "estimated_system_tokens": result.estimated_system_tokens,
        "estimated_user_tokens": result.estimated_user_tokens,
        "estimated_input_tokens": result.estimated_input_tokens,
        "estimated_output_budget": result.estimated_output_budget,
        "network": dict(_EMPTY_NETWORK),
        "credential_available": result.credential_available,
        "cache_isolated": True,
    }


def _decide_outcome(result: VocabularyComplianceCanaryResult) -> str:
    if result.dry_run and result.actual_real_calls == 0 and result.would_call_ai:
        if result.stop_reason == STOP_PRE_CALL:
            return OUTCOME_FAIL
        return OUTCOME_PASS
    if result.actual_real_calls == 0:
        return OUTCOME_FAIL
    if result.classification == CLASS_SERVER_GRAMMAR_REGRESSION:
        return OUTCOME_FAIL
    if result.server_grammar_acceptance != GRAMMAR_ACCEPTANCE_VERIFIED:
        return OUTCOME_FAIL
    if (
        result.pipeline_result == "PASS"
        and result.vocabulary_compliance == "PASS"
        and result.vocabulary_prompt_compliance == VOCAB_PROMPT_VERIFIED
        and not result.invalid_tokens
        and not result.production_source_map_created
        and not result.global_source_analysis_success
    ):
        return OUTCOME_PASS
    return OUTCOME_PARTIAL


def _safe_post_snapshot(
    result: VocabularyComplianceCanaryResult,
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
    result: VocabularyComplianceCanaryResult,
    project_name: str,
    sortie_dir: Path | None,
) -> None:
    from app.source_analysis_vocabulary_compliance_canary.report import render_canary_report

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
