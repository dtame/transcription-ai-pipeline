"""Fixtures FakeAI / synthétiques. Domain-independent. 0 provider réel."""

from __future__ import annotations

from typing import Any

from app.source_analysis.models import (
    SOURCE_MAP_SCHEMA_VERSION,
    AnalysisProvenance,
    AuthorVoiceProfile,
    Example,
    Idea,
    IntentStatement,
    Reference,
    Repetition,
    SourceAnalysisHeader,
    SourceMap,
    SourceMapStats,
    Topic,
    Uncertainty,
)


def tiny_source_map(
    *,
    project_name: str = "demo_planner",
    idea_count: int = 4,
    example_count: int = 1,
    reference_count: int = 1,
    uncertainty_count: int = 1,
    repetition_count: int = 0,
    primary_language: str = "fr",
) -> SourceMap:
    topics = (
        Topic(
            topic_id="TOP001",
            label="Theme A",
            summary="First theme",
            source_refs=("SRC000001",),
        ),
        Topic(
            topic_id="TOP002",
            label="Theme B",
            summary="Second theme",
            source_refs=("SRC000002",),
        ),
    )
    ideas = tuple(
        Idea(
            idea_id=f"IDEA{index:03d}",
            summary=f"Idea {index}",
            kind="claim",
            importance="central" if index == 1 else "supporting",
            topic_refs=("TOP001" if index <= idea_count // 2 else "TOP002",),
            source_refs=(f"SRC{index:06d}",),
        )
        for index in range(1, idea_count + 1)
    )
    examples = tuple(
        Example(
            example_id=f"EX{index:03d}",
            kind="example",
            summary=f"Example {index}",
            supports_idea_refs=(ideas[0].idea_id,),
            source_refs=("SRC000001",),
        )
        for index in range(1, example_count + 1)
    )
    references = tuple(
        Reference(
            reference_id=f"REF{index:03d}",
            kind="other",
            raw_reference=f"Ref {index}",
            normalized_reference=f"Ref {index}",
            completeness="partial",
            source_refs=("SRC000002",),
        )
        for index in range(1, reference_count + 1)
    )
    uncertainties = tuple(
        Uncertainty(
            uncertainty_id=f"UNC{index:03d}",
            kind="ambiguous_meaning",
            description=f"Uncertainty {index}",
            severity="low",
            source_refs=("SRC000001",),
        )
        for index in range(1, uncertainty_count + 1)
    )
    repetitions = tuple(
        Repetition(
            repetition_id=f"REP{index:03d}",
            character="recap",
            description=f"Repetition {index}",
            idea_refs=(ideas[0].idea_id, ideas[min(1, len(ideas) - 1)].idea_id),
            source_refs=("SRC000001",),
        )
        for index in range(1, repetition_count + 1)
    )
    src_ids = sorted(
        {
            *{ref for idea in ideas for ref in idea.source_refs},
            *{ref for item in examples for ref in item.source_refs},
            *{ref for item in references for ref in item.source_refs},
            *{ref for item in uncertainties for ref in item.source_refs},
            *{ref for item in repetitions for ref in item.source_refs},
        }
    )
    return SourceMap(
        transcript_id="TR001",
        project_name=project_name,
        primary_language=primary_language,
        source_analysis=SourceAnalysisHeader(
            main_theme="A compact source about a subject",
            author_intent=IntentStatement(
                summary="Teach a method", confidence="high", kinds=("enseigner",)
            ),
            target_audience=IntentStatement(
                summary="Practitioners of the subject", confidence="medium"
            ),
        ),
        topics=topics,
        ideas=ideas,
        examples=examples,
        references=references,
        uncertainties=uncertainties,
        repetitions=repetitions,
        author_voice_profile=AuthorVoiceProfile(register="oral", teaching_style="direct"),
        stats=SourceMapStats(
            topic_count=len(topics),
            idea_count=len(ideas),
            example_count=len(examples),
            reference_count=len(references),
            uncertainty_count=len(uncertainties),
            repetition_count=len(repetitions),
            source_segment_count=max(8, len(src_ids)),
            referenced_source_segments=len(src_ids),
            source_coverage_ratio=0.5,
        ),
        analysis=AnalysisProvenance(
            prompt_version="1.0",
            schema_version=SOURCE_MAP_SCHEMA_VERSION,
            provider="fake",
            model="fake-model",
            strategy="global",
            signature="sig",
        ),
    )


def covering_transport(
    source_map: SourceMap,
    *,
    chapter_count: int = 2,
    exclude_ids: tuple[str, ...] = (),
    defer_ids: tuple[str, ...] = (),
    reuse_idea: str | None = None,
    reverse_ideas: bool = False,
) -> dict[str, Any]:
    """Plan synthétique qui couvre toutes les IDEA, sans sémantique de corpus."""
    exclude = set(exclude_ids)
    defer = set(defer_ids)
    ideas = [idea.idea_id for idea in source_map.ideas if idea.idea_id not in exclude and idea.idea_id not in defer]
    if reverse_ideas:
        ideas = list(reversed(ideas))
    chapter_count = max(1, min(chapter_count, max(1, len(ideas))))
    buckets: list[list[str]] = [[] for _ in range(chapter_count)]
    for index, idea_id in enumerate(ideas):
        buckets[index % chapter_count].append(idea_id)
    examples = [item.example_id for item in source_map.examples]
    references = [item.reference_id for item in source_map.references]
    uncertainties = [item.uncertainty_id for item in source_map.uncertainties]
    repetitions = [item.repetition_id for item in source_map.repetitions]
    chapters = []
    for c_index, bucket in enumerate(buckets, start=1):
        if not bucket:
            bucket = ideas[:1] or ["IDEA001"]
        mid = max(1, len(bucket) // 2)
        groups = [bucket[:mid], bucket[mid:]] if len(bucket) > 1 else [bucket]
        groups = [group for group in groups if group]
        sections = []
        for s_index, group in enumerate(groups, start=1):
            section: dict[str, Any] = {
                "h": f"c{c_index}s{s_index}",
                "t": f"Section {c_index}.{s_index}",
                "p": "Cover assigned ideas",
                "i": list(group),
                "x": [],
                "ref": [],
                "u": [],
                "rep": [],
                "top": [],
                "act": [{"k": "GROUP", "n": "group ideas"}],
            }
            if c_index == 1 and s_index == 1:
                section["x"] = examples
                section["ref"] = references
                section["u"] = uncertainties
                section["rep"] = repetitions
                if source_map.topics:
                    section["top"] = [source_map.topics[0].topic_id]
            sections.append(section)
        chapters.append(
            {
                "h": f"c{c_index}",
                "t": f"Chapter {c_index}",
                "p": "Develop a cluster of ideas",
                "sum": "Synthetic coverage chapter",
                "top": [source_map.topics[min(c_index - 1, len(source_map.topics) - 1)].topic_id]
                if source_map.topics
                else [],
                "act": [{"k": "REORDER", "n": "editorial order"}],
                "sections": sections,
            }
        )
    if reuse_idea:
        flat = [section for chapter in chapters for section in chapter["sections"]]
        if flat and reuse_idea not in flat[0]["i"]:
            flat[0]["i"].append(reuse_idea)
        if len(flat) > 1 and reuse_idea not in flat[-1]["i"]:
            flat[-1]["i"].append(reuse_idea)
    return {
        "concept": {
            "promise": "Organize the validated source into a readable book",
            "subject": source_map.source_analysis.main_theme[:180],
            "journey": "From foundation through development to application",
            "progression": "foundation-development-application",
        },
        "titles": [
            {"t": "Working Title One", "why": "Clear and source-grounded"},
            {"t": "Working Title Two", "why": "Alternate angle"},
        ],
        "pick": 0,
        "subtitle": "A source-grounded working subtitle",
        "angle": "Coherent pedagogical progression",
        "reader": source_map.source_analysis.target_audience.summary,
        "strategy": "Group related ideas; preserve every IDEA ref",
        "chapters": chapters,
        "deferred": [
            {
                "id": idea_id,
                "why": "insufficient_support",
                "n": "deferred in fixture",
            }
            for idea_id in defer_ids
        ],
        "excluded": [
            {
                "id": idea_id,
                "why": "non_substantive",
                "n": "excluded in fixture",
            }
            for idea_id in exclude_ids
        ],
    }


def empty_chapter_transport(source_map: SourceMap) -> dict[str, Any]:
    transport = covering_transport(source_map, chapter_count=1)
    transport["chapters"].append(
        {
            "h": "empty",
            "t": "Empty",
            "p": "None",
            "sum": "",
            "sections": [],
        }
    )
    return transport


def empty_section_transport(source_map: SourceMap) -> dict[str, Any]:
    transport = covering_transport(source_map, chapter_count=1)
    transport["chapters"][0]["sections"].append(
        {
            "h": "empty-sec",
            "t": "Empty section",
            "p": "No ideas",
            "i": [],
        }
    )
    return transport


def invented_section_transport(source_map: SourceMap) -> dict[str, Any]:
    transport = covering_transport(source_map, chapter_count=1)
    transport["chapters"][0]["sections"].append(
        {
            "h": "invented",
            "t": "Unsupported unit",
            "p": "Claims new content",
            "i": [],
        }
    )
    return transport


def unknown_idea_transport(source_map: SourceMap) -> dict[str, Any]:
    transport = covering_transport(source_map, chapter_count=1)
    transport["chapters"][0]["sections"][0]["i"].append("IDEA999")
    return transport


def missing_idea_transport(source_map: SourceMap) -> dict[str, Any]:
    transport = covering_transport(source_map, chapter_count=1)
    if transport["chapters"][0]["sections"][0]["i"]:
        transport["chapters"][0]["sections"][0]["i"] = transport["chapters"][0][
            "sections"
        ][0]["i"][1:]
    return transport


def nested_hierarchy_transport(source_map: SourceMap) -> dict[str, Any]:
    transport = covering_transport(source_map, chapter_count=1)
    transport["chapters"][0]["sections"][0]["chapters"] = [{"t": "nested"}]
    return transport


def manuscript_hierarchy_transport(source_map: SourceMap) -> dict[str, Any]:
    transport = covering_transport(source_map, chapter_count=1)
    transport["paragraphs"] = [{"text": "finished prose"}]
    return transport
