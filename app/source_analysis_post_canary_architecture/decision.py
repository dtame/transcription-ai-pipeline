"""Comparaison d'options et sélection d'une architecture."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_models import WINDOW_MAX_OUTPUT_TOKENS
from app.source_analysis_hybrid.constants import HARD_MAX_INPUT_TOKENS, TARGET_INPUT_TOKENS
from app.source_analysis_post_canary_architecture.constants import (
    BALANCE_MIN_RATIO,
    CALL1_FAILURE,
    CALL2_FAILURE,
    CURRENT_WINDOW_COUNT,
    NEXT_PHASE,
    NEXT_PHASE_LABEL,
    OVERHEAD_INEFFICIENT_PCT,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROPOSED_CONTEXT_POLICY,
    PROPOSED_OVERLAP_POLICY,
    PROPOSED_PLANNER_VERSION,
    REAL_CALL_AUTHORIZATION,
    RESPONSE_MODE_DECISION,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    THIRD_WIN001_CALL_AUTHORIZED,
    WINDOW_ANALYSIS_11_REAL_STATUS,
    WINDOW_ANALYSIS_11_STATUS_DETAIL,
)


def _find_plan(simulations: Mapping[str, Any], target: int, hard_max: int) -> dict[str, Any] | None:
    for row in simulations.get("candidates") or []:
        if row.get("target") == target and row.get("hard_max") == hard_max:
            return row
    return None


def select_proposed_parameters(simulations: Mapping[str, Any]) -> dict[str, Any]:
    preferred_order = (
        (25000, 35000),
        (25000, 30000),
        (20000, 25000),
        (30000, 40000),
        (35000, 45000),
        (15000, 20000),
    )
    eligible: list[dict[str, Any]] = []
    for row in simulations.get("candidates") or []:
        if not row.get("feasible"):
            continue
        if not row.get("balanced"):
            continue
        if not row.get("within_hard_max"):
            continue
        if row.get("tiny_stub"):
            continue
        if float(row.get("prompt_overhead_pct_of_mean_request") or 0) > OVERHEAD_INEFFICIENT_PCT:
            continue
        if int(row.get("target") or 0) >= 50000:
            continue
        eligible.append(row)
    chosen = None
    for target, hard_max in preferred_order:
        match = next(
            (
                row
                for row in eligible
                if row.get("target") == target and row.get("hard_max") == hard_max
            ),
            None,
        )
        if match is not None:
            chosen = match
            break
    if chosen is None and eligible:
        chosen = eligible[0]
    if chosen is None:
        # Last resort: smallest feasible balanced-or-not candidate below 50k.
        fallback = [
            row
            for row in simulations.get("candidates") or []
            if row.get("feasible") and int(row.get("target") or 0) < 50000
        ]
        chosen = fallback[0] if fallback else simulations["current_three_window"]
    return {
        "target": chosen.get("target"),
        "hard_max": chosen.get("hard_max"),
        "window_count": chosen.get("window_count"),
        "words": chosen.get("words"),
        "owned_src": chosen.get("owned_src"),
        "local_estimated_request": chosen.get("local_estimated_request"),
        "prompt_overhead_pct_of_mean_request": chosen.get(
            "prompt_overhead_pct_of_mean_request"
        ),
        "balance_metric": chosen.get("balance_metric"),
        "tiny_stub": chosen.get("tiny_stub"),
        "label": chosen.get("label"),
        "selection_rule": (
            "feasible + balanced + within hard max + no tiny stub + "
            f"overhead <= {OVERHEAD_INEFFICIENT_PCT}% + target < 50k; "
            "prefer 25k/35k then 25k/30k then 20k/25k"
        ),
    }


def build_options_table(
    simulations: Mapping[str, Any],
    costs: Mapping[str, Any],
    consolidation: Mapping[str, Any],
    response: Mapping[str, Any],
    proposed: Mapping[str, Any],
) -> list[dict[str, Any]]:
    current = simulations["current_three_window"]
    proposed_row = _find_plan(
        simulations, int(proposed["target"]), int(proposed["hard_max"])
    ) or current
    cost_by_label = {row.get("label"): row for row in costs.get("plans") or []}
    cons_by_label = {row.get("label"): row for row in consolidation.get("plans") or []}
    current_cost = cost_by_label.get(current.get("label"), {})
    proposed_cost = cost_by_label.get(proposed_row.get("label"), {})
    current_cons = cons_by_label.get(current.get("label"), {})
    proposed_cons = cons_by_label.get(proposed_row.get("label"), {})

    def _blast(row: Mapping[str, Any]) -> str:
        words = (row.get("words") or {}).get("max")
        src = (row.get("owned_src") or {}).get("max")
        return f"one call ≈ max {src} SRC / {words} words"

    return [
        {
            "option": "A",
            "name": "KEEP_CURRENT_3_WINDOWS",
            "window_count": current.get("window_count"),
            "typical_local_input": (current.get("local_estimated_request") or {}).get("mean"),
            "largest_local_input": (current.get("local_estimated_request") or {}).get("max"),
            "prompt_overhead_pct": current.get("prompt_overhead_pct_of_mean_request"),
            "expected_output_risk": "HIGH — two historical ~50k failures; 1.1 unvalidated",
            "failure_blast_radius": _blast(current),
            "cache_resume_quality": "3 artifacts; one failure loses ~1/3 corpus",
            "consolidation_burden": (
                (current_cons.get("normal") or {}).get("status")
            ),
            "traceability_complexity": "LOW — current contracts",
            "implementation_complexity": "NONE — already implemented",
            "provider_call_count": current.get("provider_calls_required"),
            "cost_scenario": (current_cost.get("corpus_range_window_analysis_only") or {}),
            "evidence_support": (
                "Fits context. Two paid WIN001 failures. Call #2 does not "
                "prove 50k cannot work. Does not justify a blind third 50k call."
            ),
            "main_unknown": "whether bounded 1.1 can complete a 50k window",
        },
        {
            "option": "B",
            "name": "SMALLER_WINDOWS_DIRECT_GLOBAL",
            "window_count": proposed_row.get("window_count"),
            "typical_local_input": (proposed_row.get("local_estimated_request") or {}).get("mean"),
            "largest_local_input": (proposed_row.get("local_estimated_request") or {}).get("max"),
            "prompt_overhead_pct": proposed_row.get("prompt_overhead_pct_of_mean_request"),
            "expected_output_risk": "LOWER per call; more total local records",
            "failure_blast_radius": _blast(proposed_row),
            "cache_resume_quality": (
                f"{proposed_row.get('window_count')} artifacts; finer resume"
            ),
            "consolidation_burden": (
                (proposed_cons.get("normal") or {}).get("status")
            ),
            "traceability_complexity": "MEDIUM — more intermediate IDs",
            "implementation_complexity": "MEDIUM — planner config only if guard holds",
            "provider_call_count": proposed_row.get("provider_calls_required"),
            "cost_scenario": (proposed_cost.get("corpus_range_window_analysis_only") or {}),
            "evidence_support": "Simulated. Depends on global consolidation still fitting 80k.",
            "main_unknown": "actual 1.1 output size on smaller windows",
        },
        {
            "option": "C",
            "name": "FIXED_HIERARCHICAL_ANALYSIS",
            "window_count": proposed_row.get("window_count"),
            "typical_local_input": (proposed_row.get("local_estimated_request") or {}).get("mean"),
            "largest_local_input": (proposed_row.get("local_estimated_request") or {}).get("max"),
            "prompt_overhead_pct": proposed_row.get("prompt_overhead_pct_of_mean_request"),
            "expected_output_risk": "LOWER per call; extra consolidation generations",
            "failure_blast_radius": _blast(proposed_row),
            "cache_resume_quality": "window + regional + global artifacts",
            "consolidation_burden": "ALWAYS regional then global",
            "traceability_complexity": "HIGH — more contracts, SRC must survive",
            "implementation_complexity": "HIGH — always extra stage",
            "provider_call_count": (
                int(proposed_row.get("provider_calls_required") or 0)
                + int((proposed_cons.get("hierarchy") or {}).get("regional_group_count") or 0)
                + 1
            ),
            "cost_scenario": (proposed_cost.get("corpus_range_window_analysis_only") or {}),
            "evidence_support": (
                "Needed if global ConsolidationInput exceeds guard. Extra "
                "calls are unnecessary when the guard holds."
            ),
            "main_unknown": "AI regional compaction ratio",
        },
        {
            "option": "D",
            "name": "RESPONSE_MODE_CHANGE_FIRST",
            "window_count": CURRENT_WINDOW_COUNT,
            "typical_local_input": (current.get("local_estimated_request") or {}).get("mean"),
            "largest_local_input": (current.get("local_estimated_request") or {}).get("max"),
            "prompt_overhead_pct": current.get("prompt_overhead_pct_of_mean_request"),
            "expected_output_risk": "UNCHANGED semantic risk",
            "failure_blast_radius": _blast(current),
            "cache_resume_quality": "unchanged",
            "consolidation_burden": "unchanged",
            "traceability_complexity": "LOW",
            "implementation_complexity": "HIGH + EXTERNAL VERIFICATION",
            "provider_call_count": CURRENT_WINDOW_COUNT,
            "cost_scenario": (current_cost.get("corpus_range_window_analysis_only") or {}),
            "evidence_support": (
                f"Streaming implemented now = {response['streaming']['anthropic_engine_supports_streaming_now']}. "
                "Does not solve overgeneration."
            ),
            "main_unknown": "provider streaming/async capabilities",
        },
        {
            "option": "SELECTED",
            "name": SELECTED_ARCHITECTURE,
            "window_count": proposed_row.get("window_count"),
            "typical_local_input": (proposed_row.get("local_estimated_request") or {}).get("mean"),
            "largest_local_input": (proposed_row.get("local_estimated_request") or {}).get("max"),
            "prompt_overhead_pct": proposed_row.get("prompt_overhead_pct_of_mean_request"),
            "expected_output_risk": "LOWER per call; hierarchy only if guard requires it",
            "failure_blast_radius": _blast(proposed_row),
            "cache_resume_quality": (
                f"{proposed_row.get('window_count')} window caches; optional regional"
            ),
            "consolidation_burden": (
                (proposed_cons.get("hierarchy") or {}).get("adaptive_trigger")
            ),
            "traceability_complexity": "MEDIUM-HIGH — SRC refs must survive if hierarchy triggers",
            "implementation_complexity": "MEDIUM — planner params + capacity branch, FakeAI first",
            "provider_call_count": proposed_row.get("provider_calls_required"),
            "cost_scenario": (proposed_cost.get("corpus_range_window_analysis_only") or {}),
            "evidence_support": (
                "Two ~50k failures justify avoiding a blind third 50k call. "
                "Simulations show balanced smaller windows. Adaptive hierarchy "
                "preserves fail-closed consolidation without always adding calls."
            ),
            "main_unknown": "real 1.1 reliability on the proposed operational unit",
        },
    ]


def build_decision(
    simulations: Mapping[str, Any],
    costs: Mapping[str, Any],
    consolidation: Mapping[str, Any],
    response: Mapping[str, Any],
    hierarchy: Mapping[str, Any],
    proposed: Mapping[str, Any],
) -> dict[str, Any]:
    proposed_row = _find_plan(
        simulations, int(proposed["target"]), int(proposed["hard_max"])
    ) or simulations["current_three_window"]
    proposed_cons = next(
        (
            row
            for row in consolidation.get("plans") or []
            if row.get("label") == proposed_row.get("label")
        ),
        {},
    )
    current = simulations["current_three_window"]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": "OFFLINE_ARCHITECTURE_DECISION",
        "real_provider_calls": 0,
        "third_win001_call_authorized": THIRD_WIN001_CALL_AUTHORIZED,
        "real_call_authorization": REAL_CALL_AUTHORIZATION,
        "selected_architecture": SELECTED_ARCHITECTURE,
        "evidence": {
            "call_1": CALL1_FAILURE,
            "call_2": CALL2_FAILURE,
            "window_analysis_1_1_real_status": WINDOW_ANALYSIS_11_REAL_STATUS,
            "window_analysis_1_1_status_detail": WINDOW_ANALYSIS_11_STATUS_DETAIL,
            "two_failures_prove_50k_impossible": False,
            "two_failures_justify_avoiding_blind_third_50k": True,
            "context_capacity_justifies_50k": False,
            "forensics_solve_semantic_reliability": False,
            "current_windows": current.get("window_count"),
            "current_local_max": (current.get("local_estimated_request") or {}).get("max"),
        },
        "parameters": {
            "planner_version_candidate": PROPOSED_PLANNER_VERSION,
            "algorithm": PRODUCTION_PLANNER_VERSION,
            "production_planner_unchanged": True,
            "target_local_request_tokens": proposed["target"],
            "hard_max_local_request_tokens": proposed["hard_max"],
            "expected_clean_window_count": proposed["window_count"],
            "words": proposed.get("words"),
            "owned_src": proposed.get("owned_src"),
            "overlap_policy": PROPOSED_OVERLAP_POLICY,
            "context_policy": PROPOSED_CONTEXT_POLICY,
            "context_src_refs": "empty — deferred, not implemented",
            "window_prompt": WINDOW_ANALYSIS_PROMPT_VERSION,
            "granularity_policy": POLICY_VERSION,
            "max_output": WINDOW_MAX_OUTPUT_TOKENS,
            "max_output_changed": False,
            "production_target_still": TARGET_INPUT_TOKENS,
            "production_hard_max_still": HARD_MAX_INPUT_TOKENS,
        },
        "tradeoffs": {
            "reliability_over_call_count": True,
            "more_windows_repeat_prompt_overhead": True,
            "more_local_records_increase_consolidation_burden": True,
            "smaller_failure_units": True,
            "finer_resume": True,
            "hierarchy_only_if_guard_exceeded": True,
        },
        "consolidation_strategy": {
            "name": "ADAPTIVE_HIERARCHICAL",
            "direct_if": "ConsolidationInput.estimated_tokens <= 80000",
            "else": "deterministic regional groups → regional consolidation → global",
            "normal_status": (proposed_cons.get("normal") or {}).get("status"),
            "stress_status": (proposed_cons.get("stress") or {}).get("status"),
            "stress_is_not_expected_case": True,
            "python_semantic_merge": False,
            "ai_semantic_merge": True,
            "no_drop": hierarchy.get("no_drop"),
            "src_refs_survive": hierarchy.get("src_refs_survive_local_regional_global"),
        },
        "response_mode": {
            "decision": RESPONSE_MODE_DECISION,
            "current": "synchronous_non_streaming_http",
            "streaming_required": False,
            "streaming_verified": False,
            "async_batch_verified": False,
        },
        "remaining_unknowns": [
            "exact call #2 sub-condition",
            "call #2 cost",
            "actual billed tokens for bounded 1.1",
            "whether proposed smaller windows complete structured JSON",
            "provider streaming support",
            "provider async/batch support",
            "AI regional compaction ratio",
        ],
        "implementation_prerequisites": [
            "FakeAI-only planner parameterization",
            "capacity signaling already exists (ConsolidationContextExceeded)",
            "deterministic regional grouping if guard exceeded",
            "KEEP/MERGE accounting through hierarchy",
            "no production planner change until FakeAI proof",
        ],
        "provider_verification_prerequisites": [
            "EXTERNAL PROVIDER VERIFICATION REQUIRED before streaming",
            "EXTERNAL PROVIDER VERIFICATION REQUIRED before async/batch",
        ],
        "canonical_sourcemap": "UNCHANGED",
        "phase_4_contract": "UNCHANGED",
        "source_map": "NOT PUBLISHED",
        "phase_3b": PHASE_3B_STATUS,
        "next_phase": NEXT_PHASE,
        "next_phase_label": NEXT_PHASE_LABEL,
        "next_action": "HUMAN REVIEW",
        "criteria": {
            "structured_output_reliability": "primary",
            "semantic_fidelity": "primary",
            "traceability": "required",
            "failure_isolation": "required",
            "resume_recovery": "required",
            "consolidation_feasibility": "required fail-closed",
            "cost": "scenario only, secondary",
            "latency": "secondary; sequential remains",
            "implementation_complexity": "accepted for reliability",
            "observability": "forensics already hardened",
        },
        "balance_threshold": BALANCE_MIN_RATIO,
        "why_selected": (
            "Reliability and semantic fidelity outrank minimizing call count. "
            "Two failed ~50k WIN001 calls are meaningful evidence against "
            "repeating that operational unit blindly, without proving 50k "
            "impossible. Smaller bounded 1.1 windows reduce structured-output "
            "blast radius and improve resume. Adaptive hierarchy keeps global "
            "consolidation when it fits the 80k guard and fails closed into "
            "deterministic regional merge when it does not. Response-mode "
            "change is not required now."
        ),
        "why_rejected": {
            "KEEP_CURRENT_3_WINDOWS": (
                "Same operational unit as two paid failures. Context fit is "
                "not operational fitness."
            ),
            "SMALLER_WINDOWS_DIRECT_GLOBAL": (
                "Acceptable only if guard always holds, including stress. "
                "Adaptive is the fail-closed form of the same idea."
            ),
            "FIXED_HIERARCHICAL_ANALYSIS": (
                "Always-on extra calls and contracts without a capacity trigger."
            ),
            "RESPONSE_MODE_CHANGE_FIRST": (
                "Unverified locally; does not solve semantic overgeneration."
            ),
        },
    }
