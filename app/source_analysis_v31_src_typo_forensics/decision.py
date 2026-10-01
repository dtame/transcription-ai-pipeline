"""Décision architecturale unique A.32. N'implémente pas le changement."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_v31_src_typo_forensics.constants import (
    A18_PROOF_STILL_APPLIES,
    ALLOWED_DECISIONS,
    FAILURE_CLASS,
    GRANULARITY_POLICY,
    MODE,
    PHASE,
    PROMPT_CHANGE_REQUIRED,
    PROMPT_VERSION,
    SCHEMA_CHANGE_REQUIRED,
    SCHEMA_VERSION,
    TRANSPORT_CHANGE_REQUIRED,
    TRANSPORT_VERSION,
    WIN007_PROMOTION_AUTHORIZED,
)


def build_decision(
    *,
    options: Mapping[str, Any],
    intended: Mapping[str, Any],
    counterfactual: Mapping[str, Any],
    history: Mapping[str, Any],
    transformation: Mapping[str, Any],
) -> dict[str, Any]:
    intended_class = str(intended.get("intended_source_class") or "")
    technical = counterfactual.get("technical")
    semantic = counterfactual.get("semantic_review") or {}
    quality = semantic.get("semantic_quality") if isinstance(semantic, Mapping) else None
    refined = (options.get("option_b_refined_prefix_digit") or {}).get("srec_evaluation") or {}
    as_written = options.get("option_b_as_written_ed1") or {}
    isolated = bool(
        ((counterfactual.get("src_forensic") or {}).get("malformed_src") in {0, None})
        or counterfactual.get("sole_root_cause")
    )
    selected = "KEEP_STRICT_AND_RETRY_WIN007"
    future_action = "NEW_PROVIDER_CALL_FOR_WIN007_AFTER_HUMAN_AUTHORIZATION"
    rationale = []
    if (
        technical == "PASS"
        and intended_class in {"EXACT_INTENDED_SOURCE", "PLAUSIBLE_INTENDED_SOURCE"}
        and refined.get("accept")
        and isolated
    ):
        selected = "IMPLEMENT_NARROW_SRC_CANONICALIZATION_THEN_REVALIDATE_SAVED_WIN007"
        future_action = (
            "HUMAN REVIEW, then implement prefix+digit canonicalization "
            "and revalidate the saved WIN007 response offline. Do not retry first."
        )
        rationale = [
            "SRec007337 is the sole root SRC violation.",
            "Numeric payload 007337 is owned by WIN007.",
            f"Intended source class = {intended_class}.",
            "Counterfactual single correction is a complete technical PASS.",
            "Option B as written (full-token case-sensitive edit distance 1) "
            "does not cover SRec007337 (distance 2) but does cover SRc000609.",
            "The selected rule is therefore a refined, machine-testable "
            "prefix+exact-digits policy, not generic typo repair.",
            "A.19 and A.31 are the same general class "
            f"({FAILURE_CLASS}) with distinct manifestations.",
            "Prompt 1.4.0 already contains the 1.3.1 SRC exact-copy block; "
            "another wording pass is unlikely to eliminate the class.",
            "Retrying WIN007 costs a known 0.176872 USD / 68827 ms and can "
            "introduce a new unrelated defect.",
            "Raw provider token remains the source of truth; correction is "
            "derived-only and must participate in validator/policy versioning.",
        ]
    elif technical != "PASS":
        selected = "KEEP_STRICT_AND_RETRY_WIN007"
        future_action = "NEW_PROVIDER_CALL_FOR_WIN007_AFTER_HUMAN_AUTHORIZATION"
        rationale = [
            "Counterfactual single correction did not yield a complete technical PASS.",
            "Additional defects remain; do not canonicalize over them.",
        ]
    elif intended_class not in {"EXACT_INTENDED_SOURCE", "PLAUSIBLE_INTENDED_SOURCE"}:
        selected = "HUMAN_SEMANTIC_REVIEW_REQUIRED"
        future_action = "HUMAN REVIEW OF SRC007337 INTENT BEFORE ANY POLICY CHANGE"
        rationale = [
            f"Intended-source class is {intended_class}.",
            "Digits matching SRC007337 are not sufficient to prove intent.",
        ]
    if selected not in ALLOWED_DECISIONS:
        raise ValueError(f"décision hors contrat : {selected}")
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "selected_policy": selected,
        "exactly_one": True,
        "not_selected": [item for item in ALLOWED_DECISIONS if item != selected],
        "chosen_to_make_win007_pass": False,
        "standards": [
            "determinism",
            "auditability",
            "no semantic invention",
            "no ambiguity",
            "preserve raw provider evidence",
            "low unnecessary provider cost",
            "generalizable architecture",
        ],
        "rationale": rationale,
        "failure_class": FAILURE_CLASS,
        "a19_same_general_class": True,
        "distinct_manifestations_preserved": True,
        "option_b_as_written_covers_srec": as_written.get(
            "full_token_case_sensitive_ed1_covers_srec"
        ),
        "refined_rule_covers_srec": refined.get("accept"),
        "allowed_transformation_rules": [
            "T is a string and is not already ^SRC[0-9]{6}$",
            "T matches ^[A-Za-z]{3,4}[0-9]{6}$",
            "D = T[-6:]; C = 'SRC' + D",
            "C is owned by the window",
            "levenshtein(T[:-6].casefold(), 'src') <= 1",
            "semantic comparison confirms C is compatible with the record",
            "no other owned SRC is a plausible intended source",
            "correction is recorded in provenance/audit",
            "original raw provider token is preserved unchanged",
            "canonicalization occurs only in a derived representation",
            "no semantic text is changed",
            "ambiguity, empty token, non-SRC-like, numeric mutation, "
            "out-of-window, already-valid SRC, or edit-distance excess → reject",
        ],
        "required_rejection_cases": [
            "multiple possible canonical matches",
            "numeric payload changes",
            "out-of-window targets",
            "semantic mismatch",
            "more than allowed edit distance",
            "empty source token",
            "non-SRC-like arbitrary strings",
            "already-valid-but-wrong source references",
        ],
        "security_integrity": {
            "never_rewrite_syntactically_valid_src": True,
            "semantic_correctness_separately_audited": True,
        },
        "signature_cache_impact": {
            "must_participate_in_window_signature": False,
            "must_participate_in_candidate_provenance": True,
            "must_participate_in_validator_policy_version": True,
            "must_participate_in_cache_identity": True,
            "reason": (
                "A.31 strict policy must remain reproducible as FAIL on the "
                "same raw bytes. A future policy version is a new cache key."
            ),
            "implemented": False,
        },
        "historical_reproducibility": {
            "a31_strict_win007_fail_preserved": True,
            "future_policy_may_revalidate_same_raw": True,
            "a31_failure_not_erased": True,
        },
        "provider_grammar_impact": {
            "schema_588_650_unchanged": True,
            "schema_hash_unchanged": True,
            "a18_grammar_proof": "APPLIES",
            "schema_change_required": SCHEMA_CHANGE_REQUIRED,
        },
        "prompt_impact": {
            "window_analysis_140_immutable": True,
            "prompt_change_required": PROMPT_CHANGE_REQUIRED,
            "prompt_version": PROMPT_VERSION,
        },
        "transport_impact": {
            "semantic_transport_v31_local_lite_unchanged": True,
            "transport_change_required": TRANSPORT_CHANGE_REQUIRED,
            "transport_version": TRANSPORT_VERSION,
        },
        "granularity_unchanged": GRANULARITY_POLICY,
        "a18_proof_still_applies": A18_PROOF_STILL_APPLIES,
        "win007_promoted": WIN007_PROMOTION_AUTHORIZED,
        "future_win007_action": future_action,
        "counterfactual_technical": technical,
        "counterfactual_semantic_quality": quality,
        "intended_source_class": intended_class,
        "history_malformed_rate": history.get("malformed_rate"),
        "edit_distance_case_sensitive": transformation.get(
            "edit_distance_case_sensitive"
        ),
        "numeric_payload_preserved": transformation.get("numeric_payload_preserved"),
        "implemented": False,
    }


__all__ = ["build_decision"]
