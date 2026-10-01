"""Écriture atomique des artefacts A.47 — nouveaux fichiers seulement."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_a47_contract_forensics.constants import (
    CANDIDATE_SEMANTIC_ARTIFACT,
    CONTRACT_MATRIX_ARTIFACT,
    COUNTERFACTUAL_ARTIFACT,
    EDITORIAL_SCAN_ARTIFACT,
    INTENT_CONTRACT_ARTIFACT,
    INTENT_SEMANTIC_ARTIFACT,
    PHASE,
    READINESS_ARTIFACT,
    REPORT_NAME,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_global_a47_contract_forensics.paths import artifact_path
from app.source_analysis_v31_global_a47_contract_forensics.report import render_report


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
    tests: str = "offline A.47",
) -> dict[str, Path]:
    written = {
        "intent_contract": write_bytes_atomic(
            artifact_path(project_name, INTENT_CONTRACT_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("forensics")),
        ),
        "intent_semantics": write_bytes_atomic(
            artifact_path(project_name, INTENT_SEMANTIC_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("intent_semantics")),
        ),
        "matrix": write_bytes_atomic(
            artifact_path(project_name, CONTRACT_MATRIX_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("matrix")),
        ),
        "editorial": write_bytes_atomic(
            artifact_path(project_name, EDITORIAL_SCAN_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("editorial")),
        ),
        "counterfactual": write_bytes_atomic(
            artifact_path(project_name, COUNTERFACTUAL_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("counterfactual")),
        ),
        "candidate_review": write_bytes_atomic(
            artifact_path(project_name, CANDIDATE_SEMANTIC_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("candidate_review")),
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
