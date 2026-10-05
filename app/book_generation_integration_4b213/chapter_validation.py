"""Chapter-level FakeAI validation catalog for 4B.2.13."""

from __future__ import annotations

from typing import Any

from app.book_generation_integration_4b213.cache import IsolatedChapterCache, cache_document
from app.book_generation_integration_4b213.constants import (
    DECISION_BLOCK,
    DECISION_PASS,
    DECISION_REVIEW,
    FAKEAI_SOURCE,
    PHASE,
)
from app.book_generation_integration_4b213.fakeai import SEMANTIC_SCENARIO_MAP
from app.book_generation_integration_4b213.orchestrator import orchestrate_chapter
from app.book_generation_integration_4b213.phase5 import phase5_interface
from app.book_generation_integration_4b213.policy import policy_document

CHAPTER_EXPECTATIONS = {
    "fully_supported": DECISION_PASS,
    "invented_causality": DECISION_BLOCK,
    "invented_implication": DECISION_BLOCK,
    "universal_guarantee": DECISION_BLOCK,
    "unsupported_reference": DECISION_BLOCK,
    "legitimate_paraphrase": DECISION_PASS,
    "questionable": DECISION_REVIEW,
    "invalid_json": DECISION_BLOCK,
    "missing_response": DECISION_BLOCK,
    "invalid_evidence_handle": DECISION_BLOCK,
    "missing_evidence": DECISION_BLOCK,
}


def run_chapter_scenarios() -> dict[str, Any]:
    cache = IsolatedChapterCache()
    rows = []
    ok = True
    decisions = {DECISION_PASS: 0, DECISION_REVIEW: 0, DECISION_BLOCK: 0}
    for name, expected in CHAPTER_EXPECTATIONS.items():
        result = orchestrate_chapter(scenario=name, cache=cache)
        decision = result.get("decision")
        match = decision == expected
        if not match:
            ok = False
        if decision in decisions:
            decisions[decision] += 1
        coverage_ok = all(
            item.get("coverage_ok") or item.get("kind") == "connective" or not item.get("evidence_ok")
            for item in result.get("paragraph_results") or []
        )
        rows.append(
            {
                "scenario": name,
                "source": FAKEAI_SOURCE,
                "not_terra": True,
                "not_sonnet": True,
                "expected": expected,
                "decision": decision,
                "state": result.get("state"),
                "match": match,
                "isolated_acceptance_candidate": result.get("isolated_acceptance_candidate"),
                "presented_as_validated_chapter": result.get("presented_as_validated_chapter"),
                "production_cache_write": result.get("production_cache_write"),
                "coverage_ok_when_required": coverage_ok,
            }
        )
    sample_pass = next((row for row in rows if row["decision"] == DECISION_PASS), None)
    return {
        "phase": PHASE,
        "source": FAKEAI_SOURCE,
        "passed": ok,
        "scenarios": rows,
        "counts": decisions,
        "policy": policy_document(),
        "cache": cache.to_dict(),
        "cache_document": cache_document(),
        "phase5_sample": phase5_interface(
            orchestrate_chapter(scenario="fully_supported")
        ),
        "pass_review_block_covered": (
            decisions[DECISION_PASS] > 0
            and decisions[DECISION_REVIEW] > 0
            and decisions[DECISION_BLOCK] > 0
        ),
        "semantic_map": dict(SEMANTIC_SCENARIO_MAP),
        "sample_pass_not_production": (
            not (sample_pass or {}).get("production_cache_write")
            and not (sample_pass or {}).get("presented_as_validated_chapter")
        ),
        "secrets_included": False,
    }


__all__ = ["CHAPTER_EXPECTATIONS", "run_chapter_scenarios"]
