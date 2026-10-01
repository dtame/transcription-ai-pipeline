"""Porte de sortie pré-appel. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_global_output_architecture.constants import (
    NEXT_MAX_OUTPUT_TOKENS,
    SAFETY_RATIO,
)
from app.source_analysis_v31_global_output_architecture.estimator import estimate_output


def pre_call_output_gate(
    estimate: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = dict(estimate) if estimate is not None else estimate_output(**kwargs)
    hard = int((payload.get("provider_planning_tokens") or {}).get("hard") or 0)
    expected = int((payload.get("provider_planning_tokens") or {}).get("expected") or 0)
    max_output = int(payload.get("max_output") or NEXT_MAX_OUTPUT_TOKENS)
    safety = int(payload.get("safety_target") or int(max_output * SAFETY_RATIO))
    allowed = hard <= safety
    return {
        "allowed": allowed,
        "reason": (
            "predicted worst-case output is below the safety threshold"
            if allowed
            else "predicted worst-case output exceeds the safety threshold"
        ),
        "predicted_expected": expected,
        "predicted_hard": hard,
        "max_output": max_output,
        "safety_threshold": safety,
        "safety_ratio": SAFETY_RATIO,
        "real_request_blocked": not allowed,
        "telemetry_required_after_call": [
            "predicted_output",
            "actual_output",
            "error_ratio",
        ],
        "estimate": payload,
    }


__all__ = ["pre_call_output_gate"]
