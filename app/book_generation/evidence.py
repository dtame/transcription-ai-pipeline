"""
Deterministic evidence extraction from EditorialPlan + SourceMap.

Provider receives the exact subset needed for one generation unit.
Full SourceMap and full transcript are never sent.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from app.book_generation.constants import (
    EVIDENCE_BUNDLE_VERSION,
    EVIDENCE_STRATEGY_HYDRATED,
    EVIDENCE_STRATEGY_SOURCE_MAP_ONLY,
    TITLE_STATUS_WORKING,
)
from app.book_generation.context import continuity_for_chapter
from app.book_generation.coverage import (
    assigned_idea_ids_for_section,
    deferred_idea_ids,
    excluded_idea_ids,
)
from app.book_generation.hydrate import (
    TranscriptIndex,
    compact_segment_dicts,
    hydrate_src_ids,
)
from app.editorial_planning.models import EditorialChapter, EditorialPlan, EditorialSection
from app.file_utils import content_hash
from app.source_analysis.models import SourceMap


def classify_handle(handle: str) -> str:
    text = str(handle or "")
    for prefix, kind in (
        ("IDEA", "IDEA"),
        ("EX", "EX"),
        ("REF", "REF"),
        ("UNC", "UNC"),
        ("REP", "REP"),
        ("SRC", "SRC"),
        ("TOP", "TOP"),
        ("CH", "CH"),
        ("SEC", "SEC"),
        ("P", "P"),
    ):
        if text.startswith(prefix) and text[len(prefix) :].isdigit():
            return kind
    return "UNKNOWN"


def _index_source_map(source_map: SourceMap) -> dict[str, dict[str, Any]]:
    ideas = {item.idea_id: item for item in source_map.ideas}
    examples = {item.example_id: item for item in source_map.examples}
    references = {item.reference_id: item for item in source_map.references}
    uncertainties = {item.uncertainty_id: item for item in source_map.uncertainties}
    repetitions = {item.repetition_id: item for item in source_map.repetitions}
    topics = {item.topic_id: item for item in source_map.topics}
    return {
        "ideas": ideas,
        "examples": examples,
        "references": references,
        "uncertainties": uncertainties,
        "repetitions": repetitions,
        "topics": topics,
    }


def _idea_payload(idea) -> dict[str, Any]:
    return {
        "id": idea.idea_id,
        "sum": idea.summary,
        "kind": idea.kind,
        "imp": idea.importance,
        "src": list(idea.source_refs),
        "top": list(idea.topic_refs),
    }


def _example_payload(item) -> dict[str, Any]:
    return {
        "id": item.example_id,
        "kind": item.kind,
        "sum": item.summary,
        "ideas": list(item.supports_idea_refs),
        "src": list(item.source_refs),
    }


def _reference_payload(item) -> dict[str, Any]:
    return {
        "id": item.reference_id,
        "kind": item.kind,
        "raw": item.raw_reference,
        "norm": item.normalized_reference,
        "comp": item.completeness,
        "src": list(item.source_refs),
    }


def _uncertainty_payload(item) -> dict[str, Any]:
    return {
        "id": item.uncertainty_id,
        "kind": item.kind,
        "desc": item.description,
        "sev": item.severity,
        "src": list(item.source_refs),
    }


def related_support_ids(
    source_map: SourceMap, idea_ids: Iterable[str]
) -> dict[str, tuple[str, ...]]:
    wanted = set(idea_ids)
    examples = tuple(
        item.example_id
        for item in source_map.examples
        if wanted.intersection(item.supports_idea_refs)
    )
    references = tuple(
        item.reference_id
        for item in source_map.references
        if wanted.intersection(_refs_touching_ideas(item.source_refs, source_map, wanted))
        or True
    )
    # References are included when the section/chapter already lists them or
    # when they share SRC with assigned ideas. Keep section-listed refs below.
    uncertainties = tuple(
        item.uncertainty_id
        for item in source_map.uncertainties
        if wanted.intersection(_idea_ids_for_src(item.source_refs, source_map))
    )
    return {
        "examples": examples,
        "references": references,
        "uncertainties": uncertainties,
    }


def _idea_ids_for_src(src_refs: Iterable[str], source_map: SourceMap) -> set[str]:
    src = set(src_refs)
    return {
        idea.idea_id
        for idea in source_map.ideas
        if src.intersection(idea.source_refs)
    }


def _refs_touching_ideas(
    src_refs: Iterable[str], source_map: SourceMap, idea_ids: set[str]
) -> set[str]:
    return _idea_ids_for_src(src_refs, source_map) & idea_ids


def collect_unit_src_ids(
    source_map: SourceMap,
    *,
    idea_ids: Iterable[str],
    extra_src: Iterable[str] = (),
    example_ids: Iterable[str] = (),
    reference_ids: Iterable[str] = (),
    uncertainty_ids: Iterable[str] = (),
) -> tuple[str, ...]:
    index = _index_source_map(source_map)
    src: dict[str, None] = {}
    for idea_id in idea_ids:
        idea = index["ideas"].get(idea_id)
        if idea:
            for ref in idea.source_refs:
                src.setdefault(ref, None)
    for example_id in example_ids:
        item = index["examples"].get(example_id)
        if item:
            for ref in item.source_refs:
                src.setdefault(ref, None)
    for reference_id in reference_ids:
        item = index["references"].get(reference_id)
        if item:
            for ref in item.source_refs:
                src.setdefault(ref, None)
    for uncertainty_id in uncertainty_ids:
        item = index["uncertainties"].get(uncertainty_id)
        if item:
            for ref in item.source_refs:
                src.setdefault(ref, None)
    for ref in extra_src:
        src.setdefault(ref, None)
    return tuple(src)


def resolve_src_for_handles(
    handles: Iterable[str], source_map: SourceMap
) -> tuple[str, ...]:
    index = _index_source_map(source_map)
    src: dict[str, None] = {}
    for handle in handles:
        kind = classify_handle(handle)
        if kind == "SRC":
            src.setdefault(handle, None)
            continue
        item = None
        if kind == "IDEA":
            item = index["ideas"].get(handle)
        elif kind == "EX":
            item = index["examples"].get(handle)
        elif kind == "REF":
            item = index["references"].get(handle)
        elif kind == "UNC":
            item = index["uncertainties"].get(handle)
        elif kind == "REP":
            item = index["repetitions"].get(handle)
        if item is not None:
            for ref in getattr(item, "source_refs", ()):
                src.setdefault(ref, None)
    return tuple(src)


def voice_payload(source_map: SourceMap) -> dict[str, Any]:
    voice = source_map.author_voice_profile
    return {
        "tone": list(voice.tone),
        "register": voice.register,
        "sentence_style": voice.sentence_style,
        "rhetorical_patterns": list(voice.rhetorical_patterns),
        "use_of_questions": voice.use_of_questions,
        "use_of_repetition": voice.use_of_repetition,
        "use_of_examples": voice.use_of_examples,
        "direct_address": voice.direct_address,
        "teaching_style": voice.teaching_style,
        "distinctive_traits": list(voice.distinctive_traits),
    }


def book_framing(
    plan: EditorialPlan, *, language: str
) -> dict[str, Any]:
    return {
        "title": plan.selected_title,
        "subtitle": plan.subtitle,
        "title_status": TITLE_STATUS_WORKING,
        "purpose": plan.book_concept.purpose,
        "core_subject": plan.book_concept.core_subject,
        "reader_journey": plan.book_concept.reader_journey,
        "editorial_progression": plan.book_concept.editorial_progression,
        "angle": plan.editorial_angle,
        "reader": plan.target_reader,
        "strategy": plan.editorial_strategy,
        "canonical_document_language": language,
        "do_not_replace_title": True,
    }


def _section_plan(section: EditorialSection) -> dict[str, Any]:
    return {
        "id": section.section_id,
        "t": section.working_title,
        "p": section.purpose,
        "i": list(section.idea_refs),
        "x": list(section.example_refs),
        "ref": list(section.reference_refs),
        "u": list(section.uncertainty_refs),
        "src": list(section.source_refs),
    }


def build_chapter_evidence(
    plan: EditorialPlan,
    source_map: SourceMap,
    chapter: EditorialChapter,
    *,
    language: str,
    hydrate: bool = True,
    transcript_index: TranscriptIndex | None = None,
    section_ids: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    sections = chapter.sections
    if section_ids is not None:
        wanted = set(section_ids)
        sections = tuple(section for section in chapter.sections if section.section_id in wanted)
    idea_ids = []
    example_ids: dict[str, None] = {}
    reference_ids: dict[str, None] = {}
    uncertainty_ids: dict[str, None] = {}
    extra_src: dict[str, None] = {}
    for section in sections:
        for idea_id in assigned_idea_ids_for_section(section):
            if idea_id not in idea_ids:
                idea_ids.append(idea_id)
        for example_id in section.example_refs:
            example_ids.setdefault(example_id, None)
        for reference_id in section.reference_refs:
            reference_ids.setdefault(reference_id, None)
        for uncertainty_id in section.uncertainty_refs:
            uncertainty_ids.setdefault(uncertainty_id, None)
        for src in section.source_refs:
            extra_src.setdefault(src, None)

    index = _index_source_map(source_map)
    related = related_support_ids(source_map, idea_ids)
    for example_id in related["examples"]:
        example_ids.setdefault(example_id, None)
    for uncertainty_id in related["uncertainties"]:
        uncertainty_ids.setdefault(uncertainty_id, None)
    # References: section-listed plus those sharing SRC with assigned ideas,
    # but never completed from model memory. Filter related refs to those
    # that actually touch assigned ideas.
    for reference_id in related["references"]:
        item = index["references"].get(reference_id)
        if item and _refs_touching_ideas(item.source_refs, source_map, set(idea_ids)):
            reference_ids.setdefault(reference_id, None)

    ideas = [
        _idea_payload(index["ideas"][idea_id])
        for idea_id in idea_ids
        if idea_id in index["ideas"]
    ]
    examples = [
        _example_payload(index["examples"][example_id])
        for example_id in example_ids
        if example_id in index["examples"]
    ]
    references = [
        _reference_payload(index["references"][reference_id])
        for reference_id in reference_ids
        if reference_id in index["references"]
    ]
    uncertainties = [
        _uncertainty_payload(index["uncertainties"][uncertainty_id])
        for uncertainty_id in uncertainty_ids
        if uncertainty_id in index["uncertainties"]
    ]
    src_ids = collect_unit_src_ids(
        source_map,
        idea_ids=idea_ids,
        extra_src=extra_src,
        example_ids=example_ids,
        reference_ids=reference_ids,
        uncertainty_ids=uncertainty_ids,
    )
    segments = hydrate_src_ids(src_ids, transcript_index) if hydrate else ()
    allowed = []
    for idea_id in idea_ids:
        allowed.append(idea_id)
    allowed.extend(example_ids)
    allowed.extend(reference_ids)
    allowed.extend(uncertainty_ids)
    allowed.extend(src_ids)

    strategy = (
        EVIDENCE_STRATEGY_HYDRATED if hydrate else EVIDENCE_STRATEGY_SOURCE_MAP_ONLY
    )
    bundle = {
        "v": EVIDENCE_BUNDLE_VERSION,
        "strategy": strategy,
        "canonical_document_language": language,
        "book": book_framing(plan, language=language),
        "voice": voice_payload(source_map),
        "continuity": continuity_for_chapter(plan, chapter),
        "chapter": {
            "id": chapter.chapter_id,
            "t": chapter.working_title,
            "p": chapter.purpose,
            "sum": chapter.summary,
        },
        "sections": [_section_plan(section) for section in sections],
        "ideas": ideas,
        "examples": examples,
        "references": references,
        "uncertainties": uncertainties,
        "src": list(src_ids),
        "src_text": compact_segment_dicts(segments) if hydrate else [],
        "allowed": allowed,
        "blocked": sorted(deferred_idea_ids(plan) | excluded_idea_ids(plan)),
        "rules": {
            "follow_section_order": True,
            "no_invented_ids": True,
            "no_external_knowledge": True,
            "no_translation": True,
            "no_auto_section_summary": True,
            "no_auto_chapter_conclusion": True,
            "preserve_uncertainty": True,
            "preserve_prayer_exhortation_exercise": True,
        },
    }
    return bundle


def render_evidence_json(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def evidence_identity(bundle: dict[str, Any]) -> str:
    return content_hash(render_evidence_json(bundle))


def evidence_metrics(bundle: dict[str, Any]) -> dict[str, Any]:
    text = render_evidence_json(bundle)
    idea_chars = sum(len(str(item.get("sum") or "")) for item in bundle.get("ideas") or [])
    src_text_chars = sum(len(str(item.get("t") or "")) for item in bundle.get("src_text") or [])
    return {
        "chars": len(text),
        "utf8_bytes": len(text.encode("utf-8")),
        "section_count": len(bundle.get("sections") or []),
        "idea_count": len(bundle.get("ideas") or []),
        "example_count": len(bundle.get("examples") or []),
        "reference_count": len(bundle.get("references") or []),
        "uncertainty_count": len(bundle.get("uncertainties") or []),
        "src_ref_count": len(bundle.get("src") or []),
        "hydrated_segment_count": len(bundle.get("src_text") or []),
        "idea_summary_chars": idea_chars,
        "hydrated_src_chars": src_text_chars,
        "sha256": evidence_identity(bundle),
    }


def chapter_evidence_for_ids(
    plan: EditorialPlan,
    source_map: SourceMap,
    chapter_id: str,
    *,
    language: str,
    hydrate: bool = True,
    transcript_index: TranscriptIndex | None = None,
    section_ids: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    from app.book_generation.coverage import chapter_by_id

    chapter = chapter_by_id(plan, chapter_id)
    return build_chapter_evidence(
        plan,
        source_map,
        chapter,
        language=language,
        hydrate=hydrate,
        transcript_index=transcript_index,
        section_ids=section_ids,
    )
