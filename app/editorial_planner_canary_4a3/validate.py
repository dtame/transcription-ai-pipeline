"""Offline technical validation from a persisted provider response. 0 network."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.editorial_planner_canary_4a3.constants import (
    EXPECTED_IDEA_COUNT,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
)
from app.editorial_planner_preflight_4a2.payload import production_settings
from app.editorial_planning.coverage import valid_reason_for
from app.editorial_planning.errors import EditorialPlanTransportError
from app.editorial_planning.models import scan_forbidden_plan_structure
from app.editorial_planning.pipeline import materialize_plan
from app.editorial_planning.prompt import prompt_bundle
from app.editorial_planning.schema import schema_identity
from app.editorial_planning.transport import decode_transport
from app.editorial_planning.writer import plan_sha256, render_editorial_plan
from app.file_utils import content_hash
from app.source_analysis.models import SourceMap

_HANDLE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def validate_handles(transport: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    chapter_handles: list[str] = []
    section_handles: list[str] = []
    malformed = 0
    duplicate = 0
    unknown = 0
    seen_ch: set[str] = set()
    seen_sec: set[str] = set()
    for chapter in transport.get("chapters") or []:
        if not isinstance(chapter, Mapping):
            continue
        handle = str(chapter.get("h") or "").strip()
        if not handle:
            malformed += 1
            errors.append("chapter handle empty")
        elif not _HANDLE.match(handle):
            malformed += 1
            errors.append(f"chapter handle malformed: {handle}")
        elif handle in seen_ch:
            duplicate += 1
            errors.append(f"chapter handle duplicate: {handle}")
        else:
            seen_ch.add(handle)
            chapter_handles.append(handle)
        for section in chapter.get("sections") or []:
            if not isinstance(section, Mapping):
                continue
            s_handle = str(section.get("h") or "").strip()
            if not s_handle:
                malformed += 1
                errors.append("section handle empty")
            elif not _HANDLE.match(s_handle):
                malformed += 1
                errors.append(f"section handle malformed: {s_handle}")
            elif s_handle in seen_sec:
                duplicate += 1
                errors.append(f"section handle duplicate: {s_handle}")
            else:
                seen_sec.add(s_handle)
                section_handles.append(s_handle)
    return {
        "status": _status(not errors),
        "errors": errors,
        "chapter_handles": chapter_handles,
        "section_handles": section_handles,
        "unknown": unknown,
        "duplicate": duplicate,
        "malformed": malformed,
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
        {"section_id": section.section_id, "idea_refs": list(section.idea_refs)}
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


def reuse_audit(plan) -> dict[str, Any]:
    reused = [item for item in plan.idea_coverage if item.additional_section_ids]
    extra = sum(len(item.additional_section_ids) for item in reused)
    known_sections = {section.section_id for section in plan.all_sections()}
    invalid_primary = [
        item.idea_id
        for item in reused
        if item.primary_section_id not in known_sections
    ]
    invalid_extra = [
        {"idea_id": item.idea_id, "section_id": extra_id}
        for item in reused
        for extra_id in item.additional_section_ids
        if extra_id not in known_sections
    ]
    return {
        "reused_ideas": len(reused),
        "extra_section_assignments": extra,
        "primary_section_exists": not invalid_primary,
        "extra_section_ids_valid": not invalid_extra,
        "invalid_primary": invalid_primary,
        "invalid_extra": invalid_extra,
        "rows": [
            {
                "idea_id": item.idea_id,
                "primary_section_id": item.primary_section_id,
                "additional_section_ids": list(item.additional_section_ids),
            }
            for item in reused
        ],
        "auditable": not invalid_primary and not invalid_extra,
    }


def disposition_reason_audit(plan) -> dict[str, Any]:
    deferred_invalid = []
    excluded_invalid = []
    for item in plan.idea_coverage:
        if item.disposition == "DEFERRED" and not valid_reason_for(
            item.disposition, item.reason
        ):
            deferred_invalid.append(
                {"idea_id": item.idea_id, "reason": item.reason, "note": item.note}
            )
        if item.disposition == "EXCLUDED" and not valid_reason_for(
            item.disposition, item.reason
        ):
            excluded_invalid.append(
                {"idea_id": item.idea_id, "reason": item.reason, "note": item.note}
            )
    return {
        "deferred_invalid_reasons": deferred_invalid,
        "excluded_invalid_reasons": excluded_invalid,
        "deferred_reasons_valid": not deferred_invalid,
        "excluded_reasons_valid": not excluded_invalid,
    }


def interpret_production_response(
    parsed: Mapping[str, Any] | None,
    *,
    source_map: SourceMap,
    source_map_sha256: str,
    source_map_bytes: int,
    source_map_path_value: str,
    raw_text: str | None = None,
) -> dict[str, Any]:
    prompt = prompt_bundle()
    schema = schema_identity()
    settings = production_settings(max_output_tokens=PRODUCTION_MAX_OUTPUT_TOKENS)
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
        else {
            "status": "FAIL",
            "errors": ["no parsed transport"],
            "chapter_handles": [],
            "section_handles": [],
            "unknown": 0,
            "duplicate": 0,
            "malformed": 0,
        }
    )
    reconstruction = "FAIL"
    replay = "FAIL"
    plan_hash = None
    plan_hash2 = None
    validation_dict: dict[str, Any] = {"status": "FAIL", "errors": [], "warnings": []}
    plan_dict = None
    plan_bytes = None
    plan_chars = None
    coverage: dict[str, Any] = {}
    refs: dict[str, int] = {}
    grouping: dict[str, Any] = {}
    reuse: dict[str, Any] = {}
    reasons: dict[str, Any] = {}
    hierarchy = "FAIL"
    canonical_ids = "FAIL"
    chapters_n = 0
    sections_n = 0
    invention = "FAIL"
    traceability = "FAIL"
    uncertainty = "FAIL"
    silent = None
    assigned = deferred = excluded = reused = 0
    extra_assignments = 0
    distribution: list[dict[str, Any]] = []
    if decoder == "PASS" and transport is not None:
        try:
            common = dict(
                source_map_sha256=source_map_sha256,
                source_map_bytes=source_map_bytes,
                prompt_sha256=prompt["prompt_sha256"],
                response_schema_sha256=schema["raw_schema_sha256"],
                source_map_path_value=source_map_path_value,
                settings=settings,
            )
            plan, validation, plan_hash = materialize_plan(
                dict(transport), source_map, **common
            )
            plan2, validation2, plan_hash2 = materialize_plan(
                dict(transport), source_map, **common
            )
            reconstruction = "PASS"
            replay = _status(
                plan_hash == plan_hash2 and validation.status == validation2.status
            )
            validation_dict = validation.to_dict()
            plan_dict = plan.to_dict()
            rendered = render_editorial_plan(plan_dict)
            plan_bytes = len(rendered.encode("utf-8"))
            plan_chars = len(rendered)
            chapters_n = plan.stats.chapter_count
            sections_n = plan.stats.section_count
            assigned = plan.stats.assigned_idea_count
            deferred = plan.stats.deferred_idea_count
            excluded = plan.stats.excluded_idea_count
            reused = plan.stats.reused_idea_count
            known = {idea.idea_id for idea in source_map.ideas}
            covered = {item.idea_id for item in plan.idea_coverage if item.disposition}
            missing_ids = sorted(known - covered)
            empty_disp = [
                item.idea_id
                for item in plan.idea_coverage
                if item.idea_id in known and not item.disposition
            ]
            silent = len(set(missing_ids) | set(empty_disp))
            refs = unknown_ref_counts(plan, source_map)
            grouping = grouping_audit(plan)
            reuse = reuse_audit(plan)
            reasons = disposition_reason_audit(plan)
            extra_assignments = int(reuse.get("extra_section_assignments") or 0)
            chapter_ids = [chapter.chapter_id for chapter in plan.chapters]
            section_ids = [section.section_id for section in plan.all_sections()]
            expected_ch = [f"CH{i:03d}" for i in range(1, len(chapter_ids) + 1)]
            expected_sec = [f"SEC{i:03d}" for i in range(1, len(section_ids) + 1)]
            canonical_ids = _status(
                chapter_ids == expected_ch and section_ids == expected_sec
            )
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
            policy = plan.uncertainty_handling.policy
            converted = "convert" in policy.lower() and "not" not in policy.lower()
            uncertainty = _status(not converted)
            distribution = [
                {
                    "chapter_id": chapter.chapter_id,
                    "working_title": chapter.working_title,
                    "section_count": len(chapter.sections),
                    "idea_count": len(chapter.idea_refs),
                }
                for chapter in plan.chapters
            ]
            handled = assigned + deferred + excluded
            coverage = {
                "source_map_ideas": len(source_map.ideas),
                "expected_ideas": EXPECTED_IDEA_COUNT,
                "coverage_rows": len(plan.idea_coverage),
                "assigned": assigned,
                "deferred": deferred,
                "excluded": excluded,
                "reused": reused,
                "extra_section_assignments": extra_assignments,
                "silent_omissions": silent,
                "missing_idea_ids": missing_ids,
                "empty_disposition_ids": empty_disp,
                "idea_coverage": f"{handled} / {EXPECTED_IDEA_COUNT}",
                "coverage_complete": handled == EXPECTED_IDEA_COUNT and silent == 0,
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
    unknown_total = sum(int(refs.get(key) or 0) for key in refs)
    return {
        "structured_parse": structured,
        "transport_decoder": decoder,
        "decoder_errors": decoder_errors,
        "handle_validation": handles["status"],
        "handle_errors": handles.get("errors") or [],
        "handle_unknown": handles.get("unknown"),
        "handle_duplicate": handles.get("duplicate"),
        "handle_malformed": handles.get("malformed"),
        "canonical_reconstruction": reconstruction,
        "canonical_ids": canonical_ids,
        "hierarchy": hierarchy,
        "chapters": chapters_n,
        "sections": sections_n,
        "section_distribution": distribution,
        "forbidden_structure": list(leaked),
        "idea_coverage": coverage,
        "unknown_refs": refs,
        "unknown_refs_total": unknown_total,
        "grouping": grouping,
        "reuse": reuse,
        "disposition_reasons": reasons,
        "traceability": traceability,
        "invention_boundary": invention,
        "uncertainty_preservation": uncertainty,
        "editorial_plan_validator": validator_status,
        "validator": validation_dict,
        "validator_hard_fail": hard_fail,
        "deterministic_replay": replay,
        "plan_sha256": plan_hash,
        "plan_sha256_replay": plan_hash2,
        "plan_bytes": plan_bytes,
        "plan_chars": plan_chars,
        "raw_text_sha256": content_hash(raw_text) if raw_text else None,
        "plan": plan_dict,
        "transport": dict(transport) if transport is not None else None,
        "settings_max_output_tokens": settings.max_output_tokens,
        "project": PROJECT_NAME,
    }


__all__ = ["interpret_production_response", "validate_handles"]
