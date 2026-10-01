"""Offline assembly and chapter materialization. No provider call."""

from __future__ import annotations

from typing import Iterable, Mapping

from app.book_generation.cache import (
    ChapterCache,
    default_chapter_signature_inputs,
    build_chapter_signature,
)
from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION,
    BOOK_GENERATOR_VALIDATOR_VERSION,
    BOOK_SCHEMA_VERSION,
    EVIDENCE_STRATEGY_HYDRATED,
    GENERATION_UNIT_CHAPTER,
    TITLE_STATUS_WORKING,
)
from app.book_generation.models import (
    Book,
    BookChapter,
    BookGenerationMetadata,
    BookIdentity,
    BookParagraph,
    BookSection,
    ChapterCandidate,
    format_paragraph_id,
)
from app.book_generation.reconstruct import reconstruct_chapter_candidate
from app.book_generation.settings import GeneratorSettings, frozen_production_settings
from app.book_generation.validator import (
    BookGenerationValidation,
    validate_chapter_candidate,
)
from app.book_generation.writer import book_sha256, candidate_sha256
from app.editorial_planning.models import EditorialChapter, EditorialPlan
from app.source_analysis.models import SourceMap


def materialize_chapter(
    transport: Mapping,
    plan: EditorialPlan,
    source_map: SourceMap,
    chapter: EditorialChapter,
    *,
    language: str,
    allowed_handles: Iterable[str] | None = None,
    provider_raw_sha256: str = "",
    cache_signature: str = "",
) -> tuple[ChapterCandidate, BookGenerationValidation, str]:
    candidate = reconstruct_chapter_candidate(
        transport,
        chapter,
        source_map,
        provider_raw_sha256=provider_raw_sha256,
        cache_signature=cache_signature,
    )
    validation = validate_chapter_candidate(
        candidate,
        plan,
        source_map,
        chapter,
        language=language,
        allowed_handles=allowed_handles,
    )
    return candidate, validation, candidate_sha256(candidate.to_dict())


def assign_paragraph_ids(chapters: Iterable[BookChapter]) -> tuple[BookChapter, ...]:
    assigned: list[BookChapter] = []
    index = 1
    for chapter in chapters:
        sections: list[BookSection] = []
        for section in chapter.sections:
            paragraphs: list[BookParagraph] = []
            for paragraph in section.paragraphs:
                paragraphs.append(
                    BookParagraph(
                        text=paragraph.text,
                        kind=paragraph.kind,
                        evidence_handles=paragraph.evidence_handles,
                        source_refs=paragraph.source_refs,
                        idea_refs=paragraph.idea_refs,
                        example_refs=paragraph.example_refs,
                        reference_refs=paragraph.reference_refs,
                        uncertainty_refs=paragraph.uncertainty_refs,
                        paragraph_id=format_paragraph_id(index),
                        provider_handle=paragraph.provider_handle,
                    )
                )
                index += 1
            sections.append(
                BookSection(
                    section_id=section.section_id,
                    title=section.title,
                    paragraphs=tuple(paragraphs),
                    idea_refs=section.idea_refs,
                    source_refs=section.source_refs,
                )
            )
        assigned.append(
            BookChapter(
                chapter_id=chapter.chapter_id,
                title=chapter.title,
                sections=tuple(sections),
                idea_refs=chapter.idea_refs,
                source_refs=chapter.source_refs,
            )
        )
    return tuple(assigned)


def assemble_book(
    candidates: Iterable[ChapterCandidate],
    plan: EditorialPlan,
    *,
    language: str,
    identity: BookIdentity,
    settings: GeneratorSettings | None = None,
    evidence_strategy: str = EVIDENCE_STRATEGY_HYDRATED,
    signature: str = "",
) -> Book:
    settings = settings or frozen_production_settings()
    ordered = {candidate.chapter_id: candidate for candidate in candidates}
    chapters = assign_paragraph_ids(
        ordered[chapter.chapter_id].to_book_chapter()
        for chapter in plan.chapters
        if chapter.chapter_id in ordered
    )
    return Book(
        project_name=plan.project_name,
        language=language,
        title=plan.selected_title,
        subtitle=plan.subtitle,
        title_status=TITLE_STATUS_WORKING,
        chapters=chapters,
        identity=identity,
        generation=BookGenerationMetadata(
            prompt_version=BOOK_GENERATOR_PROMPT_VERSION,
            transport_version=BOOK_GENERATION_TRANSPORT_VERSION,
            schema_version=BOOK_SCHEMA_VERSION,
            validator_version=BOOK_GENERATOR_VALIDATOR_VERSION,
            evidence_strategy=evidence_strategy,
            generation_unit=GENERATION_UNIT_CHAPTER,
            provider=settings.provider,
            model=settings.model,
            thinking_mode=settings.thinking_mode,
            effort=settings.effort or "",
            language=language,
            title_status=TITLE_STATUS_WORKING,
            signature=signature,
        ),
    )


def chapter_signature_for(
    *,
    source_map_sha256: str,
    editorial_plan_sha256: str,
    chapter_id: str,
    prompt_sha256: str,
    response_schema_sha256: str,
    language: str,
    evidence_bundle_sha256: str,
    settings: GeneratorSettings | None = None,
    max_output_tokens: int | None = None,
) -> str:
    settings = settings or frozen_production_settings()
    inputs = default_chapter_signature_inputs(
        source_map_sha256=source_map_sha256,
        editorial_plan_sha256=editorial_plan_sha256,
        chapter_id=chapter_id,
        prompt_sha256=prompt_sha256,
        response_schema_sha256=response_schema_sha256,
        provider=settings.provider,
        model=settings.model,
        thinking_mode=settings.thinking_mode,
        effort=settings.effort,
        max_output_tokens=max_output_tokens
        if max_output_tokens is not None
        else settings.max_output_tokens,
        canonical_language=language,
        evidence_bundle_sha256=evidence_bundle_sha256,
    )
    return build_chapter_signature(inputs)


def remember_chapter(
    cache: ChapterCache, signature: str, digest: str
) -> ChapterCache:
    cache.remember(signature, digest)
    return cache


def assembled_book_sha256(book: Book) -> str:
    return book_sha256(book)
