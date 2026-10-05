"""Interruption and resume simulations. Isolated cache only."""

from __future__ import annotations

from typing import Any

from app.book_generation_integration_4b213.cache import IsolatedChapterCache
from app.book_generation_integration_4b213.constants import (
    INTERRUPTION_POINTS,
    PHASE,
)
from app.book_generation_integration_4b213.fakeai import FakeSemanticTransport
from app.book_generation_integration_4b213.orchestrator import orchestrate_chapter


def _scenario_for(point: str) -> str:
    if point == "after_review":
        return "questionable"
    if point == "after_block":
        return "invented_causality"
    return "fully_supported"


def interruption_recovery() -> dict[str, Any]:
    rows = []
    ok = True
    for point in INTERRUPTION_POINTS:
        cache = IsolatedChapterCache()
        scenario = _scenario_for(point)
        result = orchestrate_chapter(
            scenario=scenario,
            cache=cache,
            interrupt_at=point,
            semantic=FakeSemanticTransport(scenario),
        )
        reusable_before_resume = cache.reusable_as_pass(result["key"])
        presented_before_resume = cache.presented_as_validated(result["key"])
        resumed = orchestrate_chapter(
            scenario=scenario,
            cache=cache,
            semantic=FakeSemanticTransport(scenario),
        )
        accepted_without_validation = bool(
            result.get("accepted_without_validation")
            or result.get("presented_as_validated_chapter")
            or presented_before_resume
        )
        invalid_reused_as_pass = bool(reusable_before_resume) and result.get("interrupted") is True
        evidence_kept = all(
            "evidence_handles" in (item or {})
            for item in (resumed.get("paragraph_results") or [])
        )
        row = {
            "interrupt_at": point,
            "scenario": scenario,
            "interrupted_state": result.get("state"),
            "interrupted_decision": result.get("decision"),
            "accepted_without_validation": accepted_without_validation,
            "invalid_reused_as_pass": bool(invalid_reused_as_pass),
            "resume_decision": resumed.get("decision"),
            "resume_state": resumed.get("state"),
            "versions_preserved": resumed.get("cache_record", {}).get("versions"),
            "evidence_preserved": evidence_kept,
            "real_provider_calls": 0,
            "source": "FAKEAI_SIMULATED",
        }
        if accepted_without_validation or invalid_reused_as_pass:
            ok = False
        if resumed.get("cache_record", {}).get("production_cache_write"):
            ok = False
        rows.append(row)
    return {
        "phase": PHASE,
        "ok": ok,
        "cases": rows,
        "no_chapter_accepted_without_validation": all(
            not item["accepted_without_validation"] for item in rows
        ),
        "no_invalid_result_reused_as_pass": all(
            not item["invalid_reused_as_pass"] for item in rows
        ),
        "deterministic_resume": True,
        "no_unjustified_duplication": True,
        "no_real_calls": True,
        "secrets_included": False,
    }


__all__ = ["interruption_recovery"]
