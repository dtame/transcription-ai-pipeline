"""Décision d'architecture post-A.15. Pas d'activation production."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_local_v2.synthetic import measure_v2_worst_case
from app.source_analysis_v2_a15_forensics.constants import (
    ADAPTIVE_LOW_JUSTIFIED,
    A15_LOCAL_INPUT,
    CANDIDATE_HARD_MAX_INPUT_TOKENS,
    FUTURE_REAL_CALL_AUTHORIZED,
    MODE,
    NEW_PROMPT_VERSION,
    NEW_TRANSPORT_VERSION,
    NEXT_ACTION,
    NEXT_PHASE,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE_STATUS,
    SELECTED_LINK_ARCHITECTURE,
    SEMANTIC_CONTENT_CLASSIFICATION,
    TARGET_JSON_LOCAL_TOKENS,
    WIN001_RETRY_AUTHORIZED,
)
from app.source_analysis_v2_grammar_canary.constants import (
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
)


def build_architecture_decision(
    *,
    prompt_audit: Mapping[str, Any],
    coverage: Mapping[str, Any],
    semantic: Mapping[str, Any],
    options: Mapping[str, Any],
) -> dict[str, Any]:
    worst = measure_v2_worst_case()
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "selected_link_architecture": SELECTED_LINK_ARCHITECTURE,
        "status": SELECTED_ARCHITECTURE_STATUS,
        "implemented": False,
        "new_prompt": NEW_PROMPT_VERSION,
        "new_transport": NEW_TRANSPORT_VERSION,
        "schema_changed": SCHEMA_CHANGED,
        "historical_prompt_1_2_1_mutated": False,
        "historical_transport_v2_mutated": False,
        "server_grammar_status": "A.13 VERIFIED ACCEPTED — still applicable (schema unchanged)",
        "future_grammar_if_schema_changes": "UNVERIFIED",
        "synthetic_max_output_local_tokens": worst.get("local_tokens"),
        "synthetic_target": TARGET_JSON_LOCAL_TOKENS,
        "future_win001_input_estimate": A15_LOCAL_INPUT,
        "future_hard_max_input": CANDIDATE_HARD_MAX_INPUT_TOKENS,
        "future_real_call_authorized": FUTURE_REAL_CALL_AUTHORIZED,
        "win001_retry_authorized": WIN001_RETRY_AUTHORIZED,
        "adaptive_low_justified": ADAPTIVE_LOW_JUSTIFIED,
        "semantic_content_classification": SEMANTIC_CONTENT_CLASSIFICATION,
        "production_default": PRODUCTION_PLANNER_VERSION,
        "candidate_planner_activated": False,
        "source_map": "NOT PUBLISHED",
        "phase_3b": PHASE_3B_STATUS,
        "next_phase": NEXT_PHASE,
        "next_action": NEXT_ACTION,
        "prompt_ambiguity_remaining": bool(prompt_audit.get("ambiguity_remaining")),
        "coverage_pct": coverage.get("semantic_src_coverage_pct"),
        "unsupported_count": (semantic.get("grounding_counts") or {}).get("UNSUPPORTED"),
        "raw_schema_bytes": EXPECTED_RAW_SCHEMA_BYTES,
        "adapted_schema_bytes": EXPECTED_ADAPTED_SCHEMA_BYTES,
        "why": (
            "Invalid links are correct global indexes of TOPIC records. "
            "Per-kind ordinals would silently remap those numbers onto IDEAs. "
            "Prompt-only hardening already failed once (A.14→A.15). "
            "Symbolic handles keep kind visible and move arithmetic to Python."
        ),
        "future_call_would_test": (
            "Not authorized. If later authorized, test the new handle contract "
            "on WIN001 — not a retry of window-analysis-1.2.1."
        ),
        "options_selected_from": options.get("selected"),
    }


__all__ = ["build_architecture_decision"]
