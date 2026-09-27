"""
Persistance atomique des artefacts d'une fenêtre.

Layout production (tests = temp dirs) :

    analysis/windows/WIN001/transport.json
    analysis/windows/WIN001/result.json
    analysis/windows/WIN001/metadata.json

transport.json : écrit DÈS que le provider a renvoyé un parsed structuré,
AVANT decode / validation / result.

result.json : uniquement si decode + validators PASS.

Même primitive que source_map : write_text_atomic
(.partial → replace, nettoyage sur BaseException). Pas de fsync :
la politique existante n'en utilise pas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import hashlib

from app.file_utils import write_text_atomic
from app.paths import SORTIE_DIR
from app.source_analysis.errors import WindowTransportWriteError
from app.source_analysis.window_models import assert_safe_window_id
from app.source_analysis.writer import analysis_dir, partial_path

WINDOWS_DIR_NAME = "windows"
TRANSPORT_NAME = "transport.json"
RESULT_NAME = "result.json"
METADATA_NAME = "metadata.json"
_JSON_INDENT = 2
_CANONICAL_ARTIFACT_NAMES = frozenset({TRANSPORT_NAME, RESULT_NAME, METADATA_NAME})


def windows_root(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return analysis_dir(project_name, sortie_dir=sortie_dir) / WINDOWS_DIR_NAME


def window_dir(
    project_name: str,
    window_id: str,
    *,
    sortie_dir: Path | None = None,
    root: Path | None = None,
) -> Path:
    assert_safe_window_id(window_id)
    base = Path(root) if root is not None else windows_root(
        project_name, sortie_dir=sortie_dir
    )
    return base / window_id


def transport_path(
    project_name: str,
    window_id: str,
    *,
    sortie_dir: Path | None = None,
    root: Path | None = None,
) -> Path:
    return window_dir(
        project_name, window_id, sortie_dir=sortie_dir, root=root
    ) / TRANSPORT_NAME


def result_path(
    project_name: str,
    window_id: str,
    *,
    sortie_dir: Path | None = None,
    root: Path | None = None,
) -> Path:
    return window_dir(
        project_name, window_id, sortie_dir=sortie_dir, root=root
    ) / RESULT_NAME


def metadata_path(
    project_name: str,
    window_id: str,
    *,
    sortie_dir: Path | None = None,
    root: Path | None = None,
) -> Path:
    return window_dir(
        project_name, window_id, sortie_dir=sortie_dir, root=root
    ) / METADATA_NAME


def artifact_sha256(path: Path) -> str:
    """SHA-256 des octets bruts. Pas de mtime, pas de taille comme identité."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json_artifact(path: Path) -> tuple[str, dict | None]:
    """
    Lecture fail-closed d'un artefact JSON.

    Retourne (status, payload) où status ∈
    missing | corrupt | partial | ok.
    Un fichier ``.partial`` n'est jamais un artefact valide.
    """
    path = Path(path)
    if path.name.endswith(".partial"):
        return "partial", None
    if leftover_partial(path) is not None and not path.exists():
        return "partial", None
    if not path.exists():
        return "missing", None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return "corrupt", None
    if not isinstance(payload, dict):
        return "corrupt", None
    return "ok", payload


def ambiguous_window_artifacts(directory: Path) -> tuple[str, ...]:
    """
    Candidats JSON supplémentaires dans le dossier fenêtre.

    Fail-closed : on ne choisit jamais le fichier le plus récent.
    Les ``.partial`` ne comptent pas comme candidats valides.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return ()
    extras: list[str] = []
    for child in sorted(directory.iterdir(), key=lambda item: item.name):
        if not child.is_file():
            continue
        name = child.name
        if name.endswith(".partial"):
            continue
        if name in _CANONICAL_ARTIFACT_NAMES:
            continue
        lowered = name.lower()
        if lowered.endswith(".json") and any(
            token in lowered for token in ("result", "transport", "metadata")
        ):
            extras.append(name)
    return tuple(extras)


def write_window_metadata(path: Path, payload: Mapping[str, Any]) -> Path:
    """Écrit metadata.json (identité déterministe + observabilité hors cache)."""
    return write_text_atomic(Path(path), render_exact_json(payload))


def render_exact_json(payload: Mapping[str, Any]) -> str:
    """
    Sérialisation de persistance : valeurs sémantiques intactes.

    Pas de sort_keys, pas de réparation de jetons, pas de tri sémantique.
    L'ordre des clés est l'ordre d'insertion reçu.
    """
    return json.dumps(dict(payload), ensure_ascii=False, indent=_JSON_INDENT) + "\n"


def write_window_transport(path: Path, payload: Mapping[str, Any]) -> Path:
    """Écrit le transport exact. Si cela échoue : STOP, pas de decode."""
    try:
        return write_text_atomic(Path(path), render_exact_json(payload))
    except WindowTransportWriteError:
        raise
    except Exception as exc:
        raise WindowTransportWriteError(
            f"échec d'écriture de transport.json : {type(exc).__name__}: {exc}"
        ) from exc


def write_window_result(path: Path, payload: Mapping[str, Any]) -> Path:
    """Écrit result.json APRÈS validation complète uniquement."""
    return write_text_atomic(Path(path), render_exact_json(payload))


def read_json_payload(path: Path) -> dict | None:
    path = Path(path)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def leftover_partial(path: Path) -> Path | None:
    candidate = partial_path(Path(path))
    return candidate if candidate.exists() else None


def production_windows_exist(
    project_name: str, *, sortie_dir: Path | None = None
) -> bool:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    project = root / project_name / "analysis"
    for candidate in (
        project / WINDOWS_DIR_NAME,
        project / "hybrid" / WINDOWS_DIR_NAME,
    ):
        if candidate.exists():
            return True
    return False


__all__ = [
    "METADATA_NAME",
    "RESULT_NAME",
    "TRANSPORT_NAME",
    "WINDOWS_DIR_NAME",
    "ambiguous_window_artifacts",
    "artifact_sha256",
    "leftover_partial",
    "metadata_path",
    "production_windows_exist",
    "read_json_artifact",
    "read_json_payload",
    "render_exact_json",
    "result_path",
    "transport_path",
    "window_dir",
    "windows_root",
    "write_window_metadata",
    "write_window_result",
    "write_window_transport",
]
