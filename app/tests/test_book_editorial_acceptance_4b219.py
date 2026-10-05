"""Phase 4B.2.19 — offline editorial acceptance. Network is not used."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.book_editorial_acceptance_4b219.chapter_io import (
    load_accepted_chapter,
    load_accepted_markdown,
    paragraph_idea_handles,
    paragraph_ids,
    section_ids,
)
from app.book_editorial_acceptance_4b219.consistency import compare_markdown_json
from app.book_editorial_acceptance_4b219.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    CHAPTER_ID,
    CLASS_CONTENT_SUPPORTED,
    CLASS_NOT_SUPPORTED,
    CONSUMED_4B217_SCOPE,
    CONSUMED_4B218_SCOPE,
    EXPECTED_ACCEPTED_JSON_SHA256,
    EXPECTED_ACCEPTED_MD_SHA256,
    FAITHFUL_PROMPT_1_1,
    HISTORICAL_4B217_STATUS,
    HISTORICAL_4B218_STATUS,
    PARAGRAPH_IDS,
    PUBLICATION_AUTHORIZED,
    RECOMMENDED_OPTION,
    RECORDING_DATE,
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
    review_idea_mappings,
    src_overlap_alone_is_not_support,
)
from app.book_editorial_acceptance_4b219.paths import (
    accepted_chapter_json_path,
    accepted_chapter_md_path,
    original_chapter_json_path,
    original_lock_path,
    production_book_path,
)
from app.book_editorial_acceptance_4b219.prompt_readiness import generator_prompt_readiness
from app.book_editorial_acceptance_4b219.runner import run_phase
from app.book_editorial_acceptance_4b219.scenarios import evaluate_offline_scenarios
from app.book_generation.prompt_select import resolve_prompt_module


def test_historical_labels_and_offline_authorizations():
    assert HISTORICAL_4B217_STATUS == "PARTIAL"
    assert HISTORICAL_4B218_STATUS == "PASS"
    assert PUBLICATION_AUTHORIZED is False
    assert AUTHORIZED_ANTHROPIC_CALLS == 0
    assert AUTHORIZED_OPENAI_CALLS == 0
    assert AUTHORIZED_SONNET_CALLS == 0
    assert AUTHORIZED_TERRA_CALLS == 0
    assert_offline_only()
    with pytest.raises(ValueError):
        resolve_prompt_module(FAITHFUL_PROMPT_1_1)


def test_consumed_authorizations_cannot_be_reused():
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    with pytest.raises(BookEditorialAcceptance4219Error):
        validate_authorization_scope(CONSUMED_4B217_SCOPE)
    with pytest.raises(BookEditorialAcceptance4219Error):
        validate_authorization_scope(CONSUMED_4B218_SCOPE)
    with pytest.raises(BookEditorialAcceptance4219Error):
        validate_authorization_scope("WRONG")


def test_accepted_chapter_ids_and_unc029():
    chapter = load_accepted_chapter()
    assert chapter["chapter_id"] == CHAPTER_ID
    assert paragraph_ids(chapter) == PARAGRAPH_IDS
    assert section_ids(chapter) == SECTION_IDS
    unc = [
        paragraph
        for section in chapter["sections"]
        for paragraph in section["paragraphs"]
        if UNCERTAINTY_ID in (paragraph.get("uncertainty_refs") or [])
    ]
    assert unc
    assert "unclear" in unc[0]["text"]
    assert paragraph_idea_handles(chapter) == []


def test_markdown_json_consistency_and_fourteen_paragraphs():
    chapter = load_accepted_chapter()
    markdown = load_accepted_markdown()
    report = compare_markdown_json(chapter, markdown)
    assert report["consistent"] is True
    assert report["freeze_blocked"] is False
    assert report["json_paragraph_count"] == 14
    assert report["markdown_paragraph_count"] == 14
    assert report["prose_mismatches"] == []
    assert report["rewritten"] is False


def test_src_overlap_alone_is_not_content_support():
    assert src_overlap_alone_is_not_support() is True
    assert (
        classify_content(
            missing_required=["missing-claim"],
            missing_groups=1,
            required_groups=1,
        )
        == CLASS_NOT_SUPPORTED
    )
    assert (
        classify_content(missing_required=[], missing_groups=0, required_groups=1)
        == CLASS_CONTENT_SUPPORTED
    )


def test_idea_review_does_not_write_handles():
    chapter = load_accepted_chapter()
    before = paragraph_idea_handles(chapter)
    review = review_idea_mappings(chapter)
    after = load_accepted_chapter()
    assert before == []
    assert paragraph_idea_handles(after) == []
    assert review["written_into_paragraph_evidence"] is False
    assert review["src_overlap_alone_rejected"] is True
    assert all(row["confirmed_on_src_overlap_alone"] is False for row in review["mappings"])
    assert all(row["applied_to_accepted_chapter"] is False for row in review["mappings"])
    assert len(review["mappings"]) == 11
    assert review["counts"][CLASS_CONTENT_SUPPORTED] == 11
    assert review["counts"][CLASS_NOT_SUPPORTED] == 0


def test_canonical_and_accepted_hashes():
    snap = snapshot()
    assert snap["canonical_match_expected"] is True
    assert snap["original_match_expected"] is True
    assert snap["accepted_match_expected"] is True
    assert production_book_path().is_file() is False
    assert original_chapter_json_path().is_file()
    assert original_lock_path().is_file()
    assert accepted_chapter_json_path().is_file()
    assert accepted_chapter_md_path().is_file()
    assert (
        snap["accepted_chapter"]["chapter_candidate_authorial_v2_json"]["sha256"]
        == EXPECTED_ACCEPTED_JSON_SHA256
    )
    assert (
        snap["accepted_chapter"]["chapter_candidate_authorial_v2_md"]["sha256"]
        == EXPECTED_ACCEPTED_MD_SHA256
    )


def test_prompt_readiness_is_candidate_only():
    prompt = generator_prompt_readiness()
    assert prompt["version"] == FAITHFUL_PROMPT_1_1
    assert prompt["activated"] is False
    assert prompt["ready_as_reference_candidate"] is True
    assert prompt["ready_for_production"] is False
    assert prompt["automatically_promoted"] is False
    assert all(prompt["checks"].values())


def test_offline_scenarios_pass():
    report = evaluate_offline_scenarios()
    assert report["failed"] == 0
    assert report["failed_ids"] == []
    assert report["real_provider_calls"] == 0
    assert report["not_a_terra_validation"] is True


def test_phase_writes_isolated_audits_without_touching_accepted(tmp_path: Path):
    before = snapshot()
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=True,
        run_tests=False,
        root=tmp_path,
    )
    after = snapshot()
    assert result.accepted is True
    header = result.bundle["header"]
    assert header["result"] == "PASS"
    assert header["provider_calls"] == 0
    assert header["human_editorial_acceptance"] == "YES"
    assert header["p000001_accepted"] == "YES"
    assert header["recommended_next_option"] == RECOMMENDED_OPTION == "C"
    assert header["ready_for_controlled_scale_up"] == "NO"
    assert header["semantic_certification"] == "NOT PERFORMED"
    assert result.bundle["ch012_editorial_acceptance"]["recording_date"] == RECORDING_DATE
    assert result.bundle["ch012_editorial_acceptance"]["not_a_digital_signature"] is True
    assert result.bundle["ch012_accepted_editorial_manifest"]["freeze_status"] == "FROZEN"
    audit = tmp_path / "audit" / "book_editorial_acceptance_4b219"
    assert (audit / "ch012_editorial_acceptance.json").is_file()
    assert (audit / "ch012_accepted_editorial_manifest.json").is_file()
    assert (audit / "idea_content_mapping_review.json").is_file()
    assert not (
        tmp_path / "audit" / "book_authorial_voice_4b218" / "chapter_candidate_authorial_v2.json"
    ).exists()
    assert accepted_chapter_json_path().is_file()
    assert before["accepted_chapter"] == after["accepted_chapter"]
    assert before["original_chapter"] == after["original_chapter"]
    assert production_book_path().is_file() is False
    again = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=True,
        run_tests=False,
        root=tmp_path,
    )
    assert again.bundle["header"]["result"] == "PASS"
    assert (
        again.bundle["ch012_editorial_acceptance"]
        == result.bundle["ch012_editorial_acceptance"]
    )
    assert (
        again.bundle["ch012_accepted_editorial_manifest"]
        == result.bundle["ch012_accepted_editorial_manifest"]
    )
