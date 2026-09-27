"""Comparaison offline des trois appels WIN001 réels. Aucune valeur inventée."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.source_analysis_output_ceiling_review.constants import (
    CALL1_SIGNATURE,
    CALL2_SIGNATURE,
    CALL_A_COST,
    CALL_A_FINISH,
    CALL_A_LOCAL,
    CALL_A_OUTPUT,
    CALL_A_PROVIDER_INPUT,
    CALL_A_RATIO,
    CALL_B_COST,
    CALL_B_FINISH,
    CALL_B_LOCAL,
    CALL_B_OUTPUT,
    CALL_B_PROVIDER_INPUT,
    CALL_C_COST,
    CALL_C_FINISH,
    CALL_C_LOCAL,
    CALL_C_OUTPUT,
    CALL_C_PROVIDER_INPUT,
    CALL_C_RATIO,
    CALL_C_THINKING_TOKENS,
    SMALL_SIGNATURE,
)


def build_three_call_comparison() -> dict[str, Any]:
    ratio_a = Decimal(CALL_A_RATIO)
    ratio_c = Decimal(CALL_C_RATIO)
    difference = ratio_a - ratio_c
    return {
        "invented_missing_values": False,
        "calls": [
            {
                "id": "CALL_A",
                "label": "large WIN001 / prompt 1.0",
                "planner": "window-planner-v2.0",
                "prompt": "window-analysis-1.0",
                "signature": CALL1_SIGNATURE,
                "local_estimate": CALL_A_LOCAL,
                "provider_input": CALL_A_PROVIDER_INPUT,
                "input_ratio": CALL_A_RATIO,
                "output_tokens": CALL_A_OUTPUT,
                "finish_reason": CALL_A_FINISH,
                "structured_parse": "FAIL",
                "cost_usd": CALL_A_COST,
                "thinking_tokens": None,
                "thinking_tokens_status": "UNKNOWN",
                "http_forensics": "ABSENT_AT_TIME_OF_CALL",
            },
            {
                "id": "CALL_B",
                "label": "large WIN001 / prompt 1.1",
                "planner": "window-planner-v2.0",
                "prompt": "window-analysis-1.1",
                "signature": CALL2_SIGNATURE,
                "local_estimate": CALL_B_LOCAL,
                "provider_input": CALL_B_PROVIDER_INPUT,
                "input_ratio": None,
                "output_tokens": CALL_B_OUTPUT,
                "finish_reason": CALL_B_FINISH,
                "structured_parse": "AIResponseError",
                "cost_usd": CALL_B_COST,
                "thinking_tokens": None,
                "thinking_tokens_status": "UNKNOWN",
                "body_status": "LOST_HISTORICALLY",
            },
            {
                "id": "CALL_C",
                "label": "small WIN001 / prompt 1.1",
                "planner": "window-planner-v2.1-small",
                "prompt": "window-analysis-1.1",
                "signature": SMALL_SIGNATURE,
                "local_estimate": CALL_C_LOCAL,
                "provider_input": CALL_C_PROVIDER_INPUT,
                "input_ratio": CALL_C_RATIO,
                "output_tokens": CALL_C_OUTPUT,
                "finish_reason": CALL_C_FINISH,
                "structured_parse": "FAIL",
                "parse_condition": "unterminated JSON",
                "cost_usd": CALL_C_COST,
                "thinking_tokens": CALL_C_THINKING_TOKENS,
                "thinking_tokens_status": "PROVEN",
                "http_forensics": "AVAILABLE",
            },
        ],
        "input_ratios": {
            "call_a": CALL_A_RATIO,
            "call_c": CALL_C_RATIO,
            "difference_a_minus_c": format(difference, "f"),
            "difference_percent_of_a": format(
                (difference / ratio_a * Decimal("100")).quantize(Decimal("0.0001")),
                "f",
            ),
            "not_a_universal_conversion_factor": True,
            "estimator_bias_note": (
                "Both observed ratios sit near 2.14–2.16. The 0.013414 "
                "gap is useful local-estimator evidence, not a provider law."
            ),
        },
        "output_ceiling": {
            "call_a_output": CALL_A_OUTPUT,
            "call_c_output": CALL_C_OUTPUT,
            "both_hit_32000": True,
            "call_c_local_was_about_half_of_call_a": True,
            "shrinking_input_prevented_32k_output": False,
            "proves_smaller_windows_useless": False,
            "proves_input_reduction_alone_insufficient": True,
        },
    }
