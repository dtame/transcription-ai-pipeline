"""
Fixtures de la Phase 3A.2A (simulation des politiques de nettoyage).

Deux niveaux, comme pour semantic_batch :

    _record(...)              un BlockRecord synthétique isolé, pour les
                               tests unitaires de risk.py / policies.py /
                               aggregator.py (aucun disque, aucun fichier).

    build_full_fixture_project(sortie_dir)
                               réutilise le VRAI petit projet de
                               app.tests.semantic_canary_fixtures (transcript
                               V2 -> vrai auditeur -> vrai analyseur), ajoute
                               un stub canary (comme semantic_batch_fixtures)
                               et un semantic_translation_classification.json
                               écrit à la main (jamais un vrai run réseau) —
                               pour les tests d'intégration bout en bout de
                               app.cleanup_policy.runner.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.cleanup_policy.constants import CLASSIFICATION_TRANSLATION_BEFORE
from app.cleanup_policy.population import BlockRecord
from app.language_blocks.writer import manifest_path as blocks_manifest_path
from app.language_blocks.writer import read_manifest_payload as read_blocks_manifest
from app.semantic_batch.writer import classification_artifact_path
from app.semantic_canary.writer import artifact_path as canary_artifact_path
from app.semantic_canary.writer import write_artifact as write_canary_artifact
from app.tests.semantic_canary_fixtures import PROJECT, build_fixture_project

__all__ = [
    "PROJECT",
    "make_record",
    "write_stub_canary_artifact",
    "build_full_fixture_project",
    "write_classification_artifact_for_fixture",
]


# ---------------------------------------------------------------------------
# BlockRecord synthétique — tests unitaires purs
# ---------------------------------------------------------------------------

def make_record(
    block_id: str = "FRB0001",
    *,
    audio_id: str = "AUDIO001",
    start_seconds: float = 0.0,
    end_seconds: float = 5.0,
    fr_source_refs: tuple[str, ...] = ("SRC000001",),
    bridge_source_refs: tuple[str, ...] = (),
    word_count: int = 10,
    segment_count: int | None = None,
    fr_segment_count: int | None = None,
    structure: str = "EN_FR_EN",
    phase_3a1_status: str = "ALL_REVIEW",
    text: str = "Ceci est un bloc francais de test.",
    semantic_origin: str = "SEMANTIC_BATCH",
    classification: str | None = "TRANSLATION_BEFORE",
    matched_direction: str | None = "BEFORE",
    confidence: float | None = 0.99,
    confidence_range: str | None = None,
    reason: str | None = "Correspondance directe et complete.",
    requires_human_review_flag: bool = False,
    is_high_risk_existing: bool = False,
    english_before_text: str | None = "English before text.",
    english_after_text: str | None = "English after text.",
) -> BlockRecord:
    """Un BlockRecord entièrement paramétrable, valeurs par défaut « propres »."""
    if segment_count is None:
        segment_count = len(fr_source_refs) + len(bridge_source_refs)
    if fr_segment_count is None:
        fr_segment_count = len(fr_source_refs)

    return BlockRecord(
        block_id=block_id,
        audio_id=audio_id,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        fr_source_refs=tuple(fr_source_refs),
        bridge_source_refs=tuple(bridge_source_refs),
        word_count=word_count,
        segment_count=segment_count,
        fr_segment_count=fr_segment_count,
        structure=structure,
        phase_3a1_status=phase_3a1_status,
        text=text,
        semantic_origin=semantic_origin,
        classification=classification,
        matched_direction=matched_direction,
        confidence=confidence,
        confidence_range=confidence_range,
        reason=reason,
        requires_human_review_flag=requires_human_review_flag,
        is_high_risk_existing=is_high_risk_existing,
        english_before_text=english_before_text,
        english_after_text=english_after_text,
    )


# ---------------------------------------------------------------------------
# Projet fixture complet sur disque — tests d'intégration du runner
# ---------------------------------------------------------------------------

def write_stub_canary_artifact(sortie_dir: Path) -> Path:
    """Identique à app.tests.semantic_batch_fixtures : présence/hash seuls comptent."""
    payload = {
        "schema_version": "1.0",
        "prompt_version": "1.0",
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "project": PROJECT,
        "results": [],
        "note": "Stub de test — pas un vrai run du canary Phase 3A.1.2A.",
    }
    path = canary_artifact_path(PROJECT, sortie_dir=sortie_dir)
    return write_canary_artifact(path, payload)


def write_classification_artifact_for_fixture(
    sortie_dir: Path,
    *,
    blocks: list[dict],
    overrides: dict[str, dict] | None = None,
) -> Path:
    """
    Écrit semantic_translation_classification.json à la main (JAMAIS un
    appel réseau réel ni un FakeAIEngine ici — juste le contrat JSON attendu
    par app.cleanup_policy.loader), pour les blocs `NEEDED` du fixture.

    `overrides[block_id]` permet de personnaliser classification/confidence/
    reason/matched_direction pour un bloc précis ; les autres reçoivent une
    classification neutre par défaut (UNCERTAIN, confidence 0.5).
    """
    overrides = overrides or {}
    needed = [b for b in blocks if b.get("semantic_review_status") == "NEEDED"]

    results = []
    high_risk_ids = []

    for block in needed:
        block_id = str(block["block_id"])
        override = overrides.get(block_id, {})

        classification = override.get("classification", "UNCERTAIN")
        matched_direction = override.get(
            "matched_direction",
            "BEFORE" if classification == CLASSIFICATION_TRANSLATION_BEFORE else "NONE",
        )
        confidence = override.get("confidence", 0.5)
        reason = override.get("reason", "Justification neutre de test.")

        word_count = int(block.get("word_count", 0))
        requires_human_review = word_count > 60 and classification in (
            "TRANSLATION_BEFORE",
            "TRANSLATION_AFTER",
        )

        results.append(
            {
                "block_id": block_id,
                "classification": classification,
                "matched_direction": matched_direction,
                "confidence": confidence,
                "reason": reason,
                "audio_id": block.get("audio_id"),
                "structure": block.get("structure"),
                "phase_3a1_status": block.get("phase_3a1_status"),
                "word_count": word_count,
                "fr_segment_count": block.get("fr_segment_count"),
                "confidence_range": None,
                "requires_human_review": requires_human_review,
                "risk_reasons": [],
                "is_high_risk_for_deletion_review": bool(override.get("high_risk", False)),
            }
        )

        if override.get("high_risk"):
            high_risk_ids.append(block_id)

    payload = {
        "schema_version": "1.0",
        "prompt_version": "1.0",
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "project": PROJECT,
        "results": results,
        "previously_resolved_blocks": [
            {"block_id": str(b["block_id"]), "existing_status": "ALREADY_RESOLVED"}
            for b in blocks
            if b.get("semantic_review_status") == "ALREADY_RESOLVED"
        ],
        "no_english_context_blocks": [
            {"block_id": str(b["block_id"]), "status": "NO_ENGLISH_CONTEXT"}
            for b in blocks
            if b.get("semantic_review_status") == "NO_ENGLISH_CONTEXT"
        ],
        "high_risk_for_deletion_review": [
            {"block_id": bid, "classification": "TRANSLATION_BEFORE", "confidence": 0.5, "risk_reasons": ["test"]}
            for bid in high_risk_ids
        ],
        "long_blocks": [],
    }

    path = classification_artifact_path(PROJECT, sortie_dir=sortie_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def build_full_fixture_project(sortie_dir: Path, *, overrides: dict[str, dict] | None = None):
    """
    Construit le projet fixture complet : transcript_data.json ->
    language_cleanup.json -> language_blocks.json (vrai pipeline, réutilisé
    tel quel de semantic_canary_fixtures) + stub canary + classification
    écrite à la main pour les blocs NEEDED du fixture (16 dans ce projet).
    """
    result = build_fixture_project(sortie_dir)

    manifest_payload = read_blocks_manifest(
        blocks_manifest_path(PROJECT, sortie_dir=sortie_dir)
    )
    blocks = list(manifest_payload["blocks"])

    write_stub_canary_artifact(sortie_dir)
    write_classification_artifact_for_fixture(sortie_dir, blocks=blocks, overrides=overrides)
    return result
