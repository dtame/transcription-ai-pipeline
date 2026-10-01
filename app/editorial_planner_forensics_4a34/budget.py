"""Future 1.0.2 input/output/cost. Calibrated on A.3.3 actuals. 0 provider."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any

from app.ai.estimation import estimate_tokens
from app.ai.pricing import build_default_catalog
from app.editorial_planner_forensics_4a34.constants import (
    A2_CONSERVATIVE_OUTPUT_TOKENS,
    A2_EXPECTED_OUTPUT_TOKENS,
    A2_HARD_OUTPUT_TOKENS,
    A3_COST_USD,
    A33_COST_USD,
    A33_INPUT_TOKENS,
    A33_OUTPUT_TOKENS,
    A33_THINKING_TOKENS,
    A34_COST_USD,
    MAX_OUTPUT_TOKENS,
    MODEL,
    PROVIDER,
)
from app.editorial_planner_forensics_4a34.payload import encode_payload
from app.editorial_planner_preflight_4a2.costing import estimate_pair, long_context_status
from app.editorial_planning.budget import (
    _PROVIDER_CHARS_PER_TOKEN_MID,
    _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC,
    usable_input_budget,
)


def _provider_tokens(chars: int, chars_per_token: float) -> int:
    return int(math.ceil(max(0, chars) / chars_per_token))


def _as_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def measure_input_budget(
    *,
    system: str,
    user: str,
    payload: dict[str, Any],
    a33_payload_utf8_bytes: int,
    selected_max_output: int = MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    local = estimate_tokens(system + "\n" + user, model=MODEL)
    request_chars = len(system) + len(user)
    encoded = encode_payload(payload)
    payload_chars = len(encoded)
    payload_utf8 = len(encoded.encode("utf-8"))
    mid = _provider_tokens(request_chars, _PROVIDER_CHARS_PER_TOKEN_MID)
    pessimistic = _provider_tokens(
        request_chars, _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC
    )
    payload_pessimistic = _provider_tokens(
        payload_chars, _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC
    )
    density = a33_payload_utf8_bytes / A33_INPUT_TOKENS if A33_INPUT_TOKENS else 2.75
    a33_calibrated = _provider_tokens(payload_utf8, density)
    usable = usable_input_budget(max_output_tokens=selected_max_output)
    planning_estimate = max(
        local.tokens, pessimistic, payload_pessimistic, a33_calibrated
    )
    headroom = int(usable["usable_input_tokens"]) - planning_estimate
    feasible = planning_estimate < int(usable["usable_input_tokens"])
    return {
        "system_chars": len(system),
        "user_chars": len(user),
        "system_plus_user_chars": request_chars,
        "payload_chars": payload_chars,
        "payload_utf8_bytes": payload_utf8,
        "local_token_estimate": local.to_dict(),
        "provider_adjusted_mid": mid,
        "provider_adjusted_pessimistic": pessimistic,
        "payload_inclusive_pessimistic": payload_pessimistic,
        "a33_calibrated_input": a33_calibrated,
        "planning_input_estimate": planning_estimate,
        "a33_actual_provider_input": A33_INPUT_TOKENS,
        "input_delta_vs_a33_actual": planning_estimate - A33_INPUT_TOKENS,
        "usable": usable,
        "usable_input_tokens": usable["usable_input_tokens"],
        "headroom_tokens": headroom,
        "input_safety": "PASS" if feasible else "FAIL",
        "context_safety": "PASS" if feasible else "FAIL",
        "selected_max_output": selected_max_output,
        "formula": usable["formula"],
    }


def measure_output_budget() -> dict[str, Any]:
    return {
        "prompt_change_materially_alters_output_scenarios": False,
        "expected_output_tokens": A33_OUTPUT_TOKENS,
        "conservative_output_tokens": A2_CONSERVATIVE_OUTPUT_TOKENS,
        "hard_output_tokens": A2_HARD_OUTPUT_TOKENS,
        "selected_max_output": MAX_OUTPUT_TOKENS,
        "a33_actual_output": A33_OUTPUT_TOKENS,
        "a33_actual_thinking": A33_THINKING_TOKENS,
        "a2_expected_output_tokens": A2_EXPECTED_OUTPUT_TOKENS,
        "thinking_may_reappear_under_provider_default": True,
        "output_budget_redesign": False,
        "max_output_changed": False,
        "output_fits_selected": A2_HARD_OUTPUT_TOKENS < MAX_OUTPUT_TOKENS,
        "output_cap_failure_a33": "NO",
    }


def future_cost_estimate(
    *,
    input_tokens: int,
    expected_output: int,
    conservative_output: int,
    hard_output: int,
) -> dict[str, Any]:
    catalog = build_default_catalog()
    a33_check = catalog.estimate_cost(
        PROVIDER,
        MODEL,
        A33_INPUT_TOKENS,
        A33_OUTPUT_TOKENS,
    )
    expected = estimate_pair(input_tokens=input_tokens, output_tokens=expected_output)
    conservative = estimate_pair(
        input_tokens=input_tokens, output_tokens=conservative_output
    )
    hard = estimate_pair(input_tokens=input_tokens, output_tokens=hard_output)
    thinking_reappear = estimate_pair(
        input_tokens=input_tokens,
        output_tokens=expected_output,
    )
    return {
        "cost_status_mark": "ESTIMATED",
        "not_actual": True,
        "a34_actual_usd": A34_COST_USD,
        "do_not_double_count": {
            "a3_usd": A3_COST_USD,
            "a33_usd": A33_COST_USD,
            "a34_usd": A34_COST_USD,
        },
        "a33_actual_calibration": {
            "input_tokens": A33_INPUT_TOKENS,
            "output_tokens": A33_OUTPUT_TOKENS,
            "thinking_tokens": A33_THINKING_TOKENS,
            "cost_usd": A33_COST_USD,
            "catalog_recompute": _as_float(a33_check.total_cost),
            "note": (
                "A.3.3 actual 41945 / 10800 / 0 thinking = 0.4797250 USD "
                "is the primary calibration. Thinking may reappear under "
                "provider_default and is not assumed to stay 0."
            ),
        },
        "pricing": {
            "provider": PROVIDER,
            "model": MODEL,
            "input_cost_per_1m": 5.00,
            "output_cost_per_1m": 25.00,
            "source": "Phase 2B catalog / A.3.3 actual",
        },
        "long_context": long_context_status(input_tokens),
        "expected": expected,
        "conservative": conservative,
        "hard": hard,
        "thinking_reappear_acknowledged": True,
        "thinking_reappear_estimate_note": (
            "If thinking returns near the A.3 6443-token observation, "
            "add that volume to output-side cost. Not assumed equal."
        ),
        "expected_cost": expected.get("display"),
        "conservative_cost": conservative.get("display"),
        "hard_cost": hard.get("display"),
        "estimated_cost": expected.get("display"),
        "thinking_placeholder": thinking_reappear.get("display"),
    }


__all__ = ["future_cost_estimate", "measure_input_budget", "measure_output_budget"]
