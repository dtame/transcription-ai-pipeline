"""Écriture atomique des artefacts A.33 — nouveaux fichiers seulement."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_src_canonicalization.constants import (
    INVENTORY_ARTIFACT,
    PHASE,
    POLICY_ARTIFACT,
    PROMOTION_ARTIFACT,
    PROVENANCE_ARTIFACT,
    READY_ARTIFACT,
    REPLAY_ARTIFACT,
    REPORT_NAME,
    SCHEMA_ARTIFACT,
    SCHEMA_VERSION,
    TEST_DELTA_ARTIFACT,
)
from app.source_analysis_v31_src_canonicalization.report import render_report


def artifact_path(project_name: str, name: str, *, sortie_dir: Path | None = None) -> Path:
    return audit_dir(project_name, sortie_dir=sortie_dir) / name


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
    tests: str = "offline A.33",
) -> dict[str, Path]:
    written = {
        "policy": write_bytes_atomic(
            artifact_path(project_name, POLICY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle["policy"]),
        ),
        "replay": write_bytes_atomic(
            artifact_path(project_name, REPLAY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle["replay_public"]),
        ),
        "provenance": write_bytes_atomic(
            artifact_path(project_name, PROVENANCE_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle["provenance"]),
        ),
        "promotion": write_bytes_atomic(
            artifact_path(project_name, PROMOTION_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle["promotion"]),
        ),
        "ready": write_bytes_atomic(
            artifact_path(project_name, READY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle["ready"]),
        ),
        "schema": write_bytes_atomic(
            artifact_path(project_name, SCHEMA_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle["schema"]),
        ),
        "test_delta": write_bytes_atomic(
            artifact_path(project_name, TEST_DELTA_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle["test_delta"]),
        ),
        "report": write_bytes_atomic(
            artifact_path(project_name, REPORT_NAME, sortie_dir=sortie_dir),
            render_report(bundle, tests=tests),
        ),
    }
    inventory = bundle.get("inventory")
    if isinstance(inventory, Mapping):
        written["inventory"] = write_bytes_atomic(
            artifact_path(project_name, INVENTORY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(inventory),
        )
    return written


__all__ = ["artifact_path", "write_audit_bundle"]
