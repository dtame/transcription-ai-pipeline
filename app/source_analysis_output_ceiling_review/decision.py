"""Décision d'architecture 3B.7.7A.10. Aucune implémentation production."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_output_ceiling_review.constants import (
    ADAPTIVE_HIERARCHY_STATUS,
    NEXT_ACTION,
    NEXT_PHASE,
    NEXT_PHASE_LABEL,
    PRIMARY_ROOT_CAUSE,
    PRODUCTION_PLANNER_VERSION,
    PROPOSED_PROMPT,
    PROPOSED_TRANSPORT,
    REAL_PROVIDER_CALL_AUTHORIZED_NEXT,
    SELECTED_ARCHITECTURE,
    SMALL_PLANNER_STATUS,
)


def build_decision(
    *,
    forensics: Mapping[str, Any],
    contract: Mapping[str, Any],
    worst_case: Mapping[str, Any],
) -> dict[str, Any]:
    prefix = forensics.get("structured_prefix") or {}
    composition = forensics.get("output_composition") or {}
    return {
        "selected_architecture": SELECTED_ARCHITECTURE,
        "root_cause": {
            "primary": PRIMARY_ROOT_CAUSE,
            "secondary": [
                "SINGLE_PASS_KIND_ORDER_TAIL_TRUNCATION",
                "PROMPT_LIMIT_NOT_PROVIDER_ENFORCED",
                "OUTPUT_CONTRACT_NOT_GENERATION_BOUNDED",
            ],
            "unknown": [
                "CALL_A_thinking_tokens",
                "whether_thinking_budget_is_request_controllable_for_this_model",
                "whether_JSON_would_have_closed_if_thinking_were_capped",
            ],
            "not_attributed": [
                "model_motive",
                "one_record_per_src",
                "source_ref_explosion",
                "hard_ceiling_160_exceeded",
            ],
        },
        "evidence": {
            "complete_records": prefix.get("complete_record_count"),
            "ideas": (prefix.get("metrics") or {}).get("kind_counts", {}).get("IDEA"),
            "relations": (prefix.get("metrics") or {}).get("kind_counts", {}).get(
                "RELATION"
            ),
            "thinking_tokens": composition.get("provider_thinking_tokens"),
            "output_tokens": composition.get("provider_output_tokens"),
            "truncation": prefix.get("truncation"),
            "missing_categories": prefix.get("missing_categories_before_truncation"),
            "grouping_observed": (prefix.get("metrics") or {}).get("grouping_observed"),
            "exceeded_160": prefix.get("exceeded_total_hard_ceiling"),
        },
        "unchanged": {
            "canonical_sourcemap": True,
            "window_analysis_1_1": True,
            "window_granularity_1_0": True,
            "generation_c_historical": True,
            "production_planner": PRODUCTION_PLANNER_VERSION,
            "max_output": 32000,
            "small_planner_not_activated_globally": True,
        },
        "new_proposed_contracts": {
            "transport": PROPOSED_TRANSPORT,
            "prompt": PROPOSED_PROMPT,
            "historical_v1_not_mutated": True,
            "historical_1_1_not_modified": True,
            "local_kinds": worst_case.get("local_kinds"),
            "deferred_kinds": worst_case.get("deferred_kinds"),
            "python_semantic_merge": False,
            "ai_semantic_merge": True,
            "src_traceability_preserved": True,
            "no_drop": "capacity signal + deterministic subdivision",
        },
        "structural_worst_case": {
            "local_tokens": worst_case.get("local_tokens"),
            "target_json_local_tokens": worst_case.get("target_json_local_tokens"),
            "within_target": worst_case.get("within_json_target"),
            "reserved_thinking_tokens": worst_case.get("reserved_thinking_tokens"),
            "comfortably_below_32000_if_thinking_capped": worst_case.get(
                "comfortably_below_32000_if_thinking_capped"
            ),
            "provider_enforced": False,
        },
        "provider_enforcement_status": {
            "records_bounded_by_schema": False,
            "thinking_bounded_by_request_today": False,
            "true_output_boundedness_claimed": False,
            "blocker_for_true_boundedness": (
                "Thinking shares max_tokens and is not currently request-capped. "
                "maxItems is locally classified unsupported. Worst-case JSON "
                "size is a design target, not a provider guarantee."
            ),
        },
        "small_planner_status": SMALL_PLANNER_STATUS,
        "adaptive_hierarchy_status": ADAPTIVE_HIERARCHY_STATUS,
        "implementation_prerequisites": [
            "Design semantic-transport-v2 without mutating v1.",
            "Design window-analysis-1.2 without modifying 1.1.",
            "Add explicit thinking/output budget fields to request construction (FakeAI first).",
            "Keep Generation C historical bytes unchanged.",
            "Implement capacity/overflow + deterministic SRC subdivision.",
            "Do not publish source_map. Do not mark SUCCESS.",
            "No real provider call until the FakeAI contract is green.",
        ],
        "real_provider_call_authorized_next": REAL_PROVIDER_CALL_AUTHORIZED_NEXT,
        "next_phase": NEXT_PHASE,
        "next_phase_label": NEXT_PHASE_LABEL,
        "next_action": NEXT_ACTION,
        "why_alternatives_deferred": {
            "A": "Already observed to hit 32000/32000.",
            "B": "Multiplies thinking cost.",
            "C": "Second stage later; thinking must be capped first.",
            "D": "Call explosion; grouping already works.",
            "E": "Model-invented cursor rejected.",
            "F": "Kept as overflow, not the primary pass.",
        },
        "contract_notes": {
            "post_validation_prevents_token_spend": False,
            "raise_max_output": False,
            "lower_max_output_alone": False,
            "generation_c_bounds_records": False,
            "generation_c_bounds_value_length": False,
        },
    }
