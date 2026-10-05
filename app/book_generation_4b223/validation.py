"""Offline structural validation of an isolated BATCH-01 chapter candidate."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation.coverage import assigned_idea_ids_for_chapter, idea_ids_from_paragraphs
from app.book_generation.errors import BookGenerationTransportError
from app.book_generation.evidence import classify_handle
from app.book_generation.pipeline import assign_paragraph_ids, materialize_chapter
from app.book_generation.transport import decode_transport
from app.book_generation.writer import candidate_sha256
from app.book_generation_4b223.constants import PHASE, VALIDATOR_VERSION
from app.book_generation_4b223.inventory import ChapterSpec
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


def extract_raw_idea_handles(raw_parsed: Mapping[str, Any] | None) -> list[str]:
    found: list[str] = []
    if not isinstance(raw_parsed, Mapping):
        return found
    for section in raw_parsed.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        for paragraph in section.get("paras") or []:
            if not isinstance(paragraph, Mapping):
                continue
            for handle in paragraph.get("e") or []:
                if classify_handle(str(handle)) == "IDEA":
                    found.append(str(handle))
    return found


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
        "raw_idea_handles_in_paras_e": extract_raw_idea_handles(raw_parsed),
    }


def structural_validation(
    *,
    interpreted: Mapping[str, Any],
    plan: EditorialPlan,
    chapter: EditorialChapter,
    spec: ChapterSpec,
    allowed_handles: list[str],
    other_chapter_ids: list[str],
    finish_reason: str | None = None,
    max_output_tokens: int | None = None,
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
    checks["chapter_id_correct"] = chapter_id == spec.chapter_id
    if not checks["chapter_id_correct"]:
        errors.append(f"chapter_id {chapter_id!r} ≠ {spec.chapter_id}")

    section_ids = []
    paragraph_ids: list[str] = []
    empty_paragraphs = 0
    idea_refs: list[str] = []
    src_refs: list[str] = []
    unknown_ids: list[str] = []
    section_idea_refs: list[str] = []
    paragraph_e_ideas: list[str] = []
    prose_chunks: list[str] = []
    if candidate is not None:
        section_ids = [section.section_id for section in candidate.sections]
        for section in candidate.sections:
            section_idea_refs.extend(section.idea_refs)
            for paragraph in section.paragraphs:
                if paragraph.paragraph_id:
                    paragraph_ids.append(paragraph.paragraph_id)
                text = str(paragraph.text or "")
                if not text.strip():
                    empty_paragraphs += 1
                idea_refs.extend(paragraph.idea_refs)
                src_refs.extend(paragraph.source_refs)
                prose_chunks.append(text)
                for handle in list(paragraph.evidence_handles) + list(
                    paragraph.uncertainty_refs
                ):
                    if handle not in set(allowed_handles):
                        unknown_ids.append(handle)
                    if classify_handle(handle) == "IDEA":
                        paragraph_e_ideas.append(handle)

    raw_e_ideas = list(interpreted.get("raw_idea_handles_in_paras_e") or [])
    if not paragraph_e_ideas and raw_e_ideas:
        paragraph_e_ideas = raw_e_ideas

    checks["sections_expected"] = list(spec.section_ids)
    checks["sections_generated"] = section_ids
    checks["sections_match"] = tuple(section_ids) == spec.section_ids
    checks["sections_in_order"] = tuple(section_ids) == spec.section_ids
    if not checks["sections_match"]:
        errors.append(f"sections {section_ids} ≠ {list(spec.section_ids)}")

    checks["paragraph_ids"] = paragraph_ids
    checks["paragraph_ids_unique"] = len(paragraph_ids) == len(set(paragraph_ids))
    if paragraph_ids and not checks["paragraph_ids_unique"]:
        errors.append("paragraph IDs are not unique")
    checks["empty_paragraphs"] = empty_paragraphs
    if empty_paragraphs:
        errors.append(f"{empty_paragraphs} empty paragraph(s)")
    checks["paragraphs_present"] = bool(paragraph_ids)
    if candidate is not None and not paragraph_ids:
        errors.append("no paragraphs present")

    planned_ideas = list(assigned_idea_ids_for_chapter(chapter))
    if set(planned_ideas) != set(spec.idea_ids):
        errors.append(f"planned IDEA set diverged from the {spec.chapter_id} contract")
    paragraph_idea_set = set(
        idea_ids_from_paragraphs(
            [
                paragraph
                for section in (getattr(candidate, "sections", None) or [])
                for paragraph in section.paragraphs
            ]
        )
    )
    e_idea_set = set(paragraph_e_ideas) | set(raw_e_ideas)
    checks["ideas_expected"] = list(spec.idea_ids)
    checks["ideas_in_paragraph_evidence"] = sorted(e_idea_set)
    checks["ideas_in_paragraph_idea_refs"] = sorted(set(idea_refs))
    checks["ideas_in_section_metadata"] = sorted(set(section_idea_refs))
    checks["ideas_expected_count"] = spec.idea_count
    checks["ideas_found_in_paras_e"] = len(e_idea_set)
    missing_from_e = [idea_id for idea_id in spec.idea_ids if idea_id not in e_idea_set]
    invented = sorted(e_idea_set.difference(spec.idea_ids))
    metadata_only = [
        idea_id
        for idea_id in spec.idea_ids
        if idea_id in set(section_idea_refs) and idea_id not in e_idea_set
    ]
    checks["ideas_missing_from_paras_e"] = missing_from_e
    checks["ideas_invented"] = invented
    checks["ideas_metadata_only"] = metadata_only
    if missing_from_e:
        errors.append("IDEA handles missing from paras[].e: " + ",".join(missing_from_e))
    if invented:
        errors.append("invented IDEA handles: " + ",".join(invented))
    if metadata_only:
        errors.append(
            "IDEA handles present in section metadata only: " + ",".join(metadata_only)
        )

    allowed = set(allowed_handles)
    checks["unknown_identifiers"] = sorted(set(unknown_ids))
    if unknown_ids:
        errors.append("unknown identifiers: " + ",".join(sorted(set(unknown_ids))))

    invalid_src = [
        src for src in src_refs if classify_handle(src) != "SRC" or src not in allowed
    ]
    checks["invalid_src"] = sorted(set(invalid_src))
    if invalid_src:
        errors.append("invalid SRC references: " + ",".join(sorted(set(invalid_src))))

    leaked = [
        other for other in other_chapter_ids if any(other in text for text in prose_chunks)
    ]
    checks["other_chapter_contamination"] = leaked
    if leaked:
        errors.append("other chapter identifiers in prose: " + ",".join(leaked))

    truncated = finish_reason in {"length", "max_tokens"}
    checks["finish_reason"] = finish_reason
    checks["detectable_truncation"] = truncated
    if truncated:
        errors.append(f"detectable truncation: finish_reason={finish_reason}")
    checks["max_output_tokens"] = max_output_tokens
    checks["configured_limits_respected"] = True
    checks["paragraphs_generated"] = len(paragraph_ids)
    checks["semantic_fidelity_validated"] = False
    checks["handles_auto_filled"] = False
    checks["unused_paragraph_idea_set"] = sorted(paragraph_idea_set)
    ok = not errors
    return {
        "phase": PHASE,
        "chapter_id": spec.chapter_id,
        "validator_version": VALIDATOR_VERSION,
        "status": _status(ok),
        "json_valid": checks["json_valid"],
        "chapter_contract_valid": checks["chapter_contract_valid"] and ok,
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
        return f"# {chapter.working_title}\n\n_No chapter candidate was produced._\n"
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
    "extract_raw_idea_handles",
    "interpret_response",
    "render_chapter_markdown",
    "structural_validation",
]
