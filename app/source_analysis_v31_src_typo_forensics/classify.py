"""Classification forensique des jetons SRC. Aucune réparation production."""

from __future__ import annotations

import re
from typing import Any

from app.source_analysis_local_v3.source_refs import (
    SRC_PREFIX,
    SRC_WIDTH,
    classify_src_token,
    is_canonical_src,
)
from app.source_analysis_v31_src_typo_forensics.constants import (
    EXPECTED_CANONICAL,
    MALFORMED_TOKEN,
    NUMERIC_PAYLOAD,
)

_LETTER_DIGIT = re.compile(r"^([A-Za-z]{3,6})([0-9]+)$")
_DIGIT_RUN = re.compile(r"[0-9]+")


def levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, left_ch in enumerate(left, start=1):
        current = [i]
        for j, right_ch in enumerate(right, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (left_ch != right_ch)
            current.append(min(insert, delete, replace))
        previous = current
    return previous[-1]


def edit_script(source: str, target: str) -> dict[str, Any]:
    """Alignement simple source→target. Compte insertions / suppressions / substitutions."""
    n, m = len(source), len(target)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i
    for j in range(1, m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if source[i - 1] == target[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
    i, j = n, m
    inserted: list[str] = []
    deleted: list[str] = []
    substituted: list[str] = []
    case_changes: list[str] = []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and source[i - 1] == target[j - 1]:
            i -= 1
            j -= 1
            continue
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            left_ch, right_ch = source[i - 1], target[j - 1]
            if left_ch.lower() == right_ch.lower():
                case_changes.append(f"{left_ch}→{right_ch}")
            else:
                substituted.append(f"{left_ch}→{right_ch}")
            i -= 1
            j -= 1
            continue
        if j > 0 and dp[i][j] == dp[i][j - 1] + 1:
            inserted.append(target[j - 1])
            j -= 1
            continue
        if i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            deleted.append(source[i - 1])
            i -= 1
            continue
        break
    return {
        "distance": dp[n][m],
        "inserted": list(reversed(inserted)),
        "deleted": list(reversed(deleted)),
        "substituted": list(reversed(substituted)),
        "case_changes": list(reversed(case_changes)),
    }


def analyze_transformation(malformed: str, canonical: str) -> dict[str, Any]:
    digits_malformed = "".join(_DIGIT_RUN.findall(malformed))
    digits_canonical = "".join(_DIGIT_RUN.findall(canonical))
    match_m = _LETTER_DIGIT.fullmatch(malformed)
    match_c = _LETTER_DIGIT.fullmatch(canonical)
    prefix_m = match_m.group(1) if match_m else malformed
    prefix_c = match_c.group(1) if match_c else canonical[:3]
    script = edit_script(canonical, malformed)
    casefold_script = edit_script(canonical.casefold(), malformed.casefold())
    prefix_script = edit_script(prefix_c, prefix_m)
    return {
        "from": canonical,
        "to": malformed,
        "edit_distance_case_sensitive": script["distance"],
        "edit_distance_case_insensitive": casefold_script["distance"],
        "prefix_from": prefix_c,
        "prefix_to": prefix_m,
        "prefix_edit_distance_case_sensitive": prefix_script["distance"],
        "prefix_edit_distance_case_insensitive": levenshtein(
            prefix_c.casefold(), prefix_m.casefold()
        ),
        "inserted": script["inserted"],
        "deleted": script["deleted"],
        "substituted": script["substituted"],
        "case_changes": script["case_changes"],
        "prefix_corruption": prefix_m != prefix_c,
        "numeric_from": digits_canonical,
        "numeric_to": digits_malformed,
        "numeric_payload_preserved": digits_malformed == digits_canonical,
        "option_b_full_token_ed1": script["distance"] == 1,
        "production_corrected": False,
    }


def forensic_token_class(
    token: Any,
    *,
    allowed: set[str],
    owned: set[str],
    seen_in_record: set[str],
) -> str:
    if not isinstance(token, str) or not token:
        return "OTHER"
    lexical = classify_src_token(token)
    if lexical == "canonical":
        if token in seen_in_record:
            return "DUPLICATE_WHERE_FORBIDDEN"
        if token in owned or token in allowed:
            return "VALID_EXACT"
        if token in owned:
            return "VALID_EXACT"
        return "OUT_OF_WINDOW" if token.startswith("SRC") else "UNKNOWN_CANONICAL_ID"
    if lexical == "wrong_case":
        return "WRONG_CASE"
    if lexical == "missing_zeros" or lexical == "excessive_digits":
        return "WRONG_ZERO_PADDING"
    digits = "".join(_DIGIT_RUN.findall(token))
    match = _LETTER_DIGIT.fullmatch(token)
    if match:
        prefix, numeric = match.group(1), match.group(2)
        if len(numeric) != SRC_WIDTH:
            return "MALFORMED_NUMERIC_PART"
        if prefix.casefold() == SRC_PREFIX.casefold() and prefix != SRC_PREFIX:
            return "WRONG_CASE"
        if numeric == NUMERIC_PAYLOAD or len(numeric) == SRC_WIDTH:
            prefix_ed = levenshtein(SRC_PREFIX.casefold(), prefix.casefold())
            if prefix != SRC_PREFIX and prefix_ed <= 1:
                if len(prefix) > len(SRC_PREFIX):
                    return "INSERTED_CHARACTER"
                if len(prefix) < len(SRC_PREFIX):
                    return "DELETED_CHARACTER"
                return "SUBSTITUTED_CHARACTER"
            if prefix != SRC_PREFIX:
                return "WRONG_PREFIX"
    if lexical == "separator_mutated":
        return "OTHER"
    return "OTHER"


def srec_transformation() -> dict[str, Any]:
    analysis = analyze_transformation(MALFORMED_TOKEN, EXPECTED_CANONICAL)
    analysis["observed_token"] = MALFORMED_TOKEN
    analysis["expected_canonical"] = EXPECTED_CANONICAL
    analysis["numeric_payload"] = NUMERIC_PAYLOAD
    analysis["same_general_class_as_a19"] = True
    analysis["distinct_manifestation_from_a19"] = (
        "A.19 = 3-letter prefix case-only (SRc); "
        "A.31 = 4-letter prefix insertion+case (SRec)"
    )
    return analysis


__all__ = [
    "analyze_transformation",
    "edit_script",
    "forensic_token_class",
    "is_canonical_src",
    "levenshtein",
    "srec_transformation",
]
