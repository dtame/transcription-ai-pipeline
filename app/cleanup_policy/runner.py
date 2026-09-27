"""
Orchestration complète de la Phase 3A.2A (§1-§44) — AUCUN appel réseau,
AUCUNE écriture sur les cinq sources protégées.

Enchaînement, une seule fois par exécution :

    charge + valide les 5 sources (§5, §39)      loader.load_and_validate_sources
          |
    intégrité AVANT (§5, §44)                    integrity.snapshot_sources
          |
    index transcript (§20, §24)                  transcript_index.build_transcript_index
          |
    population fusionnée, 333 blocs (§6-7)       population.build_population
          |
    validation locale de la population (§7, §39) population.validate_population
          |
    risk flags + 3 décisions par bloc (§11, §8)  evaluation.evaluate_population
          |
    entrées blocks[] (§20-21)                    simulation.build_block_entries
          |
    statistiques (§23-38)                        aggregator.build_statistics
          |
    artefact final (§21)                         (assemblé ici)
          |
    validation stricte de l'artefact (§39)        validator.validate_artifact
          |
    intégrité APRÈS (§5, §44)                    integrity.snapshot_sources + ensure_unchanged
          |
    écriture atomique (§21)                       writer.write_artifact

Un échec à n'importe quelle étape lève une exception (SourceIntegrityError,
PopulationError, SimulationValidationError) : STOP, rien n'est écrit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.cleanup_policy import aggregator as aggregator_module
from app.cleanup_policy import integrity as integrity_module
from app.cleanup_policy import loader as loader_module
from app.cleanup_policy import population as population_module
from app.cleanup_policy import simulation as simulation_module
from app.cleanup_policy import writer as writer_module
from app.cleanup_policy.evaluation import BlockEvaluation, evaluate_population
from app.cleanup_policy.transcript_index import TranscriptIndex, build_transcript_index
from app.cleanup_policy.validator import validate_artifact

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class CleanupPolicySimulationResult:
    project_name: str
    artifact: dict
    artifact_path: Path
    evaluations: list[BlockEvaluation]
    integrity_before: integrity_module.IntegritySnapshot
    integrity_after: integrity_module.IntegritySnapshot


def build_artifact(
    *,
    project_name: str,
    evaluations: list[BlockEvaluation],
    transcript_index: TranscriptIndex,
    integrity_before: integrity_module.IntegritySnapshot,
) -> dict:
    """Contenu canonique de cleanup_policy_simulation.json (§21-22) — déterministe."""
    counts = population_module.count_population([e.record for e in evaluations])

    return {
        "schema_version": SCHEMA_VERSION,
        "project": project_name,
        "source_hashes": integrity_before.to_dict(),
        "population": {
            "total": counts.total,
            "semantic_batch": counts.semantic_batch,
            "phase_3a1_resolved": counts.phase_3a1_resolved,
            "no_english_context": counts.no_english_context,
        },
        "policies": simulation_module.build_policy_definitions(),
        "statistics": aggregator_module.build_statistics(evaluations, transcript_index),
        "blocks": simulation_module.build_block_entries(evaluations),
    }


def run_cleanup_policy_simulation(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    expected_total: int | None = None,
    expected_semantic_batch: int | None = None,
    expected_phase_3a1_resolved: int | None = None,
    expected_no_english_context: int | None = None,
) -> CleanupPolicySimulationResult:
    """
    Exécute la simulation complète (§1-§44). Les `expected_*` sont optionnels
    (aucun compte n'est figé en dur dans ce module — §7 s'applique
    précisément à pastoral_retreat_v2_validation, mais le code reste
    générique pour un projet de test plus petit) : l'appelant (cli.py ou un
    test) les fournit pour un contrôle strict sur un projet donné.
    """
    # §5, §39 : cinq sources protégées
    sources = loader_module.load_and_validate_sources(project_name, sortie_dir=sortie_dir)
    blocks = sources["blocks"]

    # §5, §44 : intégrité AVANT tout calcul
    integrity_before = integrity_module.snapshot_sources(project_name, sortie_dir=sortie_dir)

    # §20, §24 : index des segments (mots/durée), lecture seule
    transcript_index = build_transcript_index(sources["transcript_data"])

    # §6-7 : population fusionnée, une seule fois, jamais mélangée silencieusement
    records = population_module.build_population(blocks, sources["classification"])
    population_module.validate_population(
        records,
        expected_total=expected_total,
        expected_semantic_batch=expected_semantic_batch,
        expected_phase_3a1_resolved=expected_phase_3a1_resolved,
        expected_no_english_context=expected_no_english_context,
    )

    # §8, §11 : risk flags + 3 décisions simulées par bloc — calculé UNE fois
    evaluations = evaluate_population(records)

    # §21 : artefact complet
    artifact = build_artifact(
        project_name=project_name,
        evaluations=evaluations,
        transcript_index=transcript_index,
        integrity_before=integrity_before,
    )

    # §39 : validation stricte, indépendante, AVANT écriture
    valid_block_ids = {str(block["block_id"]) for block in blocks}
    valid_src_ids = set(transcript_index.segments_by_id)

    validate_artifact(
        artifact,
        expected_total=expected_total,
        expected_semantic_batch=expected_semantic_batch,
        expected_phase_3a1_resolved=expected_phase_3a1_resolved,
        expected_no_english_context=expected_no_english_context,
        valid_block_ids=valid_block_ids,
        valid_src_ids=valid_src_ids,
        expected_source_hashes=integrity_before.to_dict(),
    )

    # §5, §44 : intégrité APRÈS — les 5 artefacts doivent être restés
    # byte-identiques (cette phase ne les a jamais ouverts en écriture).
    integrity_after = integrity_module.snapshot_sources(project_name, sortie_dir=sortie_dir)
    integrity_module.ensure_unchanged(integrity_before, integrity_after)

    # §21 : écriture atomique, uniquement après validation complète
    artifact_path = writer_module.write_artifact(
        writer_module.artifact_path(project_name, sortie_dir=sortie_dir), artifact
    )

    return CleanupPolicySimulationResult(
        project_name=project_name,
        artifact=artifact,
        artifact_path=artifact_path,
        evaluations=evaluations,
        integrity_before=integrity_before,
        integrity_after=integrity_after,
    )
