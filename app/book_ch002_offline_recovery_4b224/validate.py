"""Revalidation of a derived CH002 candidate with the existing validators."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_ch002_offline_recovery_4b224.chapter_io import (
    candidate_from_dict,
    idea_handles,
    iter_candidate_paragraphs,
)
from app.book_ch002_offline_recovery_4b224.constants import (
    EXPECTED_CH002_IDEA_COUNT,
    EXPECTED_CH002_SECTION_IDS,
    PHASE,
    TARGET_CHAPTER_ID,
    VALIDATOR_VERSION,
)
from app.book_generation.validator import validate_chapter_candidate
from app.book_generation_4b223.context import build_chapter_context
from app.book_generation_4b223.inventory import chapter_from_plan, chapter_spec
from app.book_generation_4b223.validation import render_chapter_markdown, structural_validation
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus


def validate_recovered_chapter(
    recovered: Mapping[str, Any],
    *,
    corpus: CanonicalCorpus,
    finish_reason: str | None,
    max_output_tokens: int | None,
) -> dict[str, Any]:
    spec = chapter_spec(TARGET_CHAPTER_ID, corpus=corpus)
    chapter = chapter_from_plan(corpus.plan, TARGET_CHAPTER_ID)
    built = build_chapter_context(spec, corpus=corpus)
    allowed = list((built.get("evidence") or {}).get("allowed") or [])
    candidate = candidate_from_dict(dict(recovered))
    production = validate_chapter_candidate(
        candidate,
        corpus.plan,
        corpus.source_map,
        chapter,
        language=corpus.language,
        allowed_handles=allowed,
    )
    interpreted = {
        "json_valid": True,
        "transport_ok": True,
        "candidate": candidate,
        "validation": production.to_dict(),
        "raw_idea_handles_in_paras_e": sorted(set(idea_handles(dict(recovered)))),
    }
    structural = structural_validation(
        interpreted=interpreted,
        plan=corpus.plan,
        chapter=chapter,
        spec=spec,
        allowed_handles=allowed,
        other_chapter_ids=[
            item.chapter_id
            for item in corpus.plan.chapters
            if item.chapter_id != TARGET_CHAPTER_ID
        ],
        finish_reason=finish_reason,
        max_output_tokens=max_output_tokens,
    )
    markdown = render_chapter_markdown(candidate, chapter)
    empty = 0
    for _section_id, _index, paragraph in iter_candidate_paragraphs(dict(recovered)):
        if not str(paragraph.get("text") or "").strip():
            empty += 1
    checks = dict(structural.get("checks") or {})
    extra = {
        "json_valid": True,
        "chapter_id_correct": recovered.get("chapter_id") == TARGET_CHAPTER_ID,
        "four_sections_exact": tuple(
            section.get("section_id") for section in recovered.get("sections") or []
        )
        == EXPECTED_CH002_SECTION_IDS,
        "sections_in_order": tuple(
            section.get("section_id") for section in recovered.get("sections") or []
        )
        == EXPECTED_CH002_SECTION_IDS,
        "no_empty_paragraphs": empty == 0,
        "paragraph_ids_unique": len(checks.get("paragraph_ids") or [])
        == len(set(checks.get("paragraph_ids") or [])),
        "no_invented_ideas": not checks.get("ideas_invented"),
        "no_invalid_src": not checks.get("invalid_src"),
        "no_unknown_ids": not checks.get("unknown_identifiers"),
        "ideas_expected": EXPECTED_CH002_IDEA_COUNT,
        "ideas_traced": int(checks.get("ideas_found_in_paras_e") or 0),
        "no_detectable_truncation": checks.get("detectable_truncation") is False,
        "production_validator_status": production.status,
        "structural_status": structural.get("status"),
        "json_markdown_consistent": _json_markdown_consistent(recovered, markdown),
    }
    extra["ideas_traced_match"] = extra["ideas_traced"] == EXPECTED_CH002_IDEA_COUNT
    boolean_keys = (
        "json_valid",
        "chapter_id_correct",
        "four_sections_exact",
        "sections_in_order",
        "no_empty_paragraphs",
        "paragraph_ids_unique",
        "no_invented_ideas",
        "no_invalid_src",
        "no_unknown_ids",
        "no_detectable_truncation",
        "json_markdown_consistent",
        "ideas_traced_match",
    )
    ok = (
        structural.get("status") == "PASS"
        and production.status != "FAIL"
        and all(extra[key] is True for key in boolean_keys)
    )
    return {
        "phase": PHASE,
        "chapter_id": TARGET_CHAPTER_ID,
        "validator_version": VALIDATOR_VERSION,
        "weakened_validator_used": False,
        "production_validator": production.to_dict(),
        "structural_validation": structural,
        "checks": extra,
        "markdown": markdown,
        "status": "PASS" if ok else "FAIL",
        "errors": list(structural.get("errors") or []) + list(production.errors),
        "secrets_included": False,
    }


def _json_markdown_consistent(chapter: Mapping[str, Any], markdown: str) -> bool:
    texts = [
        str(paragraph.get("text") or "").strip()
        for _section_id, _index, paragraph in iter_candidate_paragraphs(dict(chapter))
        if str(paragraph.get("text") or "").strip()
    ]
    body = markdown
    for text in texts:
        if text not in body:
            return False
        body = body.replace(text, "", 1)
    return True


__all__ = ["validate_recovered_chapter"]
