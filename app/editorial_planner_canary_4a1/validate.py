"""Validation contrat canary à partir d'une réponse déjà persistée. 0 réseau."""

from __future__ import annotations

from typing import Any, Mapping

from app.editorial_planner_canary_4a1.payload import canary_settings
from app.editorial_planning.errors import EditorialPlanTransportError
from app.editorial_planning.models import scan_forbidden_plan_structure
from app.editorial_planning.pipeline import materialize_plan
from app.editorial_planning.prompt import prompt_bundle
from app.editorial_planning.schema import schema_identity
from app.editorial_planning.transport import decode_transport
from app.editorial_planning.writer import plan_sha256
from app.file_utils import content_hash
from app.source_analysis.models import SourceMap


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def validate_handles(transport: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    chapter_handles: list[str] = []
    section_handles: list[str] = []
    for c_index, chapter in enumerate(transport.get("chapters") or []):
        if not isinstance(chapter, Mapping):
            continue
        handle = str(chapter.get("h") or "").strip()
        if handle:
            if handle in chapter_handles:
                errors.append(f"chapter handle dupliqué : {handle}")
            chapter_handles.append(handle)
        for section in chapter.get("sections") or []:
            if not isinstance(section, Mapping):
                continue
            s_handle = str(section.get("h") or "").strip()
            if s_handle:
                if s_handle in section_handles:
                    errors.append(f"section handle dupliqué : {s_handle}")
                section_handles.append(s_handle)
        _ = c_index
    return {
        "status": _status(not errors),
        "errors": errors,
        "chapter_handles": chapter_handles,
        "section_handles": section_handles,
    }


def unknown_ref_counts(plan, source_map: SourceMap) -> dict[str, int]:
    known_ideas = {idea.idea_id for idea in source_map.ideas}
    known_topics = {topic.topic_id for topic in source_map.topics}
    known_ex = {item.example_id for item in source_map.examples}
    known_ref = {item.reference_id for item in source_map.references}
    known_unc = {item.uncertainty_id for item in source_map.uncertainties}
    unknown_ideas = 0
    unknown_topics = 0
    unknown_ex = 0
    unknown_ref_n = 0
    unknown_unc = 0
    for chapter in plan.chapters:
        unknown_topics += sum(1 for ref in chapter.topic_refs if ref not in known_topics)
        for section in chapter.sections:
            unknown_ideas += sum(1 for ref in section.idea_refs if ref not in known_ideas)
            unknown_topics += sum(
                1 for ref in section.topic_refs if ref not in known_topics
            )
            unknown_ex += sum(1 for ref in section.example_refs if ref not in known_ex)
            unknown_ref_n += sum(
                1 for ref in section.reference_refs if ref not in known_ref
            )
            unknown_unc += sum(
                1 for ref in section.uncertainty_refs if ref not in known_unc
            )
    return {
        "unknown_idea_refs": unknown_ideas,
        "unknown_topic_refs": unknown_topics,
        "unknown_example_refs": unknown_ex,
        "unknown_reference_refs": unknown_ref_n,
        "unknown_uncertainty_refs": unknown_unc,
    }


def grouping_audit(plan) -> dict[str, Any]:
    grouped = [
        {
            "section_id": section.section_id,
            "idea_refs": list(section.idea_refs),
        }
        for section in plan.all_sections()
        if len(section.idea_refs) >= 2
    ]
    distinct = all(
        len(row["idea_refs"]) == len(set(row["idea_refs"])) for row in grouped
    )
    return {
        "grouped_sections": grouped,
        "grouping_observed": bool(grouped),
        "refs_remain_distinct": distinct,
        "status": _status(distinct),
    }


def interpret_canary_response(
    parsed: Mapping[str, Any] | None,
    *,
    source_map: SourceMap,
    source_map_sha256: str,
    source_map_bytes: int,
    raw_text: str | None = None,
) -> dict[str, Any]:
    prompt = prompt_bundle()
    schema = schema_identity()
    settings = canary_settings()
    leaked = scan_forbidden_plan_structure(parsed or {})
    structured = "PASS" if isinstance(parsed, Mapping) else "FAIL"
    decoder = "FAIL"
    transport: dict[str, Any] | None = None
    decoder_errors: list[str] = []
    if isinstance(parsed, Mapping):
        try:
            transport = decode_transport(parsed)
            decoder = "PASS"
        except EditorialPlanTransportError as exc:
            decoder_errors = list(exc.errors)
            decoder = "FAIL"
    handles = (
        validate_handles(transport or parsed or {})
        if isinstance(parsed, Mapping)
        else {"status": "FAIL", "errors": ["no parsed transport"], "chapter_handles": [], "section_handles": []}
    )
    reconstruction = "FAIL"
    replay = "FAIL"
    plan_hash = None
    plan_hash2 = None
    validation_dict: dict[str, Any] = {"status": "FAIL", "errors": [], "warnings": []}
    plan_dict = None
    coverage: dict[str, Any] = {}
    refs = {}
    grouping = {}
    hierarchy = "FAIL"
    canonical_ids = "FAIL"
    chapters_n = 0
    sections_n = 0
    invention = "FAIL"
    traceability = "FAIL"
    uncertainty = "FAIL"
    silent = None
    assigned = deferred = excluded = reused = 0
    if decoder == "PASS" and transport is not None:
        try:
            plan, validation, plan_hash = materialize_plan(
                dict(transport),
                source_map,
                source_map_sha256=source_map_sha256,
                source_map_bytes=source_map_bytes,
                prompt_sha256=prompt["prompt_sha256"],
                response_schema_sha256=schema["raw_schema_sha256"],
                source_map_path_value="synthetic://community_garden_workshop_canary_4a1",
                settings=settings,
            )
            plan2, validation2, plan_hash2 = materialize_plan(
                dict(transport),
                source_map,
                source_map_sha256=source_map_sha256,
                source_map_bytes=source_map_bytes,
                prompt_sha256=prompt["prompt_sha256"],
                response_schema_sha256=schema["raw_schema_sha256"],
                source_map_path_value="synthetic://community_garden_workshop_canary_4a1",
                settings=settings,
            )
            reconstruction = "PASS"
            replay = _status(plan_hash == plan_hash2 and validation.status == validation2.status)
            validation_dict = validation.to_dict()
            plan_dict = plan.to_dict()
            chapters_n = plan.stats.chapter_count
            sections_n = plan.stats.section_count
            assigned = plan.stats.assigned_idea_count
            deferred = plan.stats.deferred_idea_count
            excluded = plan.stats.excluded_idea_count
            reused = plan.stats.reused_idea_count
            silent = sum(1 for item in plan.idea_coverage if not item.disposition)
            missing_ids = [
                idea.idea_id
                for idea in source_map.ideas
                if idea.idea_id not in {item.idea_id for item in plan.idea_coverage}
                or next(
                    (row.disposition for row in plan.idea_coverage if row.idea_id == idea.idea_id),
                    "",
                )
                == ""
            ]
            silent = len(missing_ids)
            refs = unknown_ref_counts(plan, source_map)
            grouping = grouping_audit(plan)
            chapter_ids = [chapter.chapter_id for chapter in plan.chapters]
            section_ids = [section.section_id for section in plan.all_sections()]
            expected_ch = [f"CH{i:03d}" for i in range(1, len(chapter_ids) + 1)]
            expected_sec = [f"SEC{i:03d}" for i in range(1, len(section_ids) + 1)]
            canonical_ids = _status(chapter_ids == expected_ch and section_ids == expected_sec)
            hierarchy = _status(
                bool(plan.chapters)
                and all(chapter.sections for chapter in plan.chapters)
                and not leaked
            )
            empty_sections = [
                section.section_id
                for section in plan.all_sections()
                if not section.idea_refs
            ]
            empty_trace = [
                section.section_id
                for section in plan.all_sections()
                if section.idea_refs and not section.source_refs
            ]
            invention = _status(not empty_sections)
            traceability = _status(not empty_sections and not empty_trace)
            assigned_unc = plan.uncertainty_handling.assigned_uncertainty_refs
            policy = plan.uncertainty_handling.policy
            converted = "convert" in policy.lower() and "not" not in policy.lower()
            uncertainty = _status(not converted and bool(source_map.uncertainties))
            coverage = {
                "synthetic_ideas": len(source_map.ideas),
                "coverage_rows": len(plan.idea_coverage),
                "assigned": assigned,
                "deferred": deferred,
                "excluded": excluded,
                "reused": reused,
                "silent_omissions": silent,
                "idea_coverage": f"{assigned + deferred + excluded} / {len(source_map.ideas)}",
                "coverage_complete": (assigned + deferred + excluded) == len(source_map.ideas)
                and silent == 0,
                "dispositions": [item.to_dict() for item in plan.idea_coverage],
            }
        except EditorialPlanTransportError as exc:
            decoder = "FAIL"
            decoder_errors = list(exc.errors)
        except Exception as exc:  # noqa: BLE001 — canary records exact failure
            reconstruction = "FAIL"
            decoder_errors.append(f"{type(exc).__name__}: {exc}")

    validator_status = validation_dict.get("status") or "FAIL"
    hard_fail = validator_status == "FAIL"
    expected_warnings = [
        warning
        for warning in (validation_dict.get("warnings") or [])
        if any(
            token in warning
            for token in (
                "concentre",
                "très petit",
                "nombre de chapitres",
                "réutilisation",
            )
        )
    ]
    return {
        "structured_parse": structured,
        "transport_decoder": decoder,
        "decoder_errors": decoder_errors,
        "handle_validation": handles["status"],
        "handle_errors": handles.get("errors") or [],
        "canonical_reconstruction": reconstruction,
        "canonical_ids": canonical_ids,
        "hierarchy": hierarchy,
        "chapters": chapters_n,
        "sections": sections_n,
        "forbidden_structure": list(leaked),
        "idea_coverage": coverage,
        "unknown_refs": refs,
        "grouping": grouping,
        "traceability": traceability,
        "invention_boundary": invention,
        "uncertainty_preservation": uncertainty,
        "editorial_plan_validator": validator_status,
        "validator": validation_dict,
        "expected_tiny_fixture_warnings": expected_warnings,
        "validator_hard_fail": hard_fail,
        "deterministic_replay": replay,
        "plan_sha256": plan_hash,
        "plan_sha256_replay": plan_hash2,
        "raw_text_sha256": content_hash(raw_text) if raw_text else None,
        "plan": plan_dict,
        "transport": dict(transport) if transport is not None else None,
    }


__all__ = ["interpret_canary_response", "validate_handles"]
