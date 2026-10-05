"""Offline structural validation of the isolated CH012 candidate."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation.constants import (
    PARAGRAPH_KIND_CONNECTIVE,
    PARAGRAPH_KIND_SUBSTANTIVE,
)
from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.errors import BookGenerationTransportError
from app.book_generation.evidence import classify_handle
from app.book_generation.pipeline import assign_paragraph_ids, materialize_chapter
from app.book_generation.transport import decode_transport
from app.book_generation.writer import candidate_sha256
from app.book_generation_4b217.constants import (
    EXPECTED_IDEA_COUNT,
    EXPECTED_SECTION_IDS,
    EXPECTED_UNCERTAINTY_ID,
    PHASE,
    TARGET_CHAPTER_ID,
    VALIDATOR_VERSION,
)
from app.editorial_planning.models import EditorialChapter, EditorialPlan
from app.source_analysis.models import SourceMap


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def assign_candidate_paragraph_ids(candidate) -> Any:
    assigned = assign_paragraph_ids([candidate.to_book_chapter()])[0]
    from app.book_generation.models import ChapterCandidate

    return ChapterCandidate(
        chapter_id=candidate.chapter_id,
        title=candidate.title,
        sections=assigned.sections,
        idea_refs=candidate.idea_refs,
        source_refs=candidate.source_refs,
        provider_raw_sha256=candidate.provider_raw_sha256,
        cache_signature=candidate.cache_signature,
    )


def interpret_response(
    raw_parsed: Mapping[str, Any] | None,
    *,
    plan: EditorialPlan,
    source_map: SourceMap,
    chapter: EditorialChapter,
    language: str,
    allowed_handles: list[str] | None,
    provider_raw_sha256: str = "",
) -> dict[str, Any]:
    json_valid = isinstance(raw_parsed, Mapping)
    transport = None
    transport_errors: list[str] = []
    if json_valid:
        try:
            transport = decode_transport(raw_parsed)
        except BookGenerationTransportError as exc:
            transport_errors = list(exc.errors)
    candidate = None
    validation = None
    candidate_hash = None
    if transport is not None:
        candidate, validation, candidate_hash = materialize_chapter(
            transport,
            plan,
            source_map,
            chapter,
            language=language,
            allowed_handles=allowed_handles,
            provider_raw_sha256=provider_raw_sha256,
        )
        candidate = assign_candidate_paragraph_ids(candidate)
        candidate_hash = candidate_sha256(candidate.to_dict())
    return {
        "json_valid": json_valid,
        "transport_ok": transport is not None,
        "transport_errors": transport_errors,
        "candidate": candidate,
        "validation": validation.to_dict() if validation is not None else None,
        "candidate_sha256": candidate_hash,
    }


def structural_validation(
    *,
    interpreted: Mapping[str, Any],
    plan: EditorialPlan,
    chapter: EditorialChapter,
    allowed_handles: list[str],
    other_chapter_ids: list[str],
) -> dict[str, Any]:
    candidate = interpreted.get("candidate")
    validation = interpreted.get("validation") or {}
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    checks["json_valid"] = bool(interpreted.get("json_valid"))
    if not checks["json_valid"]:
        errors.append("provider JSON is not a valid object")
    checks["chapter_contract_valid"] = (
        bool(interpreted.get("transport_ok"))
        and str(validation.get("status") or "") != "FAIL"
    )
    if validation.get("errors"):
        errors.extend(list(validation.get("errors") or []))
    if validation.get("warnings"):
        warnings.extend(list(validation.get("warnings") or []))

    chapter_id = getattr(candidate, "chapter_id", None)
    checks["chapter_id_correct"] = chapter_id == TARGET_CHAPTER_ID
    if not checks["chapter_id_correct"]:
        errors.append(f"chapter_id {chapter_id!r} ≠ {TARGET_CHAPTER_ID}")

    section_ids = []
    paragraph_ids: list[str] = []
    empty_paragraphs = 0
    idea_refs: list[str] = []
    src_refs: list[str] = []
    unknown_ids: list[str] = []
    unc_refs: list[str] = []
    prose_chunks: list[str] = []
    if candidate is not None:
        section_ids = [section.section_id for section in candidate.sections]
        for section in candidate.sections:
            for paragraph in section.paragraphs:
                if paragraph.paragraph_id:
                    paragraph_ids.append(paragraph.paragraph_id)
                if not str(paragraph.text or "").strip():
                    empty_paragraphs += 1
                idea_refs.extend(paragraph.idea_refs)
                src_refs.extend(paragraph.source_refs)
                unc_refs.extend(paragraph.uncertainty_refs)
                prose_chunks.append(paragraph.text)
                for handle in list(paragraph.evidence_handles) + list(
                    paragraph.uncertainty_refs
                ):
                    if handle not in set(allowed_handles):
                        unknown_ids.append(handle)

    checks["sections_expected"] = list(EXPECTED_SECTION_IDS)
    checks["sections_generated"] = section_ids
    checks["sections_match"] = tuple(section_ids) == EXPECTED_SECTION_IDS
    if not checks["sections_match"]:
        errors.append(f"sections {section_ids} ≠ {list(EXPECTED_SECTION_IDS)}")

    checks["paragraph_ids"] = paragraph_ids
    checks["paragraph_ids_unique"] = len(paragraph_ids) == len(set(paragraph_ids))
    if paragraph_ids and not checks["paragraph_ids_unique"]:
        errors.append("paragraph IDs are not unique")
    checks["empty_paragraphs"] = empty_paragraphs
    if empty_paragraphs:
        errors.append(f"{empty_paragraphs} empty paragraph(s)")

    planned_ideas = list(assigned_idea_ids_for_chapter(chapter))
    referenced = sorted(set(idea_refs))
    checks["ideas_expected"] = planned_ideas
    checks["ideas_referenced"] = referenced
    checks["ideas_expected_count"] = EXPECTED_IDEA_COUNT
    checks["ideas_referenced_count"] = len(referenced)
    missing_ideas = [idea_id for idea_id in planned_ideas if idea_id not in set(referenced)]
    checks["ideas_missing_from_metadata"] = missing_ideas
    if missing_ideas:
        errors.append("ideas not referenced: " + ",".join(missing_ideas))

    allowed = set(allowed_handles)
    checks["unknown_identifiers"] = sorted(set(unknown_ids))
    if unknown_ids:
        errors.append("unknown identifiers: " + ",".join(sorted(set(unknown_ids))))

    invalid_src = [src for src in src_refs if classify_handle(src) != "SRC" or src not in allowed]
    checks["invalid_src"] = sorted(set(invalid_src))
    if invalid_src:
        errors.append("invalid SRC references: " + ",".join(sorted(set(invalid_src))))

    checks["unc029_present"] = EXPECTED_UNCERTAINTY_ID in set(unc_refs) or any(
        EXPECTED_UNCERTAINTY_ID in text for text in prose_chunks
    )
    checks["unc029_resolved_arbitrarily"] = False
    if EXPECTED_UNCERTAINTY_ID not in set(unc_refs):
        warnings.append("UNC029 is not cited on a paragraph uncertainty field")

    leaked = [
        other
        for other in other_chapter_ids
        if any(other in text for text in prose_chunks)
    ]
    checks["other_chapter_contamination"] = leaked
    if leaked:
        errors.append("other chapter identifiers in prose: " + ",".join(leaked))

    checks["paragraphs_generated"] = len(paragraph_ids)
    checks["semantic_fidelity_validated"] = False
    ok = not errors
    return {
        "phase": PHASE,
        "validator_version": VALIDATOR_VERSION,
        "status": _status(ok),
        "json_valid": checks["json_valid"],
        "chapter_contract_valid": checks["chapter_contract_valid"],
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "semantic_fidelity_validated": False,
        "secrets_included": False,
    }


def render_chapter_markdown(candidate, chapter: EditorialChapter) -> str:
    titles = {section.section_id: section.working_title for section in chapter.sections}
    lines = [f"# {chapter.working_title}", ""]
    if candidate is None:
        return "# Prayer Corrected\n\n_No chapter candidate was produced._\n"
    for section in candidate.sections:
        title = titles.get(section.section_id) or section.title or section.section_id
        lines.append(f"## {title}")
        lines.append("")
        for paragraph in section.paragraphs:
            text = str(paragraph.text or "").strip()
            if text:
                lines.append(text)
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "assign_candidate_paragraph_ids",
    "interpret_response",
    "render_chapter_markdown",
    "structural_validation",
]
