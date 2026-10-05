"""Select a single Semantic Gate 2.0 canary candidate. Audit only."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b23.constants import CLASS_SUPPORTED
from app.book_semantic_gate_4b210.constants import (
    H01_CASE_HANDLE,
    H01_CASE_ID,
    H01_COST_USD,
    H01_HUMAN_LABEL,
    H01_INPUT_TOKENS,
    H02_CASE_HANDLE,
    H02_CASE_ID,
    H02_HUMAN_LABEL,
    H11_CASE_HANDLE,
    H11_CASE_ID,
    H11_COST_USD,
    H11_HUMAN_LABEL,
    H11_INPUT_TOKENS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    PHASE,
    SELECTED_CASE_HANDLE,
    SELECTED_CASE_HUMAN_LABEL,
    SELECTED_CASE_ID,
    SELECTED_CASE_ORIGIN,
    SELECTED_CASE_ROLE,
    TARGET_FAILURE_FAMILY,
)


def candidate_selection() -> dict[str, Any]:
    options = [
        {
            "handle": H01_CASE_HANDLE,
            "historical_case_id_audit_only": H01_CASE_ID,
            "kind": "historical_positive_problematic",
            "human_label_audit_only": H01_HUMAN_LABEL,
            "historical_status": HISTORICAL_H01_STATUS,
            "discriminates": "false_rejection_of_faithful_paraphrase",
            "evidence_available": True,
            "observed_input_tokens": H01_INPUT_TOKENS,
            "observed_cost_usd": H01_COST_USD,
            "selected": True,
            "why_selected": (
                "h01 is the documented false rejection of a supported "
                "paraphrase. Semantic Gate 2.0 exists to keep segmentation "
                "local and to judge entailment rather than wording. One "
                "discriminating case is enough for a first 2.0 Terra decision."
            ),
        },
        {
            "handle": H02_CASE_HANDLE,
            "historical_case_id_audit_only": H02_CASE_ID,
            "kind": "historical_negative_mixed",
            "human_label_audit_only": H02_HUMAN_LABEL,
            "historical_status": HISTORICAL_H02_STATUS,
            "discriminates": "invented_causality_plus_false_rejections",
            "evidence_available": True,
            "observed_input_tokens": None,
            "observed_cost_usd": None,
            "selected": False,
            "why_deferred": (
                "Useful later. Larger and mixed. Not the first 2.0 canary."
            ),
        },
        {
            "handle": H11_CASE_HANDLE,
            "historical_case_id_audit_only": H11_CASE_ID,
            "kind": "historical_negative_mixed",
            "human_label_audit_only": H11_HUMAN_LABEL,
            "historical_status": HISTORICAL_H11_STATUS,
            "discriminates": "universal_guarantee_plus_false_rejections",
            "evidence_available": True,
            "observed_input_tokens": H11_INPUT_TOKENS,
            "observed_cost_usd": H11_COST_USD,
            "selected": False,
            "why_deferred": (
                "Already used as a 1.1.3 real Terra discriminator. Deferred "
                "so this phase does not launch a new series of canaries."
            ),
        },
        {
            "handle": None,
            "kind": "new_controlled_case",
            "selected": False,
            "why_deferred": (
                "A new synthetic case is unnecessary while a documented "
                "historical positive remains the 2.0 hypothesis to test."
            ),
        },
    ]
    return {
        "phase": PHASE,
        "exactly_one_selected": True,
        "selected_handle": SELECTED_CASE_HANDLE,
        "selected_case_id_audit_only": SELECTED_CASE_ID,
        "selected_role_audit_only": SELECTED_CASE_ROLE,
        "selected_origin": SELECTED_CASE_ORIGIN,
        "human_label_audit_only": SELECTED_CASE_HUMAN_LABEL,
        "human_label_must_not_enter_provider_request": True,
        "target_failure_family": TARGET_FAILURE_FAMILY,
        "avoids_canary_series": True,
        "options": options,
        "rejected_new_series": True,
        "label_matches_supported": SELECTED_CASE_HUMAN_LABEL == CLASS_SUPPORTED,
        "historical_statuses_unchanged": {
            "h01": HISTORICAL_H01_STATUS,
            "h02": HISTORICAL_H02_STATUS,
            "h11": HISTORICAL_H11_STATUS,
        },
        "secrets_included": False,
    }


__all__ = ["candidate_selection"]
