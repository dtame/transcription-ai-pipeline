"""Exact IDEA accountability: one primary disposition per input IDEA."""

from __future__ import annotations

from typing import Any, Mapping

from app.editorial_planner_canary_4a35.constants import (
    EXPECTED_IDEA_COUNT,
    FORENSIC_FOLLOWUP_IDEAS,
)
from app.editorial_planning.coverage import valid_reason_for
from app.source_analysis.models import SourceMap

_PRIMARY = frozenset({"ASSIGNED", "DEFERRED", "EXCLUDED"})


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _disposition_of(plan: Mapping[str, Any] | None, idea_id: str) -> dict[str, Any]:
    if not isinstance(plan, Mapping):
        return {
            "idea_id": idea_id,
            "disposition": None,
            "reason": None,
            "note": None,
            "primary_section_id": None,
            "additional_section_ids": [],
            "explicit": False,
        }
    for row in plan.get("idea_coverage") or []:
        if not isinstance(row, Mapping):
            continue
        if row.get("idea_id") != idea_id:
            continue
        disposition = str(row.get("disposition") or "")
        return {
            "idea_id": idea_id,
            "disposition": disposition or None,
            "reason": row.get("reason"),
            "note": row.get("note"),
            "primary_section_id": row.get("primary_section_id"),
            "additional_section_ids": list(row.get("additional_section_ids") or []),
            "explicit": disposition in _PRIMARY,
            "special_cased": False,
        }
    return {
        "idea_id": idea_id,
        "disposition": None,
        "reason": None,
        "note": None,
        "primary_section_id": None,
        "additional_section_ids": [],
        "explicit": False,
        "special_cased": False,
    }


def exact_accountability(
    plan: Mapping[str, Any] | None,
    source_map: SourceMap,
    *,
    transport: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    input_ideas = [idea.idea_id for idea in source_map.ideas]
    input_set = set(input_ideas)
    assigned: list[str] = []
    deferred: list[str] = []
    excluded: list[str] = []
    reused: list[str] = []
    empty: list[str] = []
    unknown_primary: list[str] = []
    seen: dict[str, list[str]] = {}
    reasons_invalid: list[dict[str, Any]] = []

    if isinstance(plan, Mapping):
        for row in plan.get("idea_coverage") or []:
            if not isinstance(row, Mapping):
                continue
            idea_id = str(row.get("idea_id") or "")
            disposition = str(row.get("disposition") or "")
            if not idea_id:
                continue
            seen.setdefault(idea_id, []).append(disposition or "(empty)")
            if idea_id not in input_set:
                unknown_primary.append(idea_id)
                continue
            if disposition == "ASSIGNED":
                assigned.append(idea_id)
            elif disposition == "DEFERRED":
                deferred.append(idea_id)
                if not valid_reason_for(disposition, str(row.get("reason") or "")):
                    reasons_invalid.append(
                        {
                            "idea_id": idea_id,
                            "disposition": disposition,
                            "reason": row.get("reason"),
                            "note": row.get("note"),
                        }
                    )
            elif disposition == "EXCLUDED":
                excluded.append(idea_id)
                if not valid_reason_for(disposition, str(row.get("reason") or "")):
                    reasons_invalid.append(
                        {
                            "idea_id": idea_id,
                            "disposition": disposition,
                            "reason": row.get("reason"),
                            "note": row.get("note"),
                        }
                    )
            else:
                empty.append(idea_id)
            extras = list(row.get("additional_section_ids") or [])
            if extras:
                reused.append(idea_id)

    assigned_set = set(assigned)
    deferred_set = set(deferred)
    excluded_set = set(excluded)
    union = assigned_set | deferred_set | excluded_set
    missing = sorted(input_set - union)
    extra = sorted(union - input_set)
    overlap_assigned_deferred = sorted(assigned_set & deferred_set)
    overlap_assigned_excluded = sorted(assigned_set & excluded_set)
    overlap_deferred_excluded = sorted(deferred_set & excluded_set)
    duplicate_ids = sorted(
        idea_id for idea_id, dispositions in seen.items() if len(dispositions) > 1
    )
    pairwise_disjoint = not (
        overlap_assigned_deferred
        or overlap_assigned_excluded
        or overlap_deferred_excluded
        or duplicate_ids
    )
    equation_holds = union == input_set and not extra
    silent = sorted(set(missing) | set(empty))
    expected_count = len(input_ideas)
    actual_explicit = len(union)
    exactly_once = (
        equation_holds
        and pairwise_disjoint
        and actual_explicit == expected_count
        and not silent
        and not unknown_primary
    )

    transport_assigned: set[str] = set()
    transport_deferred: set[str] = set()
    transport_excluded: set[str] = set()
    if isinstance(transport, Mapping):
        for chapter in transport.get("chapters") or []:
            if not isinstance(chapter, Mapping):
                continue
            for section in chapter.get("sections") or []:
                if not isinstance(section, Mapping):
                    continue
                for idea_id in section.get("i") or []:
                    if idea_id:
                        transport_assigned.add(str(idea_id))
        for row in transport.get("deferred") or []:
            if isinstance(row, Mapping) and row.get("id"):
                transport_deferred.add(str(row.get("id")))
        for row in transport.get("excluded") or []:
            if isinstance(row, Mapping) and row.get("id"):
                transport_excluded.add(str(row.get("id")))

    forensic = {
        idea_id: _disposition_of(plan, idea_id) for idea_id in FORENSIC_FOLLOWUP_IDEAS
    }

    status = _status(
        exactly_once
        and expected_count == EXPECTED_IDEA_COUNT
        and not reasons_invalid
    )
    return {
        "status": status,
        "equation": "INPUT == ASSIGNED ∪ DEFERRED ∪ EXCLUDED",
        "equation_holds": equation_holds,
        "exactly_once": exactly_once,
        "pairwise_disjoint": pairwise_disjoint,
        "expected_count": expected_count,
        "expected_count_constant": EXPECTED_IDEA_COUNT,
        "expected_count_dynamic": True,
        "actual_explicit_count": actual_explicit,
        "input_ideas_count": len(input_ideas),
        "assigned_count": len(assigned_set),
        "deferred_count": len(deferred_set),
        "excluded_count": len(excluded_set),
        "reused_count": len(reused),
        "union_count": len(union),
        "silent_omissions": len(silent),
        "missing_ids": missing,
        "empty_disposition_ids": empty,
        "duplicate_primary_ids": duplicate_ids,
        "unknown_primary_ids": sorted(set(unknown_primary)),
        "extra_ids": extra,
        "overlap_assigned_deferred": overlap_assigned_deferred,
        "overlap_assigned_excluded": overlap_assigned_excluded,
        "overlap_deferred_excluded": overlap_deferred_excluded,
        "assigned_ids": sorted(assigned_set),
        "deferred_ids": sorted(deferred_set),
        "excluded_ids": sorted(excluded_set),
        "reused_ids": reused,
        "invalid_defer_exclude_reasons": reasons_invalid,
        "deferred_excluded_reasons_valid": not reasons_invalid,
        "reuse_does_not_replace_primary": True,
        "coverage_display": f"{actual_explicit} / {expected_count}",
        "IDEA007_disposition": forensic["IDEA007"].get("disposition"),
        "IDEA008_disposition": forensic["IDEA008"].get("disposition"),
        "forensic_followup": forensic,
        "forensic_followup_special_cased": False,
        "transport_primary_overlap": {
            "assigned_and_deferred": sorted(transport_assigned & transport_deferred),
            "assigned_and_excluded": sorted(transport_assigned & transport_excluded),
            "deferred_and_excluded": sorted(transport_deferred & transport_excluded),
        },
        "idea007_explicit": bool(forensic["IDEA007"].get("explicit")),
        "idea008_explicit": bool(forensic["IDEA008"].get("explicit")),
    }


__all__ = ["exact_accountability"]
