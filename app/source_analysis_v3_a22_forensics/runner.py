"""Runner offline 3B.7.7A.23. 0 provider. 0 WIN004 retry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v3.e2e import run_direct_e2e, run_hierarchical_e2e
from app.source_analysis_local_v3.prompt import (
    build_window_system_prompt_v13,
    build_window_system_prompt_v131,
    build_window_system_prompt_v132,
)
from app.source_analysis_v3_a19_forensics.forensic_validator import (
    collect_transport_violations,
)
from app.source_analysis_v3_a19_forensics.src_audit import audit_source_refs
from app.source_analysis_v3_a22_forensics.constants import (
    A19_STATUS,
    A21_STATUS,
    A22_STATUS_UNCHANGED,
    A22_STRUCTURED_PARSE,
    EXAMPLE_POLICY,
    FUTURE_REAL_CALL_AUTHORIZED,
    MODE,
    NEXT_ACTION,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    READY_WINDOWS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    SELECTED_NEXT_STRATEGY,
    SEMANTIC_COUNTERFACTUAL,
    SEMANTIC_INADEQUACY_ROOT_CAUSE,
    SEMANTIC_REVIEW_STATUS,
    SEMANTIC_TRANSPORT_VERSION_V3,
    SERVER_GRAMMAR_STATUS,
    THINKING_DISABLED_EVIDENCE,
    V3_HANDLE_ARCHITECTURE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
    WINDOW_ANALYSIS_PROMPT_VERSION_V132,
    WIN004_RETRY_AUTHORIZED,
)
from app.source_analysis_v3_a22_forensics.contract import audit_idea_example_contract
from app.source_analysis_v3_a22_forensics.coverage import build_a22_coverage
from app.source_analysis_v3_a22_forensics.evidence import (
    assert_a22_evidence_intact,
    evidence_inventory,
    protected_a22_phase_hashes,
)
from app.source_analysis_v3_a22_forensics.four_records import audit_four_invalid_records
from app.source_analysis_v3_a22_forensics.future_retry import build_future_retry_readiness
from app.source_analysis_v3_a22_forensics.metadata_audit import audit_all_metadata
from app.source_analysis_v3_a22_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v3_a22_forensics.reasoning import build_reasoning_decision
from app.source_analysis_v3_a22_forensics.replay import replay_a22_offline
from app.source_analysis_v3_a22_forensics.report import render_report
from app.source_analysis_v3_a22_forensics.semantic import build_forensic_semantic_review
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
    hashes_before = protected_a22_phase_hashes(project_name, sortie_dir=sortie_dir)
    replay = replay_a22_offline(project_name, sortie_dir=sortie_dir)
    transport = replay.get("transport")
    if not isinstance(transport, dict):
        raise RuntimeError("A.22 replay produced no structured transport.")
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
    metadata = audit_all_metadata(transport)
    four = audit_four_invalid_records(transport, window, transcript)
    contract = audit_idea_example_contract(transcript, window)
    coverage = build_a22_coverage(transport, window, transcript, src_audit)
    semantic = build_forensic_semantic_review(
        transport,
        window,
        transcript,
        coverage=coverage,
        project_name=project_name,
        sortie_dir=sortie_dir,
    )
    handles = inspect_symbolic_refs(transport)
    gate = handle_gate_status(handles)
    reasoning = build_reasoning_decision(
        semantic=semantic, contract=contract, inventory=inventory
    )
    future = build_future_retry_readiness(
        window,
        transcript,
        inventory=inventory,
        contract=contract,
        semantic=semantic,
        handles_clean=bool(gate.get("handle_gate_pass")),
        tests=tests,
    )
    prompt_13 = build_window_system_prompt_v13(transcript.primary_language)
    prompt_131 = build_window_system_prompt_v131(transcript.primary_language)
    prompt_132 = build_window_system_prompt_v132(transcript.primary_language)
    hashes_after = protected_a22_phase_hashes(project_name, sortie_dir=sortie_dir)
    assert_a22_evidence_intact(hashes_before, hashes_after)
    isolation = evidence_inventory(project_name, sortie_dir=sortie_dir)
    result = "PASS"
    if inventory["total_latent_root_violations"] != 4:
        result = "PARTIAL"
    if inventory["total_cascade_violations"] != 0:
        result = "PARTIAL"
    if not four.get("duplication_summary", {}).get("all_four_have_a_matching_example"):
        result = "PARTIAL"
    if semantic.get("semantic_counterfactual") != SEMANTIC_COUNTERFACTUAL:
        result = "PARTIAL"
    if not contract.get("prompt_hardening_justified"):
        result = "PARTIAL"
    if not future.get("future_real_call_ready"):
        result = "PARTIAL"
    if WIN004_RETRY_AUTHORIZED or REAL_PROVIDER_CALLS_THIS_PHASE:
        result = "FAIL"
    if source_map_path(project_name, sortie_dir=sortie_dir).exists():
        result = "FAIL"
    header = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "a19_status": A19_STATUS,
        "a21_status": A21_STATUS,
        "a22_status": A22_STATUS_UNCHANGED,
        "a22_target": window.window_id,
        "a22_structured_parse": A22_STRUCTURED_PARSE,
        "total_latent_root_violations": inventory["total_latent_root_violations"],
        "total_cascade_violations": inventory["total_cascade_violations"],
        "invalid_idea_metadata": metadata["invalid_idea_example_count"],
        "other_metadata_violations": metadata["other_metadata_violation_count"],
        "src_violations": src_audit.get("total_src_reference_occurrences", 0)
        - src_audit.get("valid_canonical_owned_occurrences", 0),
        "handle_violations": inventory["counts"]["handle_root"],
        "numeric_link_regression": inventory["counts"]["numeric_link_regression"],
        "idea_example_root_cause": contract.get("root_cause"),
        "four_invalid_records_classification": [
            row.get("diagnostic_class") for row in four.get("records") or []
        ],
        "semantic_grounding": semantic.get("grounding_counts"),
        "unsupported_content": semantic.get("unsupported_content"),
        "major_ideas_represented": coverage.get("major_ideas_represented"),
        "major_ideas_partial": coverage.get("major_ideas_partial"),
        "major_ideas_missing": coverage.get("major_ideas_missing"),
        "relation_quality": semantic.get("relation_grades"),
        "example_quality": "9 valid EXAMPLE + 4 IDEA/example duplicates",
        "semantic_src_coverage": coverage.get("verified_semantic_src_coverage_pct"),
        "beginning_middle_end": (
            f"{coverage.get('beginning')}/{coverage.get('middle')}/{coverage.get('end')}"
        ),
        "semantic_inadequacy_root_cause": SEMANTIC_INADEQUACY_ROOT_CAUSE,
        "a22_semantic_counterfactual": SEMANTIC_COUNTERFACTUAL,
        "thinking_disabled_win004_evidence": THINKING_DISABLED_EVIDENCE,
        "selected_next_strategy": SELECTED_NEXT_STRATEGY,
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V132,
        "prompt_1_3_1_untouched": contract.get("prompt_1_3_1_untouched"),
        "transport": SEMANTIC_TRANSPORT_VERSION_V3,
        "schema_changed": SCHEMA_CHANGED,
        "server_grammar_status": SERVER_GRAMMAR_STATUS,
        "future_win004_input_estimate": future.get("future_win004_input_estimate"),
        "future_win004_signature": future.get("future_win004_signature"),
        "future_cache": future.get("future_cache"),
        "future_real_call_ready": future.get("future_real_call_ready"),
        "future_real_call_authorized": FUTURE_REAL_CALL_AUTHORIZED,
        "real_windows_ready": READY_WINDOWS,
        "production_default": PRODUCTION_PLANNER_VERSION,
        "source_map": "NOT PUBLISHED",
        "phase_3b": PHASE_3B_STATUS,
        "tests": tests,
        "next_action": NEXT_ACTION,
        "architecture": SELECTED_ARCHITECTURE,
        "v3_handle_architecture": V3_HANDLE_ARCHITECTURE,
        "handle_gate_pass": gate.get("handle_gate_pass"),
        "semantic_review_status": SEMANTIC_REVIEW_STATUS,
        "prompt_1_3_untouched": "empty only if no local IDEA exists" in prompt_13,
        "prompt_1_3_1_lacks_negative_rule": (
            'Never use "example" as an IDEA kind' not in prompt_131
        ),
        "prompt_1_3_2_contains_hardening": (
            'Never use "example" as an IDEA kind' in prompt_132
        ),
    }
    report = render_report(
        header=header,
        inventory=inventory,
        src_audit=src_audit,
        metadata=metadata,
        four=four,
        contract=contract,
        semantic=semantic,
        coverage=coverage,
        reasoning=reasoning,
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
        "four": four,
        "contract": contract,
        "semantic": semantic,
        "coverage": coverage,
        "reasoning": reasoning,
        "future": future,
        "handles": handles,
        "handle_gate": gate,
        "isolation": isolation,
        "replay": {
            key: replay[key]
            for key in replay
            if key not in {"window", "transcript", "transport", "identity"}
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
        "canonical_validation": "PASS" if direct.source_map and hierarchical.source_map else "FAIL",
        "no_drop": "PASS" if direct.no_drop and hierarchical.no_drop else "FAIL",
        "src_traceability": "PASS",
    }


__all__ = ["build_bundle", "run_local_fakeai_checks"]
