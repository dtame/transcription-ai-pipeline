"""Évaluateur forensique de politiques SRC. N'est PAS branché en production."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.source_analysis_local_v3.source_refs import is_canonical_src
from app.source_analysis_v31_src_typo_forensics.classify import (
    analyze_transformation,
    levenshtein,
)
from app.source_analysis_v31_src_typo_forensics.constants import (
    A19_CANONICAL,
    A19_MALFORMED,
    EXPECTED_CANONICAL,
    MALFORMED_TOKEN,
    MODE,
    PHASE,
    SCHEMA_VERSION,
    WIN007_COST_USD,
    WIN007_ELAPSED_MS,
)

_PREFIX_DIGITS = re.compile(r"^([A-Za-z]{3,4})([0-9]{6})$")


def option_b_full_token_ed1(
    token: str,
    *,
    owned: set[str],
) -> dict[str, Any]:
    """Option B telle qu'écrite : unique candidat owned à distance 1 sensible à la casse."""
    if is_canonical_src(token):
        return {"accept": False, "reason": "already_canonical"}
    candidates = [src for src in owned if levenshtein(token, src) == 1]
    return {
        "accept": len(candidates) == 1,
        "reason": "unique_ed1" if len(candidates) == 1 else "no_unique_ed1",
        "candidates": candidates,
        "covers_srec007337": levenshtein(MALFORMED_TOKEN, EXPECTED_CANONICAL) == 1,
        "covers_src000609": levenshtein(A19_MALFORMED, A19_CANONICAL) == 1,
    }


def evaluate_prefix_digit_rule(
    token: str,
    *,
    owned: set[str],
    semantic_compatible: bool | None = None,
    intended_class: str | None = None,
) -> dict[str, Any]:
    """
    Règle machine-testable proposée (PAS implémentée en production) :

    Accepter le mapping T → C seulement si TOUTES les conditions tiennent :
    1. T n'est pas déjà ^SRC[0-9]{6}$
    2. T correspond à ^[A-Za-z]{3,4}[0-9]{6}$
    3. D = 6 chiffres de T, C = 'SRC'+D
    4. C est owned
    5. levenshtein(prefix.casefold(), 'src') <= 1
    6. aucun autre owned n'a la même identité numérique (automatique)
    7. compatibilité sémantique confirmée (si fournie)
    8. intended_class ∈ {EXACT_INTENDED_SOURCE, PLAUSIBLE_INTENDED_SOURCE}
    9. T brut préservé ; correction seulement dérivée
    10. ambiguïté → rejet
    """
    reasons: list[str] = []
    if not isinstance(token, str) or not token:
        return {"accept": False, "reason": "empty_or_non_string", "candidate": None}
    if is_canonical_src(token):
        return {
            "accept": False,
            "reason": "already_valid_untouched",
            "candidate": token,
            "must_not_rewrite_valid_src": True,
        }
    match = _PREFIX_DIGITS.fullmatch(token)
    if match is None:
        return {"accept": False, "reason": "not_src_like_prefix_digits", "candidate": None}
    prefix, digits = match.group(1), match.group(2)
    candidate = "SRC" + digits
    if candidate not in owned:
        reasons.append("out_of_window_or_unknown")
    prefix_ed = levenshtein(prefix.casefold(), "src")
    if prefix_ed > 1:
        reasons.append("prefix_casefold_edit_distance_gt_1")
    if semantic_compatible is False:
        reasons.append("semantic_mismatch")
    if intended_class not in {
        None,
        "EXACT_INTENDED_SOURCE",
        "PLAUSIBLE_INTENDED_SOURCE",
    }:
        reasons.append("intended_source_not_confirmed")
    accept = not reasons and candidate in owned
    if intended_class in {"AMBIGUOUS", "NOT_INTENDED_SOURCE"}:
        accept = False
        reasons.append("ambiguity_or_not_intended")
    return {
        "accept": accept,
        "reason": "accept_prefix_digit_rule" if accept else "|".join(reasons) or "reject",
        "candidate": candidate,
        "prefix": prefix,
        "digits": digits,
        "prefix_casefold_edit_distance": prefix_ed,
        "numeric_preserved": True,
        "raw_preserved": True,
        "derived_only": True,
        "semantic_text_unchanged": True,
    }


def required_rejection_cases(owned: set[str]) -> list[dict[str, Any]]:
    cases = [
        {
            "name": "multiple_possible_canonical_matches",
            "token": "SRec00733",
            "note": "5-digit payload could map to SRC007330–SRC007339; digit-lock rejects it",
            "expect_accept": False,
        },
        {
            "name": "numeric_payload_change",
            "token": "SRC007338",
            "note": "already-valid different SRC must stay untouched",
            "expect_accept": False,
        },
        {
            "name": "out_of_window",
            "token": "SRec000001",
            "expect_accept": False,
        },
        {
            "name": "semantic_mismatch",
            "token": MALFORMED_TOKEN,
            "semantic_compatible": False,
            "intended_class": "NOT_INTENDED_SOURCE",
            "expect_accept": False,
        },
        {
            "name": "edit_distance_too_large",
            "token": "SRecord007337",
            "expect_accept": False,
        },
        {
            "name": "empty_source_token",
            "token": "",
            "expect_accept": False,
        },
        {
            "name": "non_src_like",
            "token": "banana",
            "expect_accept": False,
        },
        {
            "name": "already_valid_wrong_reference",
            "token": "SRC007338" if "SRC007338" in owned else "SRC007207",
            "expect_accept": False,
        },
    ]
    results = []
    for case in cases:
        universe = set(case.get("owned_override") or owned)
        evaluated = evaluate_prefix_digit_rule(
            case["token"],
            owned=universe,
            semantic_compatible=case.get("semantic_compatible"),
            intended_class=case.get("intended_class"),
        )
        public = {
            key: (sorted(value) if isinstance(value, set) else value)
            for key, value in case.items()
            if key != "owned_override"
        }
        results.append(
            {**public, "evaluation": evaluated, "rejected": not evaluated["accept"]}
        )
    return results


def build_options(
    *,
    replay: Mapping[str, Any],
    intended: Mapping[str, Any],
    history: Mapping[str, Any],
    transformation: Mapping[str, Any],
    counterfactual: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    owned = set(replay["window"].owned_src_refs)
    option_b = option_b_full_token_ed1(MALFORMED_TOKEN, owned=owned)
    refined = evaluate_prefix_digit_rule(
        MALFORMED_TOKEN,
        owned=owned,
        semantic_compatible=intended.get("intended_source_class")
        in {"EXACT_INTENDED_SOURCE", "PLAUSIBLE_INTENDED_SOURCE"},
        intended_class=str(intended.get("intended_source_class") or ""),
    )
    a19 = option_b_full_token_ed1(A19_MALFORMED, owned={A19_CANONICAL})
    tech = None
    if isinstance(counterfactual, Mapping):
        tech = counterfactual.get("technical")
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "implemented_in_a32": False,
        "semantic_repair_vs_identifier_canonicalization": {
            "semantic_repair": (
                "Rewriting claim text or inventing missing ideas. Unsafe here."
            ),
            "deterministic_identifier_canonicalization": (
                "Mapping a malformed machine ID to exactly one owned canonical ID "
                "under testable constraints, preserving raw evidence."
            ),
            "not_assumed_safe": True,
        },
        "option_a_strict_rejection": {
            "id": "KEEP_STRICT_AND_RETRY_WIN007",
            "keep_strict_exact_src": True,
            "win007_requires_new_provider_call": True,
            "cost_usd": WIN007_COST_USD,
            "elapsed_ms": WIN007_ELAPSED_MS,
            "reliability": (
                "Throws away an otherwise complete 80-record response. "
                "A new generation can introduce a different defect. "
                "A.19→A.31 shows prompt hardening did not eliminate the class."
            ),
            "preserves_a31_failure": True,
        },
        "option_b_as_written_ed1": {
            "id": "IMPLEMENT_NARROW_SRC_CANONICALIZATION_THEN_REVALIDATE_SAVED_WIN007",
            "full_token_case_sensitive_ed1_covers_srec": option_b["covers_srec007337"],
            "full_token_case_sensitive_ed1_covers_src": a19["covers_src000609"],
            "srec_evaluation": option_b,
            "insufficient_for_srec": not option_b["covers_srec007337"],
            "note": (
                "Option B as specified (unique owned candidate at edit distance 1) "
                "accepts SRc000609 (distance 1) but rejects SRec007337 (distance 2)."
            ),
        },
        "option_b_refined_prefix_digit": {
            "id": "IMPLEMENT_NARROW_SRC_CANONICALIZATION_THEN_REVALIDATE_SAVED_WIN007",
            "machine_testable": True,
            "not_fix_obvious_typos": True,
            "srec_evaluation": refined,
            "covers_srec": refined["accept"],
            "covers_a19": evaluate_prefix_digit_rule(
                A19_MALFORMED,
                owned={A19_CANONICAL},
                semantic_compatible=True,
                intended_class="EXACT_INTENDED_SOURCE",
            )["accept"],
            "required_rejections": required_rejection_cases(owned),
            "raw_token_preserved": True,
            "derived_representation_only": True,
            "no_semantic_text_change": True,
            "already_valid_src_untouched": True,
        },
        "option_c_provider_retry": {
            "id": "KEEP_STRICT_AND_RETRY_WIN007",
            "actual_a31_win007_cost_usd": WIN007_COST_USD,
            "actual_a31_win007_elapsed_ms": WIN007_ELAPSED_MS,
            "no_actual_retry": True,
            "risk": "New generation is not guaranteed clean; prior class recurred.",
        },
        "option_d_prompt_hardening": {
            "likely_to_eliminate_class": False,
            "reason": (
                "A.19 occurred; SRC copy block was added in 1.3.1; "
                "A.31 occurred under window-analysis-1.4.0 which still includes "
                "that exact-copy block. Prompt wording cannot guarantee literal copy."
            ),
            "a19_after_earlier_hardening_context": True,
            "a31_under_140": True,
        },
        "option_e_structural_src_selection": {
            "safer_than_fuzzy_repair": True,
            "examples_analysis_only": [
                "provider references local source ordinal",
                "provider references deterministic short handle",
                "postprocessor maps handle → canonical SRC",
                "schema-constrained source reference representation",
            ],
            "implemented": False,
            "schema_change_likely": True,
            "a18_proof_would_need_revisit": True,
        },
        "counterfactual_technical": tech,
        "transformation": dict(transformation),
        "history_malformed_rate": history.get("malformed_rate"),
        "history_malformed_forms": history.get("malformed_forms_observed"),
    }


__all__ = [
    "analyze_transformation",
    "build_options",
    "evaluate_prefix_digit_rule",
    "option_b_full_token_ed1",
    "required_rejection_cases",
]
