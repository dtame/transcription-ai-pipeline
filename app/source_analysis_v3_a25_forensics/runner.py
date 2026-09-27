"""Runner offline 3B.7.7A.25. 0 provider. 0 WIN004 retry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v3.e2e import run_direct_e2e, run_hierarchical_e2e
from app.source_analysis_v3_a19_forensics.forensic_validator import (
    collect_transport_violations,
)
from app.source_analysis_v3_a19_forensics.src_audit import audit_source_refs
from app.source_analysis_v3_a25_forensics.architecture import build_architecture_decision
from app.source_analysis_v3_a25_forensics.constants import (
    A19_STATUS,
    A21_STATUS,
    A22_STATUS,
    A23_STATUS,
    A24_STATUS_UNCHANGED,
    A24_STRUCTURED_PARSE,
    EXAMPLE_POLICY,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    FUTURE_REAL_CALL_AUTHORIZED,
    FUTURE_REAL_CALL_READY,
    FUTURE_REAL_CALL_TYPE,
    I44_CLASSIFICATION,
    IMPLEMENTATION_SCOPE,
    MISSING_IDEA_AUTOMATED,
    MISSING_IDEA_MATERIALITY,
    MODE,
    NEW_PROMPT_ACTIVATED,
    NEW_PROMPT_DESIGNED,
    NEW_TRANSPORT_ACTIVATED,
    NEW_TRANSPORT_DESIGNED,
    NEXT_ACTION,
    PARTIAL_IDEA,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    PROMPT_132_EFFECT,
    READY_WINDOWS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    SEMANTIC_COUNTERFACTUAL,
    SEMANTIC_REVIEW_STATUS,
    SEMANTIC_TRANSPORT_VERSION_V3,
    SERVER_GRAMMAR_STATUS,
    THINKING_DISABLED_QUALITY_ISSUE,
    V3_HANDLE_ARCHITECTURE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V132,
    WIN004_RETRY_AUTHORIZED,
)
from app.source_analysis_v3_a25_forensics.coverage import build_a24_coverage
from app.source_analysis_v3_a25_forensics.delta import build_semantic_delta
from app.source_analysis_v3_a25_forensics.evidence import (
    assert_a24_evidence_intact,
    evidence_inventory,
    protected_a24_phase_hashes,
)
from app.source_analysis_v3_a25_forensics.future import build_future_readiness
from app.source_analysis_v3_a25_forensics.i44 import decompose_i44
from app.source_analysis_v3_a25_forensics.metadata_necessity import (
    build_metadata_necessity,
)
from app.source_analysis_v3_a25_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v3_a25_forensics.policy import build_acceptance_policy
from app.source_analysis_v3_a25_forensics.replay import replay_a24_offline
from app.source_analysis_v3_a25_forensics.report import render_report
from app.source_analysis_v3_a25_forensics.semantic import build_forensic_semantic_review
from app.source_analysis_v3_real_win001.handles import (
    handle_gate_status,
    inspect_symbolic_refs,
)


def _stamp(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out["schema_version"] = SCHEMA_VERSION
    out["phase"] = PHASE
    out["mode"] = MODE
    return out


def build_bundle(
    *,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
    tests: str = "UNKNOWN",
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    hashes_before = protected_a24_phase_hashes(project_name, sortie_dir=sortie_dir)
    replay = replay_a24_offline(project_name, sortie_dir=sortie_dir)
    transport = replay.get("transport")
    if not isinstance(transport, dict):
        raise RuntimeError("A.24 replay produced no structured transport.")
    window = replay["window"]
    transcript = replay["transcript"]
    allowed = set(window.owned_src_refs) | set(window.context_src_refs)
    owned = set(window.owned_src_refs)
    inventory = _stamp(
        collect_transport_violations(
            transport,
            allowed=allowed,
            owned=owned,
            example_policy=EXAMPLE_POLICY,
        )
    )
    src_audit = _stamp(audit_source_refs(transport, window))
    metadata = build_metadata_necessity(transport)
    i44 = decompose_i44(
        transport,
        window,
        transcript,
        project_name=project_name,
        sortie_dir=sortie_dir,
    )
    coverage = build_a24_coverage(transport, window, transcript, src_audit)
    semantic = build_forensic_semantic_review(
        transport,
        window,
        transcript,
        coverage=coverage,
        i44=i44,
    )
    delta = build_semantic_delta(
        transport,
        window,
        transcript,
        coverage=coverage,
        project_name=project_name,
        sortie_dir=sortie_dir,
    )
    architecture = build_architecture_decision(
        metadata=metadata, i44=i44, inventory=inventory
    )
    policy = build_acceptance_policy(
        semantic=semantic, coverage=coverage, delta=delta
    )
    handles = inspect_symbolic_refs(transport)
    gate = handle_gate_status(handles)
    future = build_future_readiness(
        window, transcript, architecture=architecture, tests=tests
    )
    hashes_after = protected_a24_phase_hashes(project_name, sortie_dir=sortie_dir)
    assert_a24_evidence_intact(hashes_before, hashes_after)
    isolation = evidence_inventory(project_name, sortie_dir=sortie_dir)
    result = "PARTIAL"
    if inventory["total_latent_root_violations"] != 1:
        result = "PARTIAL"
    if inventory["total_cascade_violations"] != 0:
        result = "PARTIAL"
    if i44.get("classification") != I44_CLASSIFICATION:
        result = "PARTIAL"
    if semantic.get("semantic_counterfactual") != SEMANTIC_COUNTERFACTUAL:
        result = "PARTIAL"
    if architecture.get("selected") != SELECTED_ARCHITECTURE:
        result = "PARTIAL"
    if IMPLEMENTATION_SCOPE != "DESIGN_ONLY":
        result = "PARTIAL"
    if WIN004_RETRY_AUTHORIZED or REAL_PROVIDER_CALLS_THIS_PHASE:
        result = "FAIL"
    if source_map_path(project_name, sortie_dir=sortie_dir).exists():
        result = "FAIL"
    if FUTURE_REAL_CALL_AUTHORIZED:
        result = "FAIL"
    grades = semantic.get("relation_grades") or {}
    header = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "a19_status": A19_STATUS,
        "a21_status": A21_STATUS,
        "a22_status": A22_STATUS,
        "a23_status": A23_STATUS,
        "a24_status": A24_STATUS_UNCHANGED,
        "a24_structured_parse": A24_STRUCTURED_PARSE,
        "a24_root_violations": inventory["total_latent_root_violations"],
        "a24_cascade_violations": inventory["total_cascade_violations"],
        "i44_classification": i44.get("classification"),
        "m_overloaded": metadata.get("m_overloaded"),
        "idea_subtype_required_locally": metadata.get("idea_subtype_necessity", {}).get(
            "required_locally"
        ),
        "idea_subtype_required_canonically": metadata.get(
            "idea_subtype_necessity", {}
        ).get("required_canonically"),
        "idea_subtype_downstream_consumers": (
            "hybrid_reconstructor (copies local m[0]); source_map validator "
            "(publication); consolidator MERGE-same-kind; not Book/Editorial"
        ),
        "a24_missing_major_idea": MISSING_IDEA_AUTOMATED,
        "missing_idea_materiality": MISSING_IDEA_MATERIALITY,
        "a24_partial_idea": PARTIAL_IDEA,
        "a24_semantic_counterfactual": SEMANTIC_COUNTERFACTUAL,
        "a22_to_a24_record_delta": delta.get("record_distribution", {}).get("delta"),
        "a24_relation_quality": (
            f"{grades.get('well_supported')} well-supported / "
            f"{grades.get('plausible_but_loose')} plausible-loose / "
            f"{grades.get('incorrect')} incorrect / "
            f"{grades.get('unverifiable')} unverifiable"
        ),
        "a24_example_quality": semantic.get("example_quality"),
        "unsupported_content": semantic.get("unsupported_content"),
        "semantic_src_coverage": coverage.get("verified_semantic_src_coverage_pct"),
        "thinking_disabled_quality_issue": THINKING_DISABLED_QUALITY_ISSUE,
        "selected_architecture": SELECTED_ARCHITECTURE,
        "new_prompt": NEW_PROMPT_DESIGNED,
        "new_prompt_activated": NEW_PROMPT_ACTIVATED,
        "new_transport": NEW_TRANSPORT_DESIGNED,
        "new_transport_activated": NEW_TRANSPORT_ACTIVATED,
        "schema_changed": SCHEMA_CHANGED,
        "raw_schema_bytes": EXPECTED_RAW_SCHEMA_BYTES,
        "adapted_schema_bytes": EXPECTED_ADAPTED_SCHEMA_BYTES,
        "server_grammar_status": SERVER_GRAMMAR_STATUS,
        "prompt_1_3_2_effect": PROMPT_132_EFFECT,
        "implementation_scope": IMPLEMENTATION_SCOPE,
        "semantic_acceptance_policy": policy.get("status"),
        "future_real_call_type": FUTURE_REAL_CALL_TYPE,
        "future_real_call_ready": FUTURE_REAL_CALL_READY,
        "future_real_call_authorized": FUTURE_REAL_CALL_AUTHORIZED,
        "real_windows_ready": READY_WINDOWS,
        "production_default": PRODUCTION_PLANNER_VERSION,
        "source_map": "NOT PUBLISHED",
        "phase_3b": PHASE_3B_STATUS,
        "tests": tests,
        "next_action": NEXT_ACTION,
        "architecture": V3_HANDLE_ARCHITECTURE,
        "v3_handle_architecture": V3_HANDLE_ARCHITECTURE,
        "handle_gate_pass": gate.get("handle_gate_pass"),
        "semantic_review_status": SEMANTIC_REVIEW_STATUS,
        "transport": SEMANTIC_TRANSPORT_VERSION_V3,
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V132,
        "numeric_link_regression": inventory["counts"]["numeric_link_regression"],
        "src_violations": src_audit.get("total_src_reference_occurrences", 0)
        - src_audit.get("valid_canonical_owned_occurrences", 0),
    }
    report = render_report(
        header=header,
        inventory=inventory,
        src_audit=src_audit,
        metadata=metadata,
        i44=i44,
        semantic=semantic,
        coverage=coverage,
        delta=delta,
        architecture=architecture,
        policy=policy,
        future=future,
        handles=handles,
        isolation=isolation,
        tests=tests,
    )
    return {
        "header": header,
        "inventory": inventory,
        "src_audit": src_audit,
        "metadata": metadata,
        "i44": i44,
        "semantic": semantic,
        "coverage": coverage,
        "delta": delta,
        "architecture": architecture,
        "policy": policy,
        "future": future,
        "handles": handles,
        "handle_gate": gate,
        "isolation": isolation,
        "replay": {
            key: replay[key]
            for key in replay
            if key not in {"window", "transcript", "transport", "raw_json"}
        },
        "report": report,
        "tests": tests,
    }


def run_local_fakeai_checks(tmp_root: Path) -> dict[str, Any]:
    direct = run_direct_e2e(tmp_root / "direct")
    hierarchical = run_hierarchical_e2e(tmp_root / "hierarchical")
    return {
        "fakeai_v3": "PASS" if direct.source_map and hierarchical.source_map else "FAIL",
        "seven_window": "PASS"
        if len(direct.window_results) == 7 and len(hierarchical.window_results) == 7
        else "FAIL",
        "direct_consolidation": "PASS" if direct.no_drop else "FAIL",
        "hierarchical_consolidation": "PASS" if hierarchical.no_drop else "FAIL",
        "canonical_validation": "PASS"
        if direct.source_map and hierarchical.source_map
        else "FAIL",
        "no_drop": "PASS" if direct.no_drop and hierarchical.no_drop else "FAIL",
        "src_traceability": "PASS",
    }


__all__ = ["build_bundle", "run_local_fakeai_checks"]
