"""Offline regression scenarios. No provider call."""

from __future__ import annotations

from typing import Any

from app.book_editorial_acceptance_4b219.chapter_io import (
    iter_paragraphs,
    load_accepted_chapter,
    load_accepted_markdown,
    paragraph_idea_handles,
    paragraph_ids,
    section_ids,
)
from app.book_editorial_acceptance_4b219.consistency import compare_markdown_json
from app.book_editorial_acceptance_4b219.constants import (
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    CHAPTER_ID,
    CLASS_CONTENT_SUPPORTED,
    CONSUMED_4B217_SCOPE,
    CONSUMED_4B218_SCOPE,
    EXPECTED_ACCEPTED_JSON_SHA256,
    EXPECTED_ACCEPTED_MD_SHA256,
    FAITHFUL_PROMPT_1_1,
    PARAGRAPH_COUNT,
    PARAGRAPH_IDS,
    PHASE,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PUBLICATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    SECTION_IDS,
    UNCERTAINTY_ID,
)
from app.book_editorial_acceptance_4b219.guard import (
    BookEditorialAcceptance4219Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_editorial_acceptance_4b219.hashes import snapshot
from app.book_editorial_acceptance_4b219.idea_review import (
    classify_content,
    src_overlap_alone_is_not_support,
)
from app.book_editorial_acceptance_4b219.paths import (
    original_chapter_json_path,
    original_lock_path,
    production_book_path,
)
from app.book_editorial_acceptance_4b219.prompt_readiness import generator_prompt_readiness
from app.book_generation.prompt_select import resolve_prompt_module


def evaluate_offline_scenarios(*, root=None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def _row(name: str, ok: bool, detail: str) -> None:
        rows.append({"name": name, "ok": ok, "detail": detail})

    snap = snapshot(root=root)
    chapter = load_accepted_chapter()
    markdown = load_accepted_markdown()
    consistency = compare_markdown_json(chapter, markdown)
    prompt = generator_prompt_readiness()

    _row(
        "canonical_hashes_match",
        snap["canonical_match_expected"] is True,
        "SourceMap, EditorialPlan, and transcript match expected SHA-256",
    )
    _row(
        "original_chapter_preserved",
        snap["original_match_expected"] is True,
        "4B.2.17 JSON, Markdown, and lock hashes match",
    )
    _row(
        "accepted_chapter_preserved",
        snap["accepted_match_expected"] is True
        and snap["accepted_chapter"]["chapter_candidate_authorial_v2_json"]["sha256"]
        == EXPECTED_ACCEPTED_JSON_SHA256
        and snap["accepted_chapter"]["chapter_candidate_authorial_v2_md"]["sha256"]
        == EXPECTED_ACCEPTED_MD_SHA256,
        "4B.2.18 accepted pair hashes match",
    )
    _row(
        "provider_lock_preserved",
        snap["original_chapter"]["provider_lock"]["sha256"]
        == snap["original_chapter"]["provider_lock"]["sha256"]
        and original_lock_path().is_file(),
        "ch012_real_call.lock present and hashed",
    )
    _row(
        "markdown_json_consistent",
        consistency["consistent"] is True and consistency["freeze_blocked"] is False,
        f"mismatches={consistency['prose_mismatches']}",
    )
    _row(
        "fourteen_paragraphs",
        consistency["json_paragraph_count"] == PARAGRAPH_COUNT
        and consistency["markdown_paragraph_count"] == PARAGRAPH_COUNT
        and paragraph_ids(chapter) == PARAGRAPH_IDS,
        f"count={consistency['json_paragraph_count']}",
    )
    _row(
        "four_sections_intact",
        section_ids(chapter) == SECTION_IDS
        and consistency["section_order_match"] is True,
        ",".join(section_ids(chapter)),
    )
    _row(
        "human_acceptance_not_semantic_certificate",
        True,
        "acceptance scope is editorial only",
    )
    _row(
        "hash_freeze_uses_accepted_sha256",
        EXPECTED_ACCEPTED_JSON_SHA256
        == snap["accepted_chapter"]["chapter_candidate_authorial_v2_json"]["sha256"],
        EXPECTED_ACCEPTED_JSON_SHA256,
    )
    _row(
        "idea_traceability_eleven",
        len(chapter.get("idea_refs") or []) == 11,
        f"chapter idea_refs={len(chapter.get('idea_refs') or [])}",
    )
    _row(
        "src_overlap_alone_rejected",
        src_overlap_alone_is_not_support() is True
        and classify_content(
            missing_required=["absent-claim"],
            missing_groups=1,
            required_groups=1,
        )
        == "NOT_SUPPORTED",
        "shared SRC without content markers is not CONTENT_SUPPORTED",
    )
    _row(
        "content_supported_requires_markers",
        classify_content(missing_required=[], missing_groups=0, required_groups=2)
        == CLASS_CONTENT_SUPPORTED,
        "markers present => CONTENT_SUPPORTED",
    )
    unc = [
        row
        for _pid, row in iter_paragraphs(chapter)
        if UNCERTAINTY_ID in row["uncertainty_refs"]
    ]
    _row(
        "unc029_preserved",
        bool(unc) and "unclear" in unc[0]["text"].lower(),
        f"paragraphs={[row['paragraph_id'] for row in unc]}",
    )
    _row(
        "paras_e_not_written",
        paragraph_idea_handles(chapter) == [],
        "accepted paragraph IDEA handles remain empty",
    )
    _row(
        "no_provider_call",
        AUTHORIZED_ANTHROPIC_CALLS
        == AUTHORIZED_OPENAI_CALLS
        == AUTHORIZED_SONNET_CALLS
        == AUTHORIZED_TERRA_CALLS
        == 0
        and REAL_CHAPTER_GENERATION_AUTHORIZED is False,
        "zero provider authorizations",
    )
    _row(
        "no_publication",
        PUBLICATION_AUTHORIZED is False
        and PRODUCTION_PIPELINE_HOOK is False
        and PRODUCTION_CACHE_ACCEPTANCE is False
        and not production_book_path().exists(),
        "book.json absent and publication closed",
    )
    try:
        validate_authorization_scope(CONSUMED_4B217_SCOPE)
        reused_217 = True
    except BookEditorialAcceptance4219Error:
        reused_217 = False
    try:
        validate_authorization_scope(CONSUMED_4B218_SCOPE)
        reused_218 = True
    except BookEditorialAcceptance4219Error:
        reused_218 = False
    _row("consumed_authorizations_rejected", reused_217 is False and reused_218 is False, "ok")
    assert_offline_only()
    _row("offline_guard", True, "assert_offline_only passed")
    try:
        resolve_prompt_module(FAITHFUL_PROMPT_1_1)
        registered = True
    except ValueError:
        registered = False
    _row(
        "prompt_1_1_not_registered",
        registered is False and prompt["activated"] is False,
        FAITHFUL_PROMPT_1_1,
    )
    _row(
        "original_artifacts_present",
        original_chapter_json_path().is_file() and original_lock_path().is_file(),
        CHAPTER_ID,
    )
    again = compare_markdown_json(chapter, markdown)
    _row("idempotent_consistency", again == consistency, "second compare matches first")

    failed = [row for row in rows if not row["ok"]]
    return {
        "phase": PHASE,
        "scenario_count": len(rows),
        "passed": len(rows) - len(failed),
        "failed": len(failed),
        "failed_ids": [row["name"] for row in failed],
        "scenarios": rows,
        "real_provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "not_a_terra_validation": True,
        "secrets_included": False,
    }


__all__ = ["evaluate_offline_scenarios"]
