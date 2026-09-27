"""Intégrité des artefacts protégés jusqu'à 3B.7.7A.1."""

from __future__ import annotations

from pathlib import Path

from app.language_cleanup.transcript_source import audit_dir
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_window_output_bounding.constants import (
    PROJECT_NAME,
    PROTECTED_EVIDENCE,
)


def protected_hashes(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, str]:
    audit = audit_dir(project_name, sortie_dir=sortie_dir)
    hashes: dict[str, str] = {}
    for rel in PROTECTED_EVIDENCE:
        path = audit / Path(rel).name
        if path.is_file():
            hashes[rel] = sha256_of_file(path)
    return hashes
