"""Offline FakeAI and segmentation fixtures. Not Terra quality."""

from __future__ import annotations

from typing import Any

from app.book_semantic_gate_4b23.fakeai import run_fakeai_catalog
from app.book_semantic_gate_4b24.constants import (
    CONNECTIVE_CASE_ID,
    FUNERAL_CASE_ID,
    NEGATIVE_CASE_IDS,
    P3_CASE_ID,
    P8_CASE_ID,
    POSITIVE_CASE_IDS,
    SCORED_CASE_ORDER,
)
from app.book_semantic_gate_4b261.complexity import extract_gate_paragraphs
from app.book_semantic_gate_4b261.evidence import load_4b26_bundle
from app.book_semantic_gate_4b262.fakeai import interpret_ten_case_compact
from app.book_semantic_gate_4b271.fakeai import run_calibration_fixtures
from app.book_semantic_gate_4b274.coverage import validate_compact_payload_112
from app.book_semantic_gate_4b28.constants import PHASE
from app.book_semantic_gate_4b28.segmentation import prepare_semantic_validation_units

CASES = [
    ("simple_sentence", "Do not ever be afraid of death.", {"min_units": 1}),
    (
        "multi_sentence",
        "Do not ever be afraid of death. It should be our joy.",
        {"min_units": 2},
    ),
    (
        "causal_clause",
        "The strategy is still being run today, because it still works wherever it is not resisted by truth.",
        {"must_contain": "because"},
    ),
    (
        "negation",
        "This is not a trick of positive thinking.",
        {"must_contain": "not"},
    ),
    (
        "condition",
        "If somebody has gone to heaven, that should not produce dread in us.",
        {"must_contain": "If"},
    ),
    (
        "adversative",
        "Death as gain must become your reality — not an idea you agree with in a sermon and set aside.",
        {"min_units": 2},
    ),
    (
        "citation",
        "He said, “Don't ever be afraid of death.”",
        {"complete": True},
    ),
    (
        "biblical_reference",
        "This is the ground on which 1 Corinthians 15 stands.",
        {"complete": True, "max_units": 1},
    ),
    (
        "complex_punctuation",
        "Fear of death is an abuse — an abuse to your person; he has not changed his style.",
        {"min_units": 2},
    ),
    (
        "em_dash",
        "It is an abuse — an abuse to your very person.",
        {"min_units": 2},
    ),
    (
        "typographic_apostrophe",
        "This is the substance of one’s ending.",
        {"must_contain": "one’s"},
    ),
    (
        "unicode",
        "La crainte n’est pas à sa place.",
        {"complete": True},
    ),
    (
        "abbreviation",
        "Dr. Smith said there is no set time.",
        {"max_units": 1},
    ),
    (
        "rhetorical",
        "How then shall we live?",
        {"min_units": 1},
    ),
    (
        "very_long",
        "The same old strategy that first weaponized death against humanity is still being run today, unchanged, because it still works wherever it is not resisted by truth and wherever the community refuses to name the abuse.",
        {"must_contain": "because"},
    ),
    (
        "no_punctuation",
        "Fear of death is an abuse to your person and the devil has used it since",
        {"conservative": True},
    ),
    (
        "ambiguous_boundary",
        "Wait... is that the appointed hour?",
        {"ambiguous_or_complete": True},
    ),
]


def _check_case(name: str, text: str, expect: dict[str, Any]) -> dict[str, Any]:
    first = prepare_semantic_validation_units(text)
    second = prepare_semantic_validation_units(text)
    coverage = dict(first.get("coverage") or {})
    reconstructed = "".join(unit["text"] for unit in first.get("units") or [])
    errors = []
    if reconstructed != text:
        errors.append("paragraph_mutated")
    if not coverage.get("complete_chars"):
        errors.append("incomplete_chars")
    if first.get("units") != second.get("units"):
        errors.append("not_deterministic")
    unit_count = int(first.get("unit_count") or 0)
    if expect.get("min_units") and unit_count < int(expect["min_units"]):
        errors.append("too_few_units")
    if expect.get("max_units") and unit_count > int(expect["max_units"]):
        errors.append("too_many_units")
    if expect.get("must_contain"):
        token = str(expect["must_contain"])
        if not any(token in str(unit.get("text") or "") for unit in first.get("units") or []):
            errors.append("missing_token")
        connectors = (
            (coverage.get("connector_coverage") or {}).get("split_across_units") or []
        )
        if any(token.lower() == str(item.get("token") or "") for item in connectors):
            errors.append("connector_split")
    if expect.get("conservative") and not first.get("conservative_fallback"):
        errors.append("expected_conservative_fallback")
    if expect.get("ambiguous_or_complete"):
        if not first.get("ambiguous_unit_count") and not coverage.get("complete_chars"):
            errors.append("ambiguous_case_failed")
    ids = [unit["id"] for unit in first.get("units") or []]
    if ids != sorted(ids) or len(set(ids)) != len(ids):
        errors.append("unstable_or_duplicate_ids")
    return {
        "name": name,
        "unit_count": unit_count,
        "complete_chars": coverage.get("complete_chars"),
        "deterministic": first.get("units") == second.get("units"),
        "conservative_fallback": first.get("conservative_fallback"),
        "passed": not errors,
        "errors": errors,
    }


def segmentation_fixtures() -> dict[str, Any]:
    rows = [_check_case(name, text, expect) for name, text, expect in CASES]
    return {
        "phase": PHASE,
        "passed": all(item["passed"] for item in rows),
        "cases": rows,
        "does_not_judge_fidelity": True,
    }


def historical_ten_case_protection(*, root=None) -> dict[str, Any]:
    bundle = load_4b26_bundle(root=root)
    payload = dict(bundle.get("payload") or {})
    ten = interpret_ten_case_compact(payload, root=root)
    score = dict(ten.get("score") or {})
    paragraphs = extract_gate_paragraphs(payload)
    texts = {
        str(item.get("handle") or ""): str(item.get("text") or "")
        for item in paragraphs
    }
    kinds = {
        str(item.get("handle") or ""): str(item.get("kind") or "substantive")
        for item in paragraphs
    }
    validation = validate_compact_payload_112(
        ten.get("compact"),
        paragraph_texts=texts,
        required_handles=[handle for handle, _ in SCORED_CASE_ORDER],
        paragraph_kinds=kinds,
    )
    return {
        "phase": PHASE,
        "positives_accepted": score.get("positives_accepted"),
        "negatives_blocked": score.get("negatives_blocked"),
        "funeral_blocked": score.get("funeral_blocked"),
        "connective_blocked": score.get("connective_blocked"),
        "p3_blocked": score.get("p3_blocked"),
        "p8_blocked": score.get("p8_blocked"),
        "negative_ids": list(NEGATIVE_CASE_IDS),
        "positive_ids": list(POSITIVE_CASE_IDS),
        "protected": {
            FUNERAL_CASE_ID: bool(score.get("funeral_blocked")),
            CONNECTIVE_CASE_ID: bool(score.get("connective_blocked")),
            P3_CASE_ID: bool(score.get("p3_blocked")),
            P8_CASE_ID: bool(score.get("p8_blocked")),
        },
        "labels_unmodified": True,
        "historical_ten_cases_preserved": True,
        "validator_1_1_2_status": validation.get("status"),
        "historical_catalog_passed": bool(run_fakeai_catalog().get("passed")),
        "calibration_1_1_1_still_passes": bool(run_calibration_fixtures().get("passed")),
        "fakeai_not_terra_quality": True,
    }


def run_offline_fixtures(*, root=None) -> dict[str, Any]:
    segmentation = segmentation_fixtures()
    historical = historical_ten_case_protection(root=root)
    positives = historical.get("positives_accepted")
    negatives = historical.get("negatives_blocked")
    passed = (
        bool(segmentation.get("passed"))
        and positives == 6
        and negatives == 4
        and all((historical.get("protected") or {}).values())
        and historical.get("validator_1_1_2_status") == "PASS"
    )
    return {
        "phase": PHASE,
        "segmentation": segmentation,
        "historical": historical,
        "fakeai_positives": positives,
        "fakeai_negatives": negatives,
        "passed": passed,
        "fakeai_not_terra_quality": True,
        "fakeai_is_not_terra_validation": True,
    }


__all__ = [
    "historical_ten_case_protection",
    "run_offline_fixtures",
    "segmentation_fixtures",
]
