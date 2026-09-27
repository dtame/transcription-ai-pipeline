"""
Source Analyzer — orchestration de la Phase 3.

Enchaînement, une responsabilité par étape, aucune d'elles implémentée ici :

    transcript_data.json
          ↓   transcript_input.load_transcript_input
    TranscriptInput                      (lecture + contrôle du contrat V2)
          ↓   prompt.build_system_prompt / build_user_prompt
    prompts versionnés                   (rôle, fidélité, traçabilité, langue)
          ↓   context_strategy.plan_context
    ContextPlan                          (budget réel du modèle, pas de constante)
          ↓   cache.build_signature
    signature                            (données + contrat + code + routage)
          ↓   cache hit ?  ->  0 appel, 0 coût
    AIRequest(response_schema=ultra)     (transport C, pas le SourceMap)
          ↓   engine.generate
    AIResponse.parsed                    (décodé contre le transport ultra)
          ↓   semantic_transport_decoder (records → raw canonique)
          ↓   normalizer.normalize_source_map
    SourceMap                            (IDs canoniques, ordre de la source)
          ↓   validator.ensure_valid_source_map
    validé                               (sinon rien n'est publié)
          ↓   writer.write_source_map
    analysis/source_map.json             (écriture atomique)
          ↓   CostTracker + usage_store
    report.json["ai_usage"]

CE MODULE N'EST BRANCHÉ NULLE PART AUTOMATIQUEMENT. Il n'est importé ni par
main.py, ni par pipeline_runner.py, ni par app/source_analysis/__init__.py.
Raison : le pipeline V1 tourne aujourd'hui sur Ollama en local, et l'étape
source_analysis est routée vers Anthropic. Le brancher maintenant signifierait
qu'un `python main.py` sur un projet V1 se met, sans que personne l'ait demandé,
à appeler une API payante. La convergence des deux pipelines est prévue en
Phase 9 ; jusque-là, la Phase 3 est un service autonome qu'on appelle
explicitement.

Ce module ne connaît aucun fournisseur : il passe par app.ai (registre, contrats,
capacités, estimation, sortie structurée, coût). Aucun `import anthropic` ici,
ni ailleurs dans le paquet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.ai.contracts import AIRequest
from app.ai.cost import CostTracker
from app.ai.errors import AIError
from app.ai.registry import get_engine_for_stage
from app.ai.settings import StageSettings, resolve_stage_settings
from app.ai.usage_store import record_call
from app.logger import log_event
from app.project_state import load_project_state, save_project_state
from app.source_analysis import cache as cache_module
from app.source_analysis import prompt as prompt_module
from app.source_analysis import state as state_module
from app.source_analysis import writer as writer_module
from app.source_analysis.context_strategy import ContextPlan, plan_context
from app.source_analysis.errors import (
    SourceAnalysisContextExceeded,
    SourceMapTruncatedError,
    SourceTranscriptNotSubstantial,
)

# finish_reason / stop_reason qui signalent une sortie coupée par le plafond.
# Anthropic : "max_tokens". OpenAI : "length". Jamais un succès métier.
TRUNCATION_FINISH_REASONS = frozenset({"max_tokens", "length"})


def is_truncated_finish_reason(finish_reason: str | None) -> bool:
    """True si le fournisseur a arrêté pour cause de plafond de tokens."""
    if not finish_reason:
        return False

    return str(finish_reason).strip().lower() in TRUNCATION_FINISH_REASONS
from app.source_analysis.models import (
    SOURCE_MAP_SCHEMA_VERSION,
    STRATEGY_GLOBAL,
    AnalysisProvenance,
    SourceMap,
)
from app.source_analysis.semantic_transport_decoder import decode_to_canonical_raw
from app.source_analysis.ultra_compact_schema import (
    build_ultra_compact_response_schema,
    ultra_compact_schema_fingerprint,
)
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.transcript_input import (
    TranscriptInput,
    TranscriptInputMode,
    load_transcript_input,
    transcript_data_file,
)
from app.source_analysis.validator import (
    ensure_valid_source_map,
    validate_published_payload,
)

# Étape du pipeline au sens de la Phase 2 : c'est cette chaîne qui route vers
# anthropic / claude-sonnet-5 (AI_STAGE_SETTINGS) et qui apparaît dans
# report.json["ai_usage"]["by_stage"].
STAGE = "source_analysis"


@dataclass(frozen=True)
class SourceAnalysisResult:
    """
    Issue d'une analyse, réussie.

    `source_map` n'est renseigné que lors d'une analyse FRAÎCHE ; sur réemploi du
    cache, `payload` porte le fichier relu et revalidé. `payload` est donc la
    forme toujours disponible, et le champ à privilégier par les appelants.
    """

    project_name: str
    path: Path
    payload: dict
    signature: str
    cached: bool
    plan: ContextPlan
    source_map: SourceMap | None = None

    @property
    def stats(self) -> dict:
        stats = self.payload.get("stats")

        return dict(stats) if isinstance(stats, dict) else {}


def analyze_source(
    project_name: str,
    *,
    engine=None,
    settings: StageSettings | None = None,
    transcripts_dir: Path | None = None,
    output_path: Path | None = None,
    force: bool = False,
    mode: TranscriptInputMode | str = TranscriptInputMode.SOURCE,
    provenance_path: Path | None = None,
    original_transcript_path: Path | None = None,
) -> SourceAnalysisResult:
    """
    Produit (ou réutilise) le Source Map d'un projet.

    `engine` permet d'injecter un moteur — c'est ce que font les tests avec
    FakeAIEngine, sans jamais toucher au réseau. Sans injection, le moteur vient
    du registre Phase 2 pour l'étape `source_analysis`.

    `force=True` ignore un cache pourtant valide et repaie l'analyse.

    `mode` vaut SOURCE par défaut (SRC continus). DERIVED exige une
    provenance explicite et n'est jamais déduit du chemin.
    """
    transcript = _load_transcript(
        project_name,
        transcripts_dir,
        mode=mode,
        provenance_path=provenance_path,
        original_transcript_path=original_transcript_path,
    )

    if not transcript.is_substantial:
        raise SourceTranscriptNotSubstantial(
            f"Transcript trop pauvre pour être analysé : {transcript.word_count} "
            f"mot(s) sur {transcript.segment_count} segment(s). Le Source "
            "Analyzer refuse de publier un Source Map vide, qui serait "
            "indistinguable d'une analyse ratée.",
            word_count=transcript.word_count,
            segment_count=transcript.segment_count,
        )

    engine, settings = _resolve_engine(engine, settings)

    system_prompt = prompt_module.build_system_prompt(transcript.primary_language)
    user_prompt = prompt_module.build_user_prompt(transcript)
    response_schema = build_ultra_compact_response_schema()

    model = engine.resolve_model()
    capabilities = engine.capabilities(model)

    plan = plan_context(
        transcript,
        capabilities,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        safety_ratio=settings.context_safety_ratio,
    )

    signature = cache_module.build_signature(
        cache_module.SignatureInputs(
            transcript_sha256=transcript.content_sha256,
            transcript_id=transcript.transcript_id,
            prompt_version=prompt_module.SOURCE_ANALYZER_PROMPT_VERSION,
            prompt_sha256=cache_module.prompt_fingerprint(system_prompt, user_prompt),
            schema_version=SOURCE_MAP_SCHEMA_VERSION,
            response_schema_sha256=ultra_compact_schema_fingerprint(response_schema),
            provider=engine.provider_name,
            model=model,
            temperature=settings.temperature,
            max_output_tokens=settings.max_output_tokens,
            context_safety_ratio=float(settings.context_safety_ratio),
            output_language=transcript.primary_language,
        )
    )

    path = (
        Path(output_path)
        if output_path is not None
        else writer_module.source_map_path(project_name)
    )

    if not force:
        cached = _reuse_cached(
            project_name,
            transcript,
            path=path,
            signature=signature,
            plan=plan,
        )

        if cached is not None:
            return cached

    if plan.strategy != STRATEGY_GLOBAL:
        _log(
            "source_analysis_context_exceeded",
            project_name=project_name,
            plan=plan,
            signature=signature,
        )
        raise SourceAnalysisContextExceeded(
            "La représentation complète du transcript ne tient pas dans le "
            f"budget d'entrée du modèle : {plan.budget_summary()}. "
            f"Un découpage technique de {plan.window_count} fenêtre(s) sur "
            "frontières de SRC a été calculé, mais la consolidation "
            "multi-fenêtres n'est pas implémentée en Phase 3. Aucune troncature "
            "n'a été effectuée et aucun Source Map n'a été publié.",
            plan=plan,
        )

    return _run_analysis(
        project_name,
        transcript,
        engine=engine,
        settings=settings,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_schema=response_schema,
        model=model,
        plan=plan,
        signature=signature,
        path=path,
    )


# ---------------------------------------------------------------------------
# Étapes
# ---------------------------------------------------------------------------

def _load_transcript(
    project_name: str,
    transcripts_dir: Path | None,
    *,
    mode: TranscriptInputMode | str = TranscriptInputMode.SOURCE,
    provenance_path: Path | None = None,
    original_transcript_path: Path | None = None,
) -> TranscriptInput:
    directory = (
        Path(transcripts_dir)
        if transcripts_dir is not None
        else writer_module.transcripts_dir(project_name)
    )

    return load_transcript_input(
        transcript_data_file(directory),
        project_name=project_name,
        mode=mode,
        provenance_path=provenance_path,
        original_transcript_path=original_transcript_path,
    )


def _resolve_engine(engine, settings: StageSettings | None):
    """
    Moteur et réglages de l'étape.

    Les réglages viennent de resolve_stage_settings() même lorsqu'un moteur est
    injecté : le ratio de sécurité de contexte et les plafonds appartiennent à
    la configuration de l'étape, pas au moteur, et un test qui injecte un faux
    moteur doit tout de même exercer le vrai budget.
    """
    resolved_settings = settings or resolve_stage_settings(STAGE)

    if engine is not None:
        return engine, resolved_settings

    engine, stage_settings = get_engine_for_stage(STAGE)

    return engine, settings or stage_settings


def _reuse_cached(
    project_name: str,
    transcript: TranscriptInput,
    *,
    path: Path,
    signature: str,
    plan: ContextPlan,
) -> SourceAnalysisResult | None:
    """
    Réutilise une analyse précédente si — et seulement si — elle est la même.

    Trois conditions, toutes nécessaires : la signature concorde dans l'état
    projet ET dans le fichier publié, et le fichier passe encore le validateur.
    Sinon on repaie. Une analyse dont la signature ne correspond plus n'est pas
    « proche » : le transcript, le prompt, le schéma ou le modèle a changé, donc
    son contenu ne décrit plus ce qu'on croit.
    """
    state = load_project_state(project_name)
    block = state_module.load_state_block(state)
    payload = writer_module.read_source_map_payload(path)

    if not cache_module.is_cache_valid(
        signature=signature,
        state_block=block,
        published_payload=payload,
    ):
        return None

    errors = validate_published_payload(payload, transcript)

    if errors:
        _log(
            "source_analysis_cache_rejected",
            project_name=project_name,
            plan=plan,
            signature=signature,
            error_count=len(errors),
        )
        return None

    _log(
        "source_analysis_cache_hit",
        project_name=project_name,
        plan=plan,
        signature=signature,
    )

    return SourceAnalysisResult(
        project_name=project_name,
        path=path,
        payload=payload,
        signature=signature,
        cached=True,
        plan=plan,
    )


def _run_analysis(
    project_name: str,
    transcript: TranscriptInput,
    *,
    engine,
    settings: StageSettings,
    system_prompt: str,
    user_prompt: str,
    response_schema: dict,
    model: str,
    plan: ContextPlan,
    signature: str,
    path: Path,
) -> SourceAnalysisResult:
    request = AIRequest(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
        response_schema=response_schema,
        metadata={"stage": STAGE, "project": project_name},
    )

    _log(
        "source_analysis_started",
        project_name=project_name,
        plan=plan,
        signature=signature,
    )

    try:
        response = engine.generate(request)
    except AIError as exc:
        _record_failure(
            project_name,
            provider=engine.provider_name,
            model=model,
            error=exc,
            plan=plan,
            signature=signature,
        )
        raise

    provenance = AnalysisProvenance(
        prompt_version=prompt_module.SOURCE_ANALYZER_PROMPT_VERSION,
        schema_version=SOURCE_MAP_SCHEMA_VERSION,
        provider=response.provider,
        model=response.model,
        strategy=plan.strategy,
        signature=signature,
    )

    try:
        if is_truncated_finish_reason(response.finish_reason):
            raise SourceMapTruncatedError(
                f"finish_reason={response.finish_reason!r} : sortie tronquée. "
                "Aucun source_map n'est publié."
            )
        source_map = normalize_source_map(
            decode_to_canonical_raw(response.parsed),
            transcript,
            provenance=provenance,
        )
        ensure_valid_source_map(source_map, transcript)
    except Exception as exc:
        # L'appel a bien eu lieu et a probablement été facturé : l'usage réel est
        # enregistré même si son résultat est inexploitable. En revanche rien
        # n'est publié, et l'état passe à `failed`.
        _record_usage(project_name, response)
        _write_failed_state(
            project_name,
            provider=response.provider,
            model=response.model,
            error_type=type(exc).__name__,
            plan=plan,
            signature=signature,
        )
        _log(
            "source_analysis_failed",
            project_name=project_name,
            plan=plan,
            signature=signature,
            error_type=type(exc).__name__,
        )
        raise

    payload = source_map.to_dict()

    writer_module.write_source_map(path, payload)

    _record_usage(project_name, response)

    _write_completed_state(
        project_name,
        path=path,
        signature=signature,
        provider=response.provider,
        model=response.model,
        plan=plan,
        stats=payload["stats"],
    )

    _log(
        "source_analysis_completed",
        project_name=project_name,
        plan=plan,
        signature=signature,
        latency_ms=response.latency_ms,
        topics=source_map.stats.topic_count,
        ideas=source_map.stats.idea_count,
        examples=source_map.stats.example_count,
        references=source_map.stats.reference_count,
        uncertainties=source_map.stats.uncertainty_count,
        repetitions=source_map.stats.repetition_count,
        source_coverage_ratio=source_map.stats.source_coverage_ratio,
    )

    return SourceAnalysisResult(
        project_name=project_name,
        path=path,
        payload=payload,
        signature=signature,
        cached=False,
        plan=plan,
        source_map=source_map,
    )


# ---------------------------------------------------------------------------
# Coût et état
# ---------------------------------------------------------------------------

def _record_usage(project_name: str, response) -> None:
    """
    Enregistre l'appel dans la comptabilité existante.

    Les tokens sont ceux RAPPORTÉS par le fournisseur, jamais recalculés depuis
    le texte : l'estimation de context_strategy sert au budget, pas à la
    facture. Aucun compteur local à la Phase 3 — le CostTracker de la Phase 2
    est le seul.
    """
    tracker = CostTracker()
    record = tracker.record_response(response, stage=STAGE)
    record_call(project_name, record)


def _record_failure(
    project_name: str,
    *,
    provider: str,
    model: str,
    error: BaseException,
    plan: ContextPlan,
    signature: str,
) -> None:
    # Un AIError levé APRÈS un transport réussi (sortie structurée invalide,
    # par exemple) porte l'AIResponse partielle attachée par
    # BaseAIEngine.generate() : son usage réel — et le coût qui en découle —
    # doit survivre à l'échec métier plutôt que disparaître avec l'exception
    # (voir Phase 3B.2). Une erreur de transport (timeout, config…) n'a pas
    # cet attribut renseigné, et le comportement reste celui d'avant : aucun
    # token inventé.
    tracker = CostTracker()
    record = tracker.record_failure(
        provider=provider,
        model=model,
        stage=STAGE,
        error=error,
        response=getattr(error, "response", None),
    )
    record_call(project_name, record)

    _write_failed_state(
        project_name,
        provider=provider,
        model=model,
        error_type=type(error).__name__,
        plan=plan,
        signature=signature,
    )

    _log(
        "source_analysis_failed",
        project_name=project_name,
        plan=plan,
        signature=signature,
        error_type=type(error).__name__,
    )


def _write_completed_state(
    project_name: str,
    *,
    path: Path,
    signature: str,
    provider: str,
    model: str,
    plan: ContextPlan,
    stats: dict,
) -> None:
    state = load_project_state(project_name)
    state[state_module.STATE_KEY] = state_module.build_completed_block(
        signature=signature,
        path=str(path),
        provider=provider,
        model=model,
        strategy=plan.strategy,
        prompt_version=prompt_module.SOURCE_ANALYZER_PROMPT_VERSION,
        schema_version=SOURCE_MAP_SCHEMA_VERSION,
        cached=False,
        stats=stats,
        updated_at=_now(),
    )
    save_project_state(project_name, state)


def _write_failed_state(
    project_name: str,
    *,
    provider: str,
    model: str,
    error_type: str,
    plan: ContextPlan,
    signature: str,
) -> None:
    state = load_project_state(project_name)
    previous = state_module.load_state_block(state)

    state[state_module.STATE_KEY] = state_module.build_failed_block(
        signature=signature,
        provider=provider,
        model=model,
        strategy=plan.strategy,
        prompt_version=prompt_module.SOURCE_ANALYZER_PROMPT_VERSION,
        schema_version=SOURCE_MAP_SCHEMA_VERSION,
        error_type=error_type,
        updated_at=_now(),
        previous=previous,
    )
    save_project_state(project_name, state)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _log(event: str, *, project_name: str, plan: ContextPlan, signature: str, **fields):
    """
    Journalisation de l'étape.

    Ce qui est journalisé : projet, étape, stratégie, budget estimé, provider,
    modèle, statut, cache, compteurs, latence. Ce qui ne l'est JAMAIS : le
    transcript, le prompt, le Source Map, une clé d'API. Un log ne doit ni
    fuiter le contenu d'un projet ni peser un mégaoctet par appel.

    La signature est tronquée : douze caractères suffisent à corréler deux lignes
    de log, et la valeur complète vit déjà dans project_state.json.
    """
    payload = {
        "event": event,
        "stage": STAGE,
        "project": project_name,
        "strategy": plan.strategy,
        "estimated_input_tokens": plan.estimated_input_tokens,
        "usable_input_context": plan.usable_input_context,
        "capabilities_known": plan.capabilities_known,
        "provider": plan.provider,
        "model": plan.model,
        "signature": signature[:12],
    }
    payload.update({key: value for key, value in fields.items() if value is not None})

    log_event(payload)
