"""
Orchestration du canary (§7-§37).

Enchaînement, une responsabilité par module, aucune d'elles implémentée ici :

    validate sources (§8-9)         load_and_validate_sources
          |
    intégrité AVANT (§9)            integrity.snapshot_sources
          |
    sélection déterministe (§13-14) selection.select_canary_blocks / validate_selection
          |
    payload sanitisé (§15-16)       payload.build_canary_payloads
          |
    prompt versionné (§17)          prompt.build_system_prompt / build_user_prompt
          |
    schéma structuré (§18)          schema.build_response_schema
          |
    préflight (§29)                 preflight.run_preflight
          |
    UN appel réel, gardé (§12,§32)  guard.RealCallGuard
          |
    validation stricte (§19)        validator.validate_canary_response
          |
    intégrité APRÈS (§37)           integrity.ensure_unchanged
          |
    artefact (§21)                  writer.write_artifact
          |
    comparaison locale (§22-25)     report.build_case_reports

CE MODULE N'EST BRANCHÉ NULLE PART AUTOMATIQUEMENT (comme
app/source_analysis/analyzer.py) : seul `python -m app.semantic_canary.cli`
l'invoque.

Un échec AVANT l'appel réseau (sources invalides, sélection invalide,
préflight invalide) lève une exception : il n'y a aucune observabilité
réseau à préserver, STOP AVANT RÉSEAU (§8, §14, §29). Un échec de l'APPEL
lui-même (transport, sortie structurée, validation locale de la réponse) ne
lève PAS : il est capturé dans `CanaryRunResult.error`, avec toute
l'observabilité disponible préservée (§34) — pour que l'appelant (cli.py)
puisse produire un rapport même en cas d'échec, sans jamais retenter
d'appel.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.contracts import AIRequest, AIResponse
from app.ai.cost import CostTracker, AICallRecord
from app.ai.errors import AIError
from app.ai.estimation import TokenEstimate, estimate_request_tokens
from app.ai.registry import get_ai_engine
from app.ai.retry import RetryPolicy
from app.language_blocks.combined_source import load_combined_source
from app.language_blocks.errors import LanguageBlocksError
from app.language_blocks.writer import (
    manifest_path as blocks_manifest_path,
    read_manifest_payload as read_blocks_manifest,
)
from app.language_cleanup.writer import (
    manifest_path as cleanup_manifest_path,
    read_manifest_payload as read_cleanup_manifest,
)
from app.semantic_canary import payload as payload_module
from app.semantic_canary import prompt as prompt_module
from app.semantic_canary import report as report_module
from app.semantic_canary import schema as schema_module
from app.semantic_canary import selection as selection_module
from app.semantic_canary import writer as writer_module
from app.semantic_canary.errors import SourceIntegrityError
from app.semantic_canary.guard import RealCallGuard
from app.semantic_canary.integrity import IntegritySnapshot, ensure_unchanged, snapshot_sources
from app.semantic_canary.models import SelectedBlock
from app.semantic_canary.preflight import (
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    PreflightReport,
    run_preflight,
)
from app.semantic_canary.validator import validate_canary_response
from app.source_analysis.transcript_input import transcript_data_file
from app.source_analysis.writer import transcripts_dir as transcripts_directory

STAGE = "semantic_translation_canary"

# Vérifiés manuellement contre pastoral_retreat_v2_validation (§1, §8) :
#     8415 SRC totaux, 828 SRC FR, 333 blocs FR, 314 NEEDED, 15
#     ALREADY_RESOLVED, 4 NO_ENGLISH_CONTEXT. Ce module ne les impose PAS en
# dur (un projet plus petit, notamment de test, aurait d'autres comptes) :
# il vérifie la cohérence INTERNE des trois fichiers entre eux, ce qui
# couvre le même risque (source corrompue ou désynchronisée) sans figer un
# nombre magique propre à un seul projet.


@dataclass(frozen=True)
class CanaryError:
    """Ce qui est disponible d'un appel qui n'a pas abouti (§34)."""

    error_type: str
    message: str

    def to_dict(self) -> dict:
        return {"error_type": self.error_type, "message": self.message}


@dataclass
class CanaryRunResult:
    """Issue complète d'une exécution du canary — succès ou échec (§34-35)."""

    project_name: str
    selected_blocks: list[SelectedBlock]
    payloads: list[dict]
    system_prompt: str
    user_prompt: str
    prompt_version: str
    response_schema: dict
    schema_fingerprint: str
    preflight: PreflightReport
    estimate: TokenEstimate
    integrity_before: IntegritySnapshot
    real_call_count: int
    success: bool
    response: AIResponse | None = None
    cost_record: AICallRecord | None = None
    cases: list[report_module.CaseReport] | None = None
    artifact_path: Path | None = None
    integrity_after: IntegritySnapshot | None = None
    error: CanaryError | None = None


# ---------------------------------------------------------------------------
# §8-9 : chargement et validation des trois sources
# ---------------------------------------------------------------------------

def load_and_validate_sources(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Charge et valide les trois sources (§8-9) — STOP AVANT RÉSEAU si invalide.

    Vérifie la cohérence INTERNE : les trois fichiers se référencent
    mutuellement par SHA-256 (déjà garanti par
    app.language_blocks.combined_source.load_combined_source, réutilisé
    ici), et les statistiques déclarées de language_blocks.json
    correspondent au contenu réel de `blocks[]`.
    """
    blocks_path = blocks_manifest_path(project_name, sortie_dir=sortie_dir)
    blocks_payload = read_blocks_manifest(blocks_path)

    if blocks_payload is None:
        raise SourceIntegrityError(
            f"language_blocks.json introuvable ou illisible : {blocks_path}"
        )

    cleanup_path = cleanup_manifest_path(project_name, sortie_dir=sortie_dir)
    cleanup_payload = read_cleanup_manifest(cleanup_path)

    if cleanup_payload is None:
        raise SourceIntegrityError(
            f"language_cleanup.json introuvable ou illisible : {cleanup_path}"
        )

    transcript_path = transcript_data_file(
        transcripts_directory(project_name, sortie_dir=sortie_dir)
    )

    if not transcript_path.exists():
        raise SourceIntegrityError(
            f"transcript_data.json introuvable : {transcript_path}"
        )

    try:
        combined = load_combined_source(project_name, sortie_dir=sortie_dir)
    except LanguageBlocksError as exc:
        raise SourceIntegrityError(
            "transcript_data.json et language_cleanup.json ne concordent "
            f"pas assez pour être traités ensemble : {exc}"
        ) from exc

    if combined.transcript_sha256 != blocks_payload.get("transcript_sha256"):
        raise SourceIntegrityError(
            "language_blocks.json.transcript_sha256 ne correspond pas au "
            "transcript_data.json actuel."
        )

    if combined.language_cleanup_sha256 != blocks_payload.get("language_cleanup_sha256"):
        raise SourceIntegrityError(
            "language_blocks.json.language_cleanup_sha256 ne correspond pas "
            "au language_cleanup.json actuel."
        )

    if cleanup_payload.get("transcript_sha256") != blocks_payload.get("transcript_sha256"):
        raise SourceIntegrityError(
            "language_cleanup.json et language_blocks.json ne référencent pas "
            "le même transcript_sha256."
        )

    stats = blocks_payload.get("stats") or {}
    blocks = list(blocks_payload.get("blocks") or [])

    if len(blocks) != stats.get("total_FR_blocks"):
        raise SourceIntegrityError(
            f"language_blocks.json incohérent : {len(blocks)} bloc(s) présent(s) "
            f"mais stats.total_FR_blocks={stats.get('total_FR_blocks')}."
        )

    review_distribution = stats.get("semantic_review_distribution") or {}
    recounted = Counter(block.get("semantic_review_status") for block in blocks)

    for key in ("NEEDED", "ALREADY_RESOLVED", "NO_ENGLISH_CONTEXT"):
        declared = review_distribution.get(key, 0)
        actual = recounted.get(key, 0)
        if declared != actual:
            raise SourceIntegrityError(
                f"semantic_review_distribution incohérente pour {key} : "
                f"déclaré={declared}, recompté={actual}."
            )

    return {
        "language_blocks": blocks_payload,
        "language_cleanup": cleanup_payload,
        "blocks": blocks,
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# Exécution complète (§7-§37)
# ---------------------------------------------------------------------------

def run_semantic_canary(
    project_name: str,
    *,
    engine=None,
    sortie_dir: Path | None = None,
    expected_provider: str = EXPECTED_PROVIDER,
    expected_model: str = EXPECTED_MODEL,
    retry_policy: RetryPolicy | None = None,
) -> CanaryRunResult:
    """
    Exécute le canary complet.

    `engine=None` construit le moteur réel (anthropic / claude-sonnet-5,
    retry désactivé — §12, §22) via le registre Phase 2. Les tests injectent
    un FakeAIEngine et surchargent `expected_provider`/`expected_model` pour
    exercer le même préflight sans réseau (§30.17).
    """
    # §8-9 : sources
    sources = load_and_validate_sources(project_name, sortie_dir=sortie_dir)
    blocks = sources["blocks"]

    # §9 : intégrité AVANT traitement
    integrity_before = snapshot_sources(project_name, sortie_dir=sortie_dir)

    # §13-14 : sélection déterministe, validée localement AVANT réseau
    selected_blocks = selection_module.select_canary_blocks(blocks)
    selection_module.validate_selection(selected_blocks)

    # §15-16 : payload sanitisé (aucune donnée Phase 3A.1)
    payloads = payload_module.build_canary_payloads(selected_blocks)
    for one_payload in payloads:
        payload_module.assert_no_forbidden_leak(one_payload)

    # §17-18 : prompt versionné + schéma structuré
    system_prompt = prompt_module.build_system_prompt()
    user_prompt = prompt_module.build_user_prompt(payloads)
    response_schema = schema_module.build_response_schema()
    fingerprint = schema_module.schema_fingerprint(response_schema)

    # §10-12 : moteur — anthropic/claude-sonnet-5, retry réel désactivé
    if engine is None:
        engine = get_ai_engine(
            "anthropic",
            model="claude-sonnet-5",
            retry_policy=retry_policy or RetryPolicy(max_attempts=1, base_delay_seconds=0.0),
        )

    model = engine.resolve_model()

    request = AIRequest(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model=model,
        response_schema=response_schema,
        metadata={"stage": STAGE, "project": project_name},
    )

    # §28 : estimation locale AVANT appel
    estimate = estimate_request_tokens(request)

    # §29 : préflight — STOP AVANT RÉSEAU s'il échoue (lève PreflightError)
    preflight = run_preflight(
        engine,
        model,
        response_schema,
        expected_provider=expected_provider,
        expected_model=expected_model,
    )

    # §12, §32 : UN appel réel au maximum, gardé
    guard = RealCallGuard(max_calls=1)
    tracker = CostTracker()

    try:
        response = guard.guarded_generate(engine, request)
    except AIError as exc:
        record = tracker.record_failure(
            provider=engine.provider_name,
            model=model,
            stage=STAGE,
            error=exc,
            response=getattr(exc, "response", None),
        )
        return CanaryRunResult(
            project_name=project_name,
            selected_blocks=selected_blocks,
            payloads=payloads,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_version=prompt_module.SEMANTIC_CANARY_PROMPT_VERSION,
            response_schema=response_schema,
            schema_fingerprint=fingerprint,
            preflight=preflight,
            estimate=estimate,
            integrity_before=integrity_before,
            real_call_count=guard.call_count,
            success=False,
            cost_record=record,
            error=CanaryError(error_type=type(exc).__name__, message=str(exc)),
        )

    record = tracker.record_response(response, stage=STAGE)

    # §19 : validation locale stricte de la réponse — jamais de second appel
    expected_ids = [block.block_id for block in selected_blocks]

    try:
        results = validate_canary_response(response.parsed, expected_ids)
    except Exception as exc:  # CanaryResponseValidationError, ou décodage
        integrity_after = snapshot_sources(project_name, sortie_dir=sortie_dir)
        ensure_unchanged(integrity_before, integrity_after)

        return CanaryRunResult(
            project_name=project_name,
            selected_blocks=selected_blocks,
            payloads=payloads,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_version=prompt_module.SEMANTIC_CANARY_PROMPT_VERSION,
            response_schema=response_schema,
            schema_fingerprint=fingerprint,
            preflight=preflight,
            estimate=estimate,
            integrity_before=integrity_before,
            integrity_after=integrity_after,
            real_call_count=guard.call_count,
            success=False,
            response=response,
            cost_record=record,
            error=CanaryError(error_type=type(exc).__name__, message=str(exc)),
        )

    # §22-25 : comparaison locale (jamais envoyée au modèle, jamais appliquée)
    cases = report_module.build_case_reports(selected_blocks, results)

    # §37 : intégrité APRÈS — doit rester byte-identique
    integrity_after = snapshot_sources(project_name, sortie_dir=sortie_dir)
    ensure_unchanged(integrity_before, integrity_after)

    # §21 : artefact — publié uniquement après validation complète
    artifact_payload = _build_artifact_payload(
        project_name=project_name,
        selected_blocks=selected_blocks,
        cases=cases,
        response=response,
        record=record,
        preflight=preflight,
        estimate=estimate,
        fingerprint=fingerprint,
        integrity_before=integrity_before,
        integrity_after=integrity_after,
    )
    artifact_path = writer_module.write_artifact(
        writer_module.artifact_path(project_name, sortie_dir=sortie_dir),
        artifact_payload,
    )

    return CanaryRunResult(
        project_name=project_name,
        selected_blocks=selected_blocks,
        payloads=payloads,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_version=prompt_module.SEMANTIC_CANARY_PROMPT_VERSION,
        response_schema=response_schema,
        schema_fingerprint=fingerprint,
        preflight=preflight,
        estimate=estimate,
        integrity_before=integrity_before,
        integrity_after=integrity_after,
        real_call_count=guard.call_count,
        success=True,
        response=response,
        cost_record=record,
        cases=cases,
        artifact_path=artifact_path,
    )


def _build_artifact_payload(
    *,
    project_name: str,
    selected_blocks: list[SelectedBlock],
    cases: list[report_module.CaseReport],
    response: AIResponse,
    record: AICallRecord,
    preflight: PreflightReport,
    estimate: TokenEstimate,
    fingerprint: str,
    integrity_before: IntegritySnapshot,
    integrity_after: IntegritySnapshot,
) -> dict:
    """Contenu canonique de semantic_translation_canary.json (§21)."""
    distribution = report_module.classification_distribution(
        [case.result for case in cases]
    )
    by_group = report_module.distribution_by_group(cases)
    positive_control = report_module.positive_control_summary(cases)

    return {
        "schema_version": schema_module.RESPONSE_SCHEMA_VERSION,
        "prompt_version": prompt_module.SEMANTIC_CANARY_PROMPT_VERSION,
        "response_schema_fingerprint": fingerprint,
        "provider": response.provider,
        "model": response.model,
        "project": project_name,
        "source_hashes": integrity_before.to_dict(),
        "source_hashes_after": integrity_after.to_dict(),
        "selection": {
            "total_selected": len(selected_blocks),
            "blocks": [block.control_summary() for block in selected_blocks],
        },
        "results": [case.result.to_dict() for case in cases],
        "classification_distribution": distribution,
        "classification_distribution_by_group": by_group,
        "positive_control": positive_control,
        "usage": {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "usage_source": response.usage_source,
            "latency_ms": response.latency_ms,
            "finish_reason": response.finish_reason,
            "request_id": response.request_id,
        },
        "estimation_before_call": estimate.to_dict(),
        "cost": record.cost.to_dict(),
        "preflight": preflight.to_dict(),
    }
