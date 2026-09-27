"""
Artefacts de capture structurée de la transcription (couche V2).

Rôle : conserver les données réellement produites par Whisper — timestamps
numériques précis, texte, langue détectée — au plus près de leur production,
afin que transcript_data.json n'ait jamais à être reconstruit en reparsant les
timestamps textuels « [MM:SS] » des transcripts V1.

Deux niveaux d'artefacts :

    sortie/<projet>/segment_transcripts/<stem>/part_001.json
        Capture BRUTE d'un segment technique (aucun filtrage d'overlap).
        Écrite juste avant la publication du transcript texte du segment, et
        donc restaurée telle quelle lors d'une reprise.

    sortie/<projet>/transcript_capture/<stem>.json
        Capture consolidée d'un fichier audio source (une ou plusieurs parties).
        C'est l'entrée du constructeur du contrat V2.

Invariant garanti par les services de transcription :
    un transcript texte publié possède toujours sa capture.
"""

from __future__ import annotations

from pathlib import Path

from app.file_utils import natural_sort_key, read_json, write_json_atomic
from app.transcript_models import AudioCapture, CapturedPart

CAPTURE_DIRNAME = "transcript_capture"


# ---------------------------------------------------------------------------
# Emplacements
# ---------------------------------------------------------------------------

def capture_dir(output_dir: Path) -> Path:
    """Répertoire des captures consolidées d'un projet."""
    return Path(output_dir) / CAPTURE_DIRNAME


def audio_capture_path(output_dir: Path, audio_stem: str) -> Path:
    """Chemin de la capture consolidée d'un fichier audio source."""
    return capture_dir(output_dir) / f"{audio_stem}.json"


def part_capture_path(transcript_path: Path) -> Path:
    """
    Chemin de la capture brute d'un segment technique, dérivé du chemin de son
    transcript texte : part_001.txt → part_001.json.
    """
    return Path(transcript_path).with_suffix(".json")


# ---------------------------------------------------------------------------
# Capture d'un segment technique
# ---------------------------------------------------------------------------

def write_part_capture(transcript_path: Path, part: CapturedPart) -> Path:
    """Écrit la capture brute d'un segment technique, de façon atomique."""
    return write_json_atomic(part_capture_path(transcript_path), part.to_dict())


def read_part_capture(transcript_path: Path) -> CapturedPart:
    """Relit la capture brute d'un segment technique."""
    return CapturedPart.from_dict(read_json(part_capture_path(transcript_path)))


def has_part_capture(transcript_path: Path) -> bool:
    return part_capture_path(transcript_path).exists()


# ---------------------------------------------------------------------------
# Capture consolidée d'un fichier audio
# ---------------------------------------------------------------------------

def write_audio_capture(
    output_dir: Path,
    audio_stem: str,
    capture: AudioCapture,
) -> Path:
    """Écrit la capture consolidée d'un fichier audio, de façon atomique."""
    return write_json_atomic(
        audio_capture_path(output_dir, audio_stem),
        capture.to_dict(),
    )


def read_audio_capture(path: Path) -> AudioCapture:
    return AudioCapture.from_dict(read_json(path))


def load_project_captures(output_dir: Path) -> list[AudioCapture]:
    """
    Charge toutes les captures consolidées d'un projet.

    L'ordre retourné est l'ordre naturel des noms de fichiers audio ; il ne
    dépend donc pas de l'ordre du système de fichiers.
    """
    directory = capture_dir(output_dir)

    if not directory.is_dir():
        return []

    captures = [read_audio_capture(path) for path in directory.glob("*.json")]

    return sorted(captures, key=lambda capture: natural_sort_key(capture.filename))


def captured_stems(output_dir: Path) -> set[str]:
    """Stems des fichiers audio disposant d'une capture consolidée."""
    directory = capture_dir(output_dir)

    if not directory.is_dir():
        return set()

    return {path.stem for path in directory.glob("*.json")}
