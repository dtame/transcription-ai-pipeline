"""
Exécution gardée du Source Analyzer sur un transcript DERIVED.

Contrat de cette tentative :

    mode = DERIVED
    provenance = cleanup_application.json
    provider = anthropic
    model = claude-sonnet-5
    max_real_calls = 1
    max_attempts = 1
    stratégie = global
    aucun fallback, aucun retry, aucun second prompt

CE MODULE N'EST BRANCHÉ NULLE PART AUTOMATIQUEMENT. Seul
`python -m app.source_analysis.cli <projet> --analyze-derived` l'invoque.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.errors import AIError
from app.ai.registry import get_ai_engine
from app.ai.retry import RetryPolicy
from app.ai.settings import (
    ENV_ANTHROPIC_API_KEY,
    get_api_key,
    resolve_stage_settings,
)
from app.cleanup_application.writer import audit_path, clean_dir, clean_json_path
from app.language_cleanup.transcript_source import audit_dir
from app.project_state import load_project_state
from app.report_service import build_project_report
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis import cache as cache_module
from app.source_analysis import prompt as prompt_module
from app.source_analysis import state as state_module
from app.source_analysis import writer as writer_module
from app.source_analysis.analyzer import (
    STAGE,
    analyze_source,
    is_truncated_finish_reason,
)
from app.source_analysis.errors import (
    ExistingSourceMapConflictError,
    MaxRealCallsExceededError,
    SourceAnalysisError,
)
from app.source_analysis.guard import MAX_REAL_CALLS, RealCallGuard
from app.source_analysis.models import (
    SOURCE_MAP_SCHEMA_VERSION,
    STRATEGY_GLOBAL,
    SourceMap,
    forbidden_editorial_fields,
)
from app.source_analysis.preflight import run_source_analyzer_preflight
from app.source_analysis.protected import (
    ProtectedSnapshot,
    compare_protected,
    snapshot_protected,
)
from app.source_analysis.provenance import validate_derived_provenance
from app.source_analysis.ultra_compact_schema import (
    build_ultra_compact_response_schema,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.schema import build_response_schema, schema_fingerprint
from app.source_analysis.transcript_input import (
    TranscriptInputMode,
    load_transcript_input,
)
from app.source_analysis.validator import validate_published_payload
from app.source_analysis.writer import partial_path, source_map_path, transcripts_dir

EXPECTED_PROVIDER = "anthropic"
EXPECTED_MODEL = "claude-sonnet-5"
MAX_ATTEMPTS = 1
# HISTORIQUE — runner frère, jamais utilisé par le 3B Final.
# N'est plus passé au constructeur du moteur. Les timeouts viennent
# de resolve_timeouts() (étape / env / défauts). Conservé pour ne pas
# laisser croire qu'un second 3600 contrôle encore ce chemin.
REAL_CALL_TIMEOUT_SECONDS = 3600.0
REPORT_NAME = "PHASE_3B_REAL_SOURCE_ANALYZER_CLEAN_REPORT.md"

_SRC_RE = re.compile(r"SRC\d{6}")

OUTCOME_PASS = "PASS"
OUTCOME_PARTIAL = "PARTIAL"
OUTCOME_FAIL = "FAIL"

STOP_PRE_CALL = "PRE_CALL_FAILURE"
STOP_CACHE_HIT = "CACHE_HIT"
STOP_EXISTING_MAP = "EXISTING_SOURCE_MAP"
STOP_AFTER_CALL = "POST_CALL_FAILURE"


class GuardedEngine:
    """
    Délègue à un moteur, plafonne generate() à un appel, compte les requêtes.

    `generate_calls` et le RealCallGuard sont incrémentés AVANT l'appel
    délégué. Un second generate() lève MaxRealCallsExceededError.
    """

    def __init__(self, inner, guard: RealCallGuard) -> None:
        self._inner = inner
        self._guard = guard
        self.generate_calls = 0
        self.last_payload: dict | None = None
        if hasattr(inner, "build_payload"):
            original = inner.build_payload

            def _capture(request, model):
                payload = original(request, model)
                self.last_payload = payload
                return payload

            inner.build_payload = _capture  # type: ignore[method-assign]

    @property
    def provider_name(self) -> str:
        return self._inner.provider_name

    def resolve_model(self) -> str:
        return self._inner.resolve_model()

    def capabilities(self, model: str | None = None):
        return self._inner.capabilities(model)

    def generate(self, request):
        if self.generate_calls >= MAX_REAL_CALLS:
            raise MaxRealCallsExceededError(
                f"GuardedEngine : un {self.generate_calls + 1}e generate() "
                f"a été tenté (max={MAX_REAL_CALLS})."
            )
        self.generate_calls += 1
        return self._guard.guarded_generate(self._inner, request)


@dataclass
class Phase3BResult:
    """Issue complète — succès, cache, ou échec — pour le rapport 3B."""

    project_name: str
    outcome: str
    pipeline_result: str
    real_call_result: str
    stop_reason: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    protected_before: dict[str, str] = field(default_factory=dict)
    protected_after: dict[str, str] = field(default_factory=dict)
    protected_unchanged: bool | None = None
    protected_violations: list[str] = field(default_factory=list)
    input_path: str = ""
    mode: str = "DERIVED"
    transcript_id: str = ""
    segment_count: int | None = None
    word_count: int | None = None
    duration_seconds: float | None = None
    clean_sha256: str = ""
    cleanup_application_sha256: str = ""
    provenance: dict | None = None
    provider: str = ""
    model: str = ""
    credential_available: bool | None = None
    strategy: str = ""
    estimated_tokens: dict = field(default_factory=dict)
    usable_input_budget: int | None = None
    remaining_margin: int | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    context_safety_ratio: float | None = None
    prompt_version: str = ""
    prompt_sha256: str = ""
    real_src_ids_preserved: bool | None = None
    removed_src_absent_from_prompt: bool | None = None
    canonical_schema_version: str = ""
    canonical_schema_sha256: str = ""
    provider_schema_sha256: str = ""
    schema_audit: dict = field(default_factory=dict)
    schema_audit_clean: bool | None = None
    clean_signature: str = ""
    original_signature: str = ""
    signatures_differ: bool | None = None
    cache_hit: bool = False
    source_map_existed_before: bool = False
    real_call_executed: bool = False
    real_call_count: int = 0
    max_real_calls: int = MAX_REAL_CALLS
    max_attempts: int = MAX_ATTEMPTS
    http_result: str = ""
    latency_ms: int | None = None
    request_id: str | None = None
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    usage_source: str = ""
    provider_usage: bool | None = None
    input_cost: str | None = None
    output_cost: str | None = None
    total_cost: str | None = None
    cost_status: str = ""
    cost_currency: str = ""
    pricing_effective_date: str = ""
    pricing_version: str = ""
    native_output_config: bool | None = None
    provider_parse: str = ""
    canonical_parse: str = ""
    normalization: str = ""
    source_map_validation: str = ""
    completeness: str = ""
    editorial_leakage: list[str] = field(default_factory=list)
    referenced_source_count: int | None = None
    clean_source_count: int | None = None
    coverage_ratio: float | None = None
    all_refs_in_clean: bool | None = None
    any_removed_referenced: bool | None = None
    topic_count: int | None = None
    idea_count: int | None = None
    example_count: int | None = None
    reference_count: int | None = None
    uncertainty_count: int | None = None
    repetition_count: int | None = None
    author_intent_kinds: list[str] = field(default_factory=list)
    target_audience_kinds: list[str] = field(default_factory=list)
    main_theme_present: bool | None = None
    voice_profile_present: bool | None = None
    source_map_path: str = ""
    source_map_exists: bool = False
    source_map_size: int | None = None
    source_map_sha256: str = ""
    partial_leftovers: bool = False
    report_json_updated: bool | None = None
    report_json_status: str = ""
    project_state_status: str = ""
    tests_after: str = ""
    files_created_or_modified: list[str] = field(default_factory=list)
    network: dict[str, int] = field(default_factory=dict)
    remaining_anomaly: str = ""

    def to_report_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def anthropic_credential_available() -> bool:
    """True si une clé Anthropic est résolvable. Ne renvoie jamais la clé."""
    return bool(get_api_key(ENV_ANTHROPIC_API_KEY))


def _audit_is_clean(audit: dict) -> bool:
    return all(not value for value in audit.values())


def _src_ids_in_text(text: str) -> set[str]:
    return set(_SRC_RE.findall(text or ""))


def run_derived_source_analysis(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    engine=None,
    require_protected: bool = True,
    require_credential: bool | None = None,
    lock_production_route: bool | None = None,
    write_report: bool = True,
) -> Phase3BResult:
    """
    Préflight + au plus un appel réel Anthropic sur le transcript clean.

    `engine` est réservé aux tests (FakeAIEngine). Sans injection, le moteur
    est Anthropic / claude-sonnet-5, retry désactivé, timeout long.
    """
    result = Phase3BResult(
        project_name=project_name,
        outcome=OUTCOME_FAIL,
        pipeline_result="not_started",
        real_call_result="not_attempted",
        network={
            "anthropic": 0,
            "openai": 0,
            "whisper": 0,
            "ollama": 0,
            "lm_studio": 0,
            "other": 0,
        },
    )

    lock_route = engine is None if lock_production_route is None else lock_production_route
    need_credential = engine is None if require_credential is None else require_credential

    try:
        _execute(
            result,
            project_name,
            sortie_dir=sortie_dir,
            engine=engine,
            require_protected=require_protected,
            require_credential=need_credential,
            lock_production_route=lock_route,
        )
    except Exception as exc:
        if result.stop_reason is None:
            result.stop_reason = (
                STOP_AFTER_CALL if result.real_call_executed else STOP_PRE_CALL
            )
        result.error_type = type(exc).__name__
        result.error_message = str(exc)
        if result.pipeline_result == "not_started":
            result.pipeline_result = "FAIL"
        if result.real_call_executed and result.real_call_result == "not_attempted":
            result.real_call_result = "FAIL"
        result.outcome = _decide_outcome(result)
        result.remaining_anomaly = result.error_message or type(exc).__name__
        _safe_post_snapshot(result, project_name, sortie_dir)
        if write_report:
            write_phase3b_report(result, sortie_dir=sortie_dir)
        return result

    result.outcome = _decide_outcome(result)
    if write_report:
        write_phase3b_report(result, sortie_dir=sortie_dir)
    return result


def _execute(
    result: Phase3BResult,
    project_name: str,
    *,
    sortie_dir: Path | None,
    engine,
    require_protected: bool,
    require_credential: bool,
    lock_production_route: bool,
) -> None:
    before = snapshot_protected(
        project_name, sortie_dir=sortie_dir, require_all=require_protected
    )
    result.protected_before = before.to_dict()

    clean_path = clean_json_path(project_name, sortie_dir=sortie_dir)
    provenance_path = audit_path(project_name, sortie_dir=sortie_dir)
    original_path = transcripts_dir(project_name, sortie_dir=sortie_dir) / "transcript_data.json"
    map_path = source_map_path(project_name, sortie_dir=sortie_dir)

    result.input_path = clean_path.as_posix()
    result.source_map_path = map_path.as_posix()
    result.source_map_existed_before = map_path.exists()
    result.cleanup_application_sha256 = (
        sha256_of_file(provenance_path) if provenance_path.exists() else ""
    )

    proven = validate_derived_provenance(
        derived_path=clean_path,
        provenance_path=provenance_path,
        original_transcript_path=original_path,
    )
    result.provenance = proven.to_dict()
    result.clean_sha256 = proven.derived_sha256

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
    result.clean_source_count = transcript.segment_count

    settings = resolve_stage_settings(STAGE)
    result.provider = settings.provider
    result.model = settings.model or ""
    result.temperature = settings.temperature
    result.max_output_tokens = settings.max_output_tokens
    result.context_safety_ratio = settings.context_safety_ratio

    if lock_production_route:
        if settings.provider != EXPECTED_PROVIDER or settings.model != EXPECTED_MODEL:
            raise SourceAnalysisError(
                f"Routage verrouillé : attendu {EXPECTED_PROVIDER}/"
                f"{EXPECTED_MODEL}, obtenu {settings.provider}/{settings.model}. "
                "Aucun fallback."
            )

    result.credential_available = anthropic_credential_available()
    if require_credential and not result.credential_available:
        result.stop_reason = STOP_PRE_CALL
        result.pipeline_result = "PRE_CALL_FAILURE"
        result.real_call_result = "not_attempted"
        raise SourceAnalysisError(
            "Credential Anthropic absente. STOP avant tout appel. "
            "Aucun fallback vers un autre provider."
        )

    preflight = run_source_analyzer_preflight(
        clean_path,
        project_name=project_name,
        mode=TranscriptInputMode.DERIVED,
        provenance_path=provenance_path,
        original_transcript_path=original_path,
        settings=settings,
        write_artifact_to=None,
    )
    result.strategy = preflight.plan.strategy
    result.estimated_tokens = {
        "system": preflight.system_tokens,
        "user": preflight.user_tokens,
        "total": preflight.total_tokens,
        "method": preflight.estimation_method,
        "estimated": True,
    }
    result.usable_input_budget = preflight.plan.usable_input_context
    result.remaining_margin = preflight.remaining_margin
    result.clean_signature = preflight.signature
    result.prompt_version = prompt_module.SOURCE_ANALYZER_PROMPT_VERSION
    result.prompt_sha256 = cache_module.prompt_fingerprint(
        preflight.request.system_prompt or "",
        preflight.request.prompt,
    )
    result.canonical_schema_version = SOURCE_MAP_SCHEMA_VERSION
    result.canonical_schema_sha256 = schema_fingerprint(build_response_schema())
    result.provider_schema_sha256 = ultra_compact_schema_fingerprint(preflight.provider_schema)
    result.schema_audit = {
        key: list(value) for key, value in preflight.schema_audit.items()
    }
    result.schema_audit_clean = _audit_is_clean(preflight.schema_audit)

    if preflight.plan.strategy != STRATEGY_GLOBAL:
        result.stop_reason = STOP_PRE_CALL
        result.pipeline_result = "PRE_CALL_FAILURE"
        raise SourceAnalysisError(
            "Stratégie de contexte ≠ global : "
            f"{preflight.plan.strategy}. La consolidation multi-fenêtres "
            "n'est pas implémentée. STOP avant appel."
        )

    if not result.schema_audit_clean:
        result.stop_reason = STOP_PRE_CALL
        result.pipeline_result = "PRE_CALL_FAILURE"
        raise SourceAnalysisError(
            "Audit du schéma provider Anthropic : incompatibilités restantes. "
            "STOP avant appel."
        )

    prompt_srcs = _src_ids_in_text(preflight.request.prompt)
    clean_srcs = set(transcript.src_ids())
    removed = set(proven.removed_source_refs)
    result.real_src_ids_preserved = prompt_srcs == clean_srcs
    result.removed_src_absent_from_prompt = prompt_srcs.isdisjoint(removed)
    if not result.real_src_ids_preserved or not result.removed_src_absent_from_prompt:
        result.stop_reason = STOP_PRE_CALL
        result.pipeline_result = "PRE_CALL_FAILURE"
        raise SourceAnalysisError(
            "Le prompt ne préserve pas exactement les SRC du clean "
            "(IDs réels, trous visibles, SRC retirés absents)."
        )

    original = load_transcript_input(
        original_path,
        project_name=project_name,
        mode=TranscriptInputMode.SOURCE,
    )
    original_system = prompt_module.build_system_prompt(original.primary_language)
    original_user = prompt_module.build_user_prompt(original)
    result.original_signature = cache_module.build_signature(
        cache_module.SignatureInputs(
            transcript_sha256=original.content_sha256,
            transcript_id=original.transcript_id,
            prompt_version=prompt_module.SOURCE_ANALYZER_PROMPT_VERSION,
            prompt_sha256=cache_module.prompt_fingerprint(
                original_system, original_user
            ),
            schema_version=SOURCE_MAP_SCHEMA_VERSION,
            response_schema_sha256=ultra_compact_schema_fingerprint(
                build_ultra_compact_response_schema()
            ),
            provider=settings.provider,
            model=settings.model or "",
            temperature=settings.temperature,
            max_output_tokens=settings.max_output_tokens,
            context_safety_ratio=float(settings.context_safety_ratio),
            output_language=original.primary_language,
        )
    )
    result.signatures_differ = result.original_signature != result.clean_signature
    if not result.signatures_differ:
        result.stop_reason = STOP_PRE_CALL
        result.pipeline_result = "PRE_CALL_FAILURE"
        raise SourceAnalysisError(
            "Collision de signature : clean et original produisent la même "
            f"signature malgré un transcript_id identique ({transcript.transcript_id})."
        )

    published = writer_module.read_source_map_payload(map_path)
    state = load_project_state(project_name)
    state_block = state_module.load_state_block(state)
    cache_valid = cache_module.is_cache_valid(
        signature=preflight.signature,
        state_block=state_block,
        published_payload=published,
    )

    if map_path.exists() and not cache_valid:
        result.stop_reason = STOP_EXISTING_MAP
        result.pipeline_result = "PRE_CALL_FAILURE"
        result.cache_hit = False
        result.source_map_exists = True
        result.source_map_size = map_path.stat().st_size
        result.source_map_sha256 = sha256_of_file(map_path)
        raise ExistingSourceMapConflictError(
            f"{map_path} existe déjà et n'est pas un cache valide de la "
            "signature clean. STOP : aucun écrasement, aucun appel."
        )

    if cache_valid and published is not None:
        result.cache_hit = True
        result.stop_reason = STOP_CACHE_HIT
        result.real_call_result = "not_attempted (cache_hit)"
        result.real_call_count = 0
        _fill_from_payload(result, published, transcript, proven)
        errors = validate_published_payload(published, transcript)
        result.source_map_validation = "PASS" if not errors else "FAIL"
        result.canonical_parse = "PASS"
        result.normalization = "PASS"
        result.completeness = "PASS" if not errors else "FAIL"
        result.pipeline_result = "PASS" if not errors else "FAIL"
        if errors:
            result.error_message = " | ".join(errors)
            raise SourceAnalysisError(
                "Cache hit mais revalidation du source_map échouée : "
                + result.error_message
            )
        _record_artifacts(result, project_name, map_path, sortie_dir, published=True)
        _safe_post_snapshot(result, project_name, sortie_dir)
        return

    guard = RealCallGuard(max_calls=MAX_REAL_CALLS)
    if engine is None:
        inner = get_ai_engine(
            EXPECTED_PROVIDER,
            model=EXPECTED_MODEL,
            retry_policy=RetryPolicy(
                max_attempts=MAX_ATTEMPTS, base_delay_seconds=0.0
            ),
        )
        if inner.provider_name != EXPECTED_PROVIDER or inner.resolve_model() != EXPECTED_MODEL:
            result.stop_reason = STOP_PRE_CALL
            result.pipeline_result = "PRE_CALL_FAILURE"
            raise SourceAnalysisError(
                f"Moteur résolu {inner.provider_name}/{inner.resolve_model()} "
                f"≠ {EXPECTED_PROVIDER}/{EXPECTED_MODEL}. Aucun fallback."
            )
    else:
        inner = engine

    guarded = GuardedEngine(inner, guard)

    try:
        analysis = analyze_source(
            project_name,
            engine=guarded,
            settings=settings,
            transcripts_dir=clean_dir(project_name, sortie_dir=sortie_dir),
            output_path=map_path,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=provenance_path,
            original_transcript_path=original_path,
        )
    except Exception as exc:
        result.real_call_executed = guard.call_count > 0
        result.real_call_count = guard.call_count
        result.network["anthropic"] = guard.call_count
        result.stop_reason = STOP_AFTER_CALL if guard.call_count else STOP_PRE_CALL
        result.pipeline_result = "FAIL"
        result.real_call_result = "FAIL" if guard.call_count else "not_attempted"
        _capture_error_observability(result, exc, guarded)
        _fill_state_after(result, project_name)
        _record_artifacts(result, project_name, map_path, sortie_dir, published=False)
        _safe_post_snapshot(result, project_name, sortie_dir)
        raise

    result.real_call_executed = not analysis.cached
    result.real_call_count = guard.call_count
    result.cache_hit = analysis.cached
    result.network["anthropic"] = guard.call_count
    result.pipeline_result = "PASS"
    result.real_call_result = (
        "not_attempted (cache_hit)" if analysis.cached else "HTTP/provider success"
    )
    result.canonical_parse = "PASS"
    result.normalization = "PASS"
    result.source_map_validation = "PASS"
    result.completeness = "PASS"
    result.provider_parse = "PASS"
    result.native_output_config = _native_output_active(guarded.last_payload)

    _fill_from_payload(result, analysis.payload, transcript, proven)
    _fill_state_after(result, project_name)
    try:
        build_project_report(project_name)
        result.report_json_updated = True
    except Exception as exc:
        result.report_json_updated = False
        result.error_message = f"report.json : {exc}"

    state_after = load_project_state(project_name)
    result.report_json_status = state_module.build_source_analysis_report(
        state_after
    ).get("status", "")
    result.project_state_status = result.report_json_status

    _record_artifacts(
        result, project_name, map_path, sortie_dir, published=map_path.exists()
    )
    leftover = partial_path(map_path)
    result.partial_leftovers = leftover.exists()
    _safe_post_snapshot(result, project_name, sortie_dir)

    if result.partial_leftovers:
        raise SourceAnalysisError("Fichier .partial abandonné après écriture.")
    if result.any_removed_referenced:
        result.pipeline_result = "FAIL"
        raise SourceAnalysisError(
            "Au moins un SRC retiré a été référencé dans le source_map."
        )
    if result.all_refs_in_clean is False:
        result.pipeline_result = "FAIL"
        raise SourceAnalysisError(
            "Au moins un source_ref n'appartient pas au transcript clean."
        )


def _native_output_active(payload: dict | None) -> bool | None:
    if not isinstance(payload, dict):
        return None
    fmt = ((payload.get("output_config") or {}).get("format") or {})
    return fmt.get("type") == "json_schema" and isinstance(fmt.get("schema"), dict)


def _fill_from_payload(
    result: Phase3BResult,
    payload: dict,
    transcript,
    proven,
) -> None:
    result.editorial_leakage = list(forbidden_editorial_fields(payload))
    analysis = payload.get("source_analysis") if isinstance(payload.get("source_analysis"), dict) else {}
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    voice = payload.get("author_voice_profile")
    intent = analysis.get("author_intent") if isinstance(analysis.get("author_intent"), dict) else {}
    audience = (
        analysis.get("target_audience")
        if isinstance(analysis.get("target_audience"), dict)
        else {}
    )

    result.main_theme_present = bool(str(analysis.get("main_theme") or "").strip())
    result.voice_profile_present = isinstance(voice, dict) and bool(voice)
    result.author_intent_kinds = list(intent.get("kinds") or [])
    result.target_audience_kinds = list(audience.get("kinds") or [])
    result.topic_count = int(stats.get("topic_count") or 0)
    result.idea_count = int(stats.get("idea_count") or 0)
    result.example_count = int(stats.get("example_count") or 0)
    result.reference_count = int(stats.get("reference_count") or 0)
    result.uncertainty_count = int(stats.get("uncertainty_count") or 0)
    result.repetition_count = int(stats.get("repetition_count") or 0)
    result.referenced_source_count = int(stats.get("referenced_source_segments") or 0)
    result.coverage_ratio = stats.get("source_coverage_ratio")
    result.clean_source_count = transcript.segment_count

    try:
        source_map = SourceMap.from_dict(payload)
        referenced = set(source_map.all_source_refs())
        clean_srcs = set(transcript.src_ids())
        removed = set(proven.removed_source_refs)
        result.referenced_source_count = len(referenced)
        result.all_refs_in_clean = referenced <= clean_srcs
        result.any_removed_referenced = bool(referenced & removed)
        result.coverage_ratio = (
            round(len(referenced) / transcript.segment_count, 4)
            if transcript.segment_count
            else 0.0
        )
    except Exception:
        result.all_refs_in_clean = None
        result.any_removed_referenced = None


def _fill_state_after(result: Phase3BResult, project_name: str) -> None:
    state = load_project_state(project_name)
    block = state_module.load_state_block(state)
    result.project_state_status = str(block.get("status") or "")
    report = state_module.build_source_analysis_report(state)
    result.report_json_status = str(report.get("status") or "")

    usage = state.get("ai_usage") if isinstance(state.get("ai_usage"), dict) else {}
    records = usage.get("records") if isinstance(usage.get("records"), list) else []
    last = records[-1] if records else None
    if isinstance(last, dict):
        result.input_tokens = last.get("input_tokens")
        result.output_tokens = last.get("output_tokens")
        result.total_tokens = last.get("total_tokens")
        result.usage_source = str(last.get("usage_source") or "")
        result.provider_usage = result.usage_source == "provider"
        result.latency_ms = last.get("latency_ms")
        result.request_id = last.get("request_id")
        result.finish_reason = last.get("finish_reason")
        cost = last.get("cost") if isinstance(last.get("cost"), dict) else {}
        result.input_cost = (
            None if cost.get("input_cost") is None else str(cost.get("input_cost"))
        )
        result.output_cost = (
            None if cost.get("output_cost") is None else str(cost.get("output_cost"))
        )
        result.total_cost = (
            None if cost.get("total_cost") is None else str(cost.get("total_cost"))
        )
        result.cost_status = str(cost.get("status") or "")
        result.cost_currency = str(cost.get("currency") or "")
        result.pricing_effective_date = str(cost.get("effective_date") or "")
        result.pricing_version = str(cost.get("pricing_source") or "")
        if last.get("status") == "completed" and result.real_call_executed:
            result.real_call_result = "HTTP/provider success"
        if is_truncated_finish_reason(result.finish_reason):
            result.real_call_result = f"truncated ({result.finish_reason})"
            result.canonical_parse = result.canonical_parse or "FAIL"


def _capture_error_observability(
    result: Phase3BResult, exc: BaseException, guarded: GuardedEngine
) -> None:
    result.error_type = type(exc).__name__
    result.error_message = str(exc)
    result.native_output_config = _native_output_active(guarded.last_payload)

    response = getattr(exc, "response", None)
    if response is not None:
        result.latency_ms = getattr(response, "latency_ms", None)
        result.request_id = getattr(response, "request_id", None)
        result.finish_reason = getattr(response, "finish_reason", None)
        result.input_tokens = getattr(response, "input_tokens", None)
        result.output_tokens = getattr(response, "output_tokens", None)
        result.total_tokens = getattr(response, "total_tokens", None)
        result.usage_source = str(getattr(response, "usage_source", "") or "")
        result.provider_usage = result.usage_source == "provider"
        if getattr(response, "parsed", None) is not None:
            result.provider_parse = "PASS"
            result.canonical_parse = "FAIL"
        else:
            result.provider_parse = "FAIL"
            result.canonical_parse = "FAIL"

    name = type(exc).__name__
    if name in {"AIStructuredOutputError"}:
        result.provider_parse = result.provider_parse or "FAIL"
        result.canonical_parse = "FAIL"
    elif name in {"SourceMapValidationError", "SourceMapEditorialLeakError"}:
        result.canonical_parse = result.canonical_parse or "PASS"
        result.normalization = result.normalization or "PASS"
        result.source_map_validation = "FAIL"
    elif name == "SourceMapTruncatedError":
        result.source_map_validation = "FAIL"
        result.completeness = "FAIL"
    elif isinstance(exc, AIError):
        result.provider_parse = result.provider_parse or "FAIL"


def _record_artifacts(
    result: Phase3BResult,
    project_name: str,
    map_path: Path,
    sortie_dir: Path | None,
    *,
    published: bool,
) -> None:
    result.source_map_exists = map_path.exists()
    if map_path.exists():
        result.source_map_size = map_path.stat().st_size
        result.source_map_sha256 = sha256_of_file(map_path)
    leftover = partial_path(map_path)
    result.partial_leftovers = leftover.exists()

    created: list[str] = []
    if published and map_path.exists():
        created.append("analysis/source_map.json")
    created.append("project_state.json")
    created.append("report.json")
    created.append(f"audit/{REPORT_NAME}")
    result.files_created_or_modified = created


def _safe_post_snapshot(
    result: Phase3BResult, project_name: str, sortie_dir: Path | None
) -> None:
    try:
        after = snapshot_protected(
            project_name, sortie_dir=sortie_dir, require_all=False
        )
        result.protected_after = after.to_dict()
        before = ProtectedSnapshot(hashes=result.protected_before)
        result.protected_violations = compare_protected(before, after)
        result.protected_unchanged = not result.protected_violations
    except Exception:
        result.protected_unchanged = None


def _decide_outcome(result: Phase3BResult) -> str:
    if result.stop_reason == STOP_PRE_CALL:
        return OUTCOME_FAIL
    if result.stop_reason == STOP_EXISTING_MAP:
        return OUTCOME_FAIL
    if result.pipeline_result == "PASS" and (
        result.cache_hit or result.real_call_result.startswith("HTTP")
    ):
        if (
            result.source_map_validation == "PASS"
            and result.normalization == "PASS"
            and result.canonical_parse == "PASS"
            and not result.editorial_leakage
            and result.all_refs_in_clean
            and result.any_removed_referenced is False
            and result.source_map_exists
            and not result.partial_leftovers
            and result.protected_unchanged is not False
            and result.real_call_count <= 1
        ):
            return OUTCOME_PASS
        return OUTCOME_PARTIAL
    if result.real_call_executed:
        return OUTCOME_FAIL
    return OUTCOME_FAIL


def write_phase3b_report(
    result: Phase3BResult, *, sortie_dir: Path | None = None
) -> Path:
    """Écrit le rapport markdown 3B, y compris en cas d'échec."""
    from app.source_analysis.phase3b_report import render_phase3b_report

    path = audit_dir(result.project_name, sortie_dir=sortie_dir) / REPORT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_phase3b_report(result), encoding="utf-8")
    return path
