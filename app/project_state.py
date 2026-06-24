from pathlib import Path
from datetime import datetime
from app.paths import SORTIE_DIR

import json

STATE_FILENAME = "project_state.json"


def get_project_state_path(project_name):
    if hasattr(project_name, "name"):
        project_name = project_name.name

    return SORTIE_DIR / project_name / STATE_FILENAME

def load_project_state(project_name) -> dict:
    state_path = get_project_state_path(project_name)

    if not state_path.exists():
        state = {}
    else:
        state = json.loads(state_path.read_text(encoding="utf-8"))

    ensure_state_structure(state)
    return state

def ensure_state_structure(state: dict) -> None:
    if "files" not in state:
        state["files"] = {}

    if "chunks" not in state:
        state["chunks"] = {}

    if "corrections" not in state:
        state["corrections"] = {}

    if "exports" not in state:
        state["exports"] = {}

    if "publication" not in state:
        state["publication"] = {}

    if "harmonization" not in state:
        state["harmonization"] = {}

    if "cover" not in state:
        state["cover"] = {}

    if "cover_image" not in state:
        state["cover_image"] = {}

    if "metadata" not in state:
        state["metadata"] = {}

    if "editorial" not in state:
        state["editorial"] = {}

def save_project_state(project_name: str, state: dict) -> None:
    state_path = get_project_state_path(project_name)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def is_audio_already_transcribed(
    state: dict,
    audio_path: Path,
    audio_hash: str,
    transcript_path: Path
) -> bool:
    key = str(audio_path.resolve())
    file_state = state.get("files", {}).get(key)

    if not file_state:
        return False

    return (
        file_state.get("hash") == audio_hash
        and file_state.get("status") == "transcribed"
        and transcript_path.exists()
    )


def mark_audio_processing(state: dict, audio_path: Path, audio_hash: str) -> None:
    key = str(audio_path.resolve())

    state["files"][key] = {
        "path": str(audio_path),
        "hash": audio_hash,
        "status": "processing",
        "transcript_path": None,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "error": None
    }


def mark_audio_transcribed(
    state: dict,
    audio_path: Path,
    audio_hash: str,
    transcript_path: Path
) -> None:
    key = str(audio_path.resolve())

    state["files"][key] = {
        "path": str(audio_path),
        "hash": audio_hash,
        "status": "transcribed",
        "transcript_path": str(transcript_path),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "error": None
    }


def mark_audio_failed(
    state: dict,
    audio_path: Path,
    audio_hash: str,
    error: Exception
) -> None:
    key = str(audio_path.resolve())

    state["files"][key] = {
        "path": str(audio_path),
        "hash": audio_hash,
        "status": "failed",
        "transcript_path": None,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "error": str(error)
    }


# ---------------------------------------------------------------------------
# Gestion des segments (transcription longue durée avec reprise)
# ---------------------------------------------------------------------------

def mark_audio_processing_segments(
    state: dict,
    audio_path: Path,
    audio_hash: str,
    segments: list[dict],
) -> None:
    """
    Marque un fichier audio comme en cours de transcription segmentée.

    Initialise ou met à jour la clé 'segments' dans project_state.json.
    Chaque segment est un dict avec les clés :
      id, audio_path, transcript_path, start_seconds, end_seconds,
      effective_start_local, status, updated_at, error.
    """
    key = str(audio_path.resolve())
    existing = state.get("files", {}).get(key, {})

    segments_dict = {
        s["id"]: {
            "status": s["status"],
            "audio_path": s["audio_path"],
            "transcript_path": s["transcript_path"],
            "start_seconds": s["start_seconds"],
            "end_seconds": s["end_seconds"],
            "effective_start_local": s["effective_start_local"],
            "updated_at": s["updated_at"],
            "error": s["error"],
        }
        for s in segments
    }

    state.setdefault("files", {})[key] = {
        "path": str(audio_path),
        "hash": audio_hash,
        "status": "processing_segments",
        "transcript_path": None,
        "started_at": existing.get("started_at", datetime.now().isoformat(timespec="seconds")),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "error": None,
        "segments": segments_dict,
    }


def update_segment_in_state(
    state: dict,
    audio_path: Path,
    segment: dict,
) -> None:
    """Met à jour l'entrée d'un segment individuel dans project_state.json."""
    key = str(audio_path.resolve())
    file_entry = state.get("files", {}).get(key, {})
    segments_dict = file_entry.setdefault("segments", {})

    segments_dict[segment["id"]] = {
        "status": segment["status"],
        "audio_path": segment["audio_path"],
        "transcript_path": segment["transcript_path"],
        "start_seconds": segment["start_seconds"],
        "end_seconds": segment["end_seconds"],
        "effective_start_local": segment["effective_start_local"],
        "updated_at": segment["updated_at"],
        "error": segment["error"],
    }

    file_entry["updated_at"] = datetime.now().isoformat(timespec="seconds")


def mark_audio_segmented_transcribed(
    state: dict,
    audio_path: Path,
    audio_hash: str,
    transcript_path: Path,
    segments: list[dict],
) -> None:
    """
    Marque un fichier segmenté comme entièrement transcrit.
    Conserve les données de segments pour l'audit.
    """
    key = str(audio_path.resolve())
    existing = state.get("files", {}).get(key, {})

    segments_dict = {
        s["id"]: {
            "status": s["status"],
            "audio_path": s["audio_path"],
            "transcript_path": s["transcript_path"],
            "start_seconds": s["start_seconds"],
            "end_seconds": s["end_seconds"],
            "effective_start_local": s["effective_start_local"],
            "updated_at": s["updated_at"],
            "error": s["error"],
        }
        for s in segments
    }

    state.setdefault("files", {})[key] = {
        "path": str(audio_path),
        "hash": audio_hash,
        "status": "transcribed",
        "transcript_path": str(transcript_path),
        "started_at": existing.get("started_at", datetime.now().isoformat(timespec="seconds")),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "error": None,
        "segments": segments_dict,
    }


def mark_audio_partial_error(
    state: dict,
    audio_path: Path,
    audio_hash: str,
    error: str,
    segments: list[dict],
) -> None:
    """
    Marque un fichier segmenté en erreur partielle.
    Conserve les segments déjà transcrits pour permettre la reprise.
    """
    key = str(audio_path.resolve())
    existing = state.get("files", {}).get(key, {})

    segments_dict = {
        s["id"]: {
            "status": s["status"],
            "audio_path": s["audio_path"],
            "transcript_path": s["transcript_path"],
            "start_seconds": s["start_seconds"],
            "end_seconds": s["end_seconds"],
            "effective_start_local": s["effective_start_local"],
            "updated_at": s["updated_at"],
            "error": s["error"],
        }
        for s in segments
    }

    state.setdefault("files", {})[key] = {
        "path": str(audio_path),
        "hash": audio_hash,
        "status": "partial_error",
        "transcript_path": None,
        "started_at": existing.get("started_at", datetime.now().isoformat(timespec="seconds")),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "error": error,
        "segments": segments_dict,
    }


def get_audio_segments_state(state: dict, audio_path: Path) -> dict:
    """
    Retourne le dict des segments pour un fichier audio, ou {} si absent.
    """
    key = str(audio_path.resolve())
    return state.get("files", {}).get(key, {}).get("segments", {})

def ensure_chunks_section(state: dict) -> None:
    if "chunks" not in state:
        state["chunks"] = {}


def register_chunk(
    state: dict,
    chunk_name: str,
) -> None:
    """Enregistre un chunk en "pending" s'il n'existe pas encore dans l'état."""
    ensure_chunks_section(state)

    if chunk_name not in state["chunks"]:
        state["chunks"][chunk_name] = {"status": "pending"}


def update_chunk_state(
    state: dict,
    chunk_name: str,
    chunk_hash: str,
    generation_status: str,
    needs_ai_processing: bool,
    partie_source: str | None = None,
    char_count: int = 0,
    word_count: int = 0,
    path: str | None = None,
    processed_path: str | None = None,
) -> None:
    """
    Met à jour l'entrée d'un chunk après la phase de génération.

    Règles de status :
    - needs_ai_processing=True  → status = "pending_ai"
      (couvre : created, updated, unchanged sans processed)
    - needs_ai_processing=False → status = "done"
      (couvre : unchanged avec processed existant)

    Le status "done" ne devient "pending_ai" que si le chunk change (via
    needs_ai_processing calculé dans chunk_service).

    Champs mis à jour : status, hash, generation_status, needs_ai_processing,
    path, partie_source, char_count, word_count, processed_path, updated_at.
    """
    ensure_chunks_section(state)
    existing = state["chunks"].get(chunk_name, {})

    # Règle centrale : needs_ai_processing pilote le status
    if needs_ai_processing:
        ai_status = "pending_ai"
    else:
        # unchanged + processed présent → conserver "done" si déjà "done",
        # sinon forcer "done" (le fichier processed existe, l'IA a déjà travaillé)
        prev = existing.get("status", "done")
        ai_status = "done" if prev in ("done", "pending", "pending_ai") else prev

    updated: dict = {
        **existing,
        "status":               ai_status,
        "hash":                 chunk_hash,
        "generation_status":    generation_status,
        "needs_ai_processing":  needs_ai_processing,
        "updated_at":           datetime.now().isoformat(timespec="seconds"),
    }

    if path is not None:
        updated["path"] = path
    if partie_source is not None:
        updated["partie_source"] = partie_source
    if char_count:
        updated["char_count"] = char_count
    if word_count:
        updated["word_count"] = word_count
    if processed_path is not None:
        updated["processed_path"] = processed_path
    elif processed_path is None and not needs_ai_processing:
        # Conserver processed_path ou processed_file s'il existait déjà
        updated.setdefault(
            "processed_path",
            existing.get("processed_path") or existing.get("processed_file"),
        )

    state["chunks"][chunk_name] = updated


def mark_chunk_done(
    state: dict,
    chunk_name: str,
) -> None:
    ensure_chunks_section(state)
    state["chunks"][chunk_name] = {"status": "done"}


def is_chunk_done(
    state: dict,
    chunk_name: str,
) -> bool:
    ensure_chunks_section(state)

    return (
        state["chunks"]
        .get(chunk_name, {})
        .get("status")
        == "done"
    )


def reset_chunk_for_reprocessing(
    state: dict,
    chunk_name: str,
) -> None:
    """
    Resets a single chunk entry to "pending" so it gets reprocessed.
    Removes any processed_file / processed_at / error metadata.
    """
    ensure_chunks_section(state)
    state["chunks"][chunk_name] = {"status": "pending"}


def reset_all_chunks_for_reprocessing(state: dict) -> list[str]:
    """
    Resets ALL chunk entries to "pending".

    Returns the list of chunk names that were reset.
    """
    ensure_chunks_section(state)
    reset: list[str] = []
    for chunk_name in list(state["chunks"].keys()):
        state["chunks"][chunk_name] = {"status": "pending"}
        reset.append(chunk_name)
    return reset


def force_reset_project_for_rebuild(
    project_name: str,
    reset_chunks: bool = True,
    reset_final: bool = True,
    reset_publication: bool = True,
    reset_exports: bool = True,
    reset_cover: bool = False,
) -> None:
    """
    Resets project_state.json sections to force a rebuild from chunks.

    Does NOT touch the audio transcription state.

    Args:
        project_name:       Project to reset.
        reset_chunks:       Reset all chunk states to "pending".
        reset_final:        Clear final_document state.
        reset_publication:  Clear publication state.
        reset_exports:      Clear exports state.
        reset_cover:        Also reset cover state (default: False).
    """
    state = load_project_state(project_name)

    if reset_chunks:
        reset_all_chunks_for_reprocessing(state)

    if reset_final:
        state["final_document"] = {}

    if reset_publication:
        state["publication"] = {}

    if reset_exports:
        state["exports"] = {}

    if reset_cover:
        state["cover"] = {}

    save_project_state(project_name, state)
    print(
        f"[project_state] État réinitialisé pour reconstruction : {project_name}"
    )


def update_metadata_state(project_name: str, yaml_path: Path) -> None:
    """
    Met à jour la section 'metadata' dans project_state.json après
    une modification de project.yaml depuis l'interface.

    Pose les indicateurs de reconstruction pour la publication,
    la couverture et le ZIP client.
    """
    state = load_project_state(project_name)
    state["metadata"] = {
        "path": str(yaml_path),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "last_editor": "streamlit",
        "needs_publication_rebuild": True,
        "needs_cover_rebuild": True,
        "needs_client_zip_rebuild": True,
    }
    save_project_state(project_name, state)