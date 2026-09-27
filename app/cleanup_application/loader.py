"""
Chargement des sources de vérité — lecture seule, zéro réseau.

Réutilise app.cleanup_policy.loader pour les cinq sources déjà validées
par la Phase 3A.2A, puis ajoute transcript.txt, language_cleanup.json
(contenu métier) et cleanup_policy_simulation.json.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.cleanup_application.errors import SourceIntegrityError
from app.cleanup_policy import loader as policy_loader
from app.cleanup_policy.writer import artifact_path as simulation_path
from app.cleanup_policy.writer import read_artifact as read_simulation
from app.language_cleanup.transcript_source import load_transcript_document
from app.language_cleanup.writer import manifest_path as cleanup_manifest_path
from app.language_cleanup.writer import read_manifest_payload as read_cleanup_manifest
from app.source_analysis.transcript_input import transcript_data_file
from app.source_analysis.writer import transcripts_dir as _transcripts_dir
from app.transcript_models import TranscriptSegment
from app.transcript_writer import transcript_text_path


def load_language_by_src(cleanup_payload: dict) -> dict[str, str]:
    """source_ref -> language (EN/FR/MIXED/UNKNOWN) depuis language_cleanup.json."""
    mapping: dict[str, str] = {}
    for entry in cleanup_payload.get("segments") or []:
        ref = str(entry.get("source_ref") or "")
        if not ref:
            continue
        mapping[ref] = str(entry.get("language") or "")
    return mapping


def load_block_extras(blocks: list[dict]) -> dict[str, dict]:
    """block_id -> extraits language_blocks (contextes EN, all_source_refs)."""
    extras: dict[str, dict] = {}
    for block in blocks:
        block_id = str(block["block_id"])
        before = block.get("english_before") if isinstance(block.get("english_before"), dict) else {}
        after = block.get("english_after") if isinstance(block.get("english_after"), dict) else {}
        extras[block_id] = {
            "all_source_refs": tuple(str(r) for r in (block.get("all_source_refs") or [])),
            "english_before_source_refs": tuple(str(r) for r in (before.get("source_refs") or [])),
            "english_after_source_refs": tuple(str(r) for r in (after.get("source_refs") or [])),
            "english_after_text": (
                str(after["text"]) if after.get("text") is not None else None
            ),
        }
    return extras


def occurrence_count(segments: list[TranscriptSegment]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for segment in segments:
        counts[segment.id] = counts.get(segment.id, 0) + 1
    return counts


def segments_by_id(segments: list[TranscriptSegment]) -> dict[str, TranscriptSegment]:
    """Première occurrence de chaque SRC (l'original est déjà unique)."""
    index: dict[str, TranscriptSegment] = {}
    for segment in segments:
        index.setdefault(segment.id, segment)
    return index


def original_index_by_src(segments: list[TranscriptSegment]) -> dict[str, int]:
    """Index 0-based dans le tableau original `segments`."""
    return {segment.id: index for index, segment in enumerate(segments)}


def load_and_validate_sources(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Charge toutes les sources de vérité. Lève SourceIntegrityError avant
    tout calcul si l'une est absente ou illisible.
    """
    try:
        policy_sources = policy_loader.load_and_validate_sources(
            project_name, sortie_dir=sortie_dir
        )
    except Exception as exc:
        raise SourceIntegrityError(str(exc)) from exc

    transcripts = _transcripts_dir(project_name, sortie_dir=sortie_dir)
    txt_path = transcript_text_path(transcripts)
    if not txt_path.exists():
        raise SourceIntegrityError(f"transcript.txt introuvable : {txt_path}")

    cleanup_path = cleanup_manifest_path(project_name, sortie_dir=sortie_dir)
    cleanup_payload = read_cleanup_manifest(cleanup_path)
    if cleanup_payload is None:
        raise SourceIntegrityError(
            f"language_cleanup.json introuvable ou illisible : {cleanup_path}"
        )

    sim_path = simulation_path(project_name, sortie_dir=sortie_dir)
    simulation_payload = read_simulation(sim_path)
    if simulation_payload is None:
        raise SourceIntegrityError(
            f"cleanup_policy_simulation.json introuvable ou illisible : {sim_path}"
        )

    transcript_path = transcript_data_file(transcripts)
    document = load_transcript_document(transcript_path)

    return {
        **policy_sources,
        "language_cleanup": cleanup_payload,
        "simulation": simulation_payload,
        "transcript_document": document,
        "transcript_txt_path": txt_path,
        "transcript_data_path": transcript_path,
        "language_by_src": load_language_by_src(cleanup_payload),
        "block_extras": load_block_extras(policy_sources["blocks"]),
    }
