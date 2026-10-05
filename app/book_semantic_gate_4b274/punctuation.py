"""Punctuation coverage inventory for recorded h01/h02 gaps."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b271.coverage import classify_uncovered_gaps
from app.book_semantic_gate_4b274.constants import H01_GAPS, H02_GAPS, PHASE
from app.book_semantic_gate_4b274.coverage import (
    KIND_SEPARATOR,
    KIND_SIGNIFICANT,
    classify_uncovered_gaps_112,
    validate_coverage,
)


def _gap_rows(text: str, expected: Sequence[tuple[int, int]]) -> list[dict[str, Any]]:
    rows = []
    for start, end in expected:
        snippet = text[start:end]
        classes = []
        for char in snippet:
            if char.isspace():
                classes.append("whitespace")
            elif char in ".?!":
                classes.append("terminal_punctuation")
            elif char in ",;:":
                classes.append("separating_punctuation")
            elif char in "—–-":
                classes.append("dash")
            elif char.isalnum():
                classes.append("word_or_digit")
            else:
                classes.append("other_unicode")
        logical = any(token in snippet.lower() for token in ("because", "unless", "however", "not"))
        rows.append(
            {
                "start": start,
                "end": end,
                "text": snippet,
                "repr": repr(snippet),
                "codepoints": [ord(char) for char in snippet],
                "character_classes": classes,
                "can_mark_logical_relation": logical,
                "python_slice": f"text[{start}:{end}]",
            }
        )
    return rows


def punctuation_coverage_inventory(
    *,
    h01_text: str,
    h01_claims: Sequence[Mapping[str, Any]],
    h02_text: str,
    h02_claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    h01_111 = classify_uncovered_gaps(h01_text, h01_claims)
    h02_111 = classify_uncovered_gaps(h02_text, h02_claims)
    h01_112 = classify_uncovered_gaps_112(h01_text, h01_claims)
    h02_112 = classify_uncovered_gaps_112(h02_text, h02_claims)
    h01_audit = validate_coverage(h01_text, h01_claims)
    h02_audit = validate_coverage(h02_text, h02_claims)
    return {
        "phase": PHASE,
        "h01": {
            "expected_gaps": [list(item) for item in H01_GAPS],
            "rows": _gap_rows(h01_text, H01_GAPS),
            "classified_1_1_1": h01_111,
            "classified_1_1_2": h01_112,
            "coverage_1_1_2": h01_audit["status"],
            "significant_1_1_2": h01_audit["significant_intervals"],
            "finding": (
                "Recorded h01 gaps are sentence-final periods after covered clauses."
            ),
        },
        "h02": {
            "expected_gaps": [list(item) for item in H02_GAPS],
            "rows": _gap_rows(h02_text, H02_GAPS),
            "classified_1_1_1": h02_111,
            "classified_1_1_2": h02_112,
            "coverage_1_1_2": h02_audit["status"],
            "significant_1_1_2": h02_audit["significant_intervals"],
            "finding": (
                "Recorded h02 gaps are an em dash, commas, and a semicolon between "
                "already-covered claims. The because-clause itself is covered. "
                "1.1.2 treats those separators as admissible without hiding words."
            ),
        },
        "policy": {
            "do_not_reject_only_for_admissible_separators": True,
            "do_reject_uncovered_substantive_spans": True,
            "do_not_strip_all_punctuation_before_validation": True,
            "do_not_modify_original_offsets": True,
            "do_not_shift_terra_spans": True,
            "do_not_hide_coverage_holes": True,
            "protected": [
                "significant words",
                "negations",
                "quantifiers",
                "causal connectors",
                "adversative connectors",
                "conditions",
                "comparisons",
                "propositions",
                "substantial logical relations",
            ],
        },
        "residual_intervals": {
            "h01_significant": h01_audit["significant_intervals"],
            "h02_significant": h02_audit["significant_intervals"],
            "h01_admissible": [
                [item["start"], item["end"], item["kind"]]
                for item in h01_112
                if item["kind"] != KIND_SIGNIFICANT
            ],
            "h02_admissible": [
                [item["start"], item["end"], item["kind"]]
                for item in h02_112
                if item["kind"] != KIND_SIGNIFICANT
            ],
        },
        "separator_kind_used": KIND_SEPARATOR,
        "secrets_included": False,
    }


def coverage_validator_design() -> dict[str, Any]:
    return {
        "phase": PHASE,
        "function": "validate_coverage(paragraph, claims)",
        "pure": True,
        "deterministic": True,
        "testable": True,
        "inputs": ["original paragraph", "model spans"],
        "steps": [
            "validate offsets",
            "detect overlaps without shifting spans",
            "identify uncovered intervals",
            "classify each character by identity and immediate context",
            "accept only admissible separators and terminators",
            "refuse substantive intervals",
            "emit a detailed audit",
        ],
        "does_not_infer_omitted_words_are_covered": True,
        "admissible_punctuation_is_not_a_bypass": True,
        "historical_uncovered_spans_unmodified": True,
        "secrets_included": False,
    }


__all__ = ["coverage_validator_design", "punctuation_coverage_inventory"]
