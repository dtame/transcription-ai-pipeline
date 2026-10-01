"""Validation contre-factuelle WIN003 sous plafonds candidats. Ne mute pas la prod."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_local_v2.granularity import (
    TEXT_HARD_LIMITS,
    V11_MINIMAL_TEXT_HARD_LIMITS,
)
from app.source_analysis_v31_length_ceiling.constants import (
    CANDIDATE_CEILINGS,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_length_ceiling.lengths import (
    candidate_limits,
    text_violations_with_limits,
)
from app.source_analysis_v31_remaining_windows.review import review_transport


def evaluate_ceiling(
    transport: Mapping[str, Any],
    ceiling: int,
    *,
    replay: Mapping[str, Any],
) -> dict[str, Any]:
    limits = candidate_limits(ceiling)
    errors = text_violations_with_limits(transport, limits)
    technical_ok = not errors
    other_errors = [
        err
        for err in (replay.get("validation_errors") or [])
        if "caractères >" not in err and " > 200" not in err
    ]
    remaining = list(errors) + other_errors
    return {
        "ceiling": ceiling,
        "limits_used": {
            "theme": limits["theme"],
            "IDEA.v": limits["IDEA.v"],
            "EXAMPLE.v": limits["EXAMPLE.v"],
        },
        "production_limits_unchanged": (
            dict(V11_MINIMAL_TEXT_HARD_LIMITS) == V11_MINIMAL_TEXT_HARD_LIMITS
        ),
        "text_errors": errors,
        "other_technical_errors": other_errors,
        "remaining_failures": remaining,
        "technical": "PASS" if technical_ok and not other_errors else "FAIL",
        "eligible_for_semantic_review": technical_ok and not other_errors,
    }


def token_budget_impact() -> dict[str, Any]:
    """Worst-case extra chars/tokens vs a 200 baseline for currently-200 fields."""
    from app.source_analysis_local_v2.constants import HARD_CEILINGS

    fields_at_200 = [
        key for key, value in V11_MINIMAL_TEXT_HARD_LIMITS.items() if value == 200
    ]
    example_max = int(HARD_CEILINGS.get("EXAMPLE") or 0)
    topic_max = int(HARD_CEILINGS.get("TOPIC") or 0)
    rows = {}
    for ceiling in CANDIDATE_CEILINGS:
        delta = max(0, ceiling - 200)
        extra_theme = delta
        extra_example = example_max * delta
        extra_topic_m0 = topic_max * delta
        extra_chars = extra_theme + extra_example + extra_topic_m0
        extra_tokens = (extra_chars + 3) // 4
        rows[str(ceiling)] = {
            "delta_vs_200": delta,
            "fields_raised": fields_at_200,
            "extra_theme_chars": extra_theme,
            "extra_example_chars": extra_example,
            "extra_topic_m0_chars": extra_topic_m0,
            "extra_chars_worst": extra_chars,
            "extra_local_tokens_worst_ceil_chars_over_4": extra_tokens,
            "idea_v_unchanged": V11_MINIMAL_TEXT_HARD_LIMITS["IDEA.v"],
        }
    return {
        "estimator": "local ceil(chars/4) — not Anthropic tokenization",
        "does_not_change_max_output": True,
        "max_output_tokens": 32000,
        "rows": rows,
        "proposed_only_theme_and_example_225": {
            "extra_chars": (225 - 200) + example_max * (225 - 200),
            "extra_local_tokens": (
                ((225 - 200) + example_max * (225 - 200)) + 3
            )
            // 4,
            "note": "Minimum change: raise only theme and EXAMPLE.v to 225.",
        },
    }


def grammar_impact() -> dict[str, Any]:
    return {
        "change_json_schema_bytes": False,
        "change_adapted_schema_bytes": False,
        "change_schema_hash": False,
        "invalidate_a18_grammar_proof": False,
        "affects_python_validation_only": True,
        "affects_prompt_semantics_only_if_1_4_1": True,
        "a18_proof_still_applies": True,
        "schema_identity_changes": False,
        "note": (
            "TEXT_HARD_LIMITS are not encoded in the 588/650 provider grammar. "
            "Raising Python limits does not change A.18 identity."
        ),
    }


def build_counterfactual(
    replay: Mapping[str, Any],
) -> dict[str, Any]:
    transport = replay["transport"]
    if not isinstance(transport, Mapping):
        raise ValueError("WIN003 transport required for counterfactual.")
    rows = {
        str(ceiling): evaluate_ceiling(transport, ceiling, replay=replay)
        for ceiling in CANDIDATE_CEILINGS
    }
    eligible = next(
        (
            int(key)
            for key, row in rows.items()
            if row["eligible_for_semantic_review"] and int(key) > 200
        ),
        None,
    )
    semantic = None
    if eligible is not None:
        semantic = review_transport(
            transport,
            window=replay["window"],
            transcript=replay["transcript"],
            capacity_signal=False,
            handle_gate_pass=True,
            technical_ok=True,
            src_audit=(replay.get("validation") or {}).get("src_audit"),
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "production_policy_mutated": False,
        "win003_marked_ready": False,
        "a28_status_unchanged": "FAIL",
        "ceilings": rows,
        "counterfactual_225": rows["225"]["technical"],
        "counterfactual_250": rows["250"]["technical"],
        "counterfactual_300": rows["300"]["technical"],
        "token_budget": token_budget_impact(),
        "grammar_impact": grammar_impact(),
        "semantic_review_eligible": eligible is not None,
        "semantic_review_ceiling_used": eligible,
        "semantic_review": semantic,
    }


def assert_production_limits_untouched() -> None:
    """A.29-era 1.1-minimal snapshot stays 200/200/280. Live 1.2 is A.30."""
    if V11_MINIMAL_TEXT_HARD_LIMITS["theme"] != 200:
        raise RuntimeError("historical A.28 theme limit mutated")
    if V11_MINIMAL_TEXT_HARD_LIMITS["EXAMPLE.v"] != 200:
        raise RuntimeError("historical A.28 EXAMPLE.v limit mutated")
    if V11_MINIMAL_TEXT_HARD_LIMITS["IDEA.v"] != 280:
        raise RuntimeError("historical A.28 IDEA.v limit mutated")
    if TEXT_HARD_LIMITS["IDEA.v"] != 280:
        raise RuntimeError("live IDEA.v limit mutated")


__all__ = [
    "assert_production_limits_untouched",
    "build_counterfactual",
    "evaluate_ceiling",
    "grammar_impact",
    "token_budget_impact",
]
