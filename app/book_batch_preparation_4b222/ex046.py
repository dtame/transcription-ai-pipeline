"""
Separate EX046 provenance table.

Does not modify the accepted CH018 JSON. Does not inject EX046 into paras[].e.
Does not declare the original provider response corrected.
"""

from __future__ import annotations

from typing import Any

from app.book_authorial_voice_4b218.chapter_io import iter_paragraphs
from app.book_batch_preparation_4b222.constants import (
    ACCEPTED_CH018_ID,
    CH018_EX046,
    EX046_REVIEW_VERSION,
    PHASE,
)
from app.book_batch_preparation_4b222.guard import BookBatchPreparation4222Error
from app.book_batch_preparation_4b222.integrity import load_ch018_chapter
from app.book_generation.evidence import classify_handle
from app.book_scale_up_preparation_4b220.corpus import CanonicalCorpus, load_canonical_corpus


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in "".join(
            char.lower() if char.isalnum() else " " for char in text
        ).split()
        if len(token) > 3
    }


def review_ex046_traceability(
    *,
    corpus: CanonicalCorpus | None = None,
    chapter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    corpus = corpus or load_canonical_corpus()
    chapter = chapter or load_ch018_chapter()
    example = next(
        (item for item in corpus.source_map.examples if item.example_id == CH018_EX046),
        None,
    )
    if example is None:
        raise BookBatchPreparation4222Error("EX046 is absent from the canonical SourceMap.")
    example_src = list(example.source_refs)
    example_ideas = list(example.supports_idea_refs)
    summary_tokens = _tokens(example.summary)
    rows = []
    for paragraph_id, row in iter_paragraphs(chapter):
        evidence = [str(handle) for handle in row.get("evidence_handles") or []]
        source_refs = [str(handle) for handle in row.get("source_refs") or []]
        src_overlap = [item for item in example_src if item in source_refs or item in evidence]
        idea_overlap = [
            item
            for item in example_ideas
            if item in evidence or item in (row.get("idea_refs") or [])
        ]
        text = str(row.get("text") or "")
        token_overlap = sorted(summary_tokens & _tokens(text))
        if src_overlap or idea_overlap or len(token_overlap) >= 4:
            rows.append(
                {
                    "paragraph_id": paragraph_id,
                    "section_id": row.get("section_id"),
                    "provider_handle": row.get("provider_handle"),
                    "ex046_in_paras_e": CH018_EX046 in evidence,
                    "supporting_src_overlap": src_overlap,
                    "supporting_idea_overlap": idea_overlap,
                    "summary_token_overlap": token_overlap,
                    "text_excerpt": text[:220],
                }
            )
    correspondence = bool(rows) and any(row["supporting_src_overlap"] for row in rows)
    injected = any(
        CH018_EX046 in (row.get("evidence_handles") or [])
        or CH018_EX046 in (row.get("example_refs") or [])
        for _pid, row in iter_paragraphs(chapter)
    )
    if injected:
        raise BookBatchPreparation4222Error(
            "EX046 is present in accepted paras[].e. This review must not rewrite it."
        )
    return {
        "phase": PHASE,
        "review_version": EX046_REVIEW_VERSION,
        "chapter_id": ACCEPTED_CH018_ID,
        "example_id": CH018_EX046,
        "source_map_example": {
            "kind": example.kind,
            "summary": example.summary,
            "supports_idea_refs": example_ideas,
            "source_refs": example_src,
        },
        "paras_e_contains_ex046": False,
        "accepted_json_modified": False,
        "provider_response_modified": False,
        "correspondence_established": correspondence,
        "matching_paragraphs": rows,
        "supporting_src": sorted(
            {
                src
                for row in rows
                for src in row["supporting_src_overlap"]
            }
        ),
        "future_production_projection": {
            "allowed_later": True,
            "must_not_rewrite_accepted_chapter": True,
            "must_not_backfill_provider_response": True,
            "proposed_action": (
                "When a later controlled projection writes a production contract, "
                "add EX046 to paras[].e of the matching graveside-testimony "
                "paragraphs if those paragraphs still restate this testimony. "
                "Do not invent the correspondence. Do not treat this review as "
                "that projection."
            ),
            "candidate_paragraph_ids": [row["paragraph_id"] for row in rows],
        },
        "anomaly_class": "technical_traceability",
        "not_a_rewrite_request": True,
        "secrets_included": False,
    }


__all__ = ["review_ex046_traceability"]
