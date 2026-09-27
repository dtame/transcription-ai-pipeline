"""
segmented_transcription_service.py

Transcription segmentée des longs fichiers audio avec reprise après interruption.

Principe :
  1. Calculer la durée du fichier audio.
  2. Si durée > LONG_AUDIO_THRESHOLD_MINUTES : découper en segments courts.
  3. Transcrire chaque segment indépendamment avec Whisper.
  4. Sauvegarder project_state.json après chaque segment (reprise possible).
  5. Fusionner les transcripts en un fichier final.
  6. Marquer le fichier original comme transcribed.

Structure de sortie :
  sortie/<projet>/audio_segments/<stem>/part_001.mp3  ...
  sortie/<projet>/segment_transcripts/<stem>/part_001.txt   (transcript texte V1)
  sortie/<projet>/segment_transcripts/<stem>/part_001.json  (capture brute V2)
  sortie/<projet>/transcript_capture/<stem>.json            (capture consolidée V2)
  sortie/<projet>/transcripts/<stem>.txt   (fichier final fusionné)

Overlap :
  Chaque segment inclut AUDIO_SEGMENT_OVERLAP_SECONDS secondes du segment suivant.
  Transcript texte V1 : les phrases dont le timestamp local de fin est ≤ overlap
  sont ignorées pour le segment concerné (elles ont déjà été écrites par le
  segment précédent).
  Contrat V2 : la capture conserve les segments Whisper bruts et la règle
  d'ownership est appliquée dans app.transcript_builder, qui dispose du contexte
  des segments techniques voisins (voir resolve_owned_segments).
"""

from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path

from app.audio_utils import (
    FFMPEG_EXE,
    format_timestamp,
    get_audio_duration_seconds,
    print_progress,
)
from app.config import (
    AUDIO_SEGMENT_MINUTES,
    AUDIO_SEGMENT_OVERLAP_SECONDS,
    LONG_AUDIO_SEGMENTATION_ENABLED,
    LONG_AUDIO_THRESHOLD_MINUTES,
)
from app.file_utils import file_hash, write_text_atomic
from app.logger import log_event
from app.paths import SORTIE_DIR
from app.transcript_capture import (
    part_capture_path,
    read_part_capture,
    write_audio_capture,
    write_part_capture,
)
from app.transcript_models import (
    CAPTURE_MODE_SEGMENTED,
    AudioCapture,
    CapturedPart,
    CapturedSegment,
)
from app.project_state import (
    load_project_state,
    mark_audio_partial_error,
    mark_audio_processing_segments,
    mark_audio_segmented_transcribed,
    save_project_state,
    update_segment_in_state,
)


# ---------------------------------------------------------------------------
# API publique — point d'entrée du pipeline
# ---------------------------------------------------------------------------

def should_segment_audio(audio_path: Path) -> bool:
    """
    Retourne True si le fichier audio doit être découpé en segments.

    Conditions :
    - LONG_AUDIO_SEGMENTATION_ENABLED = True dans config.py
    - Durée du fichier > LONG_AUDIO_THRESHOLD_MINUTES
    """
    if not LONG_AUDIO_SEGMENTATION_ENABLED:
        return False
    try:
        duration = get_audio_duration_seconds(audio_path)
        return duration / 60 > LONG_AUDIO_THRESHOLD_MINUTES
    except Exception:
        return False


def transcribe_long_audio_with_segments(
    model,
    project_name: str,
    audio_path: Path,
    output_path: Path,
) -> Path:
    """
    Transcrit un fichier audio long par segmentation.

    - Découpe l'audio en segments de AUDIO_SEGMENT_MINUTES minutes.
    - Transcrit chaque segment, en sautant ceux déjà traités (reprise).
    - Sauvegarde project_state.json après chaque segment.
    - Fusionne les transcripts en output_path.
    - Retourne output_path.

    Lève RuntimeError si au moins un segment est en erreur, ou si un transcript
    de segment attendu manque au moment de la fusion.
    Dans ce cas, les segments déjà transcrits sont préservés dans project_state.json
    pour permettre la reprise lors du prochain lancement.
    """
    audio_hash = file_hash(audio_path)
    total_duration = get_audio_duration_seconds(audio_path)
    total_minutes = total_duration / 60

    print(f"\n{'=' * 70}")
    print(f"Projet   : {project_name}")
    print(f"Fichier  : {audio_path.name}")
    print(f"Mode     : transcription segmentée ({total_minutes:.1f} min)")
    print(f"{'=' * 70}")

    log_event({
        "event": "segmentation_started",
        "file": audio_path.name,
        "duration_minutes": round(total_minutes, 2),
    })

    state = load_project_state(project_name)

    # Construire la liste canonique des segments
    segments = _build_segment_list(project_name, audio_path, total_duration)
    total_segments = len(segments)
    print(f"Segments : {total_segments} × {AUDIO_SEGMENT_MINUTES} min  "
          f"(overlap {AUDIO_SEGMENT_OVERLAP_SECONDS}s)")

    # Restaurer les segments déjà transcrits depuis le state (si même hash)
    _restore_transcribed_segments(state, audio_path, audio_hash, segments)

    already_done = sum(1 for s in segments if s["status"] == "transcribed")
    if already_done:
        print(f"Reprise   : {already_done}/{total_segments} segments déjà transcrits — skippés")

    # Marquer le fichier comme en cours dans project_state.json
    mark_audio_processing_segments(state, audio_path, audio_hash, segments)
    save_project_state(project_name, state)

    # Créer les fichiers audio manquants
    print("Création des segments audio manquants...")
    _create_missing_audio_segments(audio_path, segments)

    # Transcrire les segments en attente / en erreur
    errors: list[tuple[str, str]] = []

    for i, segment in enumerate(segments):
        if segment["status"] == "transcribed":
            done = sum(1 for s in segments if s["status"] == "transcribed")
            print(f"  SKIP {segment['id']}  ({done}/{total_segments} transcrits)")
            continue

        seg_idx = i + 1
        log_event({
            "event": "segment_transcription_started",
            "file": audio_path.name,
            "segment": segment["id"],
            "index": seg_idx,
            "total": total_segments,
        })

        try:
            _transcribe_one_segment(
                model=model,
                segment=segment,
                total_duration_seconds=total_duration,
                segment_index=seg_idx,
                total_segments=total_segments,
                project_name=project_name,
            )

            segment["status"] = "transcribed"
            segment["updated_at"] = datetime.now().isoformat(timespec="seconds")
            segment["error"] = None

            log_event({
                "event": "segment_transcription_completed",
                "file": audio_path.name,
                "segment": segment["id"],
                "index": seg_idx,
            })

        except Exception as exc:
            segment["status"] = "error"
            segment["error"] = str(exc)
            segment["updated_at"] = datetime.now().isoformat(timespec="seconds")
            errors.append((segment["id"], str(exc)))

            log_event({
                "event": "segment_transcription_error",
                "file": audio_path.name,
                "segment": segment["id"],
                "error": str(exc),
            })

        # Sauvegarde immédiate après chaque segment (reprise possible)
        update_segment_in_state(state, audio_path, segment)
        save_project_state(project_name, state)

    # Gestion des erreurs partielles
    if errors:
        error_msg = "; ".join(f"{seg_id}: {err}" for seg_id, err in errors)
        mark_audio_partial_error(state, audio_path, audio_hash, error_msg, segments)
        save_project_state(project_name, state)
        raise RuntimeError(
            f"{len(errors)} segment(s) en erreur pour «{audio_path.name}» : {error_msg}"
        )

    # Fusion des transcripts de segments
    try:
        _merge_segment_transcripts(segments, output_path)
    except RuntimeError as exc:
        # Un transcript attendu manque : on ne produit pas de transcript final
        # prétendument complet. Les segments déjà transcrits sont conservés dans
        # project_state.json pour permettre la reprise au prochain lancement.
        mark_audio_partial_error(state, audio_path, audio_hash, str(exc), segments)
        save_project_state(project_name, state)
        raise

    # Consolider la capture structurée du fichier audio (contrat V2)
    _write_consolidated_capture(
        project_name=project_name,
        audio_path=audio_path,
        total_duration=total_duration,
        segments=segments,
    )

    # Marquer le fichier original comme transcribed
    mark_audio_segmented_transcribed(state, audio_path, audio_hash, output_path, segments)
    save_project_state(project_name, state)

    print(f"\nTranscription segmentée terminée → {output_path.name}")
    return output_path


# ---------------------------------------------------------------------------
# Calcul des frontières de segments
# ---------------------------------------------------------------------------

def _get_segment_boundaries(total_seconds: float) -> list[tuple[float, float]]:
    """
    Retourne une liste de (start, end) en secondes pour chaque segment.

    Chaque segment couvre AUDIO_SEGMENT_MINUTES minutes de contenu,
    plus AUDIO_SEGMENT_OVERLAP_SECONDS secondes de recouvrement
    (sauf si c'est la fin du fichier).
    """
    segment_duration = AUDIO_SEGMENT_MINUTES * 60
    overlap = AUDIO_SEGMENT_OVERLAP_SECONDS

    boundaries: list[tuple[float, float]] = []
    start = 0.0

    while start < total_seconds:
        end = min(start + segment_duration + overlap, total_seconds)
        boundaries.append((start, end))
        start += segment_duration

    # Phase 1 — segment résiduel dégénéré.
    # Une durée à peine supérieure à un multiple de la durée de segment produisait
    # un dernier segment entièrement contenu dans le précédent (901 s → segment
    # principal 0-901 puis segment résiduel 900-901) : un appel Whisper inutile
    # dont tout le contenu était de toute façon absorbé par l'overlap entrant.
    # La couverture audio est préservée puisque le segment précédent atteint déjà
    # la fin du fichier.
    if len(boundaries) > 1 and boundaries[-1][1] <= boundaries[-2][1]:
        boundaries.pop()

    return boundaries


def _build_segment_list(
    project_name: str,
    audio_path: Path,
    total_seconds: float,
) -> list[dict]:
    """
    Construit la liste des descripteurs de segments pour un fichier audio.

    Ne crée pas encore les fichiers audio — uniquement les métadonnées.
    """
    boundaries = _get_segment_boundaries(total_seconds)

    segments_audio_dir = (
        SORTIE_DIR / project_name / "audio_segments" / audio_path.stem
    )
    segments_transcript_dir = (
        SORTIE_DIR / project_name / "segment_transcripts" / audio_path.stem
    )

    segments_audio_dir.mkdir(parents=True, exist_ok=True)
    segments_transcript_dir.mkdir(parents=True, exist_ok=True)

    segments: list[dict] = []

    for i, (start, end) in enumerate(boundaries):
        part_id = f"part_{i + 1:03d}"
        audio_out = segments_audio_dir / f"{part_id}.mp3"
        transcript_out = segments_transcript_dir / f"{part_id}.txt"

        # Le premier segment n'a pas d'overlap à ignorer
        effective_start_local = float(AUDIO_SEGMENT_OVERLAP_SECONDS) if i > 0 else 0.0

        segments.append({
            "id": part_id,
            "audio_path": str(audio_out),
            "transcript_path": str(transcript_out),
            "start_seconds": start,
            "end_seconds": end,
            "effective_start_local": effective_start_local,
            "status": "pending",
            "updated_at": None,
            "error": None,
        })

    return segments


# ---------------------------------------------------------------------------
# Restauration depuis project_state.json
# ---------------------------------------------------------------------------

def _restore_transcribed_segments(
    state: dict,
    audio_path: Path,
    audio_hash: str,
    segments: list[dict],
) -> None:
    """
    Restaure le statut 'transcribed' des segments depuis project_state.json
    si le hash du fichier original n'a pas changé.

    Invalide silencieusement les segments si le hash a changé.
    """
    file_key = str(audio_path.resolve())
    stored_file = state.get("files", {}).get(file_key, {})
    stored_hash = stored_file.get("hash")
    stored_segments = stored_file.get("segments", {})

    if stored_hash != audio_hash:
        if stored_hash:
            print(
                f"Hash modifié ({stored_hash[:8]} → {audio_hash[:8]}) "
                "— reprise depuis le début."
            )
        return

    for seg in segments:
        stored = stored_segments.get(seg["id"], {})
        transcript_ok = (
            stored.get("transcript_path")
            and Path(stored["transcript_path"]).exists()
        )
        if stored.get("status") == "transcribed" and transcript_ok:
            seg["status"] = "transcribed"
            seg["transcript_path"] = stored["transcript_path"]
            seg["updated_at"] = stored.get("updated_at")


# ---------------------------------------------------------------------------
# Création des fichiers audio de segments
# ---------------------------------------------------------------------------

def _create_missing_audio_segments(
    audio_path: Path,
    segments: list[dict],
) -> None:
    """
    Crée les fichiers audio de segments manquants via ffmpeg.
    Réutilise les fichiers existants (nommage stable : part_001.mp3, …).
    """
    for segment in segments:
        audio_out = Path(segment["audio_path"])
        if audio_out.exists():
            continue

        log_event({
            "event": "segment_created",
            "segment": segment["id"],
            "start_seconds": segment["start_seconds"],
            "end_seconds": segment["end_seconds"],
        })

        _create_audio_segment(
            audio_path=audio_path,
            output_path=audio_out,
            start=segment["start_seconds"],
            end=segment["end_seconds"],
        )


def _create_audio_segment(
    audio_path: Path,
    output_path: Path,
    start: float,
    end: float,
) -> None:
    """
    Extrait une portion de l'audio source via ffmpeg (-ss / -t).

    Utilise libmp3lame q:a 2 pour un bon compromis qualité/taille.
    Le -ss avant -i est intentionnel : ffmpeg cherche rapidement sans tout décoder.
    """
    duration = end - start

    subprocess.run(
        [
            FFMPEG_EXE,
            "-y",
            "-ss", str(start),
            "-i", str(audio_path),
            "-t", str(duration),
            "-c:a", "libmp3lame",
            "-q:a", "2",
            str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ---------------------------------------------------------------------------
# Transcription d'un segment
# ---------------------------------------------------------------------------

def _transcribe_one_segment(
    model,
    segment: dict,
    total_duration_seconds: float,
    segment_index: int,
    total_segments: int,
    project_name: str,
) -> None:
    """
    Transcrit un segment audio, capture ses données structurées, puis écrit le
    transcript texte avec timestamps globaux.

    Timestamps :
    - Whisper retourne des timestamps locaux (depuis 0).
    - On ajoute start_seconds pour obtenir le timestamp global.

    Overlap (transcript texte V1) :
    - Les phrases dont le timestamp local de fin ≤ effective_start_local
      sont ignorées (elles appartiennent au segment précédent).

    Capture structurée (contrat V2) :
    - La capture conserve les segments Whisper BRUTS, sans filtrage d'overlap :
      la règle d'ownership est appliquée une seule fois, dans
      app.transcript_builder, là où le contexte des segments techniques voisins
      est disponible.
    - La capture est publiée avant le transcript texte : un transcript de segment
      présent implique toujours une capture exploitable, y compris après reprise.

    Langue (contrat V2) :
    - La langue réellement détectée est conservée. Plus de retranscription
      forcée en anglais pour les langues hors fr/en.
    """
    audio_path = Path(segment["audio_path"])
    transcript_path = Path(segment["transcript_path"])
    start_offset = segment["start_seconds"]
    effective_start_local = segment["effective_start_local"]

    global_start_str = format_timestamp(start_offset)
    global_end_str = format_timestamp(segment["end_seconds"])
    print(
        f"\n  Segment {segment_index}/{total_segments} : {segment['id']}"
        f"  [{global_start_str} → {global_end_str}]"
    )
    print(
        f"  Progression projet : "
        f"{round(100 * start_offset / total_duration_seconds)}%"
    )

    start_time = time.time()

    transcription_iter, info = model.transcribe(str(audio_path))

    detected_language = info.language

    captured: list[CapturedSegment] = []
    lines: list[str] = []

    for seg in transcription_iter:
        text = seg.text.strip()

        captured.append(
            CapturedSegment(start=float(seg.start), end=float(seg.end), text=text)
        )

        # Ignorer l'overlap entrant : phrases qui terminent avant effective_start_local
        if seg.end <= effective_start_local:
            continue

        global_seg_start = seg.start + start_offset
        global_seg_end = seg.end + start_offset

        ts_start = format_timestamp(global_seg_start)
        ts_end = format_timestamp(global_seg_end)

        lines.append(f"[{ts_start} -> {ts_end}] {text}\n")

        print_progress(
            current_seconds=global_seg_end,
            total_seconds=total_duration_seconds,
            start_time=start_time,
            prefix=f"  Segment {segment_index}/{total_segments}",
        )

    write_part_capture(
        transcript_path,
        CapturedPart(
            id=segment["id"],
            start_seconds=float(start_offset),
            end_seconds=float(segment["end_seconds"]),
            effective_start_local=float(effective_start_local),
            detected_language=detected_language,
            segments=captured,
        ),
    )

    write_text_atomic(transcript_path, "".join(lines))

    print()  # Saut de ligne après la barre de progression


# ---------------------------------------------------------------------------
# Capture structurée consolidée (contrat V2)
# ---------------------------------------------------------------------------

def _write_consolidated_capture(
    project_name: str,
    audio_path: Path,
    total_duration: float,
    segments: list[dict],
) -> Path | None:
    """
    Assemble les captures brutes des segments techniques en une capture unique
    pour le fichier audio source.

    Les segments techniques n'apparaissent jamais comme sources éditoriales : ce
    fichier audio donnera UN seul AUDIOxxx, quel que soit le nombre de découpes.

    Les captures de parties étant écrites par segment et conservées d'un
    lancement à l'autre, la capture consolidée est identique qu'elle provienne
    d'un run unique ou d'un run interrompu puis repris.

    Si une capture de partie manque (transcription antérieure à la Phase 1, ou
    nettoyage externe), la capture consolidée n'est PAS écrite : la transcription
    V1 reste valide et c'est la couche V2 qui échouera explicitement, sans jamais
    publier un contrat incomplet.
    """
    missing = [
        segment["id"] for segment in segments
        if not part_capture_path(Path(segment["transcript_path"])).exists()
    ]

    if missing:
        log_event({
            "event": "transcript_v2_capture_incomplete",
            "file": audio_path.name,
            "missing_segments": missing,
        })
        return None

    parts: list[CapturedPart] = []

    for segment in segments:
        part = read_part_capture(Path(segment["transcript_path"]))
        parts.append(part)

    capture = AudioCapture(
        filename=audio_path.name,
        duration_seconds=total_duration,
        mode=CAPTURE_MODE_SEGMENTED,
        parts=parts,
    )

    return write_audio_capture(
        SORTIE_DIR / project_name,
        audio_path.stem,
        capture,
    )


# ---------------------------------------------------------------------------
# Fusion des transcripts de segments
# ---------------------------------------------------------------------------

def _merge_segment_transcripts(
    segments: list[dict],
    output_path: Path,
) -> None:
    """
    Fusionne les transcripts individuels des segments en un fichier final.

    Chaque segment a déjà ses timestamps convertis en timestamps globaux.
    Aucun traitement supplémentaire n'est nécessaire — simple concaténation.

    Lève RuntimeError si un transcript de segment attendu est absent : une
    transcription finale ne doit jamais être produite avec un trou silencieux.
    La vérification a lieu avant toute écriture, afin de ne pas détruire un
    transcript final valide déjà présent.
    """
    missing = [
        segment for segment in segments
        if not Path(segment["transcript_path"]).exists()
    ]

    if missing:
        for segment in missing:
            log_event({
                "event": "segment_transcript_missing_at_merge",
                "segment": segment["id"],
                "path": segment["transcript_path"],
            })

        missing_ids = ", ".join(segment["id"] for segment in missing)
        log_event({
            "event": "segment_merge_aborted",
            "output": str(output_path),
            "missing_segments": [segment["id"] for segment in missing],
        })
        raise RuntimeError(
            f"Fusion impossible : {len(missing)}/{len(segments)} transcript(s) "
            f"de segment manquant(s) ({missing_ids}). "
            "Le transcript final n'a pas été produit ; relancez pour reprendre."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as out:
        for segment in segments:
            content = Path(segment["transcript_path"]).read_text(encoding="utf-8")
            out.write(content)

            if content and not content.endswith("\n"):
                out.write("\n")

    log_event({
        "event": "segment_merge_completed",
        "output": str(output_path),
        "segments_count": len(segments),
    })
