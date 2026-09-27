"""Runner offline 3B.7.7A.2 — artefacts déterministes, 0 appel provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.window_granularity import granularity_policy
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis_hybrid.constants import WINDOW_TRANSPORT_VERSION
from app.source_analysis_window_output_bounding.constants import (
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_VERSION,
    WIN001_RETRIED,
)
from app.source_analysis_window_output_bounding.implementation import implementation_facts
from app.source_analysis_window_output_bounding.integrity import protected_hashes
from app.source_analysis_window_output_bounding.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_window_output_bounding.preflight import rebuild_win001_pair
from app.source_analysis_window_output_bounding.prompt_audit import (
    audit_transport_kinds,
    audit_window_analysis_10,
)
from app.source_analysis_window_output_bounding.report import render_report
from app.source_analysis_window_output_bounding.size_study import run_size_study
from app.source_analysis_window_output_bounding.writer import (
    implementation_path,
    policy_path,
    preflight_path,
    report_path,
    size_path,
    write_bytes_atomic,
)


def build_payload(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    policy = granularity_policy()
    study = run_size_study()
    preflight = rebuild_win001_pair(project_name, sortie_dir=sortie_dir)
    implementation = implementation_facts()
    prompt_audit = audit_window_analysis_10()
    kinds = audit_transport_kinds()
    result = (
        "PASS"
        if study["within_safety_margin"] and preflight["signatures_differ"]
        else "PARTIAL"
    )
    body = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "win001_retried": WIN001_RETRIED,
        "historical_prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V10,
        "successor_prompt": WINDOW_ANALYSIS_PROMPT_VERSION,
        "transport": WINDOW_TRANSPORT_VERSION,
        "policy": policy,
        "size_study": study,
        "preflight": preflight,
        "implementation": implementation,
        "prompt_audit": prompt_audit,
        "transport_kinds": kinds,
        "protected_hashes": protected_hashes(project_name, sortie_dir=sortie_dir),
        "baseline": {"passed": 2319, "failed": 0},
        "source_map_published": False,
        "project_state_success": False,
        "network": 0,
    }
    body["content_hash"] = content_hash(
        __import__("json").dumps(
            {key: value for key, value in body.items() if key != "content_hash"},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return body


def _artifact(phase_payload: dict[str, Any], name: str, extra: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        **extra,
    }
    return payload


def write_bounding_artifacts(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = payload or build_payload(project_name, sortie_dir=sortie_dir)
    policy = _artifact(
        body,
        "policy",
        {
            "policy": body["policy"],
            "prompt_successor_version": body["successor_prompt"],
            "historical_prompt_version": body["historical_prompt"],
            "size_study_max_policy_valid": body["size_study"]["max_policy_valid_local_tokens"],
            "margin_below_32000": body["size_study"]["safety_margin_tokens"],
            "rationale": body["policy"]["safety_margin_rationale"],
        },
    )
    size = _artifact(body, "size", body["size_study"])
    preflight = _artifact(body, "preflight", body["preflight"])
    implementation = _artifact(body, "implementation", body["implementation"])
    paths = {
        "policy": write_bytes_atomic(
            policy_path(project_name, sortie_dir=sortie_dir), policy
        ),
        "size_study": write_bytes_atomic(
            size_path(project_name, sortie_dir=sortie_dir), size
        ),
        "preflight": write_bytes_atomic(
            preflight_path(project_name, sortie_dir=sortie_dir), preflight
        ),
        "implementation": write_bytes_atomic(
            implementation_path(project_name, sortie_dir=sortie_dir), implementation
        ),
        "report": write_bytes_atomic(
            report_path(project_name, sortie_dir=sortie_dir),
            render_report(body),
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "result": body["result"],
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "paths": {key: str(path) for key, path in paths.items()},
        "sha256": {key: sha256_of_file(path) for key, path in paths.items()},
        "content_hash": body["content_hash"],
    }


def write_twice_and_verify(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    first = write_bounding_artifacts(project_name, sortie_dir=sortie_dir)
    second = write_bounding_artifacts(project_name, sortie_dir=sortie_dir)
    if first["sha256"] != second["sha256"]:
        raise RuntimeError(
            f"artefacts non déterministes : {first['sha256']} ≠ {second['sha256']}"
        )
    return first


def run_window_output_bounding(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    return write_twice_and_verify(project_name, sortie_dir=sortie_dir)
