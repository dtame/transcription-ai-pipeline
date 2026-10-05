"""Build and inspect targeted source context for the selected first chapter."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_generation.coverage import assigned_idea_ids_for_chapter, chapter_by_id
from app.book_generation.evidence import (
    build_chapter_evidence,
    classify_handle,
    evidence_metrics,
)
from app.book_scale_up_preparation_4b220.constants import (
    ACCEPTED_CHAPTER,
    PHASE,
)
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus
from app.book_scale_up_preparation_4b220.guard import BookScaleUpPreparation4220Error


def build_chapter_source_context(
    chapter_id: str,
    *,
    corpus: CanonicalCorpus | None = None,
) -> dict[str, Any]:
    if chapter_id == ACCEPTED_CHAPTER:
        raise BookScaleUpPreparation4220Error(
            f"{ACCEPTED_CHAPTER} is accepted and must not be regenerated."
        )
    corpus = corpus or load_canonical_corpus()
    chapter = chapter_by_id(corpus.plan, chapter_id)
    evidence = build_chapter_evidence(
        corpus.plan,
        corpus.source_map,
        chapter,
        language=corpus.language,
        hydrate=True,
        transcript_index=corpus.transcript,
    )
    metrics = evidence_metrics(evidence)
    expected_src = list(evidence.get("src") or [])
    hydrated = list(evidence.get("src_text") or [])
    hydrated_ids = [item.get("id") for item in hydrated]
    missing = [src_id for src_id in expected_src if src_id not in set(hydrated_ids)]
    extra = [src_id for src_id in hydrated_ids if src_id not in set(expected_src)]
    whole_transcript_words = sum(
        len(segment.text.split()) for segment in corpus.transcript.segments
    )
    hydrated_words = sum(len(str(item.get("t") or "").split()) for item in hydrated)
    if missing:
        raise BookScaleUpPreparation4220Error(
            "Mandatory SRC excerpts missing from hydration: " + ",".join(missing[:12])
        )
    if extra:
        raise BookScaleUpPreparation4220Error(
            "Hydration produced SRC IDs outside the chapter unit: " + ",".join(extra[:12])
        )
    if hydrated_words >= whole_transcript_words:
        raise BookScaleUpPreparation4220Error(
            "Hydration injected the whole transcript."
        )
    return {
        "phase": PHASE,
        "chapter_id": chapter.chapter_id,
        "working_title": chapter.working_title,
        "language": evidence.get("canonical_document_language"),
        "expected_sources": {
            "idea_ids": [row.get("id") for row in evidence.get("ideas") or []],
            "example_ids": [row.get("id") for row in evidence.get("examples") or []],
            "reference_ids": [row.get("id") for row in evidence.get("references") or []],
            "uncertainty_ids": [
                row.get("id") for row in evidence.get("uncertainties") or []
            ],
            "src_ids": expected_src,
            "section_ids": [row.get("id") for row in evidence.get("sections") or []],
        },
        "resolved_sources": {
            "hydrated_src_ids": hydrated_ids,
            "hydrated_count": len(hydrated),
            "hydrated_details": [
                {
                    "id": item.get("id"),
                    "chars": len(str(item.get("t") or "")),
                    "kind": classify_handle(str(item.get("id") or "")),
                }
                for item in hydrated
            ],
        },
        "missing_sources": missing,
        "context_size": metrics,
        "potentially_truncated": [],
        "coverage_risks": [
            "Targeted hydration can omit neighboring spoken detail that the plan did not attach.",
            "A resolved SRC is not proof that every idea in that SRC is restated.",
        ],
        "whole_transcript_injected": False,
        "whole_transcript_words": whole_transcript_words,
        "hydrated_src_words": hydrated_words,
        "raw_transcript_used_as_silent_fallback": False,
        "sources_dropped_to_reduce_cost": False,
        "blocked_if_mandatory_source_missing": True,
        "generation_blocked": bool(missing),
        "planned_ideas": list(assigned_idea_ids_for_chapter(chapter)),
        "allowed_handles": list(evidence.get("allowed") or []),
        "blocked_handles": list(evidence.get("blocked") or []),
        "evidence": evidence,
        "ready": not missing,
        "secrets_included": False,
    }


def first_chapter_source_context_manifest(
    selection: Mapping[str, Any],
    *,
    corpus: CanonicalCorpus | None = None,
) -> dict[str, Any]:
    chapter_id = str(selection.get("selected_chapter_id") or "")
    built = build_chapter_source_context(chapter_id, corpus=corpus)
    payload = dict(built)
    payload.pop("evidence", None)
    payload["ready"] = (
        not payload["missing_sources"]
        and payload["whole_transcript_injected"] is False
        and payload["raw_transcript_used_as_silent_fallback"] is False
        and payload["sources_dropped_to_reduce_cost"] is False
    )
    return payload


__all__ = [
    "build_chapter_source_context",
    "first_chapter_source_context_manifest",
]
