"""Runner offline 3B.7.7A.6 — artefacts déterministes, 0 appel provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_post_canary_architecture.constants import (
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    THIRD_WIN001_CALL_AUTHORIZED,
    WINDOW_ANALYSIS_11_REAL_STATUS,
)
from app.source_analysis_post_canary_architecture.cost_model import build_cost_artifact
from app.source_analysis_post_canary_architecture.decision import (
    build_decision,
    build_options_table,
    select_proposed_parameters,
)
from app.source_analysis_post_canary_architecture.facts import inspect_integrity
from app.source_analysis_post_canary_architecture.hierarchy import hierarchy_from_scaling
from app.source_analysis_post_canary_architecture.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_post_canary_architecture.report import render_report
from app.source_analysis_post_canary_architecture.response_mode import review_response_modes
from app.source_analysis_post_canary_architecture.simulate import run_window_simulations
from app.source_analysis_post_canary_architecture.synthetic import run_consolidation_scaling
from app.source_analysis_post_canary_architecture.writer import (
    consolidation_path,
    cost_path,
    decision_path,
    options_path,
    report_path,
    simulations_path,
    write_bytes_atomic,
)


def _public_simulations(simulations: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in simulations.items()
        if key not in {"plans", "transcript_obj"}
    }


def _public_consolidation(consolidation: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in consolidation.items() if key != "internal"}


def _result(
    integrity: dict[str, Any],
    simulations: dict[str, Any],
    consolidation: dict[str, Any],
    decision: dict[str, Any],
    hierarchy: dict[str, Any],
) -> str:
    if integrity.get("source_map_present"):
        return "FAIL"
    if not integrity["project_state"]["not_success"]:
        return "FAIL"
    if not integrity["forensics"]["active"]:
        return "FAIL"
    if not integrity.get("prompt_1_1_unchanged"):
        return "FAIL"
    if not integrity.get("clean_unchanged"):
        return "FAIL"
    if not integrity.get("max_output_unchanged"):
        return "FAIL"
    candidates = simulations.get("candidates") or []
    if len(candidates) < 7:
        return "PARTIAL"
    if not all(
        (row.get("coverage") or {}).get("every_present_src_owned_once")
        for row in [simulations["current_three_window"], *candidates]
        if row.get("feasible")
    ):
        return "PARTIAL"
    if decision.get("selected_architecture") != SELECTED_ARCHITECTURE:
        return "PARTIAL"
    if not hierarchy.get("no_drop"):
        return "PARTIAL"
    if consolidation.get("guard") != 80000:
        return "PARTIAL"
    return "PASS"


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    integrity = inspect_integrity(project_name, sortie_dir=sortie_dir)
    simulations = run_window_simulations(project_name, sortie_dir=sortie_dir)
    consolidation = run_consolidation_scaling(simulations)
    proposed = select_proposed_parameters(simulations)
    selected_internal = next(
        (
            row
            for row in consolidation.get("internal") or []
            if row.get("label") == proposed.get("label")
        ),
        {},
    )
    hierarchy = hierarchy_from_scaling(selected_internal)
    costs = build_cost_artifact(
        simulations,
        consolidation_by_label={
            row.get("label"): row for row in consolidation.get("plans") or []
        },
    )
    response = review_response_modes()
    options_table = build_options_table(
        simulations, costs, consolidation, response, proposed
    )
    decision = build_decision(
        simulations, costs, consolidation, response, hierarchy, proposed
    )
    result = _result(integrity, simulations, consolidation, decision, hierarchy)
    options = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "OFFLINE_ARCHITECTURE_OPTIONS",
        "real_provider_calls": 0,
        "options": options_table,
        "response_mode": response,
    }
    return {
        "result": result,
        "integrity": integrity,
        "simulations": simulations,
        "consolidation": consolidation,
        "costs": costs,
        "response": response,
        "options": options,
        "decision": decision,
        "hierarchy": hierarchy,
        "proposed": proposed,
    }


def write_architecture_artifacts(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = bundle or build_bundle(project_name, sortie_dir=sortie_dir)
    paths = {
        "simulations": write_bytes_atomic(
            simulations_path(project_name, sortie_dir=sortie_dir),
            _public_simulations(payload["simulations"]),
        ),
        "cost": write_bytes_atomic(
            cost_path(project_name, sortie_dir=sortie_dir),
            payload["costs"],
        ),
        "consolidation": write_bytes_atomic(
            consolidation_path(project_name, sortie_dir=sortie_dir),
            _public_consolidation(payload["consolidation"]),
        ),
        "options": write_bytes_atomic(
            options_path(project_name, sortie_dir=sortie_dir),
            payload["options"],
        ),
        "decision": write_bytes_atomic(
            decision_path(project_name, sortie_dir=sortie_dir),
            payload["decision"],
        ),
        "report": write_bytes_atomic(
            report_path(project_name, sortie_dir=sortie_dir),
            render_report(payload),
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "third_win001_call_authorized": THIRD_WIN001_CALL_AUTHORIZED,
        "window_analysis_1_1_real_status": WINDOW_ANALYSIS_11_REAL_STATUS,
        "result": payload["result"],
        "paths": {key: str(path) for key, path in paths.items()},
        "sha256": {key: sha256_of_file(path) for key, path in paths.items()},
    }


def write_twice_and_verify(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    bundle = build_bundle(project_name, sortie_dir=sortie_dir)
    first = write_architecture_artifacts(
        project_name, sortie_dir=sortie_dir, bundle=bundle
    )
    second = write_architecture_artifacts(
        project_name, sortie_dir=sortie_dir, bundle=bundle
    )
    if first["sha256"] != second["sha256"]:
        raise RuntimeError(
            f"artefacts non déterministes : {first['sha256']} ≠ {second['sha256']}"
        )
    first["determinism"] = {
        "run1_sha256": first["sha256"],
        "run2_sha256": second["sha256"],
        "identical": True,
    }
    return first


def run_post_canary_architecture_decision(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    return write_twice_and_verify(project_name, sortie_dir=sortie_dir)
