"""Écriture atomique des artefacts A.29 — nouveaux fichiers seulement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v31_length_ceiling.constants import (
    BOUNDARY_ARTIFACT,
    COUNTERFACTUAL_ARTIFACT,
    DECISION_ARTIFACT,
    DISTRIBUTION_ARTIFACT,
    FORENSICS_ARTIFACT,
    OPTIONS_ARTIFACT,
    PHASE,
    REPORT_NAME,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_length_ceiling.report import render_report


def artifact_path(project_name: str, name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / name


def write_bytes_atomic(path: Path, payload: Mapping[str, Any] | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        content = payload if payload.endswith("\n") else payload + "\n"
    else:
        content = json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    encoded = content.encode("utf-8")
    partial = path.with_name(path.name + ".partial")
    try:
        partial.write_bytes(encoded)
        if partial.read_bytes() != encoded:
            raise ValueError(f"Octets partiels ≠ contenu canonique pour {path.name}.")
        if not isinstance(payload, str):
            loaded = json.loads(encoded.decode("utf-8"))
            if not isinstance(loaded, dict) or loaded.get("schema_version") != SCHEMA_VERSION:
                raise ValueError(f"Artefact partiel invalide : {path.name}.")
            if loaded.get("phase") != PHASE:
                raise ValueError(f"phase inattendue dans {path.name}.")
        leftover_name = path.with_name(path.name + ".partial")
        partial.replace(path)
        if leftover_name.exists() and leftover_name != path:
            leftover_name.unlink()
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    leftover = path.with_name(path.name + ".partial")
    if leftover.exists():
        leftover.unlink()
    return path


def _jsonable(payload: Mapping[str, Any]) -> dict[str, Any]:
    skip = {"window", "transcript", "transport", "validation", "semantic_review"}
    return {key: value for key, value in payload.items() if key not in skip}


def write_audit_bundle(
    project_name: str,
    bundle: Mapping[str, Any],
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.29",
) -> dict[str, Path]:
    counter_public = _jsonable(bundle["counterfactual"])
    semantic = bundle["counterfactual"].get("semantic_review")
    if isinstance(semantic, Mapping):
        counter_public["semantic_review_summary"] = {
            "semantic_quality": semantic.get("semantic_quality"),
            "unsupported_count": semantic.get("unsupported_count"),
            "material_omissions": semantic.get("material_omissions"),
            "relation_quality_summary": semantic.get("relation_quality_summary"),
            "transport_valid": semantic.get("transport_valid"),
            "status": semantic.get("status"),
            "performed": semantic.get("performed"),
        }
    written = {
        "boundary": write_bytes_atomic(
            artifact_path(project_name, BOUNDARY_ARTIFACT, sortie_dir=sortie_dir),
            bundle["boundary"],
        ),
        "distribution": write_bytes_atomic(
            artifact_path(project_name, DISTRIBUTION_ARTIFACT, sortie_dir=sortie_dir),
            bundle["distribution"],
        ),
        "forensics": write_bytes_atomic(
            artifact_path(project_name, FORENSICS_ARTIFACT, sortie_dir=sortie_dir),
            {
                "schema_version": SCHEMA_VERSION,
                "phase": PHASE,
                **_jsonable(bundle["replay"]),
                "classification": bundle["classification"],
            },
        ),
        "options": write_bytes_atomic(
            artifact_path(project_name, OPTIONS_ARTIFACT, sortie_dir=sortie_dir),
            bundle["options"],
        ),
        "counterfactual": write_bytes_atomic(
            artifact_path(project_name, COUNTERFACTUAL_ARTIFACT, sortie_dir=sortie_dir),
            counter_public,
        ),
        "decision": write_bytes_atomic(
            artifact_path(project_name, DECISION_ARTIFACT, sortie_dir=sortie_dir),
            bundle["decision"],
        ),
        "report": write_bytes_atomic(
            artifact_path(project_name, REPORT_NAME, sortie_dir=sortie_dir),
            render_report(bundle, tests=tests),
        ),
    }
    return written


__all__ = ["artifact_path", "write_audit_bundle", "write_bytes_atomic"]
