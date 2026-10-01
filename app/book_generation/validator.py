"""
Local BookGenerationValidator.

Structural + provenance + coverage + basic fidelity.
Does not claim Phase 5 unsupported-claim detection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.book_generation.constants import (
    BOOK_GENERATOR_VALIDATOR_VERSION,
    MAX_CONNECTIVE_CHARS,
    MAX_PARAGRAPH_CHARS,
    MIN_SUBSTANTIVE_CHARS,
    PARAGRAPH_KIND_CONNECTIVE,
    PARAGRAPH_KIND_SUBSTANTIVE,
    VALIDATION_FAIL,
    VALIDATION_PASS,
    VALIDATION_REVIEW,
)
from app.book_generation.coverage import (
    assigned_idea_ids_for_section,
    deferred_idea_ids,
    excluded_idea_ids,
    idea_ids_from_paragraphs,
)
from app.book_generation.evidence import classify_handle, resolve_src_for_handles
from app.book_generation.language import validate_manuscript_language
from app.book_generation.models import (
    Book,
    BookParagraph,
    ChapterCandidate,
    scan_forbidden_book_structure,
)
from app.editorial_planning.models import EditorialChapter, EditorialPlan
from app.source_analysis.models import SourceMap


@dataclass(frozen=True)
class BookGenerationValidation:
    status: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.status != VALIDATION_FAIL

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "validator_version": BOOK_GENERATOR_VALIDATOR_VERSION,
        }


def validator_contract_dict() -> dict:
    return {
        "version": BOOK_GENERATOR_VALIDATOR_VERSION,
        "scope": [
            "generation-unit structure",
            "section identity/order",
            "IDEA accountability",
            "evidence handles",
            "SRC validity",
            "language",
            "uncertainty metadata",
            "paragraph provenance",
            "determinism of reconstruction",
        ],
        "non_scope": [
            "unsupported semantic claims",
            "subtle contradictions",
            "doctrinal distortion",
            "whole-book redundancy",
            "whole-book narrative quality",
        ],
        "phase_5": "Book Validator owns whole-book semantic validation",
        "limitation": (
            "Paragraph-level reference presence does not prove every sentence "
            "is supported."
        ),
        "silent_idea_omission": "FAIL",
        "extra_idea": "FAIL",
        "missing_section": "FAIL",
        "extra_section": "FAIL",
        "wrong_section_order": "FAIL",
        "unsourced_substantive": "FAIL",
        "empty_paragraph": "FAIL",
        "whitespace_only_paragraph": "FAIL",
        "empty_paragraph_never_dropped": True,
        "connective_without_source": "ALLOWED",
        "connective_new_claim": "SEMANTIC_NOT_DETERMINISTIC",
        "invented_example": "SEMANTIC_NOT_DETERMINISTIC",
        "invented_illustration": "SEMANTIC_NOT_DETERMINISTIC",
        "invented_hypothetical": "SEMANTIC_NOT_DETERMINISTIC",
        "deferred_or_excluded_in_manuscript": "FAIL",
        "unknown_handle": "FAIL",
    }


def validate_chapter_candidate(
    candidate: ChapterCandidate,
    plan: EditorialPlan,
    source_map: SourceMap,
    chapter: EditorialChapter,
    *,
    language: str,
    allowed_handles: Iterable[str] | None = None,
) -> BookGenerationValidation:
    errors: list[str] = []
    warnings: list[str] = []
    leaked = scan_forbidden_book_structure(candidate.to_dict())
    if leaked:
        errors.extend(f"structure interdite : {name}" for name in leaked)

    if candidate.chapter_id != chapter.chapter_id:
        errors.append(
            f"chapter_id {candidate.chapter_id!r} ≠ {chapter.chapter_id!r}"
        )
    if candidate.title != chapter.working_title:
        errors.append("chapter title must match EditorialPlan working title")

    planned_ids = [section.section_id for section in chapter.sections]
    got_ids = [section.section_id for section in candidate.sections]
    if got_ids != planned_ids:
        missing = [item for item in planned_ids if item not in got_ids]
        extra = [item for item in got_ids if item not in planned_ids]
        if missing:
            errors.append(f"missing sections: {missing}")
        if extra:
            errors.append(f"extra sections: {extra}")
        if not missing and not extra and got_ids != planned_ids:
            errors.append(f"section order {got_ids} ≠ {planned_ids}")

    allowed = set(allowed_handles or ())
    if not allowed:
        allowed = _default_allowed(chapter, source_map)
    blocked = deferred_idea_ids(plan) | excluded_idea_ids(plan)
    known = _known_handles(source_map)

    represented: set[str] = set()
    for section, planned in zip(candidate.sections, chapter.sections):
        if section.section_id != planned.section_id:
            continue
        if section.title and section.title != planned.working_title:
            errors.append(
                f"{section.section_id} title must match EditorialPlan"
            )
        if not section.paragraphs:
            errors.append(f"{section.section_id} has no paragraphs")
        section_ideas = set(assigned_idea_ids_for_section(planned))
        for index, paragraph in enumerate(section.paragraphs, start=1):
            path = f"{section.section_id}.p{index}"
            _validate_paragraph(
                paragraph,
                path=path,
                allowed=allowed,
                blocked=blocked,
                known=known,
                section_ideas=section_ideas,
                source_map=source_map,
                errors=errors,
            )
            represented.update(idea_ids_from_paragraphs([paragraph]))

    required_ideas = set()
    for section in chapter.sections:
        required_ideas.update(assigned_idea_ids_for_section(section))
    missing_ideas = sorted(required_ideas - represented)
    extra_ideas = sorted(
        idea for idea in represented if idea not in required_ideas and idea not in allowed
    )
    leaked_blocked = sorted(represented & blocked)
    if missing_ideas:
        errors.append(f"missing planned IDEAs: {missing_ideas}")
    if extra_ideas:
        errors.append(f"unknown/unassigned IDEAs: {extra_ideas}")
    if leaked_blocked:
        errors.append(f"DEFERRED/EXCLUDED IDEAs entered manuscript: {leaked_blocked}")

    language_result = validate_manuscript_language(
        [paragraph.text for paragraph in candidate.to_book_chapter().all_paragraphs()],
        canonical_document_language=language,
    )
    if language_result["status"] == VALIDATION_FAIL:
        errors.append(language_result["reason"])
    elif language_result["status"] == VALIDATION_REVIEW:
        warnings.append(language_result["reason"])

    if errors:
        status = VALIDATION_FAIL
    elif warnings:
        status = VALIDATION_REVIEW
    else:
        status = VALIDATION_PASS
    return BookGenerationValidation(
        status=status, errors=tuple(errors), warnings=tuple(warnings)
    )


def _validate_paragraph(
    paragraph: BookParagraph,
    *,
    path: str,
    allowed: set[str],
    blocked: set[str],
    known: set[str],
    section_ideas: set[str],
    source_map: SourceMap,
    errors: list[str],
) -> None:
    if paragraph.kind not in {PARAGRAPH_KIND_SUBSTANTIVE, PARAGRAPH_KIND_CONNECTIVE}:
        errors.append(f"{path}: kind invalide {paragraph.kind!r}")
    normalized = (paragraph.text or "").strip()
    if not normalized:
        errors.append(f"{path}: empty text")
    if len(paragraph.text or "") > MAX_PARAGRAPH_CHARS:
        errors.append(f"{path}: pathological paragraph length")
    handles = tuple(paragraph.evidence_handles) + tuple(paragraph.uncertainty_refs)
    for handle in handles:
        kind = classify_handle(handle)
        if kind in {"CH", "SEC", "P"}:
            errors.append(f"{path}: provider must not invent canonical {kind} id {handle}")
        if handle not in known and kind != "UNKNOWN":
            errors.append(f"{path}: unknown source handle {handle}")
        if handle not in allowed:
            errors.append(f"{path}: handle not in generation-unit evidence {handle}")
        if handle in blocked:
            errors.append(f"{path}: blocked DEFERRED/EXCLUDED handle {handle}")
        if kind == "IDEA" and handle not in section_ideas:
            errors.append(f"{path}: cross-section IDEA leakage {handle}")
    if paragraph.is_connective:
        if len(paragraph.text or "") > MAX_CONNECTIVE_CHARS:
            errors.append(f"{path}: connective paragraph too long to remain non-substantive")
        return
    if len(normalized) < MIN_SUBSTANTIVE_CHARS:
        errors.append(f"{path}: substantive paragraph empty")
    if not handles:
        errors.append(f"{path}: substantive paragraph has no evidence handles")
        return
    resolved = paragraph.source_refs or resolve_src_for_handles(handles, source_map)
    if not resolved:
        errors.append(f"{path}: substantive paragraph does not resolve to SRC evidence")


def _default_allowed(chapter: EditorialChapter, source_map: SourceMap) -> set[str]:
    from app.book_generation.evidence import collect_unit_src_ids, related_support_ids

    idea_ids = [
        idea_id
        for section in chapter.sections
        for idea_id in section.idea_refs
    ]
    related = related_support_ids(source_map, idea_ids)
    example_ids = list(related["examples"])
    for section in chapter.sections:
        example_ids.extend(section.example_refs)
    reference_ids = list(section.reference_refs for section in chapter.sections)
    flat_refs = [item for group in reference_ids for item in group]
    unc_ids = [item for section in chapter.sections for item in section.uncertainty_refs]
    unc_ids.extend(related["uncertainties"])
    src = collect_unit_src_ids(
        source_map,
        idea_ids=idea_ids,
        extra_src=[src for section in chapter.sections for src in section.source_refs],
        example_ids=example_ids,
        reference_ids=flat_refs,
        uncertainty_ids=unc_ids,
    )
    return set(idea_ids) | set(example_ids) | set(flat_refs) | set(unc_ids) | set(src)


def _known_handles(source_map: SourceMap) -> set[str]:
    known = {idea.idea_id for idea in source_map.ideas}
    known.update(item.example_id for item in source_map.examples)
    known.update(item.reference_id for item in source_map.references)
    known.update(item.uncertainty_id for item in source_map.uncertainties)
    known.update(item.repetition_id for item in source_map.repetitions)
    known.update(source_map.all_source_refs())
    return known


def validate_book_precheck(
    book: Book,
    plan: EditorialPlan,
    source_map: SourceMap,
    *,
    language: str,
) -> BookGenerationValidation:
    errors: list[str] = []
    warnings: list[str] = []
    if book.title != plan.selected_title:
        errors.append("book title must equal EditorialPlan selected_title")
    if book.title_status != "working":
        errors.append("title must remain working / not final-approved")
    if book.front_matter:
        errors.append("front matter must not be generated in 4B.1")
    if book.back_matter:
        errors.append("back-cover / back matter must not be generated in 4B.1")
    planned_chapters = [chapter.chapter_id for chapter in plan.chapters]
    got_chapters = [chapter.chapter_id for chapter in book.chapters]
    if got_chapters != planned_chapters:
        errors.append(f"chapter set/order {got_chapters} ≠ {planned_chapters}")
    planned_sections = [section.section_id for section in plan.all_sections()]
    got_sections = [section.section_id for section in book.all_sections()]
    if got_sections != planned_sections:
        errors.append(f"section set/order {got_sections} ≠ {planned_sections}")
    paragraphs = book.all_paragraphs()
    ids = [paragraph.paragraph_id for paragraph in paragraphs]
    expected = [f"P{index:06d}" for index in range(1, len(paragraphs) + 1)]
    if ids != expected:
        errors.append("canonical paragraph IDs are not sequential in reading order")
    language_result = validate_manuscript_language(
        [paragraph.text for paragraph in paragraphs],
        canonical_document_language=language,
    )
    if language_result["status"] == VALIDATION_FAIL:
        errors.append(language_result["reason"])
    elif language_result["status"] == VALIDATION_REVIEW:
        warnings.append(language_result["reason"])
    if errors:
        status = VALIDATION_FAIL
    elif warnings:
        status = VALIDATION_REVIEW
    else:
        status = VALIDATION_PASS
    return BookGenerationValidation(
        status=status, errors=tuple(errors), warnings=tuple(warnings)
    )


def ensure_valid_chapter(
    candidate: ChapterCandidate,
    plan: EditorialPlan,
    source_map: SourceMap,
    chapter: EditorialChapter,
    *,
    language: str,
    allowed_handles: Iterable[str] | None = None,
) -> BookGenerationValidation:
    from app.book_generation.errors import BookGenerationValidationError

    result = validate_chapter_candidate(
        candidate,
        plan,
        source_map,
        chapter,
        language=language,
        allowed_handles=allowed_handles,
    )
    if result.status == VALIDATION_FAIL:
        raise BookGenerationValidationError(list(result.errors))
    return result
