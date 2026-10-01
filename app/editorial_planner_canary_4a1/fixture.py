"""Fixture SourceMap synthétique — community garden workshop. 0 corpus pastoral."""

from __future__ import annotations

import json
from typing import Any

from app.editorial_planner_canary_4a1.constants import (
    PROJECT_NAME,
    SYNTHETIC_SRC_IDS,
    TRANSCRIPT_ID,
)
from app.file_utils import content_hash
from app.source_analysis.models import (
    SOURCE_MAP_SCHEMA_VERSION,
    AnalysisProvenance,
    AuthorVoiceProfile,
    Example,
    Idea,
    IntentStatement,
    Reference,
    SourceAnalysisHeader,
    SourceMap,
    SourceMapStats,
    Topic,
    Uncertainty,
)


def build_synthetic_source_map() -> SourceMap:
    """
    Neutral workshop domain. Scale: 3 TOPIC, 7 IDEA, 2 EXAMPLE, 2 REFERENCE,
    1 UNCERTAINTY. Naturally supports ~2 chapters / 2–3 sections, grouping,
    one administrative IDEA (EXCLUDED candidate), optional reuse of IDEA001,
    and UNC001 available to a planned section.
    """
    src = SYNTHETIC_SRC_IDS
    topics = (
        Topic(
            topic_id="TOP001",
            label="Soil and bed preparation",
            summary="How the workshop prepares garden soil and maps the site.",
            source_refs=(src[0], src[1]),
        ),
        Topic(
            topic_id="TOP002",
            label="Planting and watering",
            summary="How the workshop sequences planting and waters plants.",
            source_refs=(src[2], src[3], src[4]),
        ),
        Topic(
            topic_id="TOP003",
            label="Harvest sharing and volunteer roles",
            summary="How surplus produce is shared and how volunteers help.",
            source_refs=(src[5], src[6], src[7]),
        ),
    )
    ideas = (
        Idea(
            idea_id="IDEA001",
            summary="Test soil pH before planting so beds are not committed to the wrong crop.",
            kind="instruction",
            importance="central",
            topic_refs=("TOP001",),
            source_refs=(src[0],),
        ),
        Idea(
            idea_id="IDEA002",
            summary="Add compost in thin layers mixed into the topsoil rather than dumping one pile.",
            kind="instruction",
            importance="central",
            topic_refs=("TOP001",),
            source_refs=(src[1],),
        ),
        Idea(
            idea_id="IDEA003",
            summary="Map sun and shade across the plot before choosing which beds get which plants.",
            kind="instruction",
            importance="supporting",
            topic_refs=("TOP001",),
            source_refs=(src[1],),
        ),
        Idea(
            idea_id="IDEA004",
            summary="Plant in staggered weeks so harvest arrives continuously instead of all at once.",
            kind="principle",
            importance="central",
            topic_refs=("TOP002",),
            source_refs=(src[2],),
        ),
        Idea(
            idea_id="IDEA005",
            summary="Water at the base in the morning to keep leaves dry and reduce disease.",
            kind="instruction",
            importance="central",
            topic_refs=("TOP002",),
            source_refs=(src[3],),
        ),
        Idea(
            idea_id="IDEA006",
            summary="Share surplus produce on a simple weekly harvest table that neighbors can take from.",
            kind="claim",
            importance="supporting",
            topic_refs=("TOP003",),
            source_refs=(src[5],),
        ),
        Idea(
            idea_id="IDEA007",
            summary="A volunteer sign-in clipboard on the folding table collects emails for the newsletter.",
            kind="observation",
            importance="minor",
            topic_refs=("TOP003",),
            source_refs=(src[6],),
        ),
    )
    examples = (
        Example(
            example_id="EX001",
            kind="anecdote",
            summary="Last year the east bed stayed wet until June after the group skipped the soil test.",
            supports_idea_refs=("IDEA001",),
            source_refs=(src[0],),
        ),
        Example(
            example_id="EX002",
            kind="example",
            summary="A neighbor's tomatoes developed blight after evening overhead watering.",
            supports_idea_refs=("IDEA005",),
            source_refs=(src[4],),
        ),
    )
    references = (
        Reference(
            reference_id="REF001",
            kind="book",
            raw_reference="the city's community garden handbook, 2024 edition",
            normalized_reference="city community garden handbook 2024",
            completeness="partial",
            source_refs=(src[2],),
        ),
        Reference(
            reference_id="REF002",
            kind="other",
            raw_reference="the seed-packet instruction sheet from the co-op",
            normalized_reference="co-op seed packet instruction sheet",
            completeness="partial",
            source_refs=(src[3],),
        ),
    )
    uncertainties = (
        Uncertainty(
            uncertainty_id="UNC001",
            kind="ambiguous_meaning",
            description=(
                "The speaker was unsure whether the municipal compost drop-off "
                "is open on Sundays or only Saturday mornings."
            ),
            severity="low",
            source_refs=(src[7],),
        ),
    )
    src_used = sorted(
        {
            *{ref for idea in ideas for ref in idea.source_refs},
            *{ref for item in examples for ref in item.source_refs},
            *{ref for item in references for ref in item.source_refs},
            *{ref for item in uncertainties for ref in item.source_refs},
            *{ref for topic in topics for ref in topic.source_refs},
        }
    )
    return SourceMap(
        transcript_id=TRANSCRIPT_ID,
        project_name=PROJECT_NAME,
        primary_language="en",
        source_analysis=SourceAnalysisHeader(
            main_theme=(
                "A community garden workshop on preparing soil, planting in "
                "sequence, watering carefully, and sharing surplus harvest"
            ),
            author_intent=IntentStatement(
                summary="Teach neighbors a practical method for a shared garden plot",
                confidence="high",
                kinds=("enseigner",),
            ),
            target_audience=IntentStatement(
                summary="Adult neighbors joining a first-year community garden workshop",
                confidence="high",
            ),
        ),
        topics=topics,
        ideas=ideas,
        examples=examples,
        references=references,
        uncertainties=uncertainties,
        repetitions=(),
        author_voice_profile=AuthorVoiceProfile(
            register="oral",
            teaching_style="direct",
            tone=("practical", "encouraging"),
        ),
        stats=SourceMapStats(
            topic_count=len(topics),
            idea_count=len(ideas),
            example_count=len(examples),
            reference_count=len(references),
            uncertainty_count=len(uncertainties),
            repetition_count=0,
            source_segment_count=len(src),
            referenced_source_segments=len(src_used),
            source_coverage_ratio=round(len(src_used) / max(1, len(src)), 3),
        ),
        analysis=AnalysisProvenance(
            prompt_version="synthetic-canary-4a1",
            schema_version=SOURCE_MAP_SCHEMA_VERSION,
            provider="synthetic",
            model="none",
            strategy="global",
            signature="synthetic-garden-workshop-4a1",
        ),
    )


def fixture_audit(source_map: SourceMap | None = None) -> dict[str, Any]:
    source_map = source_map or build_synthetic_source_map()
    payload = source_map.to_dict()
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = content_hash(encoded)
    return {
        "domain": "community garden workshop",
        "project_name": source_map.project_name,
        "transcript_id": source_map.transcript_id,
        "primary_language": source_map.primary_language,
        "inventory": {
            "topics": len(source_map.topics),
            "ideas": len(source_map.ideas),
            "examples": len(source_map.examples),
            "references": len(source_map.references),
            "uncertainties": len(source_map.uncertainties),
            "repetitions": len(source_map.repetitions),
        },
        "ids": {
            "topics": [item.topic_id for item in source_map.topics],
            "ideas": [item.idea_id for item in source_map.ideas],
            "examples": [item.example_id for item in source_map.examples],
            "references": [item.reference_id for item in source_map.references],
            "uncertainties": [item.uncertainty_id for item in source_map.uncertainties],
        },
        "src_ids": list(source_map.all_source_refs()),
        "expected_src_ids": list(SYNTHETIC_SRC_IDS),
        "administrative_idea_candidate": "IDEA007",
        "grouping_candidates": ["IDEA001", "IDEA002", "IDEA003"],
        "optional_reuse_candidate": "IDEA001",
        "uncertainty_id": "UNC001",
        "technical_windows": False,
        "fixture_sha256": digest,
        "fixture_bytes": len(encoded.encode("utf-8")),
        "source_map": payload,
    }


__all__ = ["build_synthetic_source_map", "fixture_audit"]
