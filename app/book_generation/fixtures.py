"""Synthetic Book Generator fixtures. Domain-independent. 0 provider."""

from __future__ import annotations

from typing import Any

from app.book_generation.constants import (
    TRANSPORT_KIND_CONNECTIVE,
    TRANSPORT_KIND_SUBSTANTIVE,
)
from app.book_generation.coverage import assigned_idea_ids_for_section
from app.book_generation.hydrate import TranscriptIndex
from app.editorial_planning.constants import EDITORIAL_PLAN_SCHEMA_VERSION
from app.editorial_planning.fixtures import tiny_source_map
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
    UncertaintyHandling,
)
from app.source_analysis.models import SourceMap
from app.source_analysis.transcript_input import SourceSegment


def tiny_book_source_map(
    *,
    project_name: str = "demo_book",
    idea_count: int = 4,
    primary_language: str = "en",
) -> SourceMap:
    return tiny_source_map(
        project_name=project_name,
        idea_count=idea_count,
        example_count=1,
        reference_count=1,
        uncertainty_count=1,
        primary_language=primary_language,
    )


def tiny_transcript_index(source_map: SourceMap) -> TranscriptIndex:
    segments = []
    for index, src_id in enumerate(source_map.all_source_refs(), start=1):
        segments.append(
            SourceSegment(
                src_id=src_id,
                source_id="AUDIO001",
                start=float(index),
                end=float(index + 1),
                text=f"Spoken source wording for {src_id} with author texture.",
                source_order=index,
            )
        )
    if not segments:
        segments.append(
            SourceSegment(
                src_id="SRC000001",
                source_id="AUDIO001",
                start=0.0,
                end=1.0,
                text="Spoken source wording.",
                source_order=1,
            )
        )
    return TranscriptIndex(
        transcript_id="TR001",
        content_sha256="synthetic",
        path="transcripts/clean/transcript_data.json",
        primary_language=source_map.primary_language,
        segments=tuple(segments),
    )


def tiny_editorial_plan(
    source_map: SourceMap,
    *,
    deferred_ids: tuple[str, ...] = (),
    excluded_ids: tuple[str, ...] = (),
    language_title: str = "Working Book Title",
) -> EditorialPlan:
    assigned = [
        idea.idea_id
        for idea in source_map.ideas
        if idea.idea_id not in deferred_ids and idea.idea_id not in excluded_ids
    ]
    if not assigned:
        assigned = [source_map.ideas[0].idea_id] if source_map.ideas else ["IDEA001"]
    first = assigned[:1]
    second = assigned[1:2] or assigned[:1]
    rest = assigned[2:] or assigned[-1:]
    extra_second = assigned[0] if len(assigned) > 2 else None
    section_a = EditorialSection(
        section_id="SEC001",
        working_title="First section",
        purpose="Open the argument",
        idea_refs=tuple(first),
        example_refs=tuple(item.example_id for item in source_map.examples[:1]),
        reference_refs=tuple(item.reference_id for item in source_map.references[:1]),
        uncertainty_refs=tuple(item.uncertainty_id for item in source_map.uncertainties[:1]),
        source_refs=tuple(
            ref for idea in source_map.ideas if idea.idea_id in first for ref in idea.source_refs
        ),
    )
    section_b = EditorialSection(
        section_id="SEC002",
        working_title="Second section",
        purpose="Continue the argument",
        idea_refs=tuple(second),
        source_refs=tuple(
            ref
            for idea in source_map.ideas
            if idea.idea_id in second
            for ref in idea.source_refs
        ),
    )
    section_c = EditorialSection(
        section_id="SEC003",
        working_title="Later section",
        purpose="Develop the argument",
        idea_refs=tuple(rest),
        source_refs=tuple(
            ref for idea in source_map.ideas if idea.idea_id in rest for ref in idea.source_refs
        ),
    )
    chapter_a = EditorialChapter(
        chapter_id="CH001",
        working_title="Opening chapter",
        purpose="Begin",
        summary="Foundation",
        idea_refs=tuple(first + second),
        sections=(section_a, section_b),
        editorial_actions=(EditorialAction(kind="GROUP", note="group"),),
    )
    chapter_b = EditorialChapter(
        chapter_id="CH002",
        working_title="Continuing chapter",
        purpose="Continue",
        summary="Development",
        idea_refs=tuple(rest),
        sections=(section_c,),
    )
    coverage = []
    for idea in source_map.ideas:
        if idea.idea_id in deferred_ids:
            coverage.append(
                IdeaDisposition(
                    idea_id=idea.idea_id,
                    disposition="DEFERRED",
                    reason="insufficient_support",
                    note="fixture deferred",
                )
            )
        elif idea.idea_id in excluded_ids:
            coverage.append(
                IdeaDisposition(
                    idea_id=idea.idea_id,
                    disposition="EXCLUDED",
                    reason="non_substantive",
                    note="fixture excluded",
                )
            )
        else:
            if idea.idea_id in first:
                primary = "SEC001"
            elif idea.idea_id in second:
                primary = "SEC002"
            else:
                primary = "SEC003"
            additional = ()
            if extra_second and idea.idea_id == extra_second and primary == "SEC001":
                additional = ()
            coverage.append(
                IdeaDisposition(
                    idea_id=idea.idea_id,
                    disposition="ASSIGNED",
                    primary_section_id=primary,
                    additional_section_ids=additional,
                )
            )
    return EditorialPlan(
        project_name=source_map.project_name,
        source_map=SourceMapIdentity(
            sha256="synthetic",
            bytes=1,
            schema_version=source_map.schema_version,
            project=source_map.project_name,
            topic_count=len(source_map.topics),
            idea_count=len(source_map.ideas),
            example_count=len(source_map.examples),
            reference_count=len(source_map.references),
            uncertainty_count=len(source_map.uncertainties),
            repetition_count=len(source_map.repetitions),
        ),
        book_concept=BookConcept(
            purpose="Teach the method",
            core_subject=source_map.source_analysis.main_theme,
            reader_journey="From foundation to practice",
            editorial_progression="foundation-development",
        ),
        title_candidates=(),
        selected_title=language_title,
        subtitle="A working subtitle",
        editorial_angle="Clear pedagogical order",
        target_reader=source_map.source_analysis.target_audience.summary,
        editorial_strategy="Preserve every assigned idea",
        chapters=(chapter_a, chapter_b),
        idea_coverage=tuple(coverage),
        source_coverage=SourceCoverage(
            referenced_source_refs=source_map.all_source_refs(),
            referenced_source_count=len(source_map.all_source_refs()),
        ),
        uncertainty_handling=UncertaintyHandling(
            policy="preserve",
            assigned_uncertainty_refs=tuple(
                item.uncertainty_id for item in source_map.uncertainties
            ),
        ),
        editorial_actions=(),
        stats=EditorialPlanStats(
            chapter_count=2,
            section_count=3,
            assigned_idea_count=len(assigned),
            deferred_idea_count=len(deferred_ids),
            excluded_idea_count=len(excluded_ids),
            reused_idea_count=0,
            example_assigned_count=len(source_map.examples),
            reference_assigned_count=len(source_map.references),
            uncertainty_assigned_count=len(source_map.uncertainties),
            repetition_assigned_count=0,
            title_candidate_count=0,
        ),
        planner=EditorialPlanMetadata(
            prompt_version="editorial-planner-1.0",
            transport_version="editorial-plan-transport-1.0",
            schema_version=EDITORIAL_PLAN_SCHEMA_VERSION,
            coverage_policy_version="idea-coverage-1.0",
            validator_version="editorial-plan-validator-1.0",
            provider="fake",
            model="fake",
            strategy="global",
            thinking_mode="disabled",
            effort="",
            signature="synthetic",
        ),
    )


def covering_chapter_transport(
    chapter: EditorialChapter,
    *,
    language: str = "en",
    include_connective: bool = True,
    include_uncertainty: bool = True,
) -> dict[str, Any]:
    sections = []
    for section in chapter.sections:
        paras: list[dict[str, Any]] = []
        if include_connective:
            paras.append(
                {
                    "h": f"{section.section_id}-con",
                    "k": TRANSPORT_KIND_CONNECTIVE,
                    "t": "The next movement of the book now turns to this subject.",
                    "e": [],
                }
            )
        for idea_id in assigned_idea_ids_for_section(section):
            handles = [idea_id]
            unc = []
            if include_uncertainty and section.uncertainty_refs:
                unc = [section.uncertainty_refs[0]]
            if section.example_refs:
                handles.append(section.example_refs[0])
            if section.reference_refs:
                handles.append(section.reference_refs[0])
            paras.append(
                {
                    "h": f"{idea_id}-p",
                    "k": TRANSPORT_KIND_SUBSTANTIVE,
                    "t": (
                        f"This paragraph develops {idea_id} in written English prose "
                        "without inventing new claims."
                    ),
                    "e": handles,
                    "u": unc,
                }
            )
        sections.append({"sid": section.section_id, "paras": paras})
    return {"sections": sections}


def missing_section_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    if transport["sections"]:
        transport["sections"] = transport["sections"][:-1] or []
        if not transport["sections"] and chapter.sections:
            transport["sections"] = []
    return transport


def extra_section_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    transport["sections"].append(
        {
            "sid": "SEC999",
            "paras": [
                {
                    "h": "extra",
                    "k": TRANSPORT_KIND_SUBSTANTIVE,
                    "t": "An extra section that was not planned.",
                    "e": list(chapter.sections[0].idea_refs[:1]),
                }
            ],
        }
    )
    return transport


def wrong_order_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    transport["sections"] = list(reversed(transport["sections"]))
    return transport


def missing_idea_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    if transport["sections"] and transport["sections"][0]["paras"]:
        transport["sections"][0]["paras"] = [
            para
            for para in transport["sections"][0]["paras"]
            if para.get("k") != TRANSPORT_KIND_SUBSTANTIVE
            or (para.get("e") or [None])[0] != chapter.sections[0].idea_refs[0]
        ]
    return transport


def unknown_idea_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    transport["sections"][0]["paras"].append(
        {
            "h": "unknown",
            "k": TRANSPORT_KIND_SUBSTANTIVE,
            "t": "This paragraph cites an idea that was never assigned.",
            "e": ["IDEA999"],
        }
    )
    return transport


def unknown_source_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    transport["sections"][0]["paras"].append(
        {
            "h": "badsrc",
            "k": TRANSPORT_KIND_SUBSTANTIVE,
            "t": "This paragraph cites a source that does not exist.",
            "e": ["SRC999999"],
        }
    )
    return transport


def unsourced_paragraph_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    transport["sections"][0]["paras"].append(
        {
            "h": "bare",
            "k": TRANSPORT_KIND_SUBSTANTIVE,
            "t": "A new doctrinal claim with no evidence handles at all.",
            "e": [],
        }
    )
    return transport


def connective_only_prefix(chapter: EditorialChapter) -> dict[str, Any]:
    return covering_chapter_transport(chapter, include_connective=True)


def wrong_language_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    for section in transport["sections"]:
        for para in section["paras"]:
            para["t"] = (
                "Ce paragraphe est rédigé entièrement en français avec des "
                "articles et des prépositions clairement francophones."
            )
    return transport


def deferred_idea_transport(
    chapter: EditorialChapter, deferred_id: str
) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    transport["sections"][0]["paras"].append(
        {
            "h": "deferred",
            "k": TRANSPORT_KIND_SUBSTANTIVE,
            "t": "This paragraph reintroduces a deferred idea.",
            "e": [deferred_id],
        }
    )
    return transport


def excluded_idea_transport(
    chapter: EditorialChapter, excluded_id: str
) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    transport["sections"][0]["paras"].append(
        {
            "h": "excluded",
            "k": TRANSPORT_KIND_SUBSTANTIVE,
            "t": "This paragraph reintroduces an excluded idea.",
            "e": [excluded_id],
        }
    )
    return transport


def empty_text_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    transport["sections"][0]["paras"].append(
        {
            "h": "empty-text",
            "k": TRANSPORT_KIND_SUBSTANTIVE,
            "t": "",
            "e": list(chapter.sections[0].idea_refs[:1]),
        }
    )
    return transport


def whitespace_text_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    transport["sections"][0]["paras"].append(
        {
            "h": "whitespace-text",
            "k": TRANSPORT_KIND_SUBSTANTIVE,
            "t": "   ",
            "e": list(chapter.sections[0].idea_refs[:1]),
        }
    )
    return transport


def empty_substantive_evidence_transport(chapter: EditorialChapter) -> dict[str, Any]:
    return unsourced_paragraph_transport(chapter)


def valid_connective_transport(chapter: EditorialChapter) -> dict[str, Any]:
    return covering_chapter_transport(chapter, include_connective=True)


def connective_new_claim_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    transport["sections"][0]["paras"].append(
        {
            "h": "con-new-claim",
            "k": TRANSPORT_KIND_CONNECTIVE,
            "t": (
                "Therefore every reader must sell their house before Friday "
                "or the inherited life is forfeited."
            ),
            "e": [],
        }
    )
    return transport


def invented_example_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    idea_id = chapter.sections[0].idea_refs[0] if chapter.sections[0].idea_refs else "IDEA001"
    transport["sections"][0]["paras"].append(
        {
            "h": "invented-ex",
            "k": TRANSPORT_KIND_SUBSTANTIVE,
            "t": (
                "Picture a traveler who once met a king beside a desert oasis "
                "and was given a silver cup as proof of adoption."
            ),
            "e": [idea_id],
        }
    )
    return transport


def supported_example_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    example_id = (
        chapter.sections[0].example_refs[0]
        if chapter.sections[0].example_refs
        else None
    )
    idea_id = chapter.sections[0].idea_refs[0] if chapter.sections[0].idea_refs else "IDEA001"
    handles = [idea_id]
    text = (
        "This paragraph develops the assigned idea in written English prose "
        "without inventing new claims."
    )
    if example_id:
        handles.append(example_id)
        text = (
            f"The supplied example {example_id} is used exactly as present in "
            "the canonical evidence, without adding a new scene."
        )
    transport["sections"][0]["paras"].append(
        {
            "h": "supported-ex",
            "k": TRANSPORT_KIND_SUBSTANTIVE,
            "t": text,
            "e": handles,
        }
    )
    return transport


def invented_hypothetical_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    idea_id = chapter.sections[0].idea_refs[0] if chapter.sections[0].idea_refs else "IDEA001"
    transport["sections"][0]["paras"].append(
        {
            "h": "invented-hyp",
            "k": TRANSPORT_KIND_SUBSTANTIVE,
            "t": (
                "Suppose a lighthouse keeper woke to find the sea replaced by "
                "glass and had to choose a new vocation before dawn."
            ),
            "e": [idea_id],
        }
    )
    return transport


def invented_reference_transport(chapter: EditorialChapter) -> dict[str, Any]:
    transport = covering_chapter_transport(chapter)
    idea_id = chapter.sections[0].idea_refs[0] if chapter.sections[0].idea_refs else "IDEA001"
    transport["sections"][0]["paras"].append(
        {
            "h": "invented-ref",
            "k": TRANSPORT_KIND_SUBSTANTIVE,
            "t": (
                "This is already stated in Habakkuk 3:4, a reference that is "
                "not among the supplied canonical evidence."
            ),
            "e": [idea_id],
        }
    )
    return transport
