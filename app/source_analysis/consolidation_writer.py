"""
Persistance atomique des artefacts de consolidation.

Layout production (tests = temp dirs) :

    analysis/consolidation/input.json
    analysis/consolidation/transport.json
    analysis/consolidation/result.json
    analysis/consolidation/metadata.json

transport.json : écrit DÈS que le provider a renvoyé un parsed,
AVANT decode / validation / result.

result.json : uniquement si decode + validator PASS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.file_utils import write_text_atomic
from app.paths import SORTIE_DIR
from app.source_analysis.errors import ConsolidationTransportWriteError
from app.source_analysis.window_writer import (
    leftover_partial,
    render_exact_json,
)
from app.source_analysis.writer import analysis_dir

CONSOLIDATION_DIR_NAME = "consolidation"
INPUT_NAME = "input.json"
TRANSPORT_NAME = "transport.json"
RESULT_NAME = "result.json"
METADATA_NAME = "metadata.json"


def consolidation_root(project_name: str, *, sortie_dir: Path | None = None) -> Path:
    return analysis_dir(project_name, sortie_dir=sortie_dir) / CONSOLIDATION_DIR_NAME


def consolidation_dir(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    root: Path | None = None,
) -> Path:
    if root is not None:
        return Path(root)
    return consolidation_root(project_name, sortie_dir=sortie_dir)


def input_path(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    root: Path | None = None,
) -> Path:
    return consolidation_dir(
        project_name, sortie_dir=sortie_dir, root=root
    ) / INPUT_NAME


def transport_path(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    root: Path | None = None,
) -> Path:
    return consolidation_dir(
        project_name, sortie_dir=sortie_dir, root=root
    ) / TRANSPORT_NAME


def result_path(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    root: Path | None = None,
) -> Path:
    return consolidation_dir(
        project_name, sortie_dir=sortie_dir, root=root
    ) / RESULT_NAME


def metadata_path(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    root: Path | None = None,
) -> Path:
    return consolidation_dir(
        project_name, sortie_dir=sortie_dir, root=root
    ) / METADATA_NAME


def write_consolidation_input(path: Path, payload: Mapping[str, Any]) -> Path:
    return write_text_atomic(Path(path), render_exact_json(payload))


def write_consolidation_transport(path: Path, payload: Mapping[str, Any]) -> Path:
    try:
        return write_text_atomic(Path(path), render_exact_json(payload))
    except ConsolidationTransportWriteError:
        raise
    except Exception as exc:
        raise ConsolidationTransportWriteError(
            f"échec d'écriture de transport.json : {type(exc).__name__}: {exc}"
        ) from exc


def write_consolidation_result(path: Path, payload: Mapping[str, Any]) -> Path:
    return write_text_atomic(Path(path), render_exact_json(payload))


def write_consolidation_metadata(path: Path, payload: Mapping[str, Any]) -> Path:
    return write_text_atomic(Path(path), render_exact_json(payload))


def production_consolidation_exist(
    project_name: str, *, sortie_dir: Path | None = None
) -> bool:
    root = Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR
    project = root / project_name / "analysis"
    for candidate in (
        project / CONSOLIDATION_DIR_NAME,
        project / "hybrid" / CONSOLIDATION_DIR_NAME,
    ):
        if candidate.exists():
            return True
    return False


__all__ = [
    "CONSOLIDATION_DIR_NAME",
    "INPUT_NAME",
    "METADATA_NAME",
    "RESULT_NAME",
    "TRANSPORT_NAME",
    "consolidation_dir",
    "consolidation_root",
    "input_path",
    "leftover_partial",
    "metadata_path",
    "production_consolidation_exist",
    "result_path",
    "transport_path",
    "write_consolidation_input",
    "write_consolidation_metadata",
    "write_consolidation_result",
    "write_consolidation_transport",
]
