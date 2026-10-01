"""Transport → chapter candidate. Canonical P IDs are not assigned here."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation.constants import (
    PARAGRAPH_KIND_CONNECTIVE,
    PARAGRAPH_KIND_SUBSTANTIVE,
    TRANSPORT_KIND_CONNECTIVE,
)
from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.evidence import classify_handle, resolve_src_for_handles
from app.book_generation.models import BookParagraph, BookSection, ChapterCandidate
from app.book_generation.transport import decode_transport
from app.editorial_planning.models import EditorialChapter
from app.source_analysis.models import SourceMap


def _kind(token: str) -> str:
    if token == TRANSPORT_KIND_CONNECTIVE:
        return PARAGRAPH_KIND_CONNECTIVE
    return PARAGRAPH_KIND_SUBSTANTIVE


def _as_handles(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def reconstruct_chapter_candidate(
    transport: Mapping[str, Any],
    chapter: EditorialChapter,
    source_map: SourceMap,
    *,
    provider_raw_sha256: str = "",
    cache_signature: str = "",
) -> ChapterCandidate:
    decoded = decode_transport(transport)
    titles = {section.section_id: section.working_title for section in chapter.sections}
    planned = {section.section_id: section for section in chapter.sections}
    sections: list[BookSection] = []
    all_src: dict[str, None] = {}
    for row in decoded.get("sections") or []:
        section_id = str(row.get("sid") or "").strip()
        planned_section = planned.get(section_id)
        paragraphs: list[BookParagraph] = []
        for para in row.get("paras") or []:
            if not isinstance(para, Mapping):
                continue
            handles = _as_handles(para.get("e"))
            unc = _as_handles(para.get("u"))
            combined = handles + unc
            idea_refs = tuple(h for h in combined if classify_handle(h) == "IDEA")
            example_refs = tuple(h for h in combined if classify_handle(h) == "EX")
            reference_refs = tuple(h for h in combined if classify_handle(h) == "REF")
            uncertainty_refs = tuple(h for h in combined if classify_handle(h) == "UNC")
            direct_src = tuple(h for h in combined if classify_handle(h) == "SRC")
            resolved = resolve_src_for_handles(combined, source_map)
            source_refs = tuple(dict.fromkeys(direct_src + resolved))
            for src in source_refs:
                all_src.setdefault(src, None)
            paragraphs.append(
                BookParagraph(
                    text=str(para.get("t") or "").strip(),
                    kind=_kind(str(para.get("k") or "")),
                    evidence_handles=handles,
                    source_refs=source_refs,
                    idea_refs=idea_refs,
                    example_refs=example_refs,
                    reference_refs=reference_refs,
                    uncertainty_refs=uncertainty_refs,
                    provider_handle=str(para.get("h") or "").strip(),
                )
            )
        section_ideas = planned_section.idea_refs if planned_section else ()
        sections.append(
            BookSection(
                section_id=section_id,
                title=titles.get(section_id, ""),
                paragraphs=tuple(paragraphs),
                idea_refs=section_ideas,
                source_refs=tuple(
                    dict.fromkeys(
                        src
                        for paragraph in paragraphs
                        for src in paragraph.source_refs
                    )
                ),
            )
        )
    return ChapterCandidate(
        chapter_id=chapter.chapter_id,
        title=chapter.working_title,
        sections=tuple(sections),
        idea_refs=assigned_idea_ids_for_chapter(chapter),
        source_refs=tuple(all_src),
        provider_raw_sha256=provider_raw_sha256,
        cache_signature=cache_signature,
    )
