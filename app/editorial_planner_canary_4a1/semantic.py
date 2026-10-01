"""Revue sémantique lisible du plan canary. Aucune réparation."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import SourceMap

_INVENTED_MARKERS = (
    "hydroponic",
    "aquaponic",
    "greenhouse empire",
    "pastoral",
    "retreat",
    "sermon",
    "scripture",
)
_CERTAINTY_MARKERS = (
    "compost drop-off is open on sunday",
    "open every sunday",
    "definitely sunday",
    "confirmed sunday",
)


def review_semantics(
    plan: Mapping[str, Any] | None,
    source_map: SourceMap,
    *,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    notes: list[str] = []
    issues: list[str] = []
    if not isinstance(plan, Mapping):
        return {
            "status": "FAIL",
            "coherent_organization": "FAIL",
            "chapter_section_boundaries": "FAIL",
            "all_ideas_handled": "FAIL",
            "invention": "FAIL",
            "deferred_excluded_justified": "FAIL",
            "uncertainty_preserved": "FAIL",
            "issues": ["no reconstructed plan"],
            "notes": notes,
        }
    chapters = list(plan.get("chapters") or [])
    sections = [
        section
        for chapter in chapters
        if isinstance(chapter, Mapping)
        for section in (chapter.get("sections") or [])
        if isinstance(section, Mapping)
    ]
    titles = " ".join(
        [
            str(plan.get("selected_title") or ""),
            str(plan.get("subtitle") or ""),
            str(plan.get("editorial_angle") or ""),
            str((plan.get("book_concept") or {}).get("purpose") or ""),
            str((plan.get("book_concept") or {}).get("core_subject") or ""),
            *[str(chapter.get("working_title") or "") for chapter in chapters if isinstance(chapter, Mapping)],
            *[str(section.get("working_title") or "") for section in sections],
            *[str(section.get("purpose") or "") for section in sections],
        ]
    ).lower()
    for marker in _INVENTED_MARKERS:
        if marker in titles:
            issues.append(f"possible unsupported invention marker: {marker}")
    for marker in _CERTAINTY_MARKERS:
        if marker in titles:
            issues.append("uncertainty converted into unsupported certainty")
    coverage = list(plan.get("idea_coverage") or [])
    known = {idea.idea_id for idea in source_map.ideas}
    covered = {row.get("idea_id") for row in coverage if isinstance(row, Mapping)}
    missing = sorted(known - covered)
    if missing:
        issues.append("ideas without coverage row: " + ", ".join(missing))
    empty_disp = [
        row.get("idea_id")
        for row in coverage
        if isinstance(row, Mapping) and not row.get("disposition")
    ]
    if empty_disp:
        issues.append("silent omission: " + ", ".join(str(item) for item in empty_disp))
    deferred_excluded = [
        row
        for row in coverage
        if isinstance(row, Mapping) and row.get("disposition") in {"DEFERRED", "EXCLUDED"}
    ]
    unjustified = [
        row.get("idea_id")
        for row in deferred_excluded
        if not (row.get("reason") or "").strip()
    ]
    if unjustified:
        issues.append("deferred/excluded without reason: " + ", ".join(str(item) for item in unjustified))
    unc = plan.get("uncertainty_handling") or {}
    assigned_unc = list(unc.get("assigned_uncertainty_refs") or [])
    if source_map.uncertainties and not assigned_unc:
        notes.append("UNC present in fixture but not attached to a section (listed unassigned, not converted).")
    if len(chapters) < 1:
        issues.append("no chapters")
    if any(not (chapter.get("sections") or []) for chapter in chapters if isinstance(chapter, Mapping)):
        issues.append("empty chapter")
    plausible = 1 <= len(chapters) <= 4 and 2 <= len(sections) <= 12
    if not plausible:
        notes.append(
            f"chapter/section counts unusual for tiny fixture: "
            f"{len(chapters)} chapters / {len(sections)} sections"
        )
    contract = dict(contract or {})
    all_handled = contract.get("idea_coverage", {}).get("coverage_complete") is True or (
        not missing and not empty_disp
    )
    invention_ok = contract.get("invention_boundary") == "PASS" and not any(
        marker in titles for marker in _INVENTED_MARKERS
    )
    unc_ok = "uncertainty converted" not in " ".join(issues)
    justified = not unjustified
    coherent = plausible and bool(plan.get("selected_title")) and bool(plan.get("editorial_angle"))
    if issues:
        status = "FAIL"
    elif notes and not coherent:
        status = "REVIEW"
    else:
        status = "PASS"
    return {
        "status": status,
        "coherent_organization": "PASS" if coherent else "REVIEW",
        "chapter_section_boundaries": "PASS" if plausible else "REVIEW",
        "all_ideas_handled": "PASS" if all_handled else "FAIL",
        "invention": "PASS" if invention_ok else "FAIL",
        "deferred_excluded_justified": "PASS" if justified else "FAIL",
        "uncertainty_preserved": "PASS" if unc_ok else "FAIL",
        "selected_title": plan.get("selected_title"),
        "subtitle": plan.get("subtitle"),
        "editorial_angle": plan.get("editorial_angle"),
        "target_reader": plan.get("target_reader"),
        "chapter_titles": [
            chapter.get("working_title")
            for chapter in chapters
            if isinstance(chapter, Mapping)
        ],
        "section_titles": [
            section.get("working_title") for section in sections
        ],
        "deferred_excluded": [
            {
                "idea_id": row.get("idea_id"),
                "disposition": row.get("disposition"),
                "reason": row.get("reason"),
                "note": row.get("note"),
            }
            for row in deferred_excluded
        ],
        "issues": issues,
        "notes": notes,
    }


__all__ = ["review_semantics"]
