"""Readiness d'un futur appel payant. Non autorisé. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis_hybrid.contracts import WindowInput
from app.source_analysis_v3_a25_forensics.constants import (
    FUTURE_REAL_CALL_AUTHORIZED,
    FUTURE_REAL_CALL_READY,
    FUTURE_REAL_CALL_TYPE,
    MODE,
    NEXT_PHASE_LABEL,
    PHASE,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    SERVER_GRAMMAR_STATUS,
    WIN004_RETRY_AUTHORIZED,
)


def build_future_readiness(
    window: WindowInput,
    transcript: TranscriptInput,
    *,
    architecture: Mapping[str, Any],
    tests: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "future_real_call_type": FUTURE_REAL_CALL_TYPE,
        "future_real_call_ready": FUTURE_REAL_CALL_READY,
        "future_real_call_authorized": FUTURE_REAL_CALL_AUTHORIZED,
        "win004_retry_authorized": WIN004_RETRY_AUTHORIZED,
        "do_not_assume_next_call_is_win004": True,
        "selected_architecture": SELECTED_ARCHITECTURE,
        "schema_changed": SCHEMA_CHANGED,
        "server_grammar_status": SERVER_GRAMMAR_STATUS,
        "if_schema_unchanged_after_implementation": (
            "A later WIN004 retry may be appropriate after the new local "
            "metadata contract. Not now."
        ),
        "if_schema_changed_later": (
            "Next real call should be a tiny grammar/config canary first, "
            "not pastoral WIN004. Not authorized."
        ),
        "next_phase_candidates": {
            "A_offline_implementation_follow_up": {
                "selected": True,
                "reason": "GLOBALIZE_IDEA_SUBTYPE is designed, not implemented.",
            },
            "B_tiny_grammar_canary": {
                "selected": False,
                "reason": "Schema bytes unchanged; no new grammar to prove.",
            },
            "C_one_win004_retry": {
                "selected": False,
                "reason": "Prompt-only 1.3.3 is rejected. Contract must change first.",
            },
            "D_another_offline_semantic_redesign": {
                "selected": False,
                "reason": "Architecture is selected. Implementation is the gap.",
            },
        },
        "cost_gate_before_any_future_paid_call": {
            "exact_purpose": "not applicable — no paid call is ready",
            "new_uncertainty_the_call_would_resolve": None,
            "why_offline_tests_cannot_resolve_it": (
                "Offline tests cannot prove a new server grammar. They can "
                "prove a local-kind-omitted contract once implemented."
            ),
            "maximum_calls": 0,
            "stop_condition": "No paid call in the next phase unless separately authorized.",
        },
        "window_id": window.window_id,
        "transcript_id": transcript.transcript_id,
        "architecture_implementation_scope": architecture.get("selected_spec", {}).get(
            "implementation_scope"
        ),
        "next_phase_label": NEXT_PHASE_LABEL,
        "tests": tests,
        "thinking_mode_switch_authorized": False,
        "adaptive_low_shares_max_output": True,
        "call_c_evidence_still_applies": True,
    }


__all__ = ["build_future_readiness"]
