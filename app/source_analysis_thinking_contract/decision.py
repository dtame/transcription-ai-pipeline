"""Sélection architecturale du contrat thinking V2. Pas de qualité empirique."""

from __future__ import annotations

from typing import Any

from app.source_analysis_thinking_contract.constants import (
    FALLBACK_CONTRACT,
    FALLBACK_EFFORT,
    FALLBACK_THINKING_MODE,
    MODE,
    PHASE,
    REAL_PROVIDER_CALL_AUTHORIZED,
    SCHEMA_VERSION,
    SELECTED_CONTRACT,
    SELECTED_EFFORT,
    SELECTED_THINKING_MODE,
)
from app.source_analysis_thinking_contract.options import thinking_mode_options


def thinking_mode_decision() -> dict[str, Any]:
    options = thinking_mode_options()
    selected = next(
        item for item in options["candidates"] if item["name"] == SELECTED_CONTRACT
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "selected_future_contract": SELECTED_CONTRACT,
        "selected_thinking_mode": SELECTED_THINKING_MODE,
        "selected_effort": SELECTED_EFFORT,
        "selected_effort_payload": "omitted",
        "thinking_hard_token_cap": "N/A",
        "why": (
            "window-analysis-1.2 is source-grounded extraction/classification "
            "with a compact structured transport. CALL C failed because "
            "implicit Sonnet 5 adaptive thinking at default high effort "
            "consumed 21911 of the shared 32000 max_tokens. Official contract "
            "supports thinking.type=disabled. Reliability and preserving "
            "visible JSON budget outrank unnecessary hidden reasoning for "
            "this stage. Effort=low/medium remain non-deterministic and "
            "cannot be treated as an 8000-token thinking reserve."
        ),
        "known_benefits": [
            "provider-enforced thinking off",
            "theoretical thinking usage 0 under official contract",
            "highest conceptual JSON budget predictability",
            "lowest latency and cost risk among candidates",
            "does not implement illegal budget_tokens",
        ],
        "unknown_semantic_quality_risk": "UNVERIFIED_REAL",
        "provider_enforcement": selected["classification"],
        "fallback_candidate": FALLBACK_CONTRACT,
        "fallback_thinking_mode": FALLBACK_THINKING_MODE,
        "fallback_effort": FALLBACK_EFFORT,
        "automatic_fallback": False,
        "no_real_authorization": True,
        "real_provider_call_authorized": REAL_PROVIDER_CALL_AUTHORIZED,
        "not_selected": ["ADAPTIVE_LOW", "ADAPTIVE_MEDIUM", "ADAPTIVE_HIGH"],
        "adaptive_high_is_baseline_only": True,
        "quality_evidence": {
            "THINKING_DISABLED": "UNVERIFIED_REAL",
            "ADAPTIVE_LOW": "UNVERIFIED_REAL",
            "ADAPTIVE_MEDIUM": "UNVERIFIED_REAL",
        },
    }


__all__ = ["thinking_mode_decision"]
