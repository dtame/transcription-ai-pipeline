"""Runner offline 3B.7.7A.10 — artefacts déterministes, 0 appel provider."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis_output_ceiling_review.comparison import (
    build_three_call_comparison,
)
from app.source_analysis_output_ceiling_review.constants import (
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALL_AUTHORIZED_NEXT,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
)
from app.source_analysis_output_ceiling_review.contract import build_contract_analysis
from app.source_analysis_output_ceiling_review.decision import build_decision
from app.source_analysis_output_ceiling_review.facts import (
    inspect_integrity,
    inspect_isolation,
    load_small_forensics,
)
from app.source_analysis_output_ceiling_review.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_output_ceiling_review.options import (
    build_architecture_options,
)
from app.source_analysis_output_ceiling_review.report import render_report
from app.source_analysis_output_ceiling_review.synthetic import (
    build_proposed_worst_case,
)
from app.source_analysis_output_ceiling_review.writer import (
    contract_path,
    decision_path,
    forensics_path,
    isolation_path,
    options_path,
    report_path,
    write_bytes_atomic,
)


def _classify_result(
    integrity: dict[str, Any],
    isolation: dict[str, Any],
    forensics: dict[str, Any],
    decision: dict[str, Any],
) -> str:
    if REAL_PROVIDER_CALLS_THIS_PHASE != 0:
        return "FAIL"
    if integrity.get("source_map_present"):
        return "FAIL"
    if integrity.get("transport_exists") or integrity.get("result_exists"):
        return "FAIL"
    if not integrity["project_state"]["not_success"]:
        return "FAIL"
    if not integrity["forensic_bytes_preserved"]["http_raw_unchanged"]:
        return "FAIL"
    if not integrity["forensic_bytes_preserved"]["structured_raw_unchanged"]:
        return "FAIL"
    if forensics.get("repairs_json") or forensics.get("provider_called"):
        return "FAIL"
    prefix = forensics.get("structured_prefix") or {}
    if prefix.get("complete_record_count") is None:
        return "PARTIAL"
    if not (isolation.get("sortie") or {}).get("ok"):
        return "PARTIAL"
    if decision.get("selected_architecture") != SELECTED_ARCHITECTURE:
        return "PARTIAL"
    composition = forensics.get("output_composition") or {}
    if composition.get("provider_thinking_tokens") is None:
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
    isolation = inspect_isolation(project_name, sortie_dir=sortie_dir)
    forensics = load_small_forensics(project_name, sortie_dir=sortie_dir)
    comparison = build_three_call_comparison()
    contract = build_contract_analysis()
    options = build_architecture_options()
    worst_case = build_proposed_worst_case()
    decision = build_decision(
        forensics=forensics, contract=contract, worst_case=worst_case
    )
    result = _classify_result(integrity, isolation, forensics, decision)
    return {
        "result": result,
        "integrity": integrity,
        "isolation": isolation,
        "forensics": forensics,
        "comparison": comparison,
        "contract": contract,
        "options": options,
        "worst_case": worst_case,
        "decision": decision,
    }


def _artifact(kind: str, payload: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "OFFLINE_OUTPUT_CEILING_ARCHITECTURE_REVIEW",
        "real_provider_calls_this_phase": 0,
        "new_win001_calls": 0,
        "real_provider_call_authorized_next": REAL_PROVIDER_CALL_AUTHORIZED_NEXT,
        "kind": kind,
        **extra,
    }
    body.update(payload)
    return body


def write_review_artifacts(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = bundle or build_bundle(project_name, sortie_dir=sortie_dir)
    prefix = payload["forensics"]["structured_prefix"]
    forensics_doc = _artifact(
        "OUTPUT_CEILING_FORENSICS",
        {
            "http_envelope": payload["forensics"]["http_envelope"],
            "structured_prefix": prefix,
            "output_composition": payload["forensics"]["output_composition"],
            "repairs_json": False,
            "treated_as_transport": False,
        },
        {"result": payload["result"]},
    )
    contract_doc = _artifact(
        "OUTPUT_CONTRACT_ANALYSIS",
        payload["contract"],
        {"result": payload["result"]},
    )
    options_doc = _artifact(
        "OUTPUT_BOUNDING_OPTIONS",
        payload["options"],
        {"result": payload["result"]},
    )
    decision_doc = _artifact(
        "OUTPUT_BOUNDING_DECISION",
        payload["decision"],
        {
            "result": payload["result"],
            "comparison": payload["comparison"],
            "worst_case": payload["worst_case"],
        },
    )
    isolation_doc = _artifact(
        "FORENSIC_VS_PUBLICATION_ISOLATION",
        payload["isolation"],
        {"result": payload["result"]},
    )
    paths = {
        "forensics": write_bytes_atomic(
            forensics_path(project_name, sortie_dir=sortie_dir),
            forensics_doc,
        ),
        "contract": write_bytes_atomic(
            contract_path(project_name, sortie_dir=sortie_dir),
            contract_doc,
        ),
        "options": write_bytes_atomic(
            options_path(project_name, sortie_dir=sortie_dir),
            options_doc,
        ),
        "decision": write_bytes_atomic(
            decision_path(project_name, sortie_dir=sortie_dir),
            decision_doc,
        ),
        "isolation": write_bytes_atomic(
            isolation_path(project_name, sortie_dir=sortie_dir),
            isolation_doc,
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
        "real_provider_call_authorized_next": REAL_PROVIDER_CALL_AUTHORIZED_NEXT,
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
    first = write_review_artifacts(
        project_name, sortie_dir=sortie_dir, bundle=bundle
    )
    second = write_review_artifacts(
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


def run_output_ceiling_review(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    return write_twice_and_verify(project_name, sortie_dir=sortie_dir)
