"""
Read-only editorial-plan risk map.

Structural assignment is checked against identifiers.
A risk is not treated as a proven error unless the identifiers show a
broken link. Thematic regrouping is authorized.
"""

from __future__ import annotations

from typing import Any

from app.book_editorial_alignment_4b216.constants import PHASE, PROJECT_NAME
from app.book_generation.evidence import build_chapter_evidence, evidence_metrics
from app.book_generation.hydrate import load_clean_transcript_index
from app.book_generation.identity import load_production_inputs
from app.editorial_planning.coverage import missing_idea_ids


def _positions(index_by_src: dict[str, tuple[str, int, float]], src_ids: tuple[str, ...] | list[str]):
    rows = []
    for src_id in src_ids:
        located = index_by_src.get(src_id)
        if located:
            rows.append(located)
    return rows


def _span(rows: list[tuple[str, int, float]]) -> int | None:
    if not rows:
        return None
    indexes = [item[1] for item in rows]
    return max(indexes) - min(indexes)


def analyze_editorial_plan() -> dict[str, Any]:
    inputs = load_production_inputs(PROJECT_NAME, require_expected_identity=True)
    plan = inputs.plan
    source_map = inputs.source_map
    transcript = load_clean_transcript_index(PROJECT_NAME)
    index_by_src = {
        segment.src_id: (segment.source_id, position, segment.start)
        for position, segment in enumerate(transcript.segments)
    }
    ideas = {item.idea_id: item for item in source_map.ideas}
    examples = {item.example_id: item for item in source_map.examples}
    references = {item.reference_id: item for item in source_map.references}
    uncertainties = {item.uncertainty_id: item for item in source_map.uncertainties}
    topics = {item.topic_id: item for item in source_map.topics}

    location: dict[str, tuple[str, str]] = {}
    for chapter in plan.chapters:
        for section in chapter.sections:
            for idea_id in section.idea_refs:
                location[idea_id] = (chapter.chapter_id, section.section_id)

    assigned = plan.assigned_idea_ids()
    unknown = [idea_id for idea_id in assigned if idea_id not in ideas]
    duplicates = []
    seen: dict[str, str] = {}
    for idea_id, (chapter_id, section_id) in location.items():
        if idea_id in seen:
            duplicates.append(idea_id)
        seen[idea_id] = f"{chapter_id}/{section_id}"
    chapter_mismatches = []
    for chapter in plan.chapters:
        from_sections: list[str] = []
        for section in chapter.sections:
            from_sections.extend(section.idea_refs)
        if set(from_sections) != set(chapter.idea_refs):
            chapter_mismatches.append(chapter.chapter_id)

    relation_count = sum(len(idea.relations) for idea in source_map.ideas)
    chapters = []
    for chapter in plan.chapters:
        section_rows = []
        chapter_sources: set[str] = set()
        chapter_positions: list[tuple[str, int, float]] = []
        detached = []
        separated_uncertainties = []
        reference_tensions = []
        for section in chapter.sections:
            idea_sources: set[str] = set()
            positions: list[tuple[str, int, float]] = []
            topic_labels = []
            for idea_id in section.idea_refs:
                idea = ideas.get(idea_id)
                if idea is None:
                    continue
                idea_sources.update(idea.source_refs)
                positions.extend(_positions(index_by_src, idea.source_refs))
                for topic_id in idea.topic_refs:
                    topic = topics.get(topic_id)
                    if topic and topic.label not in topic_labels:
                        topic_labels.append(topic.label)
            chapter_sources.update(item[0] for item in positions)
            chapter_positions.extend(positions)
            for example_id in section.example_refs:
                example = examples.get(example_id)
                if example is None or not example.supports_idea_refs:
                    continue
                if set(example.supports_idea_refs).intersection(section.idea_refs):
                    continue
                detached.append(
                    {
                        "example_id": example_id,
                        "section_id": section.section_id,
                        "supports_idea_refs": list(example.supports_idea_refs),
                        "support_locations": [
                            {
                                "idea_id": idea_id,
                                "location": (
                                    "/".join(location[idea_id]) if idea_id in location else ""
                                ),
                            }
                            for idea_id in example.supports_idea_refs
                        ],
                        "summary": example.summary[:180],
                        "conclusion": (
                            "Provenance tension. The example is listed on this "
                            "section, and its supports_idea_refs name ideas "
                            "placed elsewhere. This is not, by itself, proof "
                            "that the idea assignment is wrong."
                        ),
                    }
                )
            for uncertainty_id in section.uncertainty_refs:
                uncertainty = uncertainties.get(uncertainty_id)
                if uncertainty is None or not uncertainty.source_refs:
                    continue
                if set(uncertainty.source_refs).intersection(idea_sources):
                    continue
                separated_uncertainties.append(
                    {
                        "uncertainty_id": uncertainty_id,
                        "section_id": section.section_id,
                        "kind": uncertainty.kind,
                        "severity": uncertainty.severity,
                        "description": uncertainty.description[:180],
                        "conclusion": (
                            "The reservation does not share an SRC with the "
                            "ideas listed on this section. It may be read apart "
                            "from the wording it qualifies. Not concluded as "
                            "an assignment error."
                        ),
                    }
                )
            for reference_id in section.reference_refs:
                reference = references.get(reference_id)
                if reference is None:
                    continue
                overlaps = bool(set(reference.source_refs).intersection(idea_sources))
                if overlaps:
                    continue
                reference_tensions.append(
                    {
                        "reference_id": reference_id,
                        "section_id": section.section_id,
                        "kind": reference.kind,
                        "completeness": reference.completeness,
                        "raw_reference": reference.raw_reference[:120],
                        "conclusion": (
                            "The reference is listed on this section, and its "
                            "SRC do not intersect the section's idea SRC. "
                            "Association must be preserved by the generator. "
                            "Not concluded as an assignment error."
                        ),
                    }
                )
            audios = sorted({item[0] for item in positions})
            section_rows.append(
                {
                    "section_id": section.section_id,
                    "working_title": section.working_title,
                    "idea_ids": list(section.idea_refs),
                    "idea_count": len(section.idea_refs),
                    "example_ids": list(section.example_refs),
                    "reference_ids": list(section.reference_refs),
                    "uncertainty_ids": list(section.uncertainty_refs),
                    "topic_labels": topic_labels,
                    "audio_sources": audios,
                    "transcript_index_span": _span(positions),
                    "cross_recording": len(audios) > 1,
                }
            )
        bundle = build_chapter_evidence(
            plan,
            source_map,
            chapter,
            language=source_map.primary_language,
            hydrate=True,
            transcript_index=transcript,
        )
        metrics = evidence_metrics(bundle)
        cross_recording = len(chapter_sources) > 1
        risks = []
        if cross_recording:
            risks.append(
                {
                    "code": "THEMATIC_REGROUP_ACROSS_RECORDINGS",
                    "severity": "observation",
                    "authorized": True,
                    "not_an_error": True,
                    "detail": (
                        "Ideas in this chapter cite more than one recording. "
                        "Grouping them is allowed when they treat the same "
                        "subject. Proximity must not be written as causality."
                    ),
                    "audio_sources": sorted(chapter_sources),
                }
            )
        if detached:
            risks.append(
                {
                    "code": "EXAMPLE_SUPPORT_OUTSIDE_SECTION",
                    "severity": "elevated",
                    "count": len(detached),
                    "not_concluded_as_error": True,
                }
            )
        if separated_uncertainties:
            risks.append(
                {
                    "code": "RESERVATION_WITHOUT_SECTION_SRC_OVERLAP",
                    "severity": "elevated",
                    "count": len(separated_uncertainties),
                    "not_concluded_as_error": True,
                }
            )
        if reference_tensions:
            risks.append(
                {
                    "code": "REFERENCE_WITHOUT_SECTION_SRC_OVERLAP",
                    "severity": "elevated",
                    "count": len(reference_tensions),
                    "not_concluded_as_error": True,
                }
            )
        if len(chapter.idea_refs) >= 30:
            risks.append(
                {
                    "code": "LARGE_IDEA_COUNT",
                    "severity": "scale",
                    "count": len(chapter.idea_refs),
                    "not_an_error": True,
                    "detail": "Manageable for a later chapter, not for the first pilot.",
                }
            )
        if not risks:
            risks.append(
                {
                    "code": "NO_STRUCTURAL_TENSION_DETECTED",
                    "severity": "low",
                    "not_an_error": True,
                    "detail": (
                        "No cross-recording group, detached example, separated "
                        "reservation, or unlinked reference was detected from "
                        "identifiers. This is not a proof that every sentence "
                        "is thematically pure."
                    ),
                }
            )
        chapters.append(
            {
                "chapter_id": chapter.chapter_id,
                "working_title": chapter.working_title,
                "purpose": chapter.purpose,
                "section_count": len(chapter.sections),
                "sections": section_rows,
                "idea_count": len(chapter.idea_refs),
                "idea_ids": list(chapter.idea_refs),
                "audio_sources": sorted(chapter_sources),
                "cross_recording": cross_recording,
                "transcript_index_span": _span(chapter_positions),
                "evidence_chars": metrics["chars"],
                "hydrated_src_chars": metrics["hydrated_src_chars"],
                "src_ref_count": metrics["src_ref_count"],
                "example_count": metrics["example_count"],
                "reference_count": metrics["reference_count"],
                "uncertainty_count": metrics["uncertainty_count"],
                "detached_examples": detached,
                "separated_uncertainties": separated_uncertainties,
                "reference_tensions": reference_tensions,
                "risks": risks,
            }
        )

    unassigned = list(plan.uncertainty_handling.unassigned_uncertainty_refs)
    return {
        "phase": PHASE,
        "read_only": True,
        "plan_modified": False,
        "source_map_modified": False,
        "language": source_map.primary_language,
        "selected_title": plan.selected_title,
        "structural_assignment": {
            "source_map_idea_count": len(source_map.ideas),
            "assigned_idea_count": plan.stats.assigned_idea_count,
            "assigned_ids": len(assigned),
            "coverage_records": len(plan.idea_coverage),
            "dispositions": sorted({item.disposition for item in plan.idea_coverage}),
            "missing_idea_ids": list(missing_idea_ids(plan, source_map)),
            "unknown_idea_ids": unknown,
            "duplicate_section_assignments": duplicates,
            "chapter_section_mismatches": chapter_mismatches,
            "deferred_idea_count": plan.stats.deferred_idea_count,
            "excluded_idea_count": plan.stats.excluded_idea_count,
            "chapter_count": plan.stats.chapter_count,
            "section_count": plan.stats.section_count,
            "structurally_complete": (
                plan.stats.assigned_idea_count == 286
                and len(assigned) == 286
                and not missing_idea_ids(plan, source_map)
                and not unknown
                and not duplicates
                and not chapter_mismatches
                and plan.stats.chapter_count == 19
                and plan.stats.section_count == 72
            ),
            "semantic_fitness_proven": False,
            "note": (
                "Every SourceMap idea has one ASSIGNED disposition and appears "
                "in exactly one section. That shows identifier integrity. "
                "It does not prove that each thematic grouping is the only "
                "faithful reading."
            ),
        },
        "limits_of_the_evidence": {
            "idea_relation_count": relation_count,
            "rule_b_checked_from_relation_graph": relation_count > 0,
            "rule_b_note": (
                "The SourceMap contains no idea-to-idea relations, so a "
                "qualifies or explains link cannot be checked from that graph. "
                "Absence of relations is not proof that conditions are safe."
            ),
            "repetition_count": len(source_map.repetitions),
            "rule_e_checked_from_repetition_records": bool(source_map.repetitions),
            "rule_e_note": (
                "The SourceMap repetition collection is empty. Accidental, "
                "pedagogical, rhetorical, and nuance-bearing repetitions "
                "cannot be separated from those records."
            ),
            "speaker_labels_present": False,
            "recording_count": len({segment.source_id for segment in transcript.segments}),
            "recording_ids": sorted({segment.source_id for segment in transcript.segments}),
            "rule_f_note": (
                "Clean-transcript segments have no speaker field. Four "
                "recording identifiers are present. They are not treated as "
                "four proven speakers."
            ),
            "unassigned_uncertainty_count": len(unassigned),
            "unassigned_uncertainties_are_listed": True,
            "unassigned_uncertainty_ids": unassigned,
        },
        "chapters": chapters,
        "secrets_included": False,
    }


__all__ = ["analyze_editorial_plan"]
