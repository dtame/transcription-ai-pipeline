"""Input context budget against the selected production max_output."""

from __future__ import annotations

import math
from typing import Any

from app.ai.estimation import estimate_tokens
from app.editorial_planner_preflight_4a2.constants import (
    A1_INPUT_TOKENS,
    A1_PAYLOAD_CHARS,
    MODEL,
    PHASE_4A_LOCAL_INPUT_ESTIMATE,
    PHASE_4A_PROVIDER_ADJUSTED_PESSIMISTIC,
)
from app.editorial_planner_preflight_4a2.payload import encode_payload
from app.editorial_planning.budget import (
    _PROVIDER_CHARS_PER_TOKEN_MID,
    _PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC,
    usable_input_budget,
)
from app.editorial_planning.settings import frozen_production_settings


def _provider_tokens(chars: int, chars_per_token: float) -> int:
    return int(math.ceil(max(0, chars) / chars_per_token))


def measure_input_budget_selected(
    *,
    system: str,
    user: str,
    payload: dict[str, Any],
    selected_max_output: int,
) -> dict[str, Any]:
    settings = frozen_production_settings()
    local = estimate_tokens(system + "\n" + user, model=settings.model)
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
    a1_density = A1_PAYLOAD_CHARS / A1_INPUT_TOKENS
    a1_calibrated = _provider_tokens(payload_chars, a1_density)
    usable = usable_input_budget(max_output_tokens=selected_max_output)
    planning_estimate = max(local.tokens, pessimistic, payload_pessimistic, a1_calibrated)
    headroom = int(usable["usable_input_tokens"]) - planning_estimate
    feasible = planning_estimate < int(usable["usable_input_tokens"])
    return {
        "methods": {
            "local": (
                "app.ai.estimation.estimate_tokens(system + newline + user, "
                f"model={MODEL}) — existing repository estimator used by Phase 4A"
            ),
            "provider_adjusted_mid": (
                f"ceil((system+user chars) / {_PROVIDER_CHARS_PER_TOKEN_MID})"
            ),
            "provider_adjusted_pessimistic": (
                f"ceil((system+user chars) / {_PROVIDER_CHARS_PER_TOKEN_PESSIMISTIC}) "
                "Phase 3B A.44 density — Phase 4A comparison method"
            ),
            "payload_inclusive_pessimistic": (
                "same pessimistic density applied to the exact provider payload "
                "(includes adapted JSON schema)"
            ),
            "a1_calibrated_payload": (
                f"ceil(payload_chars / {a1_density}) using A.1 actual "
                f"input_tokens={A1_INPUT_TOKENS} vs payload_chars={A1_PAYLOAD_CHARS}"
            ),
            "planning_estimate": (
                "max(local, system+user pessimistic, payload pessimistic, "
                "A.1-calibrated payload) — used for safety, not billing"
            ),
        },
        "system_chars": len(system),
        "user_chars": len(user),
        "system_plus_user_chars": request_chars,
        "payload_chars": payload_chars,
        "payload_utf8_bytes": len(encoded.encode("utf-8")),
        "local_token_estimate": local.to_dict(),
        "provider_adjusted_mid": mid,
        "provider_adjusted_pessimistic": pessimistic,
        "payload_inclusive_pessimistic": payload_pessimistic,
        "a1_calibrated_input": a1_calibrated,
        "planning_input_estimate": planning_estimate,
        "phase_4a_local": PHASE_4A_LOCAL_INPUT_ESTIMATE,
        "phase_4a_provider_adjusted_pessimistic": PHASE_4A_PROVIDER_ADJUSTED_PESSIMISTIC,
        "local_delta_vs_phase4a": local.tokens - PHASE_4A_LOCAL_INPUT_ESTIMATE,
        "provider_adjusted_delta_vs_phase4a": (
            pessimistic - PHASE_4A_PROVIDER_ADJUSTED_PESSIMISTIC
        ),
        "usable": usable,
        "usable_input_tokens": usable["usable_input_tokens"],
        "headroom_tokens": headroom,
        "input_safety": "PASS" if feasible else "FAIL",
        "one_global_call_feasible": feasible,
        "selected_max_output": selected_max_output,
        "model_context_window": usable["context_window"],
        "model_max_output_tokens": usable["model_max_output_tokens"],
        "safety_ratio": usable["safety_ratio"],
        "formula": usable["formula"],
        "web_research": False,
    }


__all__ = ["measure_input_budget_selected"]
