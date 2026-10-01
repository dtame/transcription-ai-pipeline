"""Input / output / context budget for the 1.0.1 request. Offline estimate."""

from __future__ import annotations

import math
from typing import Any

from app.ai.estimation import estimate_tokens
from app.editorial_planner_canary_4a3.constants import EXPECTED_REQUEST_UTF8_BYTES
from app.editorial_planner_language_policy_4a32.constants import (
    A2_CONSERVATIVE_OUTPUT_TOKENS,
    A2_EXPECTED_OUTPUT_TOKENS,
    A2_HARD_OUTPUT_TOKENS,
    A2_LOCAL_INPUT_ESTIMATE,
    A2_PROVIDER_ADJUSTED_PESSIMISTIC,
    A3_INPUT_TOKENS,
    A3_OUTPUT_TOKENS,
    A3_THINKING_TOKENS,
    MAX_OUTPUT_TOKENS,
    MODEL,
)
from app.editorial_planner_language_policy_4a32.payload import encode_payload
from app.editorial_planning.budget import (
    _PROVIDER_CHARS_PER_TOKEN_MID,
    _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC,
    usable_input_budget,
)


def _provider_tokens(chars: int, chars_per_token: float) -> int:
    return int(math.ceil(max(0, chars) / chars_per_token))


def measure_input_budget(
    *,
    system: str,
    user: str,
    payload: dict[str, Any],
    selected_max_output: int = MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    local = estimate_tokens(system + "\n" + user, model=MODEL)
    request_chars = len(system) + len(user)
    encoded = encode_payload(payload)
    payload_chars = len(encoded)
    mid = _provider_tokens(request_chars, _PROVIDER_CHARS_PER_TOKEN_MID)
    pessimistic = _provider_tokens(
        request_chars, _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC
    )
    payload_pessimistic = _provider_tokens(
        payload_chars, _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC
    )
    a3_density = EXPECTED_REQUEST_UTF8_BYTES / A3_INPUT_TOKENS
    a3_calibrated = _provider_tokens(payload_chars, a3_density)
    usable = usable_input_budget(max_output_tokens=selected_max_output)
    planning_estimate = max(
        local.tokens, pessimistic, payload_pessimistic, a3_calibrated
    )
    headroom = int(usable["usable_input_tokens"]) - planning_estimate
    feasible = planning_estimate < int(usable["usable_input_tokens"])
    return {
        "system_chars": len(system),
        "user_chars": len(user),
        "system_plus_user_chars": request_chars,
        "payload_chars": payload_chars,
        "payload_utf8_bytes": len(encoded.encode("utf-8")),
        "local_token_estimate": local.to_dict(),
        "provider_adjusted_mid": mid,
        "provider_adjusted_pessimistic": pessimistic,
        "payload_inclusive_pessimistic": payload_pessimistic,
        "a3_calibrated_input": a3_calibrated,
        "planning_input_estimate": planning_estimate,
        "a3_actual_provider_input": A3_INPUT_TOKENS,
        "input_delta_vs_a3_actual": planning_estimate - A3_INPUT_TOKENS,
        "a2_local": A2_LOCAL_INPUT_ESTIMATE,
        "a2_provider_adjusted_pessimistic": A2_PROVIDER_ADJUSTED_PESSIMISTIC,
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
        "expected_output_tokens": A2_EXPECTED_OUTPUT_TOKENS,
        "conservative_output_tokens": A2_CONSERVATIVE_OUTPUT_TOKENS,
        "hard_output_tokens": A2_HARD_OUTPUT_TOKENS,
        "selected_max_output": MAX_OUTPUT_TOKENS,
        "a3_actual_output": A3_OUTPUT_TOKENS,
        "a3_actual_thinking": A3_THINKING_TOKENS,
        "thinking_calibration_evidence": A3_THINKING_TOKENS,
        "future_thinking_not_assumed_equal": True,
        "output_budget_redesign": False,
        "output_fits_selected": A2_HARD_OUTPUT_TOKENS < MAX_OUTPUT_TOKENS,
    }


__all__ = ["measure_input_budget", "measure_output_budget"]
