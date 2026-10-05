"""
1.1.2 coverage validator.

Pure, deterministic, and testable. Does not mutate uncovered_spans() used by
frozen 1.0 / 1.1-candidate. Does not mutate 1.1.1 terminator-only policy.
Does not rewrite Terra spans. Does not strip punctuation from the paragraph.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b23.claims import uncovered_spans
from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
)
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b262.contract import (
    OFFSET_CONVENTION,
    validate_compact_payload,
    validate_compact_span,
)
from app.book_semantic_gate_4b271.coverage import (
    KIND_SIGNIFICANT,
    KIND_TERMINATOR,
    KIND_WHITESPACE,
    SENTENCE_TERMINATORS,
    is_allowed_sentence_terminator,
)
from app.book_semantic_gate_4b274.constants import (
    COVERAGE_POLICY_VERSION,
    PHASE,
    PROMPT_VERSION_112,
)

KIND_SEPARATOR = "admissible_separator"
ALLOWED_GAP_KINDS = frozenset({KIND_WHITESPACE, KIND_TERMINATOR, KIND_SEPARATOR})

# Isolated punctuation that may sit between already-covered claims.
# Letters, digits, and connective words are never in this set.
SEPARATOR_CHARS = frozenset(
    {
        ",",
        ";",
        ":",
        "—",  # em dash
        "–",  # en dash
        "-",  # hyphen-minus, only when isolated in a gap
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
        '"',
        "'",
        "“",
        "”",
        "‘",
        "’",
        "«",
        "»",
        "…",
    }
)
ELLIPSIS_DOT = "."

PROTECTED_CONNECTIVES = (
    "because",
    "unless",
    "however",
    "therefore",
    "thus",
    "although",
    "only if",
    "not",
    "never",
    "no",
)


def _claim_span(claim: Mapping[str, Any]) -> tuple[Any, Any]:
    start = claim.get("start_offset", claim.get("s"))
    end = claim.get("end_offset", claim.get("e"))
    return start, end


def covered_mask(text: str, claims: Sequence[Mapping[str, Any]]) -> list[bool]:
    covered = [False] * len(text)
    for claim in claims:
        start, end = _claim_span(claim)
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if start < 0 or end < start or end > len(text):
            continue
        for index in range(start, end):
            covered[index] = True
    return covered


def raw_uncovered(text: str, covered: Sequence[bool]) -> list[tuple[int, int]]:
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


def _alnum(char: str) -> bool:
    return char.isalnum()


def _has_covered_bound(
    text: str,
    index: int,
    covered: Sequence[bool],
    *,
    direction: int,
) -> bool:
    cursor = index + direction
    while 0 <= cursor < len(text):
        if covered[cursor]:
            return True
        if _alnum(text[cursor]):
            return False
        cursor += direction
    return direction > 0  # trailing punctuation at end of text is bounded on the right


def _ellipsis_dot_allowed(text: str, index: int, covered: Sequence[bool]) -> bool:
    if index < 0 or index >= len(text) or text[index] != ELLIPSIS_DOT:
        return False
    if index + 1 < len(text) and text[index + 1].isdigit():
        return False
    left_ok = False
    if index > 0 and covered[index - 1]:
        left_ok = True
    elif index > 0 and text[index - 1] == ELLIPSIS_DOT:
        left_ok = _ellipsis_dot_allowed(text, index - 1, covered) or _has_covered_bound(
            text, index, covered, direction=-1
        )
    elif _has_covered_bound(text, index, covered, direction=-1):
        left_ok = True
    if not left_ok:
        return False
    if index + 1 >= len(text):
        return True
    nxt = text[index + 1]
    if nxt.isspace() or nxt == ELLIPSIS_DOT or nxt in SEPARATOR_CHARS:
        return True
    if covered[index + 1]:
        return True
    return False


def classify_character(
    text: str,
    index: int,
    covered: Sequence[bool],
) -> str:
    if index < 0 or index >= len(text):
        return KIND_SIGNIFICANT
    char = text[index]
    if char.isspace():
        return KIND_WHITESPACE
    if is_allowed_sentence_terminator(text, index, covered):
        return KIND_TERMINATOR
    if char in SENTENCE_TERMINATORS and _ellipsis_dot_allowed(text, index, covered):
        return KIND_TERMINATOR
    if char == "…" and _has_covered_bound(text, index, covered, direction=-1):
        return KIND_TERMINATOR
    if char in SEPARATOR_CHARS:
        left = _has_covered_bound(text, index, covered, direction=-1)
        right = _has_covered_bound(text, index, covered, direction=1)
        if left or right:
            return KIND_SEPARATOR
    return KIND_SIGNIFICANT


def classify_gap(
    text: str,
    start: int,
    end: int,
    covered: Sequence[bool],
) -> dict[str, Any]:
    snippet = text[start:end]
    char_kinds = [
        classify_character(text, start + offset, covered)
        for offset, _char in enumerate(snippet)
    ]
    if snippet and all(kind == KIND_WHITESPACE for kind in char_kinds):
        kind = KIND_WHITESPACE
    elif snippet and all(kind in ALLOWED_GAP_KINDS for kind in char_kinds):
        if any(kind == KIND_SEPARATOR for kind in char_kinds) and all(
            kind != KIND_SIGNIFICANT for kind in char_kinds
        ):
            kind = KIND_SEPARATOR if KIND_SEPARATOR in char_kinds else KIND_TERMINATOR
        elif all(kind in {KIND_WHITESPACE, KIND_TERMINATOR} for kind in char_kinds):
            kind = KIND_TERMINATOR if KIND_TERMINATOR in char_kinds else KIND_WHITESPACE
        else:
            kind = KIND_SEPARATOR
    else:
        kind = KIND_SIGNIFICANT
    return {
        "start": start,
        "end": end,
        "text": snippet,
        "codepoints": [ord(char) for char in snippet],
        "isspace_flags": [char.isspace() for char in snippet],
        "char_kinds": char_kinds,
        "kind": kind,
        "python_slice": f"text[{start}:{end}]",
        "interval": "half_open",
        "contains_letter_or_digit": any(_alnum(char) for char in snippet),
        "contains_protected_connective": any(
            token in snippet.lower() for token in PROTECTED_CONNECTIVES
        ),
    }


def subdivide_gap(
    text: str,
    start: int,
    end: int,
    covered: Sequence[bool],
) -> list[dict[str, Any]]:
    """Split a raw gap into maximal runs of the same coverage kind."""
    if start >= end:
        return []
    runs: list[dict[str, Any]] = []
    run_start = start
    run_kind = classify_character(text, start, covered)
    for index in range(start + 1, end):
        kind = classify_character(text, index, covered)
        if kind != run_kind:
            runs.append(classify_gap(text, run_start, index, covered))
            run_start = index
            run_kind = kind
    runs.append(classify_gap(text, run_start, end, covered))
    return runs


def classify_uncovered_gaps_112(
    text: str,
    claims: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    covered = covered_mask(text, claims)
    rows: list[dict[str, Any]] = []
    for start, end in raw_uncovered(text, covered):
        rows.extend(subdivide_gap(text, start, end, covered))
    return rows


def uncovered_significant_spans_112(
    text: str,
    claims: Sequence[Mapping[str, Any]],
) -> list[tuple[int, int]]:
    return [
        (item["start"], item["end"])
        for item in classify_uncovered_gaps_112(text, claims)
        if item["kind"] == KIND_SIGNIFICANT
    ]


def span_validity_audit(
    text: str,
    claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    spans: list[tuple[int, int]] = []
    for index, claim in enumerate(claims):
        start, end = _claim_span(claim)
        check = validate_compact_span(text, start, end)
        if not check.get("valid"):
            errors.extend(f"claim_{index}:{item}" for item in (check.get("errors") or []))
        if not isinstance(start, int) or not isinstance(end, int):
            errors.append(f"claim_{index}:non_integer_offsets")
            continue
        if start == end:
            errors.append(f"claim_{index}:empty_span")
        if start > end:
            errors.append(f"claim_{index}:inverted_span")
        if start < 0 or end > len(text):
            errors.append(f"claim_{index}:out_of_bounds")
        if isinstance(start, int) and isinstance(end, int) and start < end:
            spans.append((start, end))
    overlaps: list[dict[str, int]] = []
    ordered = sorted(spans)
    for left, right in zip(ordered, ordered[1:]):
        if right[0] < left[1] and not (right[0] == left[0] and right[1] == left[1]):
            overlaps.append(
                {
                    "left_start": left[0],
                    "left_end": left[1],
                    "right_start": right[0],
                    "right_end": right[1],
                }
            )
    return {
        "errors": errors,
        "overlaps": overlaps,
        "valid": not errors,
        "overlap_inconsistent": bool(overlaps),
        "original_offsets_unmodified": True,
        "terra_spans_not_shifted": True,
    }


def validate_coverage(
    paragraph: str,
    claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Pure coverage audit. Does not infer that omitted words are covered."""
    covered = covered_mask(paragraph, claims)
    classified = classify_uncovered_gaps_112(paragraph, claims)
    significant = [item for item in classified if item["kind"] == KIND_SIGNIFICANT]
    allowed = [item for item in classified if item["kind"] in ALLOWED_GAP_KINDS]
    spans = span_validity_audit(paragraph, claims)
    status = "PASS" if not significant and spans["valid"] else "FAIL"
    return {
        "phase": PHASE,
        "policy_version": COVERAGE_POLICY_VERSION,
        "offset_convention": dict(OFFSET_CONVENTION),
        "paragraph_length_codepoints": len(paragraph),
        "status": status,
        "classified_gaps": classified,
        "admissible_gaps": allowed,
        "significant_gaps": significant,
        "significant_intervals": [
            [item["start"], item["end"]] for item in significant
        ],
        "span_validity": spans,
        "frozen_1_0_uncovered_spans": [
            list(item)
            for item in uncovered_spans(
                paragraph,
                [
                    {
                        "start_offset": _claim_span(claim)[0],
                        "end_offset": _claim_span(claim)[1],
                    }
                    for claim in claims
                ],
            )
        ],
        "does_not_strip_punctuation": True,
        "does_not_shift_spans": True,
        "does_not_infer_omitted_words_covered": True,
        "protected_remain_mandatory": list(PROTECTED_CONNECTIVES),
        "covered_mask_true_count": sum(1 for item in covered if item),
        "secrets_included": False,
    }


def _reason_code_errors(handle: str, claim: Mapping[str, Any]) -> list[str]:
    kind = str(claim.get("k") or "")
    reasons = list(claim.get("r") or [])
    errors: list[str] = []
    for code in reasons:
        if not isinstance(code, str) or code not in REASON_CODES:
            errors.append(f"{handle}: unknown_reason_{code}")
    if kind in {CLASS_QUESTIONABLE, CLASS_UNSUPPORTED} and not reasons:
        errors.append(f"{handle}: reason_code_missing")
    if kind in {CLASS_SUPPORTED, CLASS_NON_SUBSTANTIVE} and reasons:
        errors.append(f"{handle}: reasons_forbidden_for_{kind}")
    return errors


def validate_compact_payload_112(
    payload: Mapping[str, Any] | None,
    *,
    paragraph_texts: Mapping[str, str],
    required_handles: Sequence[str],
    paragraph_kinds: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """1.1.2 local validation. Does not replace frozen historical validators."""
    base = validate_compact_payload(
        payload,
        paragraph_texts=paragraph_texts,
        required_handles=required_handles,
        paragraph_kinds=paragraph_kinds,
    )
    coverage_errors: list[str] = []
    reason_errors: list[str] = []
    separator_notes: list[dict[str, Any]] = []
    coverage_audits: list[dict[str, Any]] = []
    if isinstance(payload, Mapping):
        for para in payload.get("pr") or []:
            handle = str(para.get("h") or "")
            text = str(paragraph_texts.get(handle) or "")
            claims = list(para.get("c") or [])
            for claim in claims:
                reason_errors.extend(_reason_code_errors(handle, claim))
            audit = validate_coverage(
                text,
                [
                    {
                        "start_offset": claim.get("s"),
                        "end_offset": claim.get("e"),
                    }
                    for claim in claims
                ],
            )
            coverage_audits.append({"handle": handle, **audit})
            if audit["admissible_gaps"]:
                separator_notes.append(
                    {"handle": handle, "allowed": audit["admissible_gaps"]}
                )
            if audit["significant_gaps"]:
                gaps = [(item["start"], item["end"]) for item in audit["significant_gaps"]]
                coverage_errors.append(f"{handle}: significant_coverage_gap_{gaps}")
            span_errors = audit["span_validity"].get("errors") or []
            coverage_errors.extend(f"{handle}: {item}" for item in span_errors)
    errors = [
        item
        for item in (base.get("errors") or [])
        if "coverage_gap_" not in str(item)
        and "unknown_reason_" not in str(item)
        and "reasons_forbidden_for_" not in str(item)
    ]
    # Keep unknown-reason failures from the frozen validator, plus 1.1.2 extras.
    frozen_reason = [
        item
        for item in (base.get("errors") or [])
        if "unknown_reason_" in str(item) or "reasons_forbidden_for_" in str(item)
    ]
    merged_reasons = list(dict.fromkeys(frozen_reason + reason_errors))
    errors.extend(coverage_errors)
    errors.extend(item for item in merged_reasons if item not in errors)
    status = "PASS" if not errors else "FAIL"
    return {
        **base,
        "status": status,
        "errors": errors,
        "coverage_errors": coverage_errors,
        "reason_code_errors": merged_reasons,
        "reason_code_warnings": [],
        "separator_notes": separator_notes,
        "coverage_audits": [
            {
                "handle": item["handle"],
                "status": item["status"],
                "significant_intervals": item["significant_intervals"],
                "admissible_kinds": sorted(
                    {gap["kind"] for gap in item["admissible_gaps"]}
                ),
            }
            for item in coverage_audits
        ],
        "coverage_policy": COVERAGE_POLICY_VERSION,
        "reason_codes_never_silently_normalized": True,
        "frozen_1_1_status_preserved_separately": base.get("status"),
        "candidate_version": PROMPT_VERSION_112,
        "does_not_mutate_historical_validator": True,
        "does_not_rewrite_historical_verdict": True,
    }


__all__ = [
    "ALLOWED_GAP_KINDS",
    "KIND_SEPARATOR",
    "KIND_SIGNIFICANT",
    "KIND_TERMINATOR",
    "KIND_WHITESPACE",
    "PROTECTED_CONNECTIVES",
    "SEPARATOR_CHARS",
    "classify_character",
    "classify_gap",
    "classify_uncovered_gaps_112",
    "covered_mask",
    "raw_uncovered",
    "span_validity_audit",
    "uncovered_significant_spans_112",
    "validate_compact_payload_112",
    "validate_coverage",
]
