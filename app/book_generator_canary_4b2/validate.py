"""Offline decode / reconstruct / validate from a persisted response. 0 network."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.book_generation.constants import (
    PARAGRAPH_KIND_CONNECTIVE,
    PARAGRAPH_KIND_SUBSTANTIVE,
)
from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.errors import BookGenerationTransportError
from app.book_generation.evidence import classify_handle
from app.book_generation.language import validate_manuscript_language
from app.book_generation.pipeline import materialize_chapter
from app.book_generation.reconstruct import reconstruct_chapter_candidate
from app.book_generation.transport import decode_transport
from app.book_generation.writer import candidate_sha256
from app.book_generator_canary_4b2.constants import TARGET_CHAPTER_ID
from app.editorial_planning.models import EditorialChapter, EditorialPlan
from app.source_analysis.models import SourceMap

_HANDLE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def validate_temporary_handles(
    transport: Mapping[str, Any],
    *,
    allowed: set[str],
    planned_sections: list[str],
) -> dict[str, Any]:
    errors: list[str] = []
    unknown = 0
    malformed = 0
    paragraph_handles: list[str] = []
    seen_p: set[str] = set()
    section_ids: list[str] = []
    for section in transport.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        sid = str(section.get("sid") or "").strip()
        section_ids.append(sid)
        if sid not in planned_sections:
            unknown += 1
            errors.append(f"unknown section handle {sid}")
        for para in section.get("paras") or []:
            if not isinstance(para, Mapping):
                continue
            handle = str(para.get("h") or "").strip()
            if handle:
                if not _HANDLE.match(handle):
                    malformed += 1
                    errors.append(f"paragraph handle malformed: {handle}")
                elif handle in seen_p:
                    errors.append(f"paragraph handle duplicate: {handle}")
                else:
                    seen_p.add(handle)
                    paragraph_handles.append(handle)
                kind = classify_handle(handle)
                if kind in {"CH", "SEC", "P", "IDEA", "SRC", "EX", "REF", "UNC"}:
                    errors.append(f"paragraph handle must not be canonical {kind}: {handle}")
            for key in ("e", "u"):
                values = para.get(key) or []
                if not isinstance(values, list):
                    continue
                for item in values:
                    token = str(item).strip()
                    if not token:
                        continue
                    if token not in allowed:
                        unknown += 1
                        errors.append(f"unknown evidence handle {token}")
    return {
        "status": _status(not errors),
        "errors": errors,
        "unknown": unknown,
        "malformed": malformed,
        "paragraph_handles": paragraph_handles,
        "section_ids": section_ids,
    }


def interpret_production_response(
    raw_parsed: Mapping[str, Any] | None,
    *,
    plan: EditorialPlan,
    source_map: SourceMap,
    chapter: EditorialChapter,
    language: str,
    allowed_handles: list[str] | None,
    raw_text: str | None = None,
    provider_raw_sha256: str = "",
) -> dict[str, Any]:
    structured_parse = "PASS" if isinstance(raw_parsed, Mapping) else "FAIL"
    transport = None
    transport_status = "FAIL"
    transport_errors: list[str] = []
    if isinstance(raw_parsed, Mapping):
        try:
            transport = decode_transport(raw_parsed)
            transport_status = "PASS"
        except BookGenerationTransportError as exc:
            transport_errors = list(exc.errors)
            transport_status = "FAIL"

    handles = validate_temporary_handles(
        transport or {},
        allowed=set(allowed_handles or []),
        planned_sections=[section.section_id for section in chapter.sections],
    )
    reconstruction = "FAIL"
    candidate = None
    candidate_hash = None
    candidate_bytes = 0
    candidate_chars = 0
    validation = None
    replay = "FAIL"
    replay_hashes: list[str] = []
    if transport is not None and transport_status == "PASS":
        first, validation, first_hash = materialize_chapter(
            transport,
            plan,
            source_map,
            chapter,
            language=language,
            allowed_handles=allowed_handles,
            provider_raw_sha256=provider_raw_sha256,
        )
        second = reconstruct_chapter_candidate(
            transport,
            chapter,
            source_map,
            provider_raw_sha256=provider_raw_sha256,
        )
        third = reconstruct_chapter_candidate(
            transport,
            chapter,
            source_map,
            provider_raw_sha256=provider_raw_sha256,
        )
        second_hash = candidate_sha256(second.to_dict())
        third_hash = candidate_sha256(third.to_dict())
        reconstruction = "PASS"
        candidate = first
        candidate_hash = first_hash
        rendered = __import__("json").dumps(first.to_dict(), ensure_ascii=False, sort_keys=True)
        candidate_bytes = len(rendered.encode("utf-8"))
        candidate_chars = len(rendered)
        replay = _status(first_hash == second_hash == third_hash)
        replay_hashes = [first_hash, second_hash, third_hash]

    planned_sections = [section.section_id for section in chapter.sections]
    got_sections = [section.section_id for section in (candidate.sections if candidate else ())]
    missing_sections = [item for item in planned_sections if item not in got_sections]
    extra_sections = [item for item in got_sections if item not in planned_sections]
    section_order = got_sections == planned_sections
    section_titles_ok = True
    if candidate is not None:
        titles = {section.section_id: section.working_title for section in chapter.sections}
        for section in candidate.sections:
            if section.title != titles.get(section.section_id, section.title):
                section_titles_ok = False

    planned_ideas = list(assigned_idea_ids_for_chapter(chapter))
    represented: set[str] = set()
    unknown_ideas: list[str] = []
    unknown_src: list[str] = []
    unsourced = 0
    connective = 0
    paragraphs = []
    if candidate is not None:
        for section in candidate.sections:
            for paragraph in section.paragraphs:
                paragraphs.append(paragraph)
                represented.update(paragraph.idea_refs)
                for handle in paragraph.idea_refs:
                    if handle not in planned_ideas:
                        unknown_ideas.append(handle)
                for src in paragraph.source_refs:
                    if classify_handle(src) == "SRC" and allowed_handles and src not in allowed_handles:
                        unknown_src.append(src)
                if paragraph.kind == PARAGRAPH_KIND_CONNECTIVE:
                    connective += 1
                elif paragraph.kind == PARAGRAPH_KIND_SUBSTANTIVE and not paragraph.source_refs:
                    unsourced += 1
    missing_ideas = [idea_id for idea_id in planned_ideas if idea_id not in represented]
    language_result = {"status": "n/a"}
    if paragraphs:
        language_result = validate_manuscript_language(
            [paragraph.text for paragraph in paragraphs],
            canonical_document_language=language,
        )

    validator_status = (validation.to_dict() if validation else {"status": "FAIL"})
    chapter_ok = candidate is not None and candidate.chapter_id == TARGET_CHAPTER_ID
    words = 0
    if paragraphs:
        words = len(" ".join(paragraph.text for paragraph in paragraphs).split())

    return {
        "structured_parse": structured_parse,
        "transport_decoder": transport_status,
        "transport_errors": transport_errors,
        "handle_validation": handles,
        "canonical_reconstruction": reconstruction,
        "deterministic_replay": replay,
        "replay_sha256": replay_hashes,
        "candidate": candidate.to_dict() if candidate else None,
        "candidate_sha256": candidate_hash,
        "candidate_bytes": candidate_bytes,
        "candidate_chars": candidate_chars,
        "chapter_identity": _status(chapter_ok),
        "section_coverage": _status(not missing_sections and not extra_sections and bool(got_sections)),
        "section_order": _status(section_order),
        "section_titles": _status(section_titles_ok),
        "missing_sections": missing_sections,
        "extra_sections": extra_sections,
        "expected_sections": planned_sections,
        "got_sections": got_sections,
        "idea_coverage": _status(not missing_ideas),
        "silent_idea_omissions": len(missing_ideas),
        "missing_idea_ids": missing_ideas,
        "unknown_idea_refs": len(unknown_ideas),
        "unknown_idea_ids": unknown_ideas,
        "unknown_src_refs": len(set(unknown_src)),
        "unknown_src_ids": sorted(set(unknown_src)),
        "unsourced_substantive_paragraphs": unsourced,
        "connective_paragraphs": connective,
        "paragraph_count": len(paragraphs),
        "word_count": words,
        "language": language_result,
        "local_validator": validator_status,
        "raw_text_chars": len(raw_text or ""),
        "chapter_id": chapter.chapter_id if chapter else None,
        "transport": transport,
    }


__all__ = ["interpret_production_response", "validate_temporary_handles"]
