"""Écriture atomique des artefacts A.49. Ne réécrit pas A.34–A.48."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_a49_source_map_publication.constants import (
    CANDIDATE_IDENTITY_ARTIFACT,
    FREEZE_ARTIFACT,
    PHASE,
    PREPUBLICATION_ARTIFACT,
    PUBLICATION_ARTIFACT,
    READINESS_ARTIFACT,
    RELOAD_ARTIFACT,
    REPORT_NAME,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_global_a49_source_map_publication.paths import (
    artifact_path,
)
from app.source_analysis_v31_global_a49_source_map_publication.report import render_report


def _strip_identity(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    nested = dict(value)
    nested.pop("payload", None)
    nested.pop("canonical_json", None)
    return nested


def _sanitize(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    data.pop("payload", None)
    data.pop("canonical_json", None)
    for key in ("identity", "candidate", "existing", "published_identity"):
        if key in data:
            data[key] = _strip_identity(data.get(key))
    validation = data.get("validation")
    if isinstance(validation, dict):
        nested = dict(validation)
        nested.pop("source_map", None)
        data["validation"] = nested
    return data


def _with_header(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = _sanitize(payload)
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("phase", PHASE)
    return data


def write_audit_bundle(
    project_name: str,
    bundle: Mapping[str, Any],
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.49",
) -> dict[str, Path]:
    written = {
        "prepublication": write_bytes_atomic(
            artifact_path(project_name, PREPUBLICATION_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("gate")),
        ),
        "candidate_identity": write_bytes_atomic(
            artifact_path(
                project_name, CANDIDATE_IDENTITY_ARTIFACT, sortie_dir=sortie_dir
            ),
            _with_header(bundle.get("candidate_identity")),
        ),
        "publication": write_bytes_atomic(
            artifact_path(project_name, PUBLICATION_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("publication")),
        ),
        "reload": write_bytes_atomic(
            artifact_path(project_name, RELOAD_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("reload")),
        ),
        "freeze": write_bytes_atomic(
            artifact_path(project_name, FREEZE_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("freeze")),
        ),
        "readiness": write_bytes_atomic(
            artifact_path(project_name, READINESS_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("readiness")),
        ),
        "report": write_bytes_atomic(
            artifact_path(project_name, REPORT_NAME, sortie_dir=sortie_dir),
            render_report(bundle, tests=tests),
        ),
    }
    return written


__all__ = ["write_audit_bundle"]
