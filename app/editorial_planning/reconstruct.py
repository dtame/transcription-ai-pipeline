"""
Reconstruction déterministe : transport provider → EditorialPlan canonique.

Les poignées provider sont jetées. CH/SEC sont assignés dans l'ordre
éditorial final. Les source_refs sont dérivés du SourceMap. Aucune IDEA
n'est créée ni fusionnée sémantiquement.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.editorial_planning.constants import (
    EDITORIAL_PLAN_SCHEMA_VERSION,
    IDEA_COVERAGE_POLICY_VERSION,
    EDITORIAL_PLAN_VALIDATOR_VERSION,
)
from app.editorial_planning.coverage import UNCERTAINTY_POLICY
from app.editorial_planning.errors import EditorialPlanTransportError
from app.editorial_planning.models import (
    BookConcept,
    EditorialAction,
    EditorialChapter,
    EditorialPlan,
    EditorialPlanMetadata,
    EditorialPlanStats,
    EditorialSection,
    IdeaDisposition,
    SourceCoverage,
    SourceMapIdentity,
    TitleCandidate,
    UncertaintyHandling,
    format_chapter_id,
    format_section_id,
)
from app.editorial_planning.transport import decode_transport
from app.source_analysis.models import SourceMap


def reconstruct_editorial_plan(
    payload: Mapping[str, Any],
    source_map: SourceMap,
    *,
    provenance: EditorialPlanMetadata,
    source_map_identity: SourceMapIdentity,
) -> EditorialPlan:
    transport = decode_transport(payload)
    errors: list[str] = []

    concept_raw = transport.get("concept") or {}
    concept = BookConcept(
        purpose=_text(concept_raw, "promise"),
        core_subject=_text(concept_raw, "subject"),
        reader_journey=_text(concept_raw, "journey"),
        editorial_progression=_text(concept_raw, "progression"),
    )

    titles_raw = _list(transport.get("titles"))
    title_candidates = tuple(
        TitleCandidate(
            title=_text(item, "t"),
            rationale=_text(item, "why"),
            is_editorial_construct=True,
        )
        for item in titles_raw
        if isinstance(item, Mapping)
    )
    pick = transport.get("pick", 0)
    try:
        pick_index = int(pick)
    except (TypeError, ValueError):
        pick_index = 0
        errors.append("pick n'est pas un entier")
    if title_candidates:
        if pick_index < 0 or pick_index >= len(title_candidates):
            errors.append("pick hors plage des title candidates")
            pick_index = 0
        selected_title = title_candidates[pick_index].title
    else:
        selected_title = ""
        errors.append("aucun title candidate")

    idea_index = {idea.idea_id: idea for idea in source_map.ideas}
    example_index = {item.example_id: item for item in source_map.examples}
    reference_index = {item.reference_id: item for item in source_map.references}
    uncertainty_index = {
        item.uncertainty_id: item for item in source_map.uncertainties
    }
    repetition_index = {item.repetition_id: item for item in source_map.repetitions}

    chapters_out: list[EditorialChapter] = []
    section_counter = 0
    idea_sections: dict[str, list[str]] = {}
    assigned_examples: set[str] = set()
    assigned_refs: set[str] = set()
    assigned_unc: set[str] = set()
    assigned_rep: set[str] = set()
    plan_actions: list[EditorialAction] = []

    for c_index, chapter_raw in enumerate(_list(transport.get("chapters")), start=1):
        if not isinstance(chapter_raw, Mapping):
            errors.append(f"chapitre {c_index} illisible")
            continue
        chapter_id = format_chapter_id(c_index)
        sections_out: list[EditorialSection] = []
        for section_raw in _list(chapter_raw.get("sections")):
            if not isinstance(section_raw, Mapping):
                errors.append(f"{chapter_id} section illisible")
                continue
            section_counter += 1
            section_id = format_section_id(section_counter)
            idea_refs = _id_tuple(section_raw.get("i"))
            example_refs = _id_tuple(section_raw.get("x"))
            reference_refs = _id_tuple(section_raw.get("ref"))
            uncertainty_refs = _id_tuple(section_raw.get("u"))
            repetition_refs = _id_tuple(section_raw.get("rep"))
            topic_refs = _id_tuple(section_raw.get("top"))
            actions = _actions(section_raw.get("act"))
            source_refs = _derive_source_refs(
                idea_refs,
                example_refs,
                reference_refs,
                uncertainty_refs,
                repetition_refs,
                idea_index,
                example_index,
                reference_index,
                uncertainty_index,
                repetition_index,
            )
            for idea_id in idea_refs:
                idea_sections.setdefault(idea_id, []).append(section_id)
            assigned_examples.update(example_refs)
            assigned_refs.update(reference_refs)
            assigned_unc.update(uncertainty_refs)
            assigned_rep.update(repetition_refs)
            sections_out.append(
                EditorialSection(
                    section_id=section_id,
                    working_title=_text(section_raw, "t"),
                    purpose=_text(section_raw, "p"),
                    idea_refs=idea_refs,
                    source_refs=source_refs,
                    example_refs=example_refs,
                    reference_refs=reference_refs,
                    uncertainty_refs=uncertainty_refs,
                    repetition_refs=repetition_refs,
                    topic_refs=topic_refs,
                    editorial_actions=actions,
                )
            )
            plan_actions.extend(actions)

        chapter_actions = _actions(chapter_raw.get("act"))
        plan_actions.extend(chapter_actions)
        chapter_idea_refs = _unique(
            idea_id for section in sections_out for idea_id in section.idea_refs
        )
        chapter_source_refs = _unique(
            ref for section in sections_out for ref in section.source_refs
        )
        chapter_unc = _unique(
            ref for section in sections_out for ref in section.uncertainty_refs
        )
        topic_refs = _id_tuple(chapter_raw.get("top"))
        if not topic_refs:
            topic_refs = _unique(
                ref for section in sections_out for ref in section.topic_refs
            )
        chapters_out.append(
            EditorialChapter(
                chapter_id=chapter_id,
                working_title=_text(chapter_raw, "t"),
                purpose=_text(chapter_raw, "p"),
                summary=_text(chapter_raw, "sum"),
                idea_refs=chapter_idea_refs,
                source_refs=chapter_source_refs,
                topic_refs=topic_refs,
                uncertainty_refs=chapter_unc,
                sections=tuple(sections_out),
                editorial_actions=chapter_actions,
            )
        )

    deferred_rows = {
        _text(row, "id"): row
        for row in _list(transport.get("deferred"))
        if isinstance(row, Mapping) and _text(row, "id")
    }
    excluded_rows = {
        _text(row, "id"): row
        for row in _list(transport.get("excluded"))
        if isinstance(row, Mapping) and _text(row, "id")
    }

    coverage: list[IdeaDisposition] = []
    for idea in source_map.ideas:
        idea_id = idea.idea_id
        sections = tuple(idea_sections.get(idea_id) or ())
        if sections:
            coverage.append(
                IdeaDisposition(
                    idea_id=idea_id,
                    disposition="ASSIGNED",
                    primary_section_id=sections[0],
                    additional_section_ids=sections[1:],
                )
            )
            continue
        if idea_id in excluded_rows:
            row = excluded_rows[idea_id]
            coverage.append(
                IdeaDisposition(
                    idea_id=idea_id,
                    disposition="EXCLUDED",
                    reason=_text(row, "why"),
                    note=_text(row, "n"),
                )
            )
            continue
        if idea_id in deferred_rows:
            row = deferred_rows[idea_id]
            coverage.append(
                IdeaDisposition(
                    idea_id=idea_id,
                    disposition="DEFERRED",
                    reason=_text(row, "why"),
                    note=_text(row, "n"),
                )
            )
            continue
        coverage.append(
            IdeaDisposition(idea_id=idea_id, disposition="")
        )

    extra_ids = sorted(
        (set(idea_sections) | set(deferred_rows) | set(excluded_rows))
        - {idea.idea_id for idea in source_map.ideas}
    )
    for idea_id in extra_ids:
        if idea_id in idea_sections:
            sections = tuple(idea_sections[idea_id])
            coverage.append(
                IdeaDisposition(
                    idea_id=idea_id,
                    disposition="ASSIGNED",
                    primary_section_id=sections[0],
                    additional_section_ids=sections[1:],
                )
            )
        elif idea_id in excluded_rows:
            row = excluded_rows[idea_id]
            coverage.append(
                IdeaDisposition(
                    idea_id=idea_id,
                    disposition="EXCLUDED",
                    reason=_text(row, "why"),
                    note=_text(row, "n"),
                )
            )
        else:
            row = deferred_rows[idea_id]
            coverage.append(
                IdeaDisposition(
                    idea_id=idea_id,
                    disposition="DEFERRED",
                    reason=_text(row, "why"),
                    note=_text(row, "n"),
                )
            )

    all_unc = tuple(item.uncertainty_id for item in source_map.uncertainties)
    assigned_unc_ordered = tuple(
        uid for uid in all_unc if uid in assigned_unc
    ) + tuple(uid for uid in sorted(assigned_unc) if uid not in set(all_unc))
    unassigned_unc = tuple(uid for uid in all_unc if uid not in assigned_unc)

    source_refs = _unique(
        ref for chapter in chapters_out for ref in chapter.source_refs
    )
    assigned_count = sum(1 for item in coverage if item.disposition == "ASSIGNED")
    deferred_count = sum(1 for item in coverage if item.disposition == "DEFERRED")
    excluded_count = sum(1 for item in coverage if item.disposition == "EXCLUDED")
    reused_count = sum(1 for item in coverage if item.additional_section_ids)
    section_count = sum(len(chapter.sections) for chapter in chapters_out)

    stats = EditorialPlanStats(
        chapter_count=len(chapters_out),
        section_count=section_count,
        assigned_idea_count=assigned_count,
        deferred_idea_count=deferred_count,
        excluded_idea_count=excluded_count,
        reused_idea_count=reused_count,
        example_assigned_count=len(assigned_examples),
        reference_assigned_count=len(assigned_refs),
        uncertainty_assigned_count=len(assigned_unc),
        repetition_assigned_count=len(assigned_rep),
        title_candidate_count=len(title_candidates),
    )

    metadata = EditorialPlanMetadata(
        prompt_version=provenance.prompt_version,
        transport_version=provenance.transport_version,
        schema_version=provenance.schema_version or EDITORIAL_PLAN_SCHEMA_VERSION,
        coverage_policy_version=provenance.coverage_policy_version
        or IDEA_COVERAGE_POLICY_VERSION,
        validator_version=provenance.validator_version
        or EDITORIAL_PLAN_VALIDATOR_VERSION,
        provider=provenance.provider,
        model=provenance.model,
        strategy=provenance.strategy,
        thinking_mode=provenance.thinking_mode,
        effort=provenance.effort,
        signature=provenance.signature,
        source_map_path=provenance.source_map_path,
    )

    if errors:
        raise EditorialPlanTransportError(errors)

    return EditorialPlan(
        project_name=source_map.project_name,
        source_map=source_map_identity,
        book_concept=concept,
        title_candidates=title_candidates,
        selected_title=selected_title,
        subtitle=_text(transport, "subtitle"),
        editorial_angle=_text(transport, "angle"),
        target_reader=_text(transport, "reader"),
        editorial_strategy=_text(transport, "strategy"),
        chapters=tuple(chapters_out),
        idea_coverage=tuple(coverage),
        source_coverage=SourceCoverage(
            referenced_source_refs=source_refs,
            referenced_source_count=len(source_refs),
        ),
        uncertainty_handling=UncertaintyHandling(
            policy=UNCERTAINTY_POLICY,
            assigned_uncertainty_refs=assigned_unc_ordered,
            unassigned_uncertainty_refs=unassigned_unc,
        ),
        editorial_actions=tuple(plan_actions),
        stats=stats,
        planner=metadata,
        schema_version=EDITORIAL_PLAN_SCHEMA_VERSION,
    )


def _text(data: Mapping[str, Any] | object, key: str) -> str:
    if not isinstance(data, Mapping):
        return ""
    value = data.get(key)
    if value is None:
        return ""
    return value.strip() if isinstance(value, str) else str(value).strip()


def _list(value: Any) -> list:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return []


def _id_tuple(value: Any) -> tuple[str, ...]:
    items: list[str] = []
    seen: set[str] = set()
    for item in _list(value):
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            items.append(text)
    return tuple(items)


def _unique(values) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for item in values:
        text = str(item).strip()
        if text:
            seen.setdefault(text, None)
    return tuple(seen)


def _actions(value: Any) -> tuple[EditorialAction, ...]:
    out: list[EditorialAction] = []
    for item in _list(value):
        if not isinstance(item, Mapping):
            continue
        kind = _text(item, "k")
        if not kind:
            continue
        out.append(EditorialAction(kind=kind, note=_text(item, "n")))
    return tuple(out)


def _derive_source_refs(
    idea_refs: Sequence[str],
    example_refs: Sequence[str],
    reference_refs: Sequence[str],
    uncertainty_refs: Sequence[str],
    repetition_refs: Sequence[str],
    ideas: Mapping,
    examples: Mapping,
    references: Mapping,
    uncertainties: Mapping,
    repetitions: Mapping,
) -> tuple[str, ...]:
    refs: dict[str, None] = {}
    for idea_id in idea_refs:
        idea = ideas.get(idea_id)
        if idea is not None:
            for src in idea.source_refs:
                refs.setdefault(src, None)
    for example_id in example_refs:
        item = examples.get(example_id)
        if item is not None:
            for src in item.source_refs:
                refs.setdefault(src, None)
    for ref_id in reference_refs:
        item = references.get(ref_id)
        if item is not None:
            for src in item.source_refs:
                refs.setdefault(src, None)
    for unc_id in uncertainty_refs:
        item = uncertainties.get(unc_id)
        if item is not None:
            for src in item.source_refs:
                refs.setdefault(src, None)
    for rep_id in repetition_refs:
        item = repetitions.get(rep_id)
        if item is not None:
            for src in item.source_refs:
                refs.setdefault(src, None)
    return tuple(refs)
