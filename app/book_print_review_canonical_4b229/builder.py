"""Build the provisional book.json from chapter JSON. Markdown is not a source."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.book_ch002_offline_recovery_4b224.chapter_io import load_json
from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    BOOK_GENERATOR_VALIDATOR_VERSION,
    BOOK_SCHEMA_VERSION,
    EVIDENCE_STRATEGY_HYDRATED,
    GENERATION_UNIT_CHAPTER,
)
from app.book_generation.models import format_paragraph_id
from app.book_print_review_canonical_4b229.constants import (
    ABSENT_EDITORIAL_FIELDS,
    BOOK_LANGUAGE,
    BOOK_STATUS,
    BOOK_TITLE,
    BOOK_VERSION,
    CODE_VERSION,
    HUMAN_ACCEPTED_STATUS,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
    STRUCTURAL_STATUS,
    TITLE_STATUS,
)
from app.book_print_review_canonical_4b229.guard import BookPrintReviewCanonical4229Error
from app.book_print_review_canonical_4b229.hashes import file_sha256
from app.book_print_review_canonical_4b229.paths import manuscript_path
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus


def _rel(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if item is not None]


def _copy_paragraph(raw: dict[str, Any], *, order: int, paragraph_id: str) -> dict[str, Any]:
    text = raw.get("text")
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    payload = {
        "paragraph_id": paragraph_id,
        "source_paragraph_id": str(raw.get("paragraph_id") or ""),
        "order": order,
        "text": text,
        "kind": str(raw.get("kind") or ""),
        "evidence_handles": _as_list(raw.get("evidence_handles")),
        "source_refs": _as_list(raw.get("source_refs")),
        "idea_refs": _as_list(raw.get("idea_refs")),
        "example_refs": _as_list(raw.get("example_refs")),
        "reference_refs": _as_list(raw.get("reference_refs")),
        "uncertainty_refs": _as_list(raw.get("uncertainty_refs")),
    }
    provider_handle = str(raw.get("provider_handle") or "")
    if provider_handle:
        payload["provider_handle"] = provider_handle
    attribution = raw.get("attribution")
    if attribution not in (None, "", [], {}):
        payload["attribution"] = deepcopy(attribution)
    return payload


def _copy_section(raw: dict[str, Any], *, order: int, paragraph_start: int) -> tuple[dict[str, Any], int]:
    paragraphs: list[dict[str, Any]] = []
    index = paragraph_start
    for local_order, paragraph in enumerate(raw.get("paragraphs") or [], start=1):
        if not isinstance(paragraph, dict):
            continue
        paragraphs.append(
            _copy_paragraph(
                paragraph,
                order=local_order,
                paragraph_id=format_paragraph_id(index),
            )
        )
        index += 1
    return (
        {
            "section_id": str(raw.get("section_id") or ""),
            "title": str(raw.get("title") or ""),
            "order": order,
            "paragraphs": paragraphs,
            "idea_refs": _as_list(raw.get("idea_refs")),
            "source_refs": _as_list(raw.get("source_refs")),
        },
        index,
    )


def _chapter_editorial_status(row: dict[str, Any]) -> dict[str, str]:
    if row.get("accepted"):
        return {
            "editorial_status": HUMAN_ACCEPTED_STATUS,
            "human_acceptance_status": HUMAN_ACCEPTED_STATUS,
            "structural_status": str(row.get("structural_status") or "PASS"),
        }
    return {
        "editorial_status": STRUCTURAL_STATUS,
        "human_acceptance_status": str(row.get("human_status_exact") or ""),
        "structural_status": STRUCTURAL_STATUS,
    }


def collect_source_paragraphs(inventory: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for row in inventory.get("chapters") or []:
        payload = load_json(Path(row["json_path"]))
        for section in payload.get("sections") or []:
            if not isinstance(section, dict):
                continue
            for paragraph in section.get("paragraphs") or []:
                if isinstance(paragraph, dict):
                    text = paragraph.get("text")
                    texts.append(text if isinstance(text, str) else str(text or ""))
    return texts


def build_book_payload(
    *,
    inventory: dict[str, Any],
    corpus: CanonicalCorpus,
    generated_at: str,
    root: Path | None = None,
) -> dict[str, Any]:
    if str(inventory.get("selected_title") or "") != BOOK_TITLE:
        raise BookPrintReviewCanonical4229Error(
            f"Selected title {inventory.get('selected_title')!r} ≠ {BOOK_TITLE!r}. STOP."
        )
    plan_subtitle = str(inventory.get("subtitle") or corpus.plan.subtitle or "")
    language = corpus.language or BOOK_LANGUAGE
    if language != BOOK_LANGUAGE:
        raise BookPrintReviewCanonical4229Error(
            f"Canonical language {language!r} ≠ {BOOK_LANGUAGE!r}. STOP."
        )
    chapters: list[dict[str, Any]] = []
    paragraph_index = 1
    idea_ids: list[str] = []
    seen_ideas: set[str] = set()
    for row in inventory.get("chapters") or []:
        raw = load_json(Path(row["json_path"]))
        if not isinstance(raw, dict):
            raise BookPrintReviewCanonical4229Error(
                f"{row['chapter_id']} JSON is not an object. STOP."
            )
        statuses = _chapter_editorial_status(row)
        sections: list[dict[str, Any]] = []
        for section_order, section in enumerate(raw.get("sections") or [], start=1):
            if not isinstance(section, dict):
                continue
            copied, paragraph_index = _copy_section(
                section, order=section_order, paragraph_start=paragraph_index
            )
            sections.append(copied)
        for idea_id in row.get("covered_idea_ids") or []:
            if idea_id not in seen_ideas:
                seen_ideas.add(idea_id)
                idea_ids.append(idea_id)
        chapters.append(
            {
                "chapter_id": str(raw.get("chapter_id") or row["chapter_id"]),
                "title": str(raw.get("title") or row["title"]),
                "order": int(row["book_order"]),
                "sections": sections,
                "idea_refs": _as_list(raw.get("idea_refs")),
                "source_refs": _as_list(raw.get("source_refs")),
                "editorial_status": statuses["editorial_status"],
                "human_acceptance_status": statuses["human_acceptance_status"],
                "structural_status": statuses["structural_status"],
                "provenance": {
                    "json_path": row["json_path"],
                    "markdown_path": row["markdown_path"],
                    "manifest_path": row.get("manifest_path") or "",
                    "json_sha256": row["json_sha256"],
                    "markdown_sha256": row["markdown_sha256"],
                    "approved_version": row.get("approved_version") or "",
                    "section_count": row["section_count"],
                    "paragraph_count": row["paragraph_count"],
                },
            }
        )
    section_count = sum(len(chapter["sections"]) for chapter in chapters)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "project": {"name": PROJECT_NAME},
        "language": language,
        "title": BOOK_TITLE,
        "subtitle": plan_subtitle,
        "title_status": TITLE_STATUS,
        "document_version": BOOK_VERSION,
        "editorial_status": BOOK_STATUS,
        "generated_at": generated_at,
        "phase": PHASE,
        "code_version": CODE_VERSION,
        "chapter_count": len(chapters),
        "section_count": section_count,
        "idea_coverage_count": len(idea_ids),
        "front_matter": [],
        "back_matter": [],
        "absent_editorial_fields": {
            field: None for field in ABSENT_EDITORIAL_FIELDS
        },
        "chapters": chapters,
        "identity": {
            "source_map_sha256": corpus.inputs.source_map_sha256,
            "editorial_plan_sha256": corpus.inputs.plan_sha256,
            "source_map_bytes": len(corpus.inputs.source_map_bytes),
            "editorial_plan_bytes": len(corpus.inputs.plan_bytes),
            "transcript_sha256": corpus.transcript.content_sha256,
            "transcript_path": _rel(corpus.transcript.path),
        },
        "generation": {
            "prompt_version": "offline-consolidation",
            "transport_version": BOOK_GENERATION_TRANSPORT_VERSION,
            "schema_version": BOOK_SCHEMA_VERSION,
            "validator_version": BOOK_GENERATOR_VALIDATOR_VERSION,
            "evidence_strategy": EVIDENCE_STRATEGY_HYDRATED,
            "generation_unit": GENERATION_UNIT_CHAPTER,
            "provider": "none",
            "model": "none",
            "thinking_mode": "none",
            "effort": "none",
            "language": language,
            "title_status": TITLE_STATUS,
            "signature": f"{BOOK_VERSION}-offline-consolidation",
        },
        "references": {
            "editorial_plan": {
                "path": _rel(corpus.inputs.plan_path),
                "sha256": corpus.inputs.plan_sha256,
            },
            "source_map": {
                "path": _rel(corpus.inputs.source_map_path),
                "sha256": corpus.inputs.source_map_sha256,
            },
            "transcript": {
                "path": _rel(corpus.transcript.path),
                "sha256": corpus.transcript.content_sha256,
            },
            "manuscript_reading_draft": {
                "path": _rel(manuscript_path(root=root)),
                "sha256": file_sha256(manuscript_path(root=root)).get("sha256") or "",
            },
            "subtitle_source": "EditorialPlan.subtitle",
            "title_source": "EditorialPlan.selected_title",
            "title_invented_by_this_phase": False,
            "subtitle_invented_by_this_phase": False,
        },
        "protection": {
            "protected": False,
            "kind": "provisional_print_review_draft",
            "overwrite": "same_phase_print-review-v1_only",
            "final_publication": False,
        },
        "future_revision_compare": {
            "prepared": True,
            "implemented": False,
            "method": "canonical_paragraph_text_and_id_diff",
            "fields": [
                "chapter_id",
                "section_id",
                "paragraph_id",
                "text",
                "editorial_status",
            ],
        },
    }
    return payload


def book_paragraph_texts(payload: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for chapter in payload.get("chapters") or []:
        for section in chapter.get("sections") or []:
            for paragraph in section.get("paragraphs") or []:
                texts.append(str(paragraph.get("text") or ""))
    return texts


def render_book(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def reproducibility_view(payload: dict[str, Any]) -> dict[str, Any]:
    view = deepcopy(payload)
    view["generated_at"] = ""
    return view


__all__ = [
    "book_paragraph_texts",
    "build_book_payload",
    "collect_source_paragraphs",
    "render_book",
    "reproducibility_view",
]
