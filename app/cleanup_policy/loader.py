"""
Chargement et validation locale des CINQ sources protégées (§5, §39) —
AUCUN appel réseau, AUCUNE modification.

N'importe PAS `app.semantic_batch.runner` ni `app.semantic_canary.runner` :
ces modules tirent la couche IA (`app.ai.*`, préflight, garde d'appel réel).
Cette phase ne fait que LIRE des artefacts déjà publiés.

Réutilise uniquement :
    app.language_blocks.writer / language_cleanup.writer   lecture des manifestes
    app.language_blocks.combined_source                    cohérence SHA croisée
    app.semantic_canary.writer / semantic_batch.writer     chemins canoniques
    app.source_analysis.transcript_input                   chemin transcript
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.cleanup_policy.errors import SourceIntegrityError
from app.language_blocks.combined_source import load_combined_source
from app.language_blocks.errors import LanguageBlocksError
from app.language_blocks.writer import manifest_path as blocks_manifest_path
from app.language_blocks.writer import read_manifest_payload as read_blocks_manifest
from app.language_cleanup.writer import manifest_path as cleanup_manifest_path
from app.language_cleanup.writer import read_manifest_payload as read_cleanup_manifest
from app.semantic_batch.writer import (
    classification_artifact_path as _classification_artifact_path,
)
from app.semantic_canary.writer import artifact_path as _canary_artifact_path
from app.source_analysis.transcript_input import transcript_data_file
from app.source_analysis.writer import transcripts_dir as _transcripts_dir


def _read_json(path: Path, *, label: str) -> dict:
    if not path.exists():
        raise SourceIntegrityError(f"{label} introuvable : {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceIntegrityError(f"{label} illisible : {exc}") from exc

    if not isinstance(payload, dict):
        raise SourceIntegrityError(f"{label} n'est pas un objet JSON : {path}")

    return payload


def load_and_validate_sources(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Charge et valide les cinq sources protégées (§5, §39) — STOP AVANT TOUT
    CALCUL si l'une est invalide.

    Retourne un dict avec :
        "language_blocks"                payload complet de language_blocks.json
        "blocks"                         language_blocks["blocks"], liste de dicts
        "language_blocks_stats"          language_blocks["stats"]
        "classification"                 payload complet de
                                          semantic_translation_classification.json
        "transcript_data"                payload complet de transcript_data.json
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
        _transcripts_dir(project_name, sortie_dir=sortie_dir)
    )
    if not transcript_path.exists():
        raise SourceIntegrityError(f"transcript_data.json introuvable : {transcript_path}")

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

    canary_path = _canary_artifact_path(project_name, sortie_dir=sortie_dir)
    if not canary_path.exists():
        raise SourceIntegrityError(
            f"semantic_translation_canary.json introuvable : {canary_path}. "
            "La Phase 3A.1.2A (canary) doit avoir été exécutée avec succès "
            "avant cette phase."
        )
    try:
        json.loads(canary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceIntegrityError(
            f"semantic_translation_canary.json illisible : {exc}"
        ) from exc

    classification_path = _classification_artifact_path(project_name, sortie_dir=sortie_dir)
    classification_payload = _read_json(
        classification_path, label="semantic_translation_classification.json"
    )

    transcript_payload = _read_json(transcript_path, label="transcript_data.json")

    return {
        "language_blocks": blocks_payload,
        "blocks": blocks,
        "language_blocks_stats": stats,
        "classification": classification_payload,
        "transcript_data": transcript_payload,
    }
