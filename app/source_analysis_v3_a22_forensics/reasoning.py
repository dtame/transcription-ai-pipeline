"""Décision offline thinking / retry. 0 appel provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v3_a22_forensics.constants import (
    A22_CAPACITY_SIGNAL,
    A22_LOCAL_INPUT,
    A22_MAX_OUTPUT,
    A22_OUTPUT,
    A22_PROVIDER_INPUT,
    A22_THINKING,
    A22_THINKING_TOKENS,
    A22_WORDS,
    MODE,
    PHASE,
    SCHEMA_VERSION,
    SELECTED_NEXT_STRATEGY,
    SEMANTIC_COUNTERFACTUAL,
    SEMANTIC_INADEQUACY_ROOT_CAUSE,
    THINKING_DISABLED_EVIDENCE,
)


def build_reasoning_decision(
    *,
    semantic: Mapping[str, Any],
    contract: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    options = {
        "A_THINKING_DISABLED_PLUS_HARDENED_PROMPT": {
            "selected": True,
            "justification": (
                "A.22 completed normally (HTTP 200, end_turn, 12719/32000, "
                "thinking tokens 0). Independent semantic review is acceptable "
                "once the four IDEA metadata tokens are set aside. A.21 already "
                "passed the same thinking-disabled + 1.3.1 contract on WIN001. "
                "The failure is a type-contract slip explained by prompt "
                "ambiguity, so compact 1.3.2 hardening is the first remedy."
            ),
        },
        "B_ADAPTIVE_LOW": {
            "selected": False,
            "justification": (
                "Do not switch to adaptive-low merely because A.22 marked "
                "quality INADEQUATE. That mark was the technical V3 gate, not "
                "an independent extraction failure. Adaptive-low remains an "
                "untested hypothesis for format slips."
            ),
        },
        "C_OTHER": {
            "selected": False,
            "justification": "No other supported reasoning configuration is indicated.",
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "semantic_counterfactual": SEMANTIC_COUNTERFACTUAL,
        "semantic_inadequacy_root_cause": SEMANTIC_INADEQUACY_ROOT_CAUSE,
        "thinking_disabled_evidence": THINKING_DISABLED_EVIDENCE,
        "thinking_disabled_classification": {
            "evidence": [
                "A.21 PASS on WIN001 with thinking disabled + window-analysis-1.3.1",
                "A.22 HTTP 200, finish end_turn, structured parse PASS",
                "A.22 output 12719 < 32000 — no max-token pressure",
                "A.22 thinking tokens = 0 as contracted",
                "capacity signal absent",
                "window size comparable to WIN001 (5662 words / 22656 local / 48249 provider)",
                "independent review ACCEPTABLE_FOR_LOCAL_EXTRACTION if technical_ok",
                "54/58 IDEA kinds already used the valid vocabulary",
                "matching EXAMPLE records were also emitted — not an extraction blank",
            ],
            "hypothesis": [
                "Disabled thinking may increase rare format/taxonomy slips. Unproven.",
            ],
            "unknown": [
                "Whether adaptive-low would have avoided IDEA m[0]=example.",
            ],
        },
        "do_not_attribute_to_truncation": True,
        "do_not_attribute_to_capacity": A22_CAPACITY_SIGNAL == "absent",
        "do_not_attribute_to_abnormal_window_size": True,
        "output_budget": {
            "actual": A22_OUTPUT,
            "max": A22_MAX_OUTPUT,
            "pressure": False,
        },
        "window_size": {
            "words": A22_WORDS,
            "local_input": A22_LOCAL_INPUT,
            "provider_input": A22_PROVIDER_INPUT,
            "comparable_to_win001": True,
        },
        "thinking": A22_THINKING,
        "thinking_tokens": A22_THINKING_TOKENS,
        "prompt_hardening_sufficient": bool(contract.get("prompt_hardening_justified")),
        "schema_change_required": False,
        "transport_redesign_required": False,
        "immediate_win004_retry_recommended": False,
        "separately_authorized_retry_reasonable": True,
        "offline_architecture_redesign_required_first": False,
        "selected_next_strategy": SELECTED_NEXT_STRATEGY,
        "options": options,
        "inventory_root_violations": inventory.get("total_latent_root_violations"),
        "official_a22_quality": semantic.get("a22_reported_quality"),
        "independent_quality": semantic.get("semantic_quality"),
    }


__all__ = ["build_reasoning_decision"]
