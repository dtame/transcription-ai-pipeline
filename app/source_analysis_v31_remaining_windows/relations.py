"""Audit relationnel transversal A.28. 0 provider."""

from __future__ import annotations

from typing import Any

from app.source_analysis_v31_remaining_windows.constants import (
    EXECUTION_ORDER,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)


def build_relation_cross(result: Any) -> dict[str, Any]:
    totals = {
        "well-supported": 0,
        "plausible-loose": 0,
        "incorrect": 0,
        "unverifiable": 0,
    }
    per_window: dict[str, Any] = {}
    successful = 0
    for window_id in EXECUTION_ORDER:
        item = (result.windows or {}).get(window_id) or {}
        execution = item.get("execution") or {}
        dist = dict(execution.get("relation_quality_summary") or {})
        if not dist:
            dist = dict((item.get("review") or {}).get("relation_quality_summary") or {})
        for key in totals:
            totals[key] += int(dist.get(key) or 0)
        if execution.get("result") == "PASS":
            successful += 1
        per_window[window_id] = {
            "result": execution.get("result") or item.get("result") or "NOT_RUN",
            "distribution": dist,
        }
    all_rel = sum(totals.values())
    pct = {
        key: round(100.0 * totals[key] / all_rel, 2) if all_rel else 0.0
        for key in totals
    }
    debt = (
        successful >= 2
        and all_rel > 0
        and (pct["plausible-loose"] >= 80.0)
        and totals["incorrect"] == 0
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "per_window": per_window,
        "totals": totals,
        "percentages": pct,
        "successful_windows": successful,
        "relation_quality_technical_debt": "YES" if debt else "NO",
        "do_not_fail_on_loose_alone": True,
        "a27_win004_signal": {
            "well-supported": 0,
            "plausible-loose": 23,
            "incorrect": 0,
            "unverifiable": 0,
        },
    }


__all__ = ["build_relation_cross"]
