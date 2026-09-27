"""Matrice des contrats thinking V2. Aucun score numérique."""

from __future__ import annotations

from typing import Any

from app.ai.thinking import conceptual_json_budget
from app.source_analysis_thinking_contract.constants import (
    CALL_C_THINKING_TOKENS,
    MAX_OUTPUT_TOKENS_FROZEN,
    MODE,
    PHASE,
    SCHEMA_VERSION,
    TARGET_JSON_LOCAL_TOKENS,
)


def _row(
    *,
    name: str,
    officially_supported: bool,
    thinking_hard_capped: str,
    thinking_disabled: bool,
    json_budget_predictability: str,
    latency_risk: str,
    cost_risk: str,
    call_c_relevance: str,
    implementation_complexity: str,
    classification: dict[str, Any],
    conceptual_budget: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "officially_supported": officially_supported,
        "thinking_hard_capped": thinking_hard_capped,
        "thinking_disabled": thinking_disabled,
        "semantic_quality_evidence": "UNVERIFIED_REAL",
        "json_budget_predictability": json_budget_predictability,
        "latency_risk": latency_risk,
        "cost_risk": cost_risk,
        "call_c_relevance": call_c_relevance,
        "implementation_complexity": implementation_complexity,
        "future_verification_needed": True,
        "classification": classification,
        "conceptual_json_budget": conceptual_budget,
    }


def thinking_mode_options() -> dict[str, Any]:
    disabled_budget = conceptual_json_budget(
        max_output=MAX_OUTPUT_TOKENS_FROZEN, thinking_disabled=True
    )
    adaptive_budget = conceptual_json_budget(
        max_output=MAX_OUTPUT_TOKENS_FROZEN, thinking_disabled=False
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "numeric_score": None,
        "weighted_ranking": False,
        "semantic_json_worst_case_local_tokens": TARGET_JSON_LOCAL_TOKENS,
        "max_output_unchanged": MAX_OUTPUT_TOKENS_FROZEN,
        "call_c_thinking_tokens": CALL_C_THINKING_TOKENS,
        "candidates": [
            _row(
                name="THINKING_DISABLED",
                officially_supported=True,
                thinking_hard_capped="N/A",
                thinking_disabled=True,
                json_budget_predictability="highest_theoretical",
                latency_risk="lowest",
                cost_risk="lowest",
                call_c_relevance=(
                    "Avoids the implicit adaptive/high path that exhausted "
                    "shared max_tokens on CALL C"
                ),
                implementation_complexity="low",
                classification={
                    "thinking": "THINKING_PROVIDER_ENFORCED_DISABLED",
                    "semantic_output": "SEMANTIC_OUTPUT_APPLICATION_BOUNDED",
                    "total_output": "TOTAL_OUTPUT_PROVIDER_CAPPED",
                    "fully_provider_bounded": False,
                },
                conceptual_budget=disabled_budget,
            ),
            _row(
                name="ADAPTIVE_LOW",
                officially_supported=True,
                thinking_hard_capped="NO",
                thinking_disabled=False,
                json_budget_predictability="not_deterministic",
                latency_risk="medium",
                cost_risk="medium",
                call_c_relevance=(
                    "Still adaptive; effort=low is not a token cap. "
                    "Thinking amount unknown."
                ),
                implementation_complexity="low",
                classification={
                    "thinking": "THINKING_PROVIDER_ADAPTIVE",
                    "effort": "EFFORT_PROVIDER_CONTROLLED_LOW",
                    "thinking_token_count": "THINKING_TOKEN_COUNT_NOT_HARD_CAPPED",
                    "semantic_output": "SEMANTIC_OUTPUT_APPLICATION_BOUNDED",
                    "total_output": "TOTAL_OUTPUT_PROVIDER_CAPPED",
                    "fully_provider_bounded": False,
                },
                conceptual_budget=adaptive_budget,
            ),
            _row(
                name="ADAPTIVE_MEDIUM",
                officially_supported=True,
                thinking_hard_capped="NO",
                thinking_disabled=False,
                json_budget_predictability="not_deterministic",
                latency_risk="medium_high",
                cost_risk="medium_high",
                call_c_relevance=(
                    "Closer to default high than disabled. Thinking not capped."
                ),
                implementation_complexity="low",
                classification={
                    "thinking": "THINKING_PROVIDER_ADAPTIVE",
                    "effort": "EFFORT_PROVIDER_CONTROLLED_MEDIUM",
                    "thinking_token_count": "THINKING_TOKEN_COUNT_NOT_HARD_CAPPED",
                    "semantic_output": "SEMANTIC_OUTPUT_APPLICATION_BOUNDED",
                    "total_output": "TOTAL_OUTPUT_PROVIDER_CAPPED",
                    "fully_provider_bounded": False,
                },
                conceptual_budget=adaptive_budget,
            ),
            _row(
                name="ADAPTIVE_HIGH",
                officially_supported=True,
                thinking_hard_capped="NO",
                thinking_disabled=False,
                json_budget_predictability="lowest",
                latency_risk="highest_observed",
                cost_risk="highest_observed",
                call_c_relevance=(
                    "Historical effective CALL C contract. Exhausted shared "
                    "32000 output (thinking 21911). Comparison baseline only."
                ),
                implementation_complexity="none_already_default",
                classification={
                    "thinking": "THINKING_PROVIDER_ADAPTIVE",
                    "effort": "EFFORT_PROVIDER_CONTROLLED_HIGH_DEFAULT",
                    "thinking_token_count": "THINKING_TOKEN_COUNT_NOT_HARD_CAPPED",
                    "semantic_output": "SEMANTIC_OUTPUT_APPLICATION_BOUNDED",
                    "total_output": "TOTAL_OUTPUT_PROVIDER_CAPPED",
                    "fully_provider_bounded": False,
                },
                conceptual_budget=adaptive_budget,
            ),
        ],
        "task_character": {
            "window_analysis_1_2": [
                "source-grounded semantic extraction",
                "classification",
                "compact structured representation",
                "traceability",
            ],
            "not": [
                "open-ended mathematical reasoning",
                "agentic tool use",
                "coding",
                "long-horizon planning",
            ],
        },
    }


__all__ = ["thinking_mode_options"]
