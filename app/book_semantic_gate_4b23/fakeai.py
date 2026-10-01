"""Scripted FakeAI semantic-gate fixtures. No engine.generate."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b23.accept import apply_acceptance, canonical_audit
from app.book_semantic_gate_4b23.constants import (
    CLASS_NON_SUBSTANTIVE,
    CLASS_QUESTIONABLE,
    CLASS_SUPPORTED,
    CLASS_UNSUPPORTED,
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_REVIEW,
)


def _claim(
    index: int,
    text: str,
    *,
    start: int,
    end: int,
    kind: str,
    evidence: list[str] | None = None,
    reasons: list[str] | None = None,
    explanation: str,
    confidence: str = "HIGH",
) -> dict[str, Any]:
    return {
        "i": index,
        "t": text,
        "s": start,
        "e": end,
        "k": kind,
        "ev": list(evidence or []),
        "r": list(reasons or []),
        "x": explanation,
        "cf": confidence,
    }


def _paragraph(
    handle: str,
    verdict: str,
    claims: list[dict[str, Any]],
    *,
    evidence: list[str] | None = None,
    reasons: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "h": handle,
        "v": verdict,
        "c": claims,
        "ev": list(evidence or []),
        "r": list(reasons or []),
    }


def _chapter(
    chapter: str,
    verdict: str,
    paragraphs: list[dict[str, Any]],
    *,
    unknown: list[str] | None = None,
    review: bool,
    counts: dict[str, int],
) -> dict[str, Any]:
    return {
        "ch": chapter,
        "v": verdict,
        "pr": paragraphs,
        "sc": counts,
        "uh": list(unknown or []),
        "rr": review,
    }


SUPPORTED_TEXT = (
    "Do not ever be afraid of death. There is no fixed hour appointed."
)
CAUSAL_CORE = (
    "Fear of death is an abuse. The devil has used it since the beginning."
)
CAUSAL_CLAUSE = " because it still works wherever it is not resisted by truth."
CAUSAL_TEXT = CAUSAL_CORE + CAUSAL_CLAUSE
FUNERAL_TEXT = (
    "Death as gain must be your reality, not a verse quoted at funerals."
)
REF_CORE = "This is the ground on which 1 Corinthians 15 stands."
REF_CLAUSE = " so that the sting long since removed from death is practiced."
REF_TEXT = REF_CORE + REF_CLAUSE
UNCERTAIN_TEXT = "The source says this may be the case; it is certainly always true."
CONNECTIVE_TEXT = "The question left standing is simpler and harder."
UNKNOWN_TEXT = "A later paragraph continues the same instruction."


def fixture_supported() -> dict[str, Any]:
    return {
        "name": "supported",
        "texts": {"p2": SUPPORTED_TEXT},
        "required": ["p2"],
        "allowed": ["IDEA224", "SRC006149"],
        "parsed": _chapter(
            "CH016",
            VERDICT_PASS,
            [
                _paragraph(
                    "p2",
                    CLASS_SUPPORTED,
                    [
                        _claim(
                            0,
                            SUPPORTED_TEXT,
                            start=0,
                            end=len(SUPPORTED_TEXT),
                            kind=CLASS_SUPPORTED,
                            evidence=["IDEA224", "SRC006149"],
                            explanation="Paraphrase of supplied IDEA224 / SRC.",
                        )
                    ],
                    evidence=["IDEA224", "SRC006149"],
                )
            ],
            review=False,
            counts={
                "supported": 1,
                "questionable": 0,
                "unsupported": 0,
                "non_substantive": 0,
            },
        ),
        "expect_verdict": VERDICT_PASS,
        "expect_cache": True,
    }


def fixture_new_causal_link() -> dict[str, Any]:
    core_end = len(CAUSAL_CORE)
    return {
        "name": "new_causal_link",
        "texts": {"p3": CAUSAL_TEXT},
        "required": ["p3"],
        "allowed": ["IDEA225", "SRC006152"],
        "parsed": _chapter(
            "CH016",
            VERDICT_REVIEW,
            [
                _paragraph(
                    "p3",
                    CLASS_QUESTIONABLE,
                    [
                        _claim(
                            0,
                            CAUSAL_CORE,
                            start=0,
                            end=core_end,
                            kind=CLASS_SUPPORTED,
                            evidence=["IDEA225", "SRC006152"],
                            explanation="Core abuse / unchanged strategy is supplied.",
                        ),
                        _claim(
                            1,
                            CAUSAL_CLAUSE.strip(),
                            start=core_end + 1,
                            end=len(CAUSAL_TEXT),
                            kind=CLASS_QUESTIONABLE,
                            evidence=["IDEA225"],
                            reasons=["NEW_CAUSAL_LINK"],
                            explanation="Causal 'because it still works' is not in evidence.",
                        ),
                    ],
                    evidence=["IDEA225", "SRC006152"],
                    reasons=["NEW_CAUSAL_LINK"],
                )
            ],
            review=True,
            counts={
                "supported": 1,
                "questionable": 1,
                "unsupported": 0,
                "non_substantive": 0,
            },
        ),
        "expect_verdict": VERDICT_REVIEW,
        "expect_cache": False,
        "expect_reason": "NEW_CAUSAL_LINK",
        "expect_class": CLASS_QUESTIONABLE,
    }


def fixture_invented_example() -> dict[str, Any]:
    return {
        "name": "invented_example",
        "texts": {"p8": FUNERAL_TEXT},
        "required": ["p8"],
        "allowed": ["IDEA226"],
        "parsed": _chapter(
            "CH016",
            VERDICT_FAIL,
            [
                _paragraph(
                    "p8",
                    CLASS_UNSUPPORTED,
                    [
                        _claim(
                            0,
                            FUNERAL_TEXT,
                            start=0,
                            end=len(FUNERAL_TEXT),
                            kind=CLASS_UNSUPPORTED,
                            evidence=["IDEA226"],
                            reasons=["INVENTED_EXAMPLE"],
                            explanation="Funeral-verse illustration is absent from evidence.",
                        )
                    ],
                    evidence=["IDEA226"],
                    reasons=["INVENTED_EXAMPLE"],
                )
            ],
            review=True,
            counts={
                "supported": 0,
                "questionable": 0,
                "unsupported": 1,
                "non_substantive": 0,
            },
        ),
        "expect_verdict": VERDICT_FAIL,
        "expect_cache": False,
        "expect_reason": "INVENTED_EXAMPLE",
        "expect_class": CLASS_UNSUPPORTED,
    }


def fixture_reference_completion() -> dict[str, Any]:
    core_end = len(REF_CORE)
    return {
        "name": "reference_completion",
        "texts": {"p8": REF_TEXT},
        "required": ["p8"],
        "allowed": ["REF050", "SRC006788"],
        "parsed": _chapter(
            "CH016",
            VERDICT_REVIEW,
            [
                _paragraph(
                    "p8",
                    CLASS_QUESTIONABLE,
                    [
                        _claim(
                            0,
                            REF_CORE,
                            start=0,
                            end=core_end,
                            kind=CLASS_SUPPORTED,
                            evidence=["REF050", "SRC006788"],
                            explanation="1 Corinthians 15 identity is supplied.",
                        ),
                        _claim(
                            1,
                            REF_CLAUSE.strip(),
                            start=core_end + 1,
                            end=len(REF_TEXT),
                            kind=CLASS_QUESTIONABLE,
                            evidence=["REF050"],
                            reasons=["REFERENCE_COMPLETION"],
                            explanation="Sting wording completes partial REF050.",
                        ),
                    ],
                    evidence=["REF050", "SRC006788"],
                    reasons=["REFERENCE_COMPLETION"],
                )
            ],
            review=True,
            counts={
                "supported": 1,
                "questionable": 1,
                "unsupported": 0,
                "non_substantive": 0,
            },
        ),
        "expect_verdict": VERDICT_REVIEW,
        "expect_cache": False,
        "expect_reason": "REFERENCE_COMPLETION",
        "expect_class": CLASS_QUESTIONABLE,
    }


def fixture_uncertainty_strengthened() -> dict[str, Any]:
    return {
        "name": "uncertainty_strengthened",
        "texts": {"p4": UNCERTAIN_TEXT},
        "required": ["p4"],
        "allowed": ["UNC001", "SRC000001"],
        "parsed": _chapter(
            "CH016",
            VERDICT_FAIL,
            [
                _paragraph(
                    "p4",
                    CLASS_UNSUPPORTED,
                    [
                        _claim(
                            0,
                            UNCERTAIN_TEXT,
                            start=0,
                            end=len(UNCERTAIN_TEXT),
                            kind=CLASS_UNSUPPORTED,
                            evidence=["UNC001"],
                            reasons=["UNCERTAINTY_STRENGTHENED"],
                            explanation="may/possible raised to certainly always.",
                        )
                    ],
                    evidence=["UNC001"],
                    reasons=["UNCERTAINTY_STRENGTHENED"],
                )
            ],
            review=True,
            counts={
                "supported": 0,
                "questionable": 0,
                "unsupported": 1,
                "non_substantive": 0,
            },
        ),
        "expect_verdict": VERDICT_FAIL,
        "expect_cache": False,
        "expect_reason": "UNCERTAINTY_STRENGTHENED",
        "expect_class": CLASS_UNSUPPORTED,
    }


def fixture_pure_connective() -> dict[str, Any]:
    return {
        "name": "pure_connective",
        "texts": {"p1": CONNECTIVE_TEXT},
        "required": ["p1"],
        "allowed": [],
        "parsed": _chapter(
            "CH016",
            VERDICT_PASS,
            [
                _paragraph(
                    "p1",
                    CLASS_NON_SUBSTANTIVE,
                    [
                        _claim(
                            0,
                            CONNECTIVE_TEXT,
                            start=0,
                            end=len(CONNECTIVE_TEXT),
                            kind=CLASS_NON_SUBSTANTIVE,
                            explanation="Rhetorical orientation only.",
                        )
                    ],
                )
            ],
            review=False,
            counts={
                "supported": 0,
                "questionable": 0,
                "unsupported": 0,
                "non_substantive": 1,
            },
        ),
        "expect_verdict": VERDICT_PASS,
        "expect_cache": True,
        "expect_class": CLASS_NON_SUBSTANTIVE,
    }


def fixture_unknown_handle() -> dict[str, Any]:
    return {
        "name": "unknown_handle",
        "texts": {"p2": SUPPORTED_TEXT},
        "required": ["p2"],
        "allowed": ["IDEA224"],
        "parsed": _chapter(
            "CH016",
            VERDICT_PASS,
            [
                _paragraph(
                    "p9",
                    CLASS_SUPPORTED,
                    [
                        _claim(
                            0,
                            SUPPORTED_TEXT,
                            start=0,
                            end=len(SUPPORTED_TEXT),
                            kind=CLASS_SUPPORTED,
                            evidence=["IDEA999"],
                            explanation="Unknown paragraph and evidence handles.",
                        )
                    ],
                    evidence=["IDEA999"],
                )
            ],
            unknown=["p9", "IDEA999"],
            review=False,
            counts={
                "supported": 1,
                "questionable": 0,
                "unsupported": 0,
                "non_substantive": 0,
            },
        ),
        "expect_verdict": VERDICT_FAIL,
        "expect_cache": False,
    }


def fixture_missing_paragraph() -> dict[str, Any]:
    return {
        "name": "missing_paragraph",
        "texts": {"p2": SUPPORTED_TEXT, "p3": CAUSAL_TEXT},
        "required": ["p2", "p3"],
        "allowed": ["IDEA224"],
        "parsed": _chapter(
            "CH016",
            VERDICT_PASS,
            [
                _paragraph(
                    "p2",
                    CLASS_SUPPORTED,
                    [
                        _claim(
                            0,
                            SUPPORTED_TEXT,
                            start=0,
                            end=len(SUPPORTED_TEXT),
                            kind=CLASS_SUPPORTED,
                            evidence=["IDEA224"],
                            explanation="Only one of two required paragraphs.",
                        )
                    ],
                    evidence=["IDEA224"],
                )
            ],
            review=False,
            counts={
                "supported": 1,
                "questionable": 0,
                "unsupported": 0,
                "non_substantive": 0,
            },
        ),
        "expect_verdict": VERDICT_FAIL,
        "expect_cache": False,
    }


def all_fixtures() -> list[dict[str, Any]]:
    return [
        fixture_supported(),
        fixture_new_causal_link(),
        fixture_invented_example(),
        fixture_reference_completion(),
        fixture_uncertainty_strengthened(),
        fixture_pure_connective(),
        fixture_unknown_handle(),
        fixture_missing_paragraph(),
    ]


def interpret_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    result = apply_acceptance(
        fixture["parsed"],
        required_handles=fixture["required"],
        paragraph_texts=fixture["texts"],
        allowed_handles=fixture.get("allowed"),
        deterministic_validator_pass=True,
    )
    return {
        "name": fixture["name"],
        "result": result,
        "canonical": canonical_audit(result),
        "expect_verdict": fixture["expect_verdict"],
        "expect_cache": fixture["expect_cache"],
        "match": (
            result["verdict"] == fixture["expect_verdict"]
            and result["cache_acceptance"] == fixture["expect_cache"]
        ),
    }


def run_fakeai_catalog() -> dict[str, Any]:
    rows = [interpret_fixture(item) for item in all_fixtures()]
    first = interpret_fixture(fixture_supported())
    second = interpret_fixture(fixture_supported())
    deterministic = first["canonical"] == second["canonical"]
    return {
        "cases": rows,
        "passed": all(item["match"] for item in rows) and deterministic,
        "determinism": deterministic,
        "count": len(rows),
    }


__all__ = [
    "all_fixtures",
    "interpret_fixture",
    "run_fakeai_catalog",
]
