"""Coverage policy review. Reuses the 1.1.2 validator. Does not auto-correct spans."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b274.coverage import (
    PROTECTED_CONNECTIVES,
    SEPARATOR_CHARS,
    validate_compact_payload_112,
    validate_coverage,
)
from app.book_semantic_gate_4b274.punctuation import punctuation_coverage_inventory
from app.book_semantic_gate_4b275.constants import (
    COVERAGE_POLICY_VERSION,
    H01_GAPS,
    H02_GAPS,
    PHASE,
    PROMPT_VERSION_113,
)

ADMISSIBLE_SEPARATORS = (
    "spaces",
    "commas",
    "terminal_periods",
    "semicolons",
    "colons",
    "em_dashes",
    "en_dashes",
    "parentheses",
    "quotation_marks",
    "ellipsis",
)

MANDATORY_COVERAGE = (
    "words",
    "negations",
    "quantifiers",
    "conditions",
    "causal_connectives",
    "adversative_connectives",
    "complete_propositions",
    "subordinate_clauses",
)


def coverage_policy_review(
    *,
    h01_text: str = "",
    h01_claims: Sequence[Mapping[str, Any]] | None = None,
    h02_text: str = "",
    h02_claims: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    inventory = None
    if h01_text and h02_text and h01_claims is not None and h02_claims is not None:
        inventory = punctuation_coverage_inventory(
            h01_text=h01_text,
            h01_claims=h01_claims,
            h02_text=h02_text,
            h02_claims=h02_claims,
        )
    return {
        "phase": PHASE,
        "policy_version": COVERAGE_POLICY_VERSION,
        "reused_by_1_1_3": True,
        "candidate_version": PROMPT_VERSION_113,
        "admissible_separators": list(ADMISSIBLE_SEPARATORS),
        "separator_chars": sorted(SEPARATOR_CHARS),
        "mandatory_coverage": list(MANDATORY_COVERAGE),
        "protected_connectives": list(PROTECTED_CONNECTIVES),
        "unicode_offsets": "python3_str_unicode_code_points",
        "does_not_auto_correct_spans": True,
        "does_not_modify_original_text": True,
        "does_not_strip_punctuation_before_validation": True,
        "h01_recorded_gaps": [list(item) for item in H01_GAPS],
        "h02_recorded_gaps": [list(item) for item in H02_GAPS],
        "historical_inventory": inventory,
        "secrets_included": False,
    }


def validate_compact_payload_113(
    payload: Mapping[str, Any] | None,
    *,
    paragraph_texts: Mapping[str, str],
    required_handles: Sequence[str],
    paragraph_kinds: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """1.1.3 local validation reuses 1.1.2 coverage and catalog rules."""
    result = validate_compact_payload_112(
        payload,
        paragraph_texts=paragraph_texts,
        required_handles=required_handles,
        paragraph_kinds=paragraph_kinds,
    )
    return {
        **result,
        "candidate_version": PROMPT_VERSION_113,
        "reuses_1_1_2_coverage": True,
        "does_not_mutate_1_1_2_validator": True,
    }


__all__ = [
    "ADMISSIBLE_SEPARATORS",
    "MANDATORY_COVERAGE",
    "coverage_policy_review",
    "validate_compact_payload_113",
    "validate_coverage",
]
