"""Lecture seule des preuves historiques A.19–A.33. Aucune écriture."""

from __future__ import annotations

from pathlib import Path

from app.paths import SORTIE_DIR
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_v31_global_preflight.constants import (
    PROJECT_NAME,
    PROTECTED_HISTORICAL,
)


def _sortie_root(sortie_dir: Path | None = None) -> Path:
    return Path(sortie_dir) if sortie_dir is not None else SORTIE_DIR


def protected_a34_historical_hashes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    root = _sortie_root(sortie_dir) / project_name
    hashes: dict[str, str] = {}
    for rel in PROTECTED_HISTORICAL:
        path = root / rel
        if path.is_file():
            hashes[rel] = sha256_of_file(path)
    return hashes


__all__ = ["protected_a34_historical_hashes"]
