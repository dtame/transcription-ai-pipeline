"""Écriture atomique des artefacts A.45 — nouveaux fichiers seulement."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    CONTRACT_ARTIFACT,
    COST_ARTIFACT,
    FAKEAI_ARTIFACT,
    FUTURE_GUARD_ARTIFACT,
    INPUT_BUDGET_ARTIFACT,
    INVENTORY_ARTIFACT,
    NORMALIZED_INPUT_ARTIFACT,
    OUTPUT_BUDGET_ARTIFACT,
    OUTPUT_COMPONENTS_ARTIFACT,
    PHASE,
    PUBLICATION_ARTIFACT,
    READINESS_ARTIFACT,
    REPORT_NAME,
    REQUEST_ARTIFACT,
    REQUEST_IDENTITY_ARTIFACT,
    SCHEMA_VERSION,
    SEMANTIC_PLAN_ARTIFACT,
    TEST_DELTA_ARTIFACT,
    WINDOW_MANIFEST_ARTIFACT,
)
from app.source_analysis_v31_global_v30_exact_preflight.paths import artifact_path
from app.source_analysis_v31_global_v30_exact_preflight.report import render_report


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
    tests: str = "offline A.45",
) -> dict[str, Path]:
    written = {
        "inventory": write_bytes_atomic(
            artifact_path(project_name, INVENTORY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("inventory")),
        ),
        "window_manifest": write_bytes_atomic(
            artifact_path(project_name, WINDOW_MANIFEST_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("window_manifest")),
        ),
        "normalized_input": write_bytes_atomic(
            artifact_path(project_name, NORMALIZED_INPUT_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("normalized_input")),
        ),
        "request": write_bytes_atomic(
            artifact_path(project_name, REQUEST_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("exact_request")),
        ),
        "request_identity": write_bytes_atomic(
            artifact_path(project_name, REQUEST_IDENTITY_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("request_identity")),
        ),
        "input_budget": write_bytes_atomic(
            artifact_path(project_name, INPUT_BUDGET_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("input_budget")),
        ),
        "output_budget": write_bytes_atomic(
            artifact_path(project_name, OUTPUT_BUDGET_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("output_budget")),
        ),
        "output_components": write_bytes_atomic(
            artifact_path(project_name, OUTPUT_COMPONENTS_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("output_components")),
        ),
        "cost": write_bytes_atomic(
            artifact_path(project_name, COST_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("cost")),
        ),
        "contract": write_bytes_atomic(
            artifact_path(project_name, CONTRACT_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("contract")),
        ),
        "publication": write_bytes_atomic(
            artifact_path(project_name, PUBLICATION_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("publication")),
        ),
        "future_guard": write_bytes_atomic(
            artifact_path(project_name, FUTURE_GUARD_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("future_guard")),
        ),
        "fakeai": write_bytes_atomic(
            artifact_path(project_name, FAKEAI_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("fakeai")),
        ),
        "semantic_plan": write_bytes_atomic(
            artifact_path(project_name, SEMANTIC_PLAN_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("semantic_review_plan")),
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
    if bundle.get("test_delta"):
        written["test_delta"] = write_bytes_atomic(
            artifact_path(project_name, TEST_DELTA_ARTIFACT, sortie_dir=sortie_dir),
            _with_header(bundle.get("test_delta")),
        )
    return written


__all__ = ["write_audit_bundle"]
