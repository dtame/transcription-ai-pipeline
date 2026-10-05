"""Phase 4B.2.29 — offline print-review book.json constitution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.book_generation.models import Book
from app.book_generation.writer import write_book
from app.book_print_review_canonical_4b229.builder import (
    book_paragraph_texts,
    build_book_payload,
    collect_source_paragraphs,
    render_book,
    reproducibility_view,
)
from app.book_print_review_canonical_4b229.constants import (
    ACCEPTED_CHAPTER_IDS,
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    BOOK_STATUS,
    BOOK_TITLE,
    BOOK_VERSION,
    CANONICAL_CHAPTER_IDS,
    CONSUMED_4B228_SCOPE,
    DOCX_GENERATION_AUTHORIZED,
    EXPECTED_EDITORIAL_PLAN_SHA256,
    EXPECTED_IDEA_COUNT,
    EXPECTED_MANUSCRIPT_SHA256,
    EXPECTED_SECTION_COUNT,
    EXPECTED_SOURCE_MAP_SHA256,
    EXPECTED_TRANSCRIPT_SHA256,
    FINAL_PUBLICATION_AUTHORIZED,
    HUMAN_ACCEPTED_STATUS,
    PDF_GENERATION_AUTHORIZED,
    PENDING_CHAPTER_IDS,
    STRUCTURAL_STATUS,
    VISUAL_DIRECTION_AUTHORIZED,
)
from app.book_print_review_canonical_4b229.guard import (
    BookPrintReviewCanonical4229Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_print_review_canonical_4b229.hashes import snapshot
from app.book_print_review_canonical_4b229.integrity import validate_book_integrity
from app.book_print_review_canonical_4b229.observations import load_editorial_observations
from app.book_print_review_canonical_4b229.paths import (
    ch002_approved_json_path,
    ch002_original_json_path,
    ch012_original_json_path,
    manuscript_path,
    phase_audit_dir,
    production_book_path,
)
from app.book_print_review_canonical_4b229.publisher import (
    assert_publication_allowed,
    inspect_existing_book,
    publish_atomic,
)
from app.book_print_review_canonical_4b229.runner import run_phase
from app.book_print_review_canonical_4b229.schema import validate_book_schema
from app.book_print_review_canonical_4b229.word import assess_word_readiness
from app.book_full_manuscript_review_4b228.constants import (
    AUTHORIZATION_SCOPE as MANUSCRIPT_SCOPE,
)
from app.book_full_manuscript_review_4b228.inventory import build_chapters_inventory
from app.book_scale_up_preparation_4b220.corpus import load_canonical_corpus
from app.file_utils import content_hash

_FIXED_AT = "2026-10-04T21:00:00+00:00"


@pytest.fixture(scope="module")
def corpus():
    return load_canonical_corpus()


@pytest.fixture(scope="module")
def inventory(corpus):
    return build_chapters_inventory(corpus=corpus)


@pytest.fixture(scope="module")
def payload(inventory, corpus):
    return build_book_payload(
        inventory=inventory,
        corpus=corpus,
        generated_at=_FIXED_AT,
    )


def test_offline_authorizations():
    assert AUTHORIZED_ANTHROPIC_CALLS == 0
    assert AUTHORIZED_OPENAI_CALLS == 0
    assert AUTHORIZED_SONNET_CALLS == 0
    assert AUTHORIZED_TERRA_CALLS == 0
    assert DOCX_GENERATION_AUTHORIZED is False
    assert PDF_GENERATION_AUTHORIZED is False
    assert VISUAL_DIRECTION_AUTHORIZED is False
    assert FINAL_PUBLICATION_AUTHORIZED is False
    assert_offline_only()
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    with pytest.raises(BookPrintReviewCanonical4229Error):
        validate_authorization_scope(CONSUMED_4B228_SCOPE)
    with pytest.raises(BookPrintReviewCanonical4229Error):
        validate_authorization_scope(MANUSCRIPT_SCOPE)
    with pytest.raises(BookPrintReviewCanonical4229Error):
        validate_authorization_scope("WRONG")


def test_canonical_sources_and_hashes():
    snap = snapshot()
    canonical = snap["canonical"]
    assert canonical["source_map"]["sha256"] == EXPECTED_SOURCE_MAP_SHA256
    assert canonical["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN_SHA256
    assert canonical["clean_transcript"]["sha256"] == EXPECTED_TRANSCRIPT_SHA256
    assert snap["manuscript"]["sha256"] == EXPECTED_MANUSCRIPT_SHA256
    assert manuscript_path().is_file()
    assert snap["canonical_match_expected"] is True
    assert snap["six_accepted_immutable"] is True
    assert snap["thirteen_candidates_present"] is True


def test_six_accepted_and_thirteen_candidates_resolved(inventory):
    by_id = {row["chapter_id"]: row for row in inventory["chapters"]}
    assert [row["chapter_id"] for row in inventory["chapters"]] == list(CANONICAL_CHAPTER_IDS)
    for chapter_id in ACCEPTED_CHAPTER_IDS:
        assert by_id[chapter_id]["accepted"] is True
        assert by_id[chapter_id]["human_status_exact"] == HUMAN_ACCEPTED_STATUS
        assert by_id[chapter_id]["manifest_path"]
    for chapter_id in PENDING_CHAPTER_IDS:
        assert by_id[chapter_id]["pending_human_review"] is True
        assert by_id[chapter_id]["accepted"] is False
        assert by_id[chapter_id]["human_status_exact"] != HUMAN_ACCEPTED_STATUS


def test_historical_versions_ch002_ch012_ch018(inventory):
    by_id = {row["chapter_id"]: row for row in inventory["chapters"]}
    assert Path(by_id["CH002"]["json_path"]) == ch002_approved_json_path()
    assert Path(by_id["CH002"]["json_path"]) != ch002_original_json_path()
    assert "chapter_candidate_authorial_v2" in by_id["CH012"]["json_path"]
    assert Path(by_id["CH012"]["json_path"]) != ch012_original_json_path()
    assert "book_generation_4b221_ch018" in by_id["CH018"]["json_path"]
    assert inventory["ch002_recovered_used"] is True
    assert inventory["ch012_authorial_v2_used"] is True
    assert inventory["ch018_accepted_used"] is True


def test_order_sections_ideas_and_statuses(payload, inventory, corpus):
    ids = [chapter["chapter_id"] for chapter in payload["chapters"]]
    assert ids == list(CANONICAL_CHAPTER_IDS)
    assert payload["chapter_count"] == 19
    assert payload["section_count"] == EXPECTED_SECTION_COUNT
    assert payload["idea_coverage_count"] == EXPECTED_IDEA_COUNT
    assert payload["title"] == BOOK_TITLE
    assert payload["editorial_status"] == BOOK_STATUS
    assert payload["document_version"] == BOOK_VERSION
    assert payload["editorial_status"] != HUMAN_ACCEPTED_STATUS
    for chapter in payload["chapters"]:
        if chapter["chapter_id"] in ACCEPTED_CHAPTER_IDS:
            assert chapter["editorial_status"] == HUMAN_ACCEPTED_STATUS
        else:
            assert chapter["editorial_status"] == STRUCTURAL_STATUS
            assert chapter["human_acceptance_status"] != HUMAN_ACCEPTED_STATUS
    integrity = validate_book_integrity(inventory=inventory, payload=payload)
    assert integrity["status"] == "PASS"
    assert integrity["section_count"] == EXPECTED_SECTION_COUNT
    assert integrity["idea_coverage_count"] == EXPECTED_IDEA_COUNT
    schema = validate_book_schema(payload, corpus=corpus)
    assert schema["status"] in {"PASS", "REVIEW"}
    Book.from_dict(payload)


def test_paragraph_and_provenance_integrity(payload, inventory):
    source = collect_source_paragraphs(inventory)
    book = book_paragraph_texts(payload)
    assert source == book
    integrity = validate_book_integrity(inventory=inventory, payload=payload)
    assert integrity["paragraph_integrity"] == "PASS"
    assert integrity["provenance_integrity"] == "PASS"
    assert integrity["comparison"]["prose_added"] == 0
    assert integrity["comparison"]["prose_removed"] == 0
    assert integrity["comparison"]["prose_modified"] == 0
    assert integrity["markdown_comparison"] == "PASS"
    assert integrity["comparison"]["punctuation_normalized"] is False


def test_schema_reproducibility_and_word_contract(payload, inventory, corpus):
    schema = validate_book_schema(payload, corpus=corpus)
    assert schema["status"] in {"PASS", "REVIEW"}
    assert schema["compatible_with_book_1_0"] is True
    second = build_book_payload(
        inventory=inventory,
        corpus=corpus,
        generated_at=_FIXED_AT,
    )
    assert reproducibility_view(payload) == reproducibility_view(second)
    word = assess_word_readiness(payload)
    assert word["status"] == "PASS"
    assert word["docx_generated"] is False
    assert word["graphic_decisions_in_content"] is False
    observations = load_editorial_observations()
    assert observations["preserved"] is True
    assert observations["strengthened_formulations"]["count"] == 8
    assert observations["references_and_examples"]["count"] == 19
    assert observations["continuity"]["count"] == 13
    assert observations["texts_modified_to_resolve_them"] is False


def test_overwrite_protection_and_atomic_publication(tmp_path, payload):
    dest = tmp_path / "analysis" / "book.json"
    audit = tmp_path / "audit" / "book.json"
    first = publish_atomic(payload, destination=dest, audit_copy=audit)
    assert first["atomic"] is True
    assert dest.is_file()
    assert audit.is_file()
    assert not dest.with_name("book.json.partial").exists()
    assert content_hash(dest.read_text(encoding="utf-8")) == first["sha256"]
    second = publish_atomic(payload, destination=dest, audit_copy=audit)
    assert second["action"] == "idempotent"
    foreign = tmp_path / "protected" / "book.json"
    foreign.parent.mkdir(parents=True)
    foreign.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "editorial_status": "HUMAN_EDITORIALLY_ACCEPTED",
                "document_version": "final-v1",
                "phase": "OTHER",
                "protection": {"protected": True},
                "chapters": [],
            }
        ),
        encoding="utf-8",
    )
    existing = inspect_existing_book(foreign)
    assert existing["protected"] is True
    with pytest.raises(BookPrintReviewCanonical4229Error):
        assert_publication_allowed(existing, new_sha256="abc")
    with pytest.raises(Exception):
        write_book(tmp_path / "blocked.json", {"schema_version": "1.0"})


def test_phase_runner_offline_without_publishing():
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=False,
        run_tests=False,
        publish=False,
        generated_at=_FIXED_AT,
    )
    header = result.bundle["header"]
    assert header["provider_calls"] == 0
    assert header["anthropic_http"] == 0
    assert header["openai_http"] == 0
    assert header["book_title"] == BOOK_TITLE
    assert header["book_status"] == BOOK_STATUS
    assert header["book_version"] == BOOK_VERSION
    assert header["chapters"] == "19 / 19"
    assert header["sections"] == f"{EXPECTED_SECTION_COUNT} / {EXPECTED_SECTION_COUNT}"
    assert header["idea_coverage"] == f"{EXPECTED_IDEA_COUNT} / {EXPECTED_IDEA_COUNT}"
    assert header["human_accepted_chapters"] == 6
    assert header["human_review_pending_chapters"] == 13
    assert header["paragraph_integrity"] == "PASS"
    assert header["provenance_integrity"] == "PASS"
    assert header["markdown_comparison"] == "PASS"
    assert header["schema_validation"] in {"PASS", "REVIEW"}
    assert header["word_renderer_readiness"] in {"PASS", "PARTIAL"}
    assert header["editorial_observations_preserved"] == "YES"
    assert header["result"] in {"PASS", "PARTIAL"}
    assert "DOCX = NOT GENERATED" in result.bundle["report_text"]
    assert "PDF = NOT GENERATED" in result.bundle["report_text"]
    assert "VISUAL DIRECTION = NOT STARTED" in result.bundle["report_text"]
    payload = result.bundle["book_payload"]
    assert payload["title"] == BOOK_TITLE
    assert not any(phase_audit_dir().glob("*.docx"))
    assert not any(phase_audit_dir().glob("*.pdf"))


def test_4b1_publication_helper_stays_blocked(tmp_path):
    from app.book_generation.errors import BookPublicationBlocked

    with pytest.raises(BookPublicationBlocked):
        write_book(tmp_path / "book.json", {"schema_version": "1.0"})


def test_existing_production_book_if_present_is_this_draft():
    path = production_book_path()
    if not path.is_file():
        return
    existing = inspect_existing_book(path)
    assert existing["status"] == BOOK_STATUS
    assert existing["version"] == BOOK_VERSION
    assert existing["protected"] is False
