"""Écriture atomique des artefacts A.48 — jamais analysis/source_map.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.source_analysis.writer import source_map_path
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_a48_offline_revalidation.constants import (
    ARCHITECTURE_ARTIFACT,
    CONTRACT_ARTIFACT,
    PHASE,
    PUBLICATION_ARTIFACT,
    RAW_IDENTITY_ARTIFACT,
    READINESS_ARTIFACT,
    REPORT_NAME,
    SCHEMA_VERSION,
    SEMANTIC_ARTIFACT,
    STRUCTURAL_ARTIFACT,
    TECHNICAL_ARTIFACT,
)
from app.source_analysis_v31_global_a48_offline_revalidation.paths import (
    artifact_path,
    candidate_path,
)
from app.source_analysis_v31_global_a48_offline_revalidation.report import render_report


def _with_header(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("phase", PHASE)
    return data


def write_audit_bundle(
    project_name: str,
    bundle: Mapping[str, Any],
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.48",
) -> dict[str, Path]:
    production = source_map_path(project_name, sortie_dir=sortie_dir)
    if production.is_file():
        raise RuntimeError(
            f"A.48 must not publish {production} — production source_map already present"
        )
    candidate = bundle.get("candidate_payload") or {}
    written = {
        "contract": write_bytes_atomic(
            artifact_path(project_name, CONTRACT_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("contract")),
        ),
        "raw_identity": write_bytes_atomic(
            artifact_path(project_name, RAW_IDENTITY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("identity")),
        ),
        "technical": write_bytes_atomic(
            artifact_path(project_name, TECHNICAL_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("technical")),
        ),
        "structural": write_bytes_atomic(
            artifact_path(project_name, STRUCTURAL_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("structural")),
        ),
        "semantic": write_bytes_atomic(
            artifact_path(project_name, SEMANTIC_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("semantic")),
        ),
        "publication": write_bytes_atomic(
            artifact_path(project_name, PUBLICATION_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("publication")),
        ),
        "architecture": write_bytes_atomic(
            artifact_path(project_name, ARCHITECTURE_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("architecture")),
        ),
        "readiness": write_bytes_atomic(
            artifact_path(project_name, READINESS_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("readiness")),
        ),
        "candidate": write_bytes_atomic(
            candidate_path(project_name, sortie_dir=sortie_dir),
            dict(candidate) if isinstance(candidate, Mapping) else {},
        ),
        "report": write_bytes_atomic(
            artifact_path(project_name, REPORT_NAME, sortie_dir=sortie_dir),
            render_report(bundle, tests=tests),
        ),
    }
    if production.is_file():
        raise RuntimeError("A.48 published analysis/source_map.json — forbidden")
    return written


__all__ = ["write_audit_bundle"]
