"""Runner offline 3B.7.7A.26. 0 provider. 0 fenêtre réelle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_v3_a25_forensics.evidence import (
    assert_a24_evidence_intact,
    evidence_inventory,
    protected_a24_phase_hashes,
)
from app.source_analysis_v31_local_lite.canonical import build_canonical_mapping
from app.source_analysis_v31_local_lite.compatibility import build_compatibility
from app.source_analysis_v31_local_lite.constants import (
    A19_STATUS,
    A21_STATUS_UNCHANGED,
    A22_STATUS,
    A23_STATUS_UNCHANGED,
    A24_STATUS,
    A25_STATUS,
    CANONICAL_IDEA_SUBTYPE,
    FUTURE_REAL_CALL_AUTHORIZED,
    GLOBAL_IDEA_SUBTYPE_STRATEGY,
    LOCAL_IDEA_METADATA,
    LOCAL_IDEA_SUBTYPE,
    MODE,
    NEXT_ACTION,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    PROMPT_VERSION,
    READY_WINDOWS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_local_lite.contract import build_local_lite_contract
from app.source_analysis_v31_local_lite.downstream import build_downstream_impact
from app.source_analysis_v31_local_lite.estimates import build_window_estimates
from app.source_analysis_v31_local_lite.fakeai import run_fakeai_validation
from app.source_analysis_v31_local_lite.future import build_future_win004_readiness
from app.source_analysis_v31_local_lite.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_local_lite.report import render_report
from app.source_analysis_v31_local_lite.schema_identity import build_schema_identity


def _pass(value: Any) -> bool:
    return value == "PASS" or value is True


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    tests: str,
    tmp_root: Path,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    before = protected_a24_phase_hashes(project_name, sortie_dir=sortie_dir)
    evidence = evidence_inventory(project_name, sortie_dir=sortie_dir)
    contract = build_local_lite_contract()
    canonical = build_canonical_mapping()
    downstream = build_downstream_impact(project_name)
    schema = build_schema_identity()
    estimates = build_window_estimates(project_name, sortie_dir=sortie_dir)
    fakeai = run_fakeai_validation(tmp_root)
    compat = build_compatibility(project_name, sortie_dir=sortie_dir)
    future = build_future_win004_readiness(
        schema_identity=schema,
        estimates=estimates,
        project_name=project_name,
        sortie_dir=sortie_dir,
    )
    after = protected_a24_phase_hashes(project_name, sortie_dir=sortie_dir)
    assert_a24_evidence_intact(before, after)
    source_map_absent = not source_map_path(project_name, sortie_dir=sortie_dir).exists()
    production_default = PLANNER_VERSION == "window-planner-v2.0"
    windows = estimates.get("windows") or {}
    result = "PASS"
    required = [
        fakeai.get("fakeai_win001"),
        fakeai.get("fakeai_win004"),
        fakeai.get("fakeai_all_7"),
        fakeai.get("direct_consolidation"),
        fakeai.get("hierarchical_consolidation"),
        fakeai.get("canonical_reconstruction"),
        fakeai.get("no_drop"),
        fakeai.get("src_traceability"),
        fakeai.get("topic_association"),
        fakeai.get("relation_preservation"),
        fakeai.get("historical_v3"),
        fakeai.get("importance_not_kind"),
        fakeai.get("old_v3_rejected_under_local_lite"),
        compat.get("historical_v3"),
        future.get("future_cache") == "MISS",
        future.get("future_real_call_authorized") is False,
        source_map_absent,
        production_default,
        REAL_PROVIDER_CALLS_THIS_PHASE == 0,
        REAL_WINDOW_CALLS == 0,
        estimates.get("within_35000"),
    ]
    if not all(_pass(item) if isinstance(item, str) else bool(item) for item in required):
        result = "PARTIAL"
    if REAL_PROVIDER_CALLS_THIS_PHASE or REAL_WINDOW_CALLS:
        result = "FAIL"
    header = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "baseline": tests,
        "selected_architecture": SELECTED_ARCHITECTURE,
        "prompt": PROMPT_VERSION,
        "transport": TRANSPORT_VERSION,
        "local_idea_subtype": LOCAL_IDEA_SUBTYPE,
        "local_idea_metadata": LOCAL_IDEA_METADATA,
        "canonical_idea_subtype": CANONICAL_IDEA_SUBTYPE,
        "global_idea_subtype_strategy": GLOBAL_IDEA_SUBTYPE_STRATEGY,
        "editorial_planner_dependency": downstream.get("editorial_planner_dependency"),
        "book_generator_dependency": downstream.get("book_generator_dependency"),
        "schema_raw_bytes": schema.get("raw_bytes"),
        "schema_adapted_bytes": schema.get("adapted_bytes"),
        "schema_hash": schema.get("schema_hash"),
        "schema_identical_to_a18": "YES" if schema.get("identical_to_a18") else "NO",
        "server_grammar_status": schema.get("server_grammar_status"),
        "prompt_token_delta": estimates.get("prompt_token_delta"),
        "win001_input_estimate": windows.get("WIN001"),
        "win002_input_estimate": windows.get("WIN002"),
        "win003_input_estimate": windows.get("WIN003"),
        "win004_input_estimate": windows.get("WIN004"),
        "win005_input_estimate": windows.get("WIN005"),
        "win006_input_estimate": windows.get("WIN006"),
        "win007_input_estimate": windows.get("WIN007"),
        "fakeai_win001": fakeai.get("fakeai_win001"),
        "fakeai_win004": fakeai.get("fakeai_win004"),
        "fakeai_all_7": fakeai.get("fakeai_all_7"),
        "direct_consolidation": fakeai.get("direct_consolidation"),
        "hierarchical_consolidation": fakeai.get("hierarchical_consolidation"),
        "canonical_reconstruction": fakeai.get("canonical_reconstruction"),
        "no_drop": fakeai.get("no_drop"),
        "src_traceability": fakeai.get("src_traceability"),
        "topic_association": fakeai.get("topic_association"),
        "relation_preservation": fakeai.get("relation_preservation"),
        "historical_v3": fakeai.get("historical_v3"),
        "a21_historical_candidate": compat.get("a21_historical_candidate"),
        "mixed_v3_v31_compatibility": compat.get("mixed_v3_v31_compatibility"),
        "derived_a21_local_lite": (
            "CREATED" if compat.get("derived_a21_local_lite") else "NOT_CREATED"
        ),
        "future_win004_input_estimate": future.get("future_win004_input_estimate"),
        "future_win004_signature": future.get("future_win004_signature"),
        "future_cache": future.get("future_cache"),
        "future_real_call_ready": "YES" if future.get("future_real_call_ready") else "NO",
        "future_real_call_authorized": "NO",
        "real_windows_ready": READY_WINDOWS,
        "production_default": PRODUCTION_PLANNER_VERSION,
        "source_map": "NOT PUBLISHED" if source_map_absent else "PRESENT",
        "phase_3b": PHASE_3B_STATUS,
        "tests": tests,
        "next_action": NEXT_ACTION,
        "a19": A19_STATUS,
        "a21": A21_STATUS_UNCHANGED,
        "a22": A22_STATUS,
        "a23": A23_STATUS_UNCHANGED,
        "a24": A24_STATUS,
        "a25": A25_STATUS,
        "historical_immutable": True,
    }
    isolation = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "production_planner": PRODUCTION_PLANNER_VERSION,
        "source_map_absent": source_map_absent,
        "historical_hashes_intact": before == after,
        "evidence": evidence,
        "future_authorized": FUTURE_REAL_CALL_AUTHORIZED,
    }
    report = render_report(
        header=header,
        contract=contract,
        canonical=canonical,
        downstream=downstream,
        schema=schema,
        fakeai=fakeai,
        compatibility=compat,
        future=future,
        isolation=isolation,
        tests=tests,
    )
    return {
        "header": header,
        "contract": contract,
        "canonical": canonical,
        "downstream": downstream,
        "schema": schema,
        "fakeai": fakeai,
        "compatibility": compat,
        "future": future,
        "isolation": isolation,
        "report": report,
    }


__all__ = ["build_bundle"]
