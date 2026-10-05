"""
Separator-aware coverage for 1.1.1-candidate local validation.

Does not mutate uncovered_spans() used by frozen 1.0 / 1.1-candidate.
Sentence-final . ? ! may be uncovered only when they close an already
covered span. Words, numbers, negations, connectives, and clauses remain
mandatory.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.claims import uncovered_spans
from app.book_semantic_gate_4b262.contract import (
    OFFSET_CONVENTION,
    validate_compact_payload,
)

SENTENCE_TERMINATORS = frozenset(".?!")
KIND_WHITESPACE = "whitespace"
KIND_TERMINATOR = "sentence_terminator"
KIND_SIGNIFICANT = "significant"


def _covered_mask(text: str, claims: Sequence[Mapping[str, Any]]) -> list[bool]:
    covered = [False] * len(text)
    for claim in claims:
        start = claim.get("start_offset", claim.get("s"))
        end = claim.get("end_offset", claim.get("e"))
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if start < 0 or end < start or end > len(text):
            continue
        for index in range(start, end):
            covered[index] = True
    return covered


def _raw_uncovered(text: str, covered: Sequence[bool]) -> list[tuple[int, int]]:
    gaps: list[tuple[int, int]] = []
    gap_start: int | None = None
    for index, is_covered in enumerate(covered):
        if not is_covered and gap_start is None:
            gap_start = index
        elif is_covered and gap_start is not None:
            gaps.append((gap_start, index))
            gap_start = None
    if gap_start is not None:
        gaps.append((gap_start, len(text)))
    return gaps


def is_allowed_sentence_terminator(text: str, index: int, covered: Sequence[bool]) -> bool:
    if index < 0 or index >= len(text):
        return False
    char = text[index]
    if char not in SENTENCE_TERMINATORS:
        return False
    if index == 0 or not covered[index - 1]:
        return False
    if index + 1 >= len(text):
        return True
    nxt = text[index + 1]
    if nxt.isspace():
        return True
    if covered[index + 1]:
        return True
    return False


def classify_gap(
    text: str,
    start: int,
    end: int,
    covered: Sequence[bool],
) -> dict[str, Any]:
    snippet = text[start:end]
    codes = [ord(char) for char in snippet]
    if snippet and all(char.isspace() for char in snippet):
        kind = KIND_WHITESPACE
    elif snippet and all(
        char.isspace() or is_allowed_sentence_terminator(text, start + offset, covered)
        for offset, char in enumerate(snippet)
    ):
        kind = KIND_TERMINATOR
    else:
        kind = KIND_SIGNIFICANT
    return {
        "start": start,
        "end": end,
        "text": snippet,
        "codepoints": codes,
        "isspace_flags": [char.isspace() for char in snippet],
        "kind": kind,
        "python_slice": f"text[{start}:{end}]",
        "interval": "half_open",
    }


def classify_uncovered_gaps(
    text: str,
    claims: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    covered = _covered_mask(text, claims)
    return [
        classify_gap(text, start, end, covered)
        for start, end in _raw_uncovered(text, covered)
    ]


def uncovered_significant_spans(
    text: str,
    claims: Sequence[Mapping[str, Any]],
) -> list[tuple[int, int]]:
    """Gaps that still block acceptance under 1.1.1 local coverage."""
    return [
        (item["start"], item["end"])
        for item in classify_uncovered_gaps(text, claims)
        if item["kind"] == KIND_SIGNIFICANT
    ]


def analyze_terra_h01_gaps(paragraph_text: str, claims: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    historical = [
        {
            "start_offset": claim.get("s"),
            "end_offset": claim.get("e"),
        }
        for claim in claims
    ]
    whitespace_gaps = uncovered_spans(paragraph_text, historical)
    classified = classify_uncovered_gaps(paragraph_text, historical)
    significant = [
        (item["start"], item["end"])
        for item in classified
        if item["kind"] == KIND_SIGNIFICANT
    ]
    return {
        "offset_convention": dict(OFFSET_CONVENTION),
        "paragraph_length_codepoints": len(paragraph_text),
        "frozen_1_0_and_1_1_uncovered_spans": [list(item) for item in whitespace_gaps],
        "classified_raw_gaps": classified,
        "significant_gaps": [list(item) for item in significant],
        "whitespace_already_ignored_by_uncovered_spans": True,
        "4b27_reported_as_spaces": False,
        "4b27_actual_gap_characters": [
            {
                "start": item["start"],
                "end": item["end"],
                "repr": repr(item["text"]),
                "codepoints": item["codepoints"],
                "kind": item["kind"],
            }
            for item in classified
            if item["kind"] != KIND_WHITESPACE
        ],
        "finding": (
            "The recorded 4B.2.7 intervals 140-141 and 209-210 are the "
            "sentence-final periods after already-covered clauses, not the "
            "following spaces. uncovered_spans() already ignores whitespace. "
            "It does not ignore those periods."
        ),
        "correction_safe_if": (
            "Only sentence-final .?! immediately after a covered span and "
            "followed by whitespace, another covered span, or end of text."
        ),
        "never_ignore": [
            "word",
            "number",
            "negation",
            "logical connective",
            "clause",
            "comma_or_colon_that_can_change_meaning",
            "decimal_point_followed_by_digit",
        ],
        "secrets_included": False,
    }


def validate_compact_payload_111(
    payload: Mapping[str, Any] | None,
    *,
    paragraph_texts: Mapping[str, str],
    required_handles: Sequence[str],
    paragraph_kinds: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """1.1.1 local validation. Does not replace frozen 1.1-candidate validation."""
    base = validate_compact_payload(
        payload,
        paragraph_texts=paragraph_texts,
        required_handles=required_handles,
        paragraph_kinds=paragraph_kinds,
    )
    reason_warnings: list[str] = []
    separator_notes: list[dict[str, Any]] = []
    coverage_errors: list[str] = []
    if isinstance(payload, Mapping):
        for para in payload.get("pr") or []:
            handle = str(para.get("h") or "")
            text = str(paragraph_texts.get(handle) or "")
            claims = list(para.get("c") or [])
            for claim in claims:
                kind = str(claim.get("k") or "")
                reasons = list(claim.get("r") or [])
                if kind in {"QUESTIONABLE", "UNSUPPORTED"} and not reasons:
                    reason_warnings.append(f"{handle}: reason_code_missing")
            classified = classify_uncovered_gaps(
                text,
                [
                    {
                        "start_offset": claim.get("s"),
                        "end_offset": claim.get("e"),
                    }
                    for claim in claims
                ],
            )
            allowed = [
                item
                for item in classified
                if item["kind"] in {KIND_WHITESPACE, KIND_TERMINATOR}
            ]
            significant = [
                item for item in classified if item["kind"] == KIND_SIGNIFICANT
            ]
            if allowed:
                separator_notes.append({"handle": handle, "allowed": allowed})
            if significant:
                gaps = [(item["start"], item["end"]) for item in significant]
                coverage_errors.append(f"{handle}: significant_coverage_gap_{gaps}")
    errors = [
        item
        for item in (base.get("errors") or [])
        if "coverage_gap_" not in str(item)
    ]
    errors.extend(coverage_errors)
    status = "PASS" if not errors else "FAIL"
    return {
        **base,
        "status": status,
        "errors": errors,
        "coverage_errors": coverage_errors,
        "reason_code_warnings": reason_warnings,
        "separator_notes": separator_notes,
        "coverage_policy": "significant_characters_plus_allowed_separators",
        "frozen_1_1_status_preserved_separately": base.get("status"),
        "candidate_version": "book-semantic-validator-1.1.1-candidate",
        "does_not_mutate_historical_validator": True,
    }


__all__ = [
    "KIND_SIGNIFICANT",
    "KIND_TERMINATOR",
    "KIND_WHITESPACE",
    "SENTENCE_TERMINATORS",
    "analyze_terra_h01_gaps",
    "classify_gap",
    "classify_uncovered_gaps",
    "is_allowed_sentence_terminator",
    "uncovered_significant_spans",
    "validate_compact_payload_111",
]
