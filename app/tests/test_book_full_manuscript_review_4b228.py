"""Phase 4B.2.28 — offline manuscript assembly and editorial consolidation."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.book_full_manuscript_review_4b228.assemble import assemble_manuscript
from app.book_full_manuscript_review_4b228.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    CANONICAL_CHAPTER_IDS,
    CONSUMED_4B227_SCOPE,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SECTION_COUNT,
    HUMAN_ACCEPTANCE_STATUS,
    HUMAN_REVIEW_PENDING_STATUS,
    PENDING_CHAPTER_IDS,
    PUBLICATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
)
from app.book_full_manuscript_review_4b228.guard import (
    BookFullManuscriptReview4228Error,
    _is_later_print_review_draft,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_full_manuscript_review_4b228.hashes import snapshot
from app.book_full_manuscript_review_4b228.integrity import validate_manuscript_integrity
from app.book_full_manuscript_review_4b228.inventory import build_chapters_inventory
from app.book_full_manuscript_review_4b228.paths import (
    ch002_approved_json_path,
    ch002_original_json_path,
    ch012_original_json_path,
    production_book_path,
)
from app.book_full_manuscript_review_4b228.review import editorial_global_review
from app.book_full_manuscript_review_4b228.runner import run_phase
from app.book_scale_up_preparation_4b220.corpus import load_canonical_corpus


def test_offline_authorizations():
    assert PUBLICATION_AUTHORIZED is False
    assert REAL_CHAPTER_GENERATION_AUTHORIZED is False
    assert AUTHORIZED_ANTHROPIC_CALLS == 0
    assert AUTHORIZED_OPENAI_CALLS == 0
    assert AUTHORIZED_SONNET_CALLS == 0
    assert AUTHORIZED_TERRA_CALLS == 0
    assert_offline_only()


def test_consumed_generation_scope_is_rejected():
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    with pytest.raises(BookFullManuscriptReview4228Error):
        validate_authorization_scope(CONSUMED_4B227_SCOPE)
    with pytest.raises(BookFullManuscriptReview4228Error):
        validate_authorization_scope("WRONG")


def test_canonical_and_accepted_hashes():
    snap = snapshot()
    assert snap["canonical_match_expected"] is True
    assert snap["six_accepted_immutable"] is True
    assert snap["thirteen_candidates_present"] is True
    assert production_book_path().is_file() is False or _is_later_print_review_draft(
        production_book_path()
    )


def test_inventory_order_coverage_and_status_split():
    inventory = build_chapters_inventory()
    ids = [row["chapter_id"] for row in inventory["chapters"]]
    assert ids == list(CANONICAL_CHAPTER_IDS)
    assert len(set(ids)) == 19
    assert inventory["section_count"] == EXPECTED_SECTION_COUNT
    assert inventory["idea_coverage_count"] == EXPECTED_IDEA_COUNT
    assert inventory["accepted_count"] == 6
    assert inventory["human_review_pending_count"] == 13
    for row in inventory["chapters"]:
        if row["chapter_id"] in PENDING_CHAPTER_IDS:
            assert row["human_status_exact"] == HUMAN_REVIEW_PENDING_STATUS
            assert row["accepted"] is False
        else:
            assert row["human_status_exact"] == HUMAN_ACCEPTANCE_STATUS
            assert row["manifest_path"]


def test_correct_historical_versions_are_used():
    inventory = build_chapters_inventory()
    by_id = {row["chapter_id"]: row for row in inventory["chapters"]}
    assert Path(by_id["CH002"]["json_path"]) == ch002_approved_json_path()
    assert Path(by_id["CH002"]["json_path"]) != ch002_original_json_path()
    assert "chapter_candidate_authorial_v2" in by_id["CH012"]["json_path"]
    assert Path(by_id["CH012"]["json_path"]) != ch012_original_json_path()
    assert "book_generation_4b221_ch018" in by_id["CH018"]["json_path"]
    assert inventory["ch002_recovered_used"] is True
    assert inventory["ch012_authorial_v2_used"] is True
    assert inventory["ch018_accepted_used"] is True


def test_manuscript_does_not_add_remove_or_rewrite_prose():
    inventory = build_chapters_inventory()
    first = assemble_manuscript(inventory)
    second = assemble_manuscript(inventory)
    assert first["manuscript_text"] == second["manuscript_text"]
    integrity = validate_manuscript_integrity(inventory=inventory, assembly=first)
    assert integrity["status"] == "PASS"
    assert integrity["paragraph_integrity"] == "PASS"
    assert integrity["provenance_integrity"] == "PASS"
    assert integrity["toc_titles"] == [row["title"] for row in inventory["chapters"]]
    assert "IDEA001" not in first["manuscript_text"]
    assert "SRC000018" not in first["manuscript_text"]
    assert first["title_info"]["invented_by_this_phase"] is False
    source_paragraphs = [
        paragraph["text"]
        for row in inventory["chapters"]
        for paragraph in row["paragraphs"]
    ]
    assembled_paragraphs = [row["text"] for row in first["paragraphs"]]
    assert assembled_paragraphs == source_paragraphs


def test_historical_observations_are_consolidated_not_erased():
    inventory = build_chapters_inventory()
    editorial = editorial_global_review(
        inventory=inventory, corpus=load_canonical_corpus()
    )
    historical = editorial["references_examples"]["historical_observations"]
    ids = {(item["chapter_id"], item["id"]) for item in historical}
    assert ("CH003", "EX005") in ids
    assert ("CH004", "REF011") in ids
    assert ("CH004", "REF012") in ids
    assert ("CH004", "REF013") in ids
    assert ("CH012", "EX030") in ids
    assert ("CH018", "EX046") in ids
    assert editorial["strengthened_claims"]["observation_count"] == 8
    assert editorial["external_model_called"] is False
    assert editorial["semantic_certification"] == "NOT PERFORMED"


def test_phase_runner_offline_without_writing():
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=False,
        run_tests=False,
    )
    header = result.bundle["header"]
    assert header["provider_calls"] == 0
    assert header["anthropic_http"] == 0
    assert header["openai_http"] == 0
    assert header["chapters_assembled"] == "19 / 19"
    assert header["sections_assembled"] == f"{EXPECTED_SECTION_COUNT} / {EXPECTED_SECTION_COUNT}"
    assert header["idea_coverage"] == f"{EXPECTED_IDEA_COUNT} / {EXPECTED_IDEA_COUNT}"
    assert header["paragraph_integrity"] == "PASS"
    assert header["result"] in {"PASS", "PARTIAL"}
    assert "book.json = NOT PUBLISHED" in result.bundle["report_text"]
    assert "DOCX = NOT GENERATED" in result.bundle["report_text"]
    assert "PDF = NOT GENERATED" in result.bundle["report_text"]
    checklist = result.bundle["human_review_checklist"]
    assert checklist["no_approval_attributed_by_this_phase"] is True
    assert all(not row["decision"] for row in checklist["pending_chapters"])
    assert production_book_path().is_file() is False or _is_later_print_review_draft(
        production_book_path()
    )
