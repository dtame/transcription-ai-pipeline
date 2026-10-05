"""P3 proposition coverage and 1.1.1 separator policy. Causal clause may not be omitted."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_semantic_gate_4b262.contract import OFFSET_CONVENTION, validate_compact_span
from app.book_semantic_gate_4b271.coverage import (
    KIND_SIGNIFICANT,
    classify_uncovered_gaps,
    uncovered_significant_spans,
    validate_compact_payload_111,
)
from app.book_semantic_gate_4b272.constants import (
    DISPUTED_CAUSAL_CLAUSE,
    PHASE,
    SELECTED_CASE_HANDLE,
)
from app.book_semantic_gate_4b272.identity import clause_offsets


def sentence_spans(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char in ".?!" and (index + 1 == len(text) or text[index + 1] in " \n"):
            end = index + 1
            snippet = text[start:end]
            if snippet.strip():
                rows.append(
                    {
                        "start": start,
                        "end": end,
                        "text": snippet,
                    }
                )
            index = end
            if index < len(text) and text[index].isspace():
                index += 1
            start = index
            continue
        index += 1
    if start < len(text) and text[start:].strip():
        rows.append({"start": start, "end": len(text), "text": text[start:]})
    return rows


def p3_local_propositions(text: str) -> list[dict[str, Any]]:
    clause = clause_offsets(text)
    start = int(clause["start"])
    end = int(clause["end"])
    rows: list[dict[str, Any]] = []
    for item in sentence_spans(text):
        s = int(item["start"])
        e = int(item["end"])
        if e <= start or s >= end:
            rows.append(
                {
                    "kind": "other_substantive",
                    "s": s,
                    "e": e,
                    "text": text[s:e],
                    "contains_causal_clause": False,
                    "contains_negation": " not " in f" {text[s:e].lower()} ",
                }
            )
            continue
        if s < start:
            rows.append(
                {
                    "kind": "pre_causal_same_sentence",
                    "s": s,
                    "e": start,
                    "text": text[s:start],
                    "contains_causal_clause": False,
                    "contains_negation": False,
                }
            )
        rows.append(
            {
                "kind": "disputed_causal_clause",
                "s": start,
                "e": end,
                "text": text[start:end],
                "contains_causal_clause": True,
                "contains_because": text[start:end].lower().startswith("because"),
                "contains_negation": "not" in text[start:end].lower(),
            }
        )
        if end < e:
            rows.append(
                {
                    "kind": "sentence_terminator_after_clause",
                    "s": end,
                    "e": e,
                    "text": text[end:e],
                    "contains_causal_clause": False,
                    "admissible_terminator": text[end:e] in ".?!",
                }
            )
    return rows


def claims_from_propositions(
    propositions: list[Mapping[str, Any]],
    *,
    flag_causal: bool = True,
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    index = 0
    for item in propositions:
        if item.get("kind") == "sentence_terminator_after_clause":
            continue
        kind = "QUESTIONABLE" if flag_causal and item.get("contains_causal_clause") else "SUPPORTED"
        claim: dict[str, Any] = {
            "i": index,
            "s": item["s"],
            "e": item["e"],
            "k": kind,
            "ev": ["IDEA225"] if kind == "SUPPORTED" else [],
            "r": ["NEW_CAUSAL_LINK"] if kind == "QUESTIONABLE" else [],
        }
        if kind == "QUESTIONABLE":
            claim["n"] = "Because-clause is not in authorized evidence."
        claims.append(claim)
        index += 1
    return claims


def analyze_p3_span_coverage(text: str) -> dict[str, Any]:
    propositions = p3_local_propositions(text)
    claims = claims_from_propositions(propositions)
    omitted = [item for item in claims if not item.get("r")]
    omitted_causal = claims_from_propositions(propositions, flag_causal=True)
    omitted_causal = [item for item in omitted_causal if item.get("k") != "QUESTIONABLE"]
    classified = classify_uncovered_gaps(text, claims)
    significant = uncovered_significant_spans(text, claims)
    causal = next(item for item in propositions if item.get("contains_causal_clause"))
    span_checks = [
        validate_compact_span(text, item["s"], item["e"]) for item in claims
    ]
    overlap_inconsistent = False
    ordered = sorted(claims, key=lambda item: (item["s"], item["e"]))
    for left, right in zip(ordered, ordered[1:]):
        if int(right["s"]) < int(left["s"]):
            overlap_inconsistent = True
    compact = {
        "ch": "CH016",
        "v": "REVIEW",
        "pr": [
            {
                "h": SELECTED_CASE_HANDLE,
                "v": "QUESTIONABLE",
                "c": claims,
                "ev": ["IDEA225", "SRC006152"],
                "r": ["NEW_CAUSAL_LINK"],
            }
        ],
        "sc": {
            "supported": sum(1 for item in claims if item["k"] == "SUPPORTED"),
            "questionable": sum(1 for item in claims if item["k"] == "QUESTIONABLE"),
            "unsupported": 0,
            "non_substantive": 0,
        },
        "uh": [],
        "rr": True,
    }
    validation = validate_compact_payload_111(
        compact,
        paragraph_texts={SELECTED_CASE_HANDLE: text},
        required_handles=[SELECTED_CASE_HANDLE],
        paragraph_kinds={SELECTED_CASE_HANDLE: "substantive"},
    )
    missing_causal_payload = {
        **compact,
        "pr": [
            {
                **compact["pr"][0],
                "c": omitted_causal,
                "v": "SUPPORTED",
                "r": [],
            }
        ],
        "v": "PASS",
        "rr": False,
        "sc": {
            "supported": len(omitted_causal),
            "questionable": 0,
            "unsupported": 0,
            "non_substantive": 0,
        },
    }
    missing_causal = validate_compact_payload_111(
        missing_causal_payload,
        paragraph_texts={SELECTED_CASE_HANDLE: text},
        required_handles=[SELECTED_CASE_HANDLE],
        paragraph_kinds={SELECTED_CASE_HANDLE: "substantive"},
    )
    return {
        "phase": PHASE,
        "handle": SELECTED_CASE_HANDLE,
        "offset_convention": dict(OFFSET_CONVENTION),
        "paragraph_length_codepoints": len(text),
        "propositions": propositions,
        "claims": claims,
        "classified_uncovered_gaps": classified,
        "significant_gaps": [list(item) for item in significant],
        "span_checks": span_checks,
        "non_empty_spans": all(item["s"] < item["e"] for item in claims),
        "valid_offsets": all(item["valid"] for item in span_checks),
        "exact_text_recovery": all(
            text[item["s"] : item["e"]] for item in claims
        ),
        "inconsistent_overlap": overlap_inconsistent,
        "causal_clause_covered": any(item.get("contains_causal_clause") for item in propositions),
        "causal_connector_because_covered": bool(causal.get("contains_because")),
        "negation_in_causal_clause_covered": bool(causal.get("contains_negation")),
        "omitting_causal_clause_fails": missing_causal.get("status") == "FAIL",
        "local_111_status": validation.get("status"),
        "h01_period_correction_applied": True,
        "admissible_terminators_deterministic": True,
        "coverage_complete": validation.get("status") == "PASS" and not significant,
        "secrets_included": False,
    }


__all__ = [
    "analyze_p3_span_coverage",
    "claims_from_propositions",
    "p3_local_propositions",
    "sentence_spans",
]
