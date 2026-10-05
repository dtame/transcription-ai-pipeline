"""Historical cost comparison and hypothetical B/C estimates. No provider call."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b28.constants import (
    H01_COMPLETION_TOKENS,
    H01_COST_USD,
    H01_INPUT_TOKENS,
    H01_REASONING_TOKENS,
    H02_COMPLETION_TOKENS,
    H02_COST_USD,
    H02_INPUT_TOKENS,
    H02_REASONING_TOKENS,
    H11_COMPLETION_TOKENS,
    H11_COST_USD,
    H11_INPUT_TOKENS,
    H11_REASONING_TOKENS,
    PHASE,
    PROMPT_VERSION_113,
)


def cost_comparison() -> dict[str, Any]:
    observed = {
        "h01": {
            "input_tokens": H01_INPUT_TOKENS,
            "completion_tokens": H01_COMPLETION_TOKENS,
            "reasoning_tokens": H01_REASONING_TOKENS,
            "cost_usd": H01_COST_USD,
            "claim_count": 7,
            "contract": "book-semantic-validator-1.1-candidate",
            "evidence_level": "OBSERVED",
        },
        "h02": {
            "input_tokens": H02_INPUT_TOKENS,
            "completion_tokens": H02_COMPLETION_TOKENS,
            "reasoning_tokens": H02_REASONING_TOKENS,
            "cost_usd": H02_COST_USD,
            "claim_count": 11,
            "contract": "book-semantic-validator-1.1.1-candidate",
            "evidence_level": "OBSERVED",
        },
        "h11": {
            "input_tokens": H11_INPUT_TOKENS,
            "completion_tokens": H11_COMPLETION_TOKENS,
            "reasoning_tokens": H11_REASONING_TOKENS,
            "cost_usd": H11_COST_USD,
            "claim_count": 7,
            "contract": PROMPT_VERSION_113,
            "evidence_level": "OBSERVED",
        },
    }
    return {
        "phase": PHASE,
        "provider_calls_this_phase": 0,
        "not_a_provider_invoice": True,
        "pricing_source": "configured project rates dated 2026-09-18",
        "input_usd_per_1m": 2.0,
        "output_usd_per_1m": 12.0,
        "reasoning_included_in_completion_not_billed_twice": True,
        "latency_not_invented": True,
        "observed": observed,
        "observations": [
            "h01 and h02 input tokens are similar (1654 vs 1692).",
            "h02 completion 5221 and reasoning 4595 greatly exceed h01 1292 / 985.",
            "h11 input 2562 exceeds h01/h02; 1.1.3-candidate is longer than 1.1/1.1.1.",
            "h11 reasoning 1647 is between h01 and h02. No single factor is claimed.",
            "Claim count alone does not explain h02 cost (11 claims vs h11 7 claims but h02 costs more).",
        ],
        "architecture_a_cost": "Observed historical costs above. No new spend.",
        "architecture_b_hypothetical": {
            "evidence_level": "HYPOTHESIS",
            "input_tokens": (
                "May fall if coverage/offset instructions are removed, or rise slightly "
                "if unit id lists are added. Not measured."
            ),
            "output_tokens": (
                "May fall if the model omits s/e/t copies and emits only id, k, ev, r, n."
            ),
            "reasoning_tokens": (
                "Unknown. Must not assert that presegmentation reduces reasoning tokens. "
                "h02 shows reasoning can dominate regardless of input similarity."
            ),
            "must_not_claim_savings": True,
        },
        "architecture_c_hypothetical": {
            "evidence_level": "HYPOTHESIS",
            "same_caveats_as_b": True,
            "local_cpu": "Not measured; expected negligible versus Terra. NOT_TESTED.",
        },
        "limitations": [
            "No new telemetry.",
            "No latency figures.",
            "No consumption figures beyond saved token counts.",
            "Estimates are explicitly hypothetical.",
        ],
        "secrets_included": False,
    }


__all__ = ["cost_comparison"]
