"""Future real Opus call gates and human semantic review plan. No response."""

from __future__ import annotations

from typing import Any

from app.editorial_planner_preflight_4a2.constants import (
    FUTURE_REAL_CALL_COUNT,
    FUTURE_RETRIES,
    RECOMMENDED_CONNECT_TIMEOUT_SECONDS,
    RECOMMENDED_READ_TIMEOUT_SECONDS,
)
from app.editorial_planning.coverage import coverage_policy_dict
from app.editorial_planning.validator import validator_contract_dict


def future_real_call_gates() -> dict[str, Any]:
    validator = validator_contract_dict()
    coverage = coverage_policy_dict()
    return {
        "future_real_call_count": FUTURE_REAL_CALL_COUNT,
        "future_retries": FUTURE_RETRIES,
        "recommended_connect_timeout_seconds": RECOMMENDED_CONNECT_TIMEOUT_SECONDS,
        "recommended_read_timeout_seconds": RECOMMENDED_READ_TIMEOUT_SECONDS,
        "publication_after_response": "NOT AUTOMATIC — editorial_plan.json remains unpublished until a later authorized phase",
        "gates": [
            {"id": "http_success", "required": True, "note": "HTTP 200, provider envelope valid"},
            {"id": "normal_finish", "required": True, "note": "finish/stop_reason end_turn (not max_tokens)"},
            {"id": "structured_parse", "required": True, "note": "JSON matches adapted schema"},
            {"id": "transport_decoder", "required": True, "note": "editorial-plan-transport-1.0 decode"},
            {"id": "handle_validation", "required": True, "note": "temporary h handles unique / well-formed"},
            {"id": "canonical_reconstruction", "required": True, "note": "CH/SEC assigned in editorial order"},
            {"id": "hierarchy", "required": True, "note": "BOOK -> CHAPTER -> SECTION only"},
            {"id": "idea_coverage", "required": True, "note": "286/286 explicit ASSIGNED|DEFERRED|EXCLUDED"},
            {"id": "silent_omission", "required": True, "note": "silent omission = FAIL"},
            {"id": "unknown_refs", "required": True, "note": "unknown IDEA/TOP/EX/REF/UNC/REP = FAIL"},
            {"id": "traceability", "required": True, "note": "every section derives SRC from SourceMap"},
            {"id": "uncertainty", "required": True, "note": "UNC remain uncertainties; do not resolve"},
            {"id": "invention_boundary", "required": True, "note": "no unsupported units / manuscript prose"},
            {"id": "balance", "required": False, "note": "REVIEW heuristics, not automatic FAIL"},
            {"id": "canonical_validator", "required": True, "note": "editorial-plan-validator-1.0 != FAIL"},
            {"id": "deterministic_replay", "required": True, "note": "same transport reconstructs identically"},
            {"id": "semantic_review", "required": True, "note": "human-readable review before any publication"},
        ],
        "coverage_policy": coverage,
        "validator_contract": validator,
        "retry_policy": {
            "first_real_production_planning_canary": "exactly one call",
            "retries": 0,
            "controlled_canary_discipline": True,
        },
    }


def semantic_review_plan() -> dict[str, Any]:
    return {
        "required_human_readable_reviews": [
            "working title",
            "subtitle",
            "editorial angle",
            "target reader",
            "book concept",
            "chapter sequence",
            "section sequence",
            "286 IDEA disposition coverage",
            "deferred ideas",
            "excluded ideas",
            "reused ideas",
            "examples",
            "references",
            "uncertainties",
            "editorial progression",
            "unsupported claims/structure",
        ],
        "title_review": {
            "selected_title_is": "editorial construct, not source fact",
            "must_review_for": ["fidelity", "scope", "unsupported promise"],
        },
        "chapter_review": {
            "every_chapter": [
                "purpose",
                "idea support",
                "coherence",
                "boundary with adjacent chapters",
                "balance",
            ]
        },
        "section_review": {
            "every_section": [
                "idea support",
                "coherence",
                "non-empty coverage",
                "lack of manuscript prose leakage",
            ]
        },
        "exclusion_review": {
            "every_excluded_idea": "individually reviewable",
            "reason_required": True,
            "closed_vocabulary": True,
        },
        "deferral_review": {
            "every_deferred_idea": "must have a reason",
            "closed_vocabulary": True,
        },
        "reuse_review": {
            "every_reused_idea_must_expose": [
                "primary section",
                "extra sections",
            ]
        },
        "no_fabricated_production_response": True,
        "no_editorial_plan_json_in_4a2": True,
    }


__all__ = ["future_real_call_gates", "semantic_review_plan"]
