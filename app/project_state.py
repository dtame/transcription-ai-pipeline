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

    if "metadata" not in state:
        state["metadata"] = {}

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

def ensure_chunks_section(state: dict) -> None:
    if "chunks" not in state:
        state["chunks"] = {}
    
def register_chunk(
    state: dict,
    chunk_name: str
) -> None:

    ensure_chunks_section(state)

    if chunk_name not in state["chunks"]:
        state["chunks"][chunk_name] = {
            "status": "pending"
        }

def mark_chunk_done(
    state: dict,
    chunk_name: str
) -> None:

    ensure_chunks_section(state)

    state["chunks"][chunk_name] = {
        "status": "done"
    }

def is_chunk_done(
    state: dict,
    chunk_name: str
) -> bool:

    ensure_chunks_section(state)

    return (
        state["chunks"]
        .get(chunk_name, {})
        .get("status")
        == "done"
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