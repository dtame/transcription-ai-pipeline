"""Phase 4B.2.28 final report."""

from __future__ import annotations

from typing import Any, Mapping

from app.book_full_manuscript_review_4b228.constants import CANONICAL_PYTHON


def render_report(bundle: Mapping[str, Any]) -> str:
    header = dict(bundle.get("header") or {})
    editorial = dict(bundle.get("editorial_global_review") or {})
    continuity = list((editorial.get("continuity") or {}).get("observations") or [])
    strengthened = list(
        (editorial.get("strengthened_claims") or {}).get("observations") or []
    )
    similar = list(
        (editorial.get("references_examples") or {}).get(
            "similar_observations_in_new_chapters"
        )
        or []
    )
    priority = [
        "Priority observations remain documentary only. No automatic rewrite.",
    ]
    for item in strengthened:
        spans = item.get("matched_spans") or []
        token = spans[0].get("matched_token") if spans else "not localized"
        priority.append(
            f"- STRENGTHENED_CLAIM {item.get('chapter_id')} {item.get('section') or ''} "
            f"{item.get('paragraph') or ''}: `{token}`."
        )
    for item in similar[:12]:
        priority.append(
            f"- {item.get('kind')} {item.get('id')} in {item.get('chapter_id')}: "
            f"{item.get('category')}."
        )
    for item in continuity:
        if item.get("code") == "POSSIBLE_ABRUPT_TRANSITION":
            priority.append(
                f"- Continuity {item.get('chapter_from')} → {item.get('chapter_to')}: "
                f"{item.get('detail')}"
            )
    lines = [
        "**PHASE 4B.2.28 — FULL MANUSCRIPT EDITORIAL REVIEW**",
        "",
        f"RESULT = {header.get('result')}",
        "PROVIDER CALLS = 0",
        "ANTHROPIC HTTP = 0",
        "OPENAI HTTP = 0",
        f"CHAPTERS ASSEMBLED = {header.get('chapters_assembled')}",
        f"SECTIONS ASSEMBLED = {header.get('sections_assembled')}",
        f"IDEA COVERAGE = {header.get('idea_coverage')}",
        f"ACCEPTED CHAPTERS = {header.get('accepted_chapters')}",
        f"HUMAN_REVIEW_PENDING CHAPTERS = {header.get('human_review_pending_chapters')}",
        f"MANUSCRIPT MARKDOWN PATH = {header.get('manuscript_markdown_path')}",
        f"MANUSCRIPT WORD COUNT = {header.get('manuscript_word_count')}",
        f"MANUSCRIPT SHA-256 = {header.get('manuscript_sha256')}",
        f"PARAGRAPH INTEGRITY = {header.get('paragraph_integrity')}",
        f"PROVENANCE INTEGRITY = {header.get('provenance_integrity')}",
        f"STRENGTHENED CLAIM OBSERVATIONS = {header.get('strengthened_claim_observations')}",
        f"REFERENCES / EXAMPLES OBSERVATIONS = {header.get('references_examples_observations')}",
        f"CONTINUITY OBSERVATIONS = {header.get('continuity_observations')}",
        f"HUMAN REVIEW GUIDE = {header.get('human_review_guide')}",
        f"CANONICAL HASHES PRE/POST = {header.get('canonical_hashes_pre_post')}",
        f"SIX ACCEPTED CHAPTERS IMMUTABLE = {header.get('six_accepted_chapters_immutable')}",
        f"THIRTEEN CANDIDATES IMMUTABLE = {header.get('thirteen_candidates_immutable')}",
        "SEMANTIC CERTIFICATION = NOT PERFORMED",
        "book.json = NOT PUBLISHED",
        "DOCX = NOT GENERATED",
        "PDF = NOT GENERATED",
        f"READY_FOR_GLOBAL_HUMAN_REVIEW = {header.get('ready_for_global_human_review')}",
        f"NEXT ACTION = {header.get('next_action')}",
        "",
        "## Priority observations",
        "",
        *priority,
        "",
        "## Why this result",
        "",
        str(header.get("notes") or ""),
        "",
        f"Canonical Python: `{CANONICAL_PYTHON}`",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_report"]
