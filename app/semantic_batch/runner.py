"""
Orchestration de la Phase 3A.1.2B — classification par lots (§7 à §39).

Réutilise directement, SANS LES DUPLIQUER (§10) :

    app.semantic_canary.prompt      system prompt, rendu de bloc, prompt utilisateur
    app.semantic_canary.schema      schéma structuré, empreinte
    app.semantic_canary.payload     payload sanitisé, garde-fou anti-fuite (§15)
    app.semantic_canary.validator   contrat strict d'une réponse (§19, §23)
    app.semantic_canary.preflight   préflight Anthropic (§25, §29)
    app.semantic_canary.guard       RealCallGuard, un seul appel réel à la fois
    app.semantic_canary.models      SelectedBlock, CanaryClassification, vocabulaire fermé

Ce module ajoute UNIQUEMENT ce qui est propre à un traitement par lots :
population complète (app.semantic_batch.selection), planification
(app.semantic_batch.planner), signature/cache (app.semantic_batch.signature
/ cache), intégrité à 4 artefacts (app.semantic_batch.integrity),
checkpoint/reprise (app.semantic_batch.writer), agrégation finale
(app.semantic_batch.aggregator).

Enchaînement (§7 à §39), une seule fois par exécution :

    validate sources, 4 artefacts (§8-9)     load_and_validate_sources
          |
    intégrité AVANT (§9)                     integrity.snapshot_sources
          |
    population NEEDED complète (§2, §14)     selection.select_needed_blocks
          |
    plan de lots complet, en mémoire (§17)   planner.build_batch_plan
          |
    prompt/schéma versionnés (§11-12, §17)   prompt_module / schema_module (canary)
          |
    préflight, UNE fois (§25, §29)           preflight.run_preflight (canary)
          |
    pour chaque lot, séquentiellement (§38) : PREPARE -> cache ou appel réel
    (max_attempts=1, §21) -> validation stricte (§23) -> écriture atomique (§18)
          |
    intégrité APRÈS (§37, §41)               integrity.ensure_unchanged
          |
    artefact final (§26, §39)                aggregator.build_classification_artifact

Un échec AVANT le premier appel (sources invalides, population invalide,
plan invalide, préflight invalide) lève une exception : aucune
observabilité réseau à préserver, STOP AVANT RÉSEAU. Un échec PENDANT
l'exécution des lots (cache incompatible, appel réseau, validation d'une
réponse) ne lève JAMAIS : il est capturé dans `BatchRunResult.error`, avec
tout ce qui a déjà réussi préservé sur disque (§21, §34) — pour qu'une
prochaine exécution reprenne exactement où celle-ci s'est arrêtée (§18).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.ai.contracts import AIRequest
from app.ai.cost import CostTracker
from app.ai.errors import AIError
from app.ai.registry import get_ai_engine
from app.ai.retry import RetryPolicy
from app.semantic_batch import aggregator as aggregator_module
from app.semantic_batch import cache as cache_module
from app.semantic_batch import integrity as integrity_module
from app.semantic_batch import planner as planner_module
from app.semantic_batch import selection as selection_module
from app.semantic_batch import writer as writer_module
from app.semantic_batch.errors import CacheSignatureMismatchError, SourceIntegrityError
from app.semantic_batch.models import MAX_BLOCKS_PER_BATCH, BatchPlanItem
from app.semantic_batch.signature import compute_batch_signature, payload_content_hash
from app.semantic_canary import payload as payload_module
from app.semantic_canary import prompt as prompt_module
from app.semantic_canary import schema as schema_module
from app.semantic_canary.errors import CanaryResponseValidationError
from app.semantic_canary.guard import RealCallGuard
from app.semantic_canary.models import CanaryClassification, SelectedBlock
from app.semantic_canary.preflight import (
    EXPECTED_MODEL,
    EXPECTED_PROVIDER,
    PreflightReport,
    run_preflight,
)
from app.semantic_canary.runner import load_and_validate_sources as _load_canary_sources
from app.semantic_canary.validator import validate_canary_response

STAGE = "semantic_translation_batch_classification"


@dataclass(frozen=True)
class BatchOutcome:
    """Issue de traitement d'UN lot — cache hit ou appel réel (§18, §23)."""

    batch_id: str
    block_ids: list[str]
    source: str  # "CACHE_HIT" | "REAL_CALL"
    results: list[CanaryClassification]
    usage: dict
    cost: dict
    latency_ms: int
    finish_reason: str | None
    request_id: str | None

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "block_ids": list(self.block_ids),
            "block_count": len(self.block_ids),
            "source": self.source,
            "usage": self.usage,
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
            "request_id": self.request_id,
        }


@dataclass
class BatchRunResult:
    """Issue complète d'une exécution du runner de lots — succès ou STOP (§34)."""

    project_name: str
    plan: list[BatchPlanItem]
    preflight: PreflightReport | None
    outcomes: list[BatchOutcome]
    success: bool
    integrity_before: integrity_module.IntegritySnapshot
    integrity_after: integrity_module.IntegritySnapshot | None = None
    artifact_path: Path | None = None
    error: dict | None = None
    stopped_at_batch: str | None = None

    @property
    def real_call_count(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.source == "REAL_CALL")

    @property
    def cache_hit_count(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.source == "CACHE_HIT")


# ---------------------------------------------------------------------------
# §8-9 : chargement et validation des QUATRE sources protégées
# ---------------------------------------------------------------------------

def load_and_validate_sources(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Charge et valide les sources (§8-9) — STOP AVANT RÉSEAU si invalide.

    Réutilise app.semantic_canary.runner.load_and_validate_sources pour les
    trois premières (cohérence interne transcript/cleanup/blocks, déjà
    couverte là-bas), et vérifie en plus la présence et la lisibilité du
    quatrième artefact protégé : semantic_translation_canary.json (§9,
    §27 — le canary doit avoir tourné avec succès avant cette phase).
    """
    sources = _load_canary_sources(project_name, sortie_dir=sortie_dir)

    canary_path = integrity_module.source_paths(project_name, sortie_dir=sortie_dir)[
        integrity_module.SEMANTIC_CANARY_KEY
    ]

    if not canary_path.exists():
        raise SourceIntegrityError(
            f"semantic_translation_canary.json introuvable : {canary_path}. "
            "La Phase 3A.1.2A (canary) doit avoir été exécutée avec succès "
            "avant cette phase (§9, §10)."
        )

    try:
        json.loads(canary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceIntegrityError(
            f"semantic_translation_canary.json illisible : {exc}"
        ) from exc

    return sources


# ---------------------------------------------------------------------------
# Exécution complète (§7-§39)
# ---------------------------------------------------------------------------

def run_semantic_batch_classification(
    project_name: str,
    *,
    engine=None,
    sortie_dir: Path | None = None,
    expected_provider: str = EXPECTED_PROVIDER,
    expected_model: str = EXPECTED_MODEL,
    retry_policy: RetryPolicy | None = None,
    max_batch_size: int = MAX_BLOCKS_PER_BATCH,
) -> BatchRunResult:
    """
    Exécute la classification par lots complète.

    `engine=None` construit le moteur réel (anthropic / claude-sonnet-5,
    max_attempts=1 — §21) via le registre Phase 2. Les tests injectent un
    FakeAIEngine et surchargent `expected_provider`/`expected_model` pour
    exercer le même préflight sans réseau. `max_batch_size` vaut 20 en
    production (§13-14) ; un test peut le réduire pour exercer la boucle
    multi-lots (cache/reprise, séquencement) sans construire une population
    de centaines de blocs.
    """
    # §8-9 : les quatre sources protégées
    sources = load_and_validate_sources(project_name, sortie_dir=sortie_dir)
    blocks = sources["blocks"]

    # §9 : intégrité AVANT traitement (4 artefacts)
    integrity_before = integrity_module.snapshot_sources(project_name, sortie_dir=sortie_dir)
    language_blocks_sha256 = integrity_before.hashes[integrity_module.LANGUAGE_BLOCKS_KEY]

    # §2, §14 : population complète NEEDED, jamais un échantillon
    selected_blocks = selection_module.select_needed_blocks(blocks)
    expected_needed_count = int(
        (sources["stats"].get("semantic_review_distribution") or {}).get("NEEDED", 0)
    )
    selection_module.validate_needed_population(
        selected_blocks, expected_count=expected_needed_count
    )

    # §13-17 : plan de lots complet, en mémoire, validé AVANT réseau
    plan = planner_module.build_batch_plan(selected_blocks, max_batch_size=max_batch_size)
    planner_module.validate_batch_plan(plan, selected_blocks, max_batch_size=max_batch_size)

    # §11-12, §17-18 : prompt/schéma — identiques au canary (même version)
    system_prompt = prompt_module.build_system_prompt()
    prompt_version = prompt_module.SEMANTIC_CANARY_PROMPT_VERSION
    response_schema = schema_module.build_response_schema()
    response_schema_fingerprint = schema_module.schema_fingerprint(response_schema)

    # §12 : moteur — anthropic/claude-sonnet-5, un seul essai par lot (§21)
    if engine is None:
        engine = get_ai_engine(
            "anthropic",
            model="claude-sonnet-5",
            retry_policy=retry_policy or RetryPolicy(max_attempts=1, base_delay_seconds=0.0),
        )

    model = engine.resolve_model()
    provider = engine.provider_name

    # §25, §29 : préflight — UNE fois, AVANT le premier appel. STOP AVANT
    # RÉSEAU s'il échoue (lève PreflightError, propagée telle quelle).
    preflight = run_preflight(
        engine,
        model,
        response_schema,
        expected_provider=expected_provider,
        expected_model=expected_model,
    )

    tracker = CostTracker()
    outcomes: list[BatchOutcome] = []

    def _stopped(error_type: str, message: str, batch_id: str, extra: dict | None = None) -> BatchRunResult:
        error = {"error_type": error_type, "message": message}
        if extra:
            error.update(extra)
        return BatchRunResult(
            project_name=project_name,
            plan=plan,
            preflight=preflight,
            outcomes=outcomes,
            success=False,
            integrity_before=integrity_before,
            error=error,
            stopped_at_batch=batch_id,
        )

    # §37, §38 : séquentiel, jamais parallèle — un lot à la fois.
    for item in plan:
        payloads = payload_module.build_canary_payloads(list(item.blocks))
        for one_payload in payloads:
            payload_module.assert_no_forbidden_leak(one_payload)

        this_batch_path = writer_module.batch_path(
            project_name, item.batch_id, sortie_dir=sortie_dir
        )
        cached_payload = writer_module.read_batch_payload(this_batch_path)

        # §18-19 : cache/reprise — STOP si un fichier existant est incompatible.
        try:
            cached_results = cache_module.check_cached_batch(
                cached_payload,
                batch_id=item.batch_id,
                block_ids=item.block_ids,
                payloads=payloads,
                language_blocks_sha256=language_blocks_sha256,
                prompt_version=prompt_version,
                response_schema_sha256=response_schema_fingerprint,
                provider=provider,
                model=model,
            )
        except CacheSignatureMismatchError as exc:
            return _stopped(type(exc).__name__, str(exc), item.batch_id)

        if cached_results is not None:
            usage = cached_payload.get("usage") or {}
            outcomes.append(
                BatchOutcome(
                    batch_id=item.batch_id,
                    block_ids=item.block_ids,
                    source="CACHE_HIT",
                    results=cached_results,
                    usage=usage,
                    cost=cached_payload.get("cost") or {},
                    latency_ms=int(usage.get("latency_ms") or 0),
                    finish_reason=usage.get("finish_reason"),
                    request_id=usage.get("request_id"),
                )
            )
            continue

        # §21 : max_attempts = 1 pour cette phase, aucun rejeu payant.
        user_prompt = prompt_module.build_user_prompt(payloads)
        request = AIRequest(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=model,
            response_schema=response_schema,
            metadata={
                "stage": STAGE,
                "project": project_name,
                "batch_id": item.batch_id,
            },
        )

        guard = RealCallGuard(max_calls=1)

        try:
            response = guard.guarded_generate(engine, request)
        except AIError as exc:
            record = tracker.record_failure(
                provider=provider,
                model=model,
                stage=STAGE,
                error=exc,
                response=getattr(exc, "response", None),
            )
            return _stopped(
                type(exc).__name__,
                str(exc),
                item.batch_id,
                extra={"usage_preserved": record.to_dict()},
            )

        record = tracker.record_response(response, stage=STAGE)

        # §19, §23 : validation locale stricte — jamais un second appel.
        try:
            results = validate_canary_response(response.parsed, item.block_ids)
        except CanaryResponseValidationError as exc:
            return _stopped(type(exc).__name__, str(exc), item.batch_id)

        payload_hash = payload_content_hash(payloads)
        signature = compute_batch_signature(
            language_blocks_sha256=language_blocks_sha256,
            prompt_version=prompt_version,
            response_schema_sha256=response_schema_fingerprint,
            provider=provider,
            model=model,
            block_ids=item.block_ids,
            payload_hash=payload_hash,
        )

        usage_block = {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "usage_source": response.usage_source,
            "latency_ms": response.latency_ms,
            "finish_reason": response.finish_reason,
            "request_id": response.request_id,
        }

        batch_checkpoint = {
            "batch_id": item.batch_id,
            "prompt_version": prompt_version,
            "response_schema_fingerprint": response_schema_fingerprint,
            "provider": provider,
            "model": model,
            "source_hashes": integrity_before.to_dict(),
            "block_ids": item.block_ids,
            "signature": signature,
            "payload_content_hash": payload_hash,
            "results": [result.to_dict() for result in results],
            "usage": usage_block,
            "cost": record.cost.to_dict(),
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
        }

        # §18 : écriture atomique, uniquement APRÈS validation complète.
        writer_module.write_batch_atomic(this_batch_path, batch_checkpoint)

        outcomes.append(
            BatchOutcome(
                batch_id=item.batch_id,
                block_ids=item.block_ids,
                source="REAL_CALL",
                results=results,
                usage=usage_block,
                cost=batch_checkpoint["cost"],
                latency_ms=response.latency_ms,
                finish_reason=response.finish_reason,
                request_id=response.request_id,
            )
        )

    # §37, §41 : intégrité APRÈS — les 4 artefacts doivent rester identiques.
    integrity_after = integrity_module.snapshot_sources(project_name, sortie_dir=sortie_dir)
    integrity_module.ensure_unchanged(integrity_before, integrity_after)

    # §26, §39 : artefact final — uniquement une fois TOUTES les
    # classifications valides (chaque lot du plan a produit un outcome).
    artifact_payload = aggregator_module.build_classification_artifact(
        project_name=project_name,
        blocks=blocks,
        selected_blocks=selected_blocks,
        outcomes=outcomes,
        prompt_version=prompt_version,
        provider=provider,
        model=model,
        schema_fingerprint=response_schema_fingerprint,
        integrity_before=integrity_before,
        integrity_after=integrity_after,
    )

    artifact_path = writer_module.write_classification_artifact(
        writer_module.classification_artifact_path(project_name, sortie_dir=sortie_dir),
        artifact_payload,
    )

    return BatchRunResult(
        project_name=project_name,
        plan=plan,
        preflight=preflight,
        outcomes=outcomes,
        success=True,
        integrity_before=integrity_before,
        integrity_after=integrity_after,
        artifact_path=artifact_path,
    )
