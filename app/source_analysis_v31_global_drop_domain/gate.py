"""Porte publication + pré-appel sortie. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_global_drop_domain.constants import (
    PRODUCTION_MAX_OUTPUT_TOKENS,
    SAFETY_70,
    SAFETY_75,
    SAFETY_80,
    SOURCE_MAP_PUBLICATION_AUTHORIZED,
)
from app.source_analysis_v31_global_output_architecture.constants import SAFETY_RATIO


def publication_eligibility(
    *,
    global_validator_ok: bool,
    canonical_reconstruction_ok: bool,
    source_map_authorized: bool = SOURCE_MAP_PUBLICATION_AUTHORIZED,
) -> dict[str, Any]:
    blocked_invalid = not global_validator_ok
    eligible = bool(
        global_validator_ok
        and canonical_reconstruction_ok
        and source_map_authorized
        and SOURCE_MAP_PUBLICATION_AUTHORIZED
    )
    return {
        "publication_eligible": eligible,
        "blocked_because_invalid_transport": blocked_invalid,
        "reconstruction_ok_is_insufficient": bool(
            canonical_reconstruction_ok and not global_validator_ok
        ),
        "source_map_authorized": False,
        "gate": "PASS" if blocked_invalid or not source_map_authorized else "OPEN",
        "rule": (
            "Invalid transport must not become publishable even if canonical "
            "reconstruction technically succeeds."
        ),
    }


def output_precall_gate(
    *,
    expected_tokens: int,
    conservative_tokens: int,
    hard_tokens: int,
    max_output: int = PRODUCTION_MAX_OUTPUT_TOKENS,
    chars_per_token: float,
    safety_factor: float = 1.0,
) -> dict[str, Any]:
    scaled_hard = int(round(hard_tokens * safety_factor))
    thresholds = {
        "70": SAFETY_70,
        "75": SAFETY_75,
        "80": SAFETY_80,
    }
    margins = {key: int(value) - scaled_hard for key, value in thresholds.items()}
    allowed = scaled_hard <= SAFETY_75
    return {
        "allowed": allowed,
        "reason": (
            "hard planning tokens at or below 75% threshold"
            if allowed
            else "hard planning tokens exceed 75% threshold"
        ),
        "expected": expected_tokens,
        "conservative": conservative_tokens,
        "hard": hard_tokens,
        "scaled_hard": scaled_hard,
        "safety_factor": safety_factor,
        "chars_per_token": chars_per_token,
        "max_output": max_output,
        "thresholds": thresholds,
        "margins": margins,
        "safety_ratio_primary": SAFETY_RATIO,
        "real_request_blocked": True,
        "reproducible": True,
        "inputs": [
            "cardinality",
            "schema length bounds",
            "empirical compact-2.0 chars/token",
            "safety factor",
        ],
    }


__all__ = ["output_precall_gate", "publication_eligibility"]
