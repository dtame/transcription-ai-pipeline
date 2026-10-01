"""Décision de gel fonctionnel de l'extraction locale. Ne supprime aucun code historique."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_global_preflight.constants import (
    FROZEN_GRANULARITY,
    FROZEN_PLANNER,
    FROZEN_PROMPT,
    FROZEN_SRC_POLICY,
    FROZEN_TRANSPORT,
    LOCAL_EXTRACTION_FREEZE_CANDIDATE,
    MODE,
    PHASE,
    PRODUCTION_PLANNER_VERSION,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_VERSION,
)


def build_freeze_decision(
    *,
    all_ready: bool,
    mixed_ok: bool,
    tests_green: bool,
    normalized_ok: bool,
    traceability_ok: bool,
    source_map_absent: bool,
    provider_calls: int,
) -> dict[str, Any]:
    conditions = {
        "ready_7_of_7": all_ready,
        "mixed_compatibility_pass": mixed_ok,
        "tests_green": tests_green,
        "normalized_consolidation_input_built": normalized_ok,
        "no_hidden_traceability_gap": traceability_ok,
        "source_map_absent": source_map_absent,
        "provider_calls_zero": provider_calls == 0,
    }
    frozen = all(conditions.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "LOCAL_EXTRACTION_FREEZE_CANDIDATE": LOCAL_EXTRACTION_FREEZE_CANDIDATE,
        "LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN": "YES" if frozen else "NO",
        "means": (
            "Future work should move to consolidation rather than continuing "
            "to tune local extraction. Historical code is not deleted."
        ),
        "frozen_architecture": {
            "planner": FROZEN_PLANNER,
            "production_planner_unchanged": PRODUCTION_PLANNER_VERSION,
            "prompt": FROZEN_PROMPT,
            "transport": FROZEN_TRANSPORT,
            "granularity": FROZEN_GRANULARITY,
            "src_policy": FROZEN_SRC_POLICY,
        },
        "conditions": conditions,
        "remaining_local_extraction_debt": [
            "RELATION_QUALITY_TECHNICAL_DEBT = YES",
            "mixed V3/V3.1 provenance remains (WIN001 historical V3)",
            "WIN007 derived SRC canonicalization (raw SRec007337 retained in provenance)",
            "local IDEA subtype absent by design",
            "REPETITION extraction deferred to global",
            "author_intent / target_audience / VOICE deferred to global",
        ],
        "RELATION_QUALITY_TECHNICAL_DEBT": RELATION_QUALITY_TECHNICAL_DEBT,
        "do_not_delete_technical_debt": True,
        "do_not_change_local_prompt_transport_granularity_src_policy": True,
    }


def build_readiness(
    *,
    freeze: Mapping[str, Any],
    gates: Mapping[str, Any],
    grammar_canary_required: bool,
) -> dict[str, Any]:
    blocked = not all(
        [
            gates.get("all_ready"),
            gates.get("normalized_ok"),
            gates.get("provider_calls_zero"),
            gates.get("source_map_absent"),
        ]
    )
    if blocked:
        status = "BLOCKED"
    elif freeze.get("LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN") == "YES" and all(
        [
            gates.get("relation_policy_selected"),
            gates.get("transport_designed"),
            gates.get("budget_measured"),
            gates.get("validator_designed"),
            gates.get("review_planned"),
        ]
    ):
        status = "READY_FOR_GLOBAL_GRAMMAR_CANARY"
    else:
        status = "NEEDS_OFFLINE_CONSOLIDATION_REDESIGN"
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "status": status,
        "grammar_canary_required": grammar_canary_required,
        "grammar_canary_run": False,
        "real_consolidation_executed": False,
        "source_map_published": False,
        "next": "HUMAN REVIEW",
        "even_if_ready_do_not_make_the_call": True,
        "gates": dict(gates),
        "freeze": freeze.get("LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN"),
    }


__all__ = ["build_freeze_decision", "build_readiness"]
