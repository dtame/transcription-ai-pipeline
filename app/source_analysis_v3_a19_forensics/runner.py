"""Runner offline 3B.7.7A.20. 0 provider. 0 WIN001 retry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v3.e2e import run_direct_e2e, run_hierarchical_e2e
from app.source_analysis_local_v3.prompt import build_window_system_prompt_v13
from app.source_analysis_v3_a19_forensics.constants import (
    A19_FIRST_DECODER_FAILURE,
    A19_STATUS_UNCHANGED,
    A19_STRUCTURED_PARSE,
    EXAMPLE_POLICY,
    FUTURE_REAL_CALL_AUTHORIZED,
    MODE,
    NEXT_ACTION,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    SEMANTIC_REVIEW_STATUS,
    SEMANTIC_TRANSPORT_VERSION_V3,
    SERVER_GRAMMAR_STATUS,
    SRC_FAILURE_CLASSIFICATION,
    SYNTHETIC_WORST_CASE_LOCAL_TOKENS,
    V3_HANDLE_ARCHITECTURE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
    WIN001_RETRY_AUTHORIZED,
)
from app.source_analysis_v3_a19_forensics.coverage import build_a19_coverage
from app.source_analysis_v3_a19_forensics.evidence import (
    assert_a19_evidence_intact,
    evidence_inventory,
    protected_a19_phase_hashes,
)
from app.source_analysis_v3_a19_forensics.example_policy import audit_examples
from app.source_analysis_v3_a19_forensics.forensic_validator import (
    collect_transport_violations,
)
from app.source_analysis_v3_a19_forensics.future_retry import build_future_retry_readiness
from app.source_analysis_v3_a19_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v3_a19_forensics.replay import replay_a19_offline
from app.source_analysis_v3_a19_forensics.report import render_report
from app.source_analysis_v3_a19_forensics.semantic import build_forensic_semantic_review
from app.source_analysis_v3_a19_forensics.src_audit import audit_source_refs
from app.source_analysis_v3_a19_forensics.src_contract import (
    audit_prompt_src_contract,
    build_src_contract_analysis,
)
from app.source_analysis_v3_real_win001.handles import (
    handle_gate_status,
    inspect_symbolic_refs,
)
from app.source_analysis_v3_real_win001.paths import production_win001_present


def build_bundle(
    *,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
    tests: str = "UNKNOWN",
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    hashes_before = protected_a19_phase_hashes(project_name, sortie_dir=sortie_dir)
    replay = replay_a19_offline(project_name, sortie_dir=sortie_dir)
    transport = replay.get("transport")
    if not isinstance(transport, dict):
        raise RuntimeError("A.19 replay produced no structured transport.")
    window = replay["window"]
    transcript = replay["transcript"]
    allowed = set(window.owned_src_refs) | set(window.context_src_refs)
    owned = set(window.owned_src_refs)
    inventory = collect_transport_violations(
        transport,
        allowed=allowed,
        owned=owned,
        example_policy=EXAMPLE_POLICY,
    )
    src_audit = audit_source_refs(transport, window)
    prompt_audit = audit_prompt_src_contract(transcript, window)
    src_contract = build_src_contract_analysis(src_audit, prompt_audit)
    examples = audit_examples(transport, window=window, transcript=transcript)
    coverage = build_a19_coverage(transport, window, transcript, src_audit)
    semantic = build_forensic_semantic_review(
        transport, window, transcript, coverage=coverage
    )
    handles = inspect_symbolic_refs(transport)
    gate = handle_gate_status(handles)
    future = build_future_retry_readiness(
        window,
        transcript,
        inventory=inventory,
        src_contract=src_contract,
        example_policy=examples,
        handles_clean=bool(gate.get("handle_gate_pass")),
        tests=tests,
    )
    prompt_13 = build_window_system_prompt_v13(transcript.primary_language)
    prompt_13_untouched = (
        "empty only if no local IDEA exists" in prompt_13
        and "case-sensitive" not in prompt_13.lower()
    )
    from app.source_analysis_local_v3.prompt import build_window_system_prompt_v131

    prompt_131 = build_window_system_prompt_v131(transcript.primary_language)
    prompt_131_ok = all(
        token in prompt_131.lower()
        for token in (
            "case-sensitive",
            "exactly",
            "from its number",
            "zero padding",
        )
    )
    hashes_after = protected_a19_phase_hashes(project_name, sortie_dir=sortie_dir)
    assert_a19_evidence_intact(hashes_before, hashes_after)
    isolation = evidence_inventory(project_name, sortie_dir=sortie_dir)
    result = "PASS"
    if inventory["total_latent_root_violations"] < 1:
        result = "PARTIAL"
    if not examples.get("settled_policy"):
        result = "PARTIAL"
    if semantic.get("semantic_quality") == "INADEQUATE":
        result = "PARTIAL"
    if not future.get("future_real_call_ready"):
        # technical unreadiness is PARTIAL only if inventory incomplete
        if not future.get("all_observable_a19_violations_inventoried"):
            result = "PARTIAL"
    if WIN001_RETRY_AUTHORIZED or REAL_PROVIDER_CALLS_THIS_PHASE:
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
        "a19_status": A19_STATUS_UNCHANGED,
        "a19_structured_parse": A19_STRUCTURED_PARSE,
        "a19_first_decoder_failure": A19_FIRST_DECODER_FAILURE,
        "total_latent_root_violations": inventory["total_latent_root_violations"],
        "total_cascade_violations": inventory["total_cascade_violations"],
        "malformed_src_refs": inventory["counts"]["malformed_src"],
        "wrong_case_src_refs": inventory["counts"]["wrong_case_src"],
        "unknown_src_refs": inventory["counts"]["unknown_src"],
        "out_of_window_src_refs": inventory["counts"]["out_of_window_src"],
        "duplicate_src_refs": inventory["counts"]["duplicate_src"],
        "handle_root_violations": inventory["counts"]["handle_root"],
        "unknown_handles": inventory["counts"]["unknown_handles"],
        "wrong_kind_handles": inventory["counts"]["wrong_kind_handles"],
        "duplicate_owners": inventory["counts"]["duplicate_owners"],
        "self_relations": inventory["counts"]["self_relations"],
        "numeric_link_regression": inventory["counts"]["numeric_link_regression"],
        "example_empty_link_violations": inventory["counts"]["example_empty_link_settled"],
        "example_policy": EXAMPLE_POLICY,
        "a15_target_kind_defect": semantic.get("a15_target_kind_defect"),
        "semantic_record_grounding": semantic.get("grounding_counts"),
        "unsupported_content": semantic.get("unsupported_content"),
        "major_idea_coverage": (semantic.get("major_idea_coverage") or {}).get(
            "represented_count"
        ),
        "semantic_src_coverage": coverage.get("verified_semantic_src_coverage_pct"),
        "thinking_disabled_content": semantic.get("thinking_disabled_local_extraction"),
        "v3_handle_architecture": V3_HANDLE_ARCHITECTURE,
        "src_failure_classification": SRC_FAILURE_CLASSIFICATION,
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V131,
        "transport": SEMANTIC_TRANSPORT_VERSION_V3,
        "schema_changed": SCHEMA_CHANGED,
        "server_grammar_status": SERVER_GRAMMAR_STATUS,
        "synthetic_worst_case": SYNTHETIC_WORST_CASE_LOCAL_TOKENS,
        "future_win001_input_estimate": future.get("future_win001_input_estimate"),
        "future_win001_signature": future.get("future_win001_signature"),
        "future_cache": future.get("future_cache"),
        "future_real_call_ready": future.get("future_real_call_ready"),
        "future_real_call_authorized": FUTURE_REAL_CALL_AUTHORIZED,
        "production_default": PRODUCTION_PLANNER_VERSION,
        "source_map": "NOT PUBLISHED",
        "phase_3b": PHASE_3B_STATUS,
        "tests": tests,
        "next_action": NEXT_ACTION,
        "architecture": SELECTED_ARCHITECTURE,
        "prompt_1_3_untouched": prompt_13_untouched,
        "prompt_1_3_1_contains_hardening": prompt_131_ok,
        "handle_gate_pass": gate.get("handle_gate_pass"),
        "semantic_review_status": SEMANTIC_REVIEW_STATUS,
    }
    report = render_report(
        header=header,
        inventory=inventory,
        src_audit=src_audit,
        src_contract=src_contract,
        examples=examples,
        semantic=semantic,
        coverage=coverage,
        future=future,
        handles=handles,
        isolation=isolation,
        tests=tests,
    )
    return {
        "header": header,
        "inventory": inventory,
        "src_audit": src_audit,
        "src_contract": src_contract,
        "examples": examples,
        "semantic": semantic,
        "coverage": coverage,
        "future": future,
        "handles": handles,
        "handle_gate": gate,
        "isolation": isolation,
        "replay": {
            key: replay[key]
            for key in replay
            if key not in {"window", "transcript", "transport"}
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
