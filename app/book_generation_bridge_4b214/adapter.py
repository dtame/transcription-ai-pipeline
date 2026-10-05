"""Adapt real Book Generator objects to the 4B.2.13 Semantic Gate envelope.

Never invent SRC. Never treat synthetic handles as real evidence.
Missing indispensable fields fail closed.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_PROMPT_VERSION,
    PARAGRAPH_KIND_SUBSTANTIVE,
    PARAGRAPH_KINDS,
)
from app.book_generation.evidence import classify_handle
from app.book_generation.models import (
    BookChapter,
    BookIdentity,
    BookParagraph,
    BookSection,
    ChapterCandidate,
)
from app.book_generation_bridge_4b214.constants import (
    ADAPTER_VERSION,
    DECISION_BLOCK,
    INTEGRATION_CONTRACT_VERSION,
    PHASE,
    PREPARATION_ALGORITHM_VERSION,
    PROMPT_VERSION_202_CANDIDATE,
    SYNTHETIC_PREFIX,
    TRANSPORT_VERSION_20_CANDIDATE,
    VALIDATOR_IMPLEMENTATION_VERSION,
)
from app.book_generation_integration_4b213.evidence import evidence_bundle_hash
from app.editorial_planning.models import EditorialPlan
from app.file_utils import content_hash
from app.source_analysis.models import SourceMap


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    return {}


def _text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        item = value.strip()
        return (item,) if item else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def source_map_handle_index(source_map: SourceMap) -> dict[str, str]:
    index: dict[str, str] = {}
    for idea in source_map.ideas:
        index[idea.idea_id] = "IDEA"
        for ref in idea.source_refs:
            index[ref] = classify_handle(ref) or "SRC"
    for example in source_map.examples:
        index[example.example_id] = "EX"
        for ref in example.source_refs:
            index[ref] = classify_handle(ref) or "SRC"
    for reference in source_map.references:
        index[reference.reference_id] = "REF"
        for ref in reference.source_refs:
            index[ref] = classify_handle(ref) or "SRC"
    for item in source_map.uncertainties:
        index[item.uncertainty_id] = "UNC"
        for ref in item.source_refs:
            index[ref] = classify_handle(ref) or "SRC"
    for item in source_map.repetitions:
        index[item.repetition_id] = "REP"
        for ref in item.source_refs:
            index[ref] = classify_handle(ref) or "SRC"
    for topic in source_map.topics:
        index[topic.topic_id] = "TOP"
    return index


def _plan_chapter(plan: EditorialPlan, chapter_id: str):
    for chapter in plan.chapters:
        if chapter.chapter_id == chapter_id:
            return chapter
    return None


def adapt_paragraph(
    paragraph: BookParagraph | Mapping[str, Any],
    *,
    chapter_id: str,
    section_id: str,
    allowed_handles: Sequence[str] | None = None,
    source_index: Mapping[str, str] | None = None,
    synthetic: bool = False,
) -> dict[str, Any]:
    payload = _as_mapping(paragraph)
    pid = str(payload.get("paragraph_id") or "").strip()
    kind = str(payload.get("kind") or "").strip()
    text = str(payload.get("text") or "")
    handles = list(_text_tuple(payload.get("evidence_handles")))
    source_refs = list(_text_tuple(payload.get("source_refs")))
    idea_refs = list(_text_tuple(payload.get("idea_refs")))
    errors: list[str] = []
    gaps: list[str] = []
    if not chapter_id:
        errors.append("chapter_id:missing")
    if not section_id:
        errors.append("section_id:missing")
    if not pid:
        errors.append("paragraph_id:missing")
        gaps.append(
            "Production ChapterCandidate paragraphs may have empty paragraph_id; "
            "canonical P000001 IDs are assigned only by pipeline.assign_paragraph_ids "
            "during assemble_book, which this phase does not run."
        )
    if kind not in PARAGRAPH_KINDS:
        errors.append(f"kind:invalid:{kind!r}")
    if not text.strip():
        errors.append("text:empty")
    if kind == PARAGRAPH_KIND_SUBSTANTIVE and not handles:
        errors.append("evidence_handles:missing_required_evidence")
    allowed = {str(item).strip() for item in (allowed_handles or ()) if str(item).strip()}
    for handle in handles:
        if allowed and handle not in allowed:
            errors.append(f"evidence_handles:unknown:{handle}")
        if source_index is not None and handle not in source_index:
            if not (synthetic and handle.startswith(SYNTHETIC_PREFIX)):
                errors.append(f"evidence_handles:not_in_source_map:{handle}")
        if synthetic and not handle.startswith(SYNTHETIC_PREFIX):
            errors.append(f"evidence_handles:real_handle_on_synthetic:{handle}")
        if not synthetic and handle.startswith(SYNTHETIC_PREFIX):
            errors.append(f"evidence_handles:synthetic_handle_as_real_proof:{handle}")
    for ref in source_refs + idea_refs:
        if source_index is not None and ref not in source_index:
            if not (synthetic and ref.startswith(SYNTHETIC_PREFIX)):
                errors.append(f"source_or_idea_ref:not_in_source_map:{ref}")
    ok = not errors
    return {
        "ok": ok,
        "status": "PASS" if ok else DECISION_BLOCK,
        "errors": errors,
        "gaps": gaps,
        "chapter_id": chapter_id,
        "section_id": section_id,
        "paragraph_id": pid,
        "text": text,
        "kind": kind,
        "evidence_handles": handles,
        "source_refs": source_refs,
        "idea_refs": idea_refs,
        "example_refs": list(_text_tuple(payload.get("example_refs"))),
        "reference_refs": list(_text_tuple(payload.get("reference_refs"))),
        "uncertainty_refs": list(_text_tuple(payload.get("uncertainty_refs"))),
        "does_not_invent_src": True,
        "does_not_use_synthetic_as_real_proof": True,
    }


def adapt_chapter_candidate(
    candidate: ChapterCandidate | BookChapter | Mapping[str, Any],
    *,
    plan: EditorialPlan | None = None,
    source_map: SourceMap | None = None,
    identity: BookIdentity | Mapping[str, Any] | None = None,
    allowed_handles: Sequence[str] | None = None,
    synthetic: bool | None = None,
) -> dict[str, Any]:
    payload = _as_mapping(candidate)
    chapter_id = str(payload.get("chapter_id") or "").strip()
    title = str(payload.get("title") or "")
    identity_payload = _as_mapping(identity) if identity is not None else {}
    source_map_sha256 = str(
        payload.get("source_map_sha256")
        or identity_payload.get("source_map_sha256")
        or ""
    ).strip()
    editorial_plan_sha256 = str(
        payload.get("editorial_plan_sha256")
        or identity_payload.get("editorial_plan_sha256")
        or ""
    ).strip()
    transcript_sha256 = str(
        payload.get("transcript_sha256")
        or identity_payload.get("transcript_sha256")
        or ""
    ).strip()
    is_synthetic = (
        bool(payload.get("synthetic")) if synthetic is None else bool(synthetic)
    )
    errors: list[str] = []
    gaps: list[str] = []
    if not chapter_id:
        errors.append("chapter_id:missing")
    plan_chapter = _plan_chapter(plan, chapter_id) if plan is not None else None
    if plan is not None and plan_chapter is None:
        errors.append(f"chapter_id:not_in_editorial_plan:{chapter_id}")
    plan_section_ids = {
        section.section_id for section in (plan_chapter.sections if plan_chapter else ())
    }
    source_index = source_map_handle_index(source_map) if source_map is not None else None
    allowed = list(allowed_handles or payload.get("allowed_evidence_handles") or [])
    if plan_chapter is not None and not allowed:
        allowed = list(
            dict.fromkeys(
                list(plan_chapter.idea_refs)
                + list(plan_chapter.source_refs)
                + [
                    ref
                    for section in plan_chapter.sections
                    for ref in list(section.idea_refs) + list(section.source_refs)
                ]
            )
        )
    sections_out: list[dict[str, Any]] = []
    paragraphs_out: list[dict[str, Any]] = []
    raw_sections = payload.get("sections") or []
    if not raw_sections:
        errors.append("sections:missing")
        gaps.append(
            "Generated paragraphs do not exist until Book Generator materialize_chapter. "
            "EditorialPlan has sections, not manuscript paragraphs."
        )
    for section in raw_sections:
        section_payload = _as_mapping(section)
        section_id = str(section_payload.get("section_id") or "").strip()
        if not section_id:
            errors.append("section_id:missing")
        elif plan is not None and plan_section_ids and section_id not in plan_section_ids:
            errors.append(f"section_id:not_in_editorial_plan:{section_id}")
        paras = section_payload.get("paragraphs") or []
        adapted_paras: list[dict[str, Any]] = []
        if not paras:
            errors.append(f"{section_id or 'section'}:paragraphs:missing")
            gaps.append("Paragraph count is unknown before generation.")
        for para in paras:
            adapted = adapt_paragraph(
                para,
                chapter_id=chapter_id,
                section_id=section_id,
                allowed_handles=allowed,
                source_index=source_index,
                synthetic=is_synthetic,
            )
            if not adapted["ok"]:
                errors.extend(
                    f"{adapted.get('paragraph_id') or section_id}:{item}"
                    for item in adapted["errors"]
                )
                gaps.extend(adapted.get("gaps") or [])
            adapted_paras.append(adapted)
            paragraphs_out.append(adapted)
        sections_out.append(
            {
                "section_id": section_id,
                "title": section_payload.get("title") or section_payload.get("working_title") or "",
                "paragraphs": adapted_paras,
                "idea_refs": list(_text_tuple(section_payload.get("idea_refs"))),
                "source_refs": list(_text_tuple(section_payload.get("source_refs"))),
            }
        )
    missing_versions = []
    for field, supplied in (
        ("semantic_contract_version", PROMPT_VERSION_202_CANDIDATE),
        ("semantic_transport_version", TRANSPORT_VERSION_20_CANDIDATE),
        ("preparation_algorithm_version", PREPARATION_ALGORITHM_VERSION),
        ("validator_implementation_version", VALIDATOR_IMPLEMENTATION_VERSION),
        ("integration_contract_version", INTEGRATION_CONTRACT_VERSION),
        ("adapter_version", ADAPTER_VERSION),
    ):
        if not payload.get(field):
            missing_versions.append(field)
        _ = supplied
    if missing_versions:
        gaps.append(
            "Production ChapterCandidate does not store "
            + ", ".join(missing_versions)
            + ". The isolated bridge envelope supplies them and does not write them into production cache."
        )
    if not source_map_sha256:
        errors.append("source_map_sha256:missing")
    if not editorial_plan_sha256:
        errors.append("editorial_plan_sha256:missing")
    ok = not errors
    all_handles = [
        handle
        for para in paragraphs_out
        for handle in para.get("evidence_handles") or []
    ]
    text_hash = content_hash(
        "\n".join(str(para.get("text") or "") for para in paragraphs_out)
    )
    envelope = {
        "phase": PHASE,
        "ok": ok,
        "status": "PASS" if ok else DECISION_BLOCK,
        "errors": list(dict.fromkeys(errors)),
        "gaps": list(dict.fromkeys(gaps)),
        "synthetic": is_synthetic,
        "chapter_id": chapter_id,
        "title": title,
        "sections": sections_out,
        "paragraphs": paragraphs_out,
        "paragraph_count": len(paragraphs_out),
        "section_count": len(sections_out),
        "allowed_evidence_handles": list(allowed),
        "evidence_handles": all_handles,
        "evidence_bundle_sha256": evidence_bundle_hash(all_handles),
        "generated_text_sha256": text_hash,
        "source_map_sha256": source_map_sha256,
        "editorial_plan_sha256": editorial_plan_sha256,
        "transcript_sha256": transcript_sha256,
        "generator_prompt_version": str(
            payload.get("generator_prompt_version") or BOOK_GENERATOR_PROMPT_VERSION
        ),
        "generator_transport_version": str(
            payload.get("generator_transport_version") or BOOK_GENERATION_TRANSPORT_VERSION
        ),
        "semantic_contract_version": PROMPT_VERSION_202_CANDIDATE,
        "semantic_transport_version": TRANSPORT_VERSION_20_CANDIDATE,
        "preparation_algorithm_version": PREPARATION_ALGORITHM_VERSION,
        "validator_implementation_version": VALIDATOR_IMPLEMENTATION_VERSION,
        "integration_contract_version": INTEGRATION_CONTRACT_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "does_not_invent_src": True,
        "does_not_reconstruct_evidence": True,
        "missing_required_evidence_is_block": True,
        "production_cache_write": False,
        "secrets_included": False,
    }
    return envelope


def adapt_editorial_chapter_without_generation(
    plan: EditorialPlan,
    source_map: SourceMap,
    chapter_id: str,
    *,
    identity: BookIdentity | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Read-only structural adaptation of a plan chapter that has no generated paragraphs."""
    chapter = _plan_chapter(plan, chapter_id)
    identity_payload = _as_mapping(identity)
    if chapter is None:
        return {
            "phase": PHASE,
            "ok": False,
            "status": DECISION_BLOCK,
            "errors": [f"chapter_id:not_in_editorial_plan:{chapter_id}"],
            "gaps": [],
            "chapter_id": chapter_id,
            "paragraph_count": 0,
            "paragraphs_unknown_before_generation": True,
            "does_not_invent_src": True,
            "secrets_included": False,
        }
    fake_candidate = {
        "chapter_id": chapter.chapter_id,
        "title": chapter.working_title,
        "source_map_sha256": identity_payload.get("source_map_sha256")
        or plan.source_map.sha256,
        "editorial_plan_sha256": identity_payload.get("editorial_plan_sha256") or "",
        "transcript_sha256": identity_payload.get("transcript_sha256") or "",
        "sections": [
            {
                "section_id": section.section_id,
                "title": section.working_title,
                "idea_refs": list(section.idea_refs),
                "source_refs": list(section.source_refs),
                "paragraphs": [],
            }
            for section in chapter.sections
        ],
        "synthetic": False,
    }
    adapted = adapt_chapter_candidate(
        fake_candidate,
        plan=plan,
        source_map=source_map,
        identity=identity,
        synthetic=False,
    )
    adapted["paragraphs_unknown_before_generation"] = True
    adapted["plan_idea_refs"] = list(chapter.idea_refs)
    adapted["plan_source_refs"] = list(chapter.source_refs)
    adapted["plan_section_ids"] = [section.section_id for section in chapter.sections]
    return adapted


__all__ = [
    "adapt_chapter_candidate",
    "adapt_editorial_chapter_without_generation",
    "adapt_paragraph",
    "source_map_handle_index",
]
