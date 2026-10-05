"""Future canary selection criteria. Does not build or send a remote request."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b275.constants import (
    H01_COMPLETION_TOKENS,
    H01_COST_USD,
    H01_INPUT_TOKENS,
    H01_REASONING_TOKENS,
    H02_COMPLETION_TOKENS,
    H02_COST_USD,
    H02_INPUT_TOKENS,
    H02_REASONING_TOKENS,
    PHASE,
)


def future_canary_selection_criteria() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "observed_cost": {
            "h01": {
                "input_tokens": H01_INPUT_TOKENS,
                "completion_tokens": H01_COMPLETION_TOKENS,
                "reasoning_tokens": H01_REASONING_TOKENS,
                "cost_usd": H01_COST_USD,
            },
            "h02": {
                "input_tokens": H02_INPUT_TOKENS,
                "completion_tokens": H02_COMPLETION_TOKENS,
                "reasoning_tokens": H02_REASONING_TOKENS,
                "cost_usd": H02_COST_USD,
            },
        },
        "cost_notes": {
            "input_tokens_similar": True,
            "h02_completion_and_reasoning_higher": True,
            "single_cause_not_claimed": True,
            "reasoning_tokens_not_predicted": True,
            "no_provider_spend_this_phase": True,
            "1_1_3_clarifies_without_needless_length": True,
        },
        "criteria": [
            {
                "id": "independence",
                "rule": (
                    "The case must be independent of h01 and h02. Do not reuse "
                    "the disputed paraphrase clause or the invented because-clause."
                ),
            },
            {
                "id": "informative_value",
                "rule": (
                    "The case must test a remaining failure mode: catalog "
                    "compliance, origin/attribution framing, or a clean "
                    "supported paraphrase that is not the prior positive canary."
                ),
            },
            {
                "id": "clear_evidence",
                "rule": (
                    "Authorized IDEA/SRC/REF text must be sufficient to judge "
                    "the target clause without neighboring unauthorized handles."
                ),
            },
            {
                "id": "low_benchmark_ambiguity",
                "rule": (
                    "Human label and target clause should be unambiguous. Do "
                    "not select a case whose offline review would remain "
                    "indeterminate."
                ),
            },
            {
                "id": "cost_control",
                "rule": (
                    "Prefer a short paragraph comparable to h01. Do not claim "
                    "a reasoning-token forecast. Observed h02 cost is not a "
                    "budget to repeat."
                ),
            },
            {
                "id": "unresolved_failure",
                "rule": (
                    "The canary should probe a defect this phase cannot prove "
                    "fixed: Terra emitting catalog codes, or applying the "
                    "stabilized verdict definitions."
                ),
            },
        ],
        "not_built": True,
        "not_sent": True,
        "no_remote_request_this_phase": True,
        "secrets_included": False,
    }


__all__ = ["future_canary_selection_criteria"]
