"""Phase 4B.2.18 — offline authorial voice. Network is not used."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.book_authorial_voice_4b218.chapter_io import (
    load_original_chapter,
    paragraph_ids,
    section_ids,
)
from app.book_authorial_voice_4b218.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIAL_VOICE_POLICY_VERSION,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    CONSUMED_4B217_SCOPE,
    EXPECTED_PARAGRAPH_IDS,
    EXPECTED_SECTION_IDS,
    EXPECTED_UNCERTAINTY_ID,
    FAITHFUL_PROMPT_1_0_VERSION,
    FAITHFUL_PROMPT_1_1_VERSION,
    HISTORICAL_4B216_STATUS,
    HISTORICAL_4B217_STATUS,
    HISTORICAL_PROMPT_V10,
    HISTORICAL_PROMPT_V101,
    PUBLICATION_AUTHORIZED,
    TARGET_CHAPTER_ID,
)
from app.book_authorial_voice_4b218.correction import (
    P000001_ORIGINAL,
    P000008_CORRECTED,
    apply_corrections,
    correction_catalog,
)
from app.book_authorial_voice_4b218.guard import (
    BookAuthorialVoice4218Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_authorial_voice_4b218.hashes import snapshot
from app.book_authorial_voice_4b218.narrative import detect_external_frames
from app.book_authorial_voice_4b218.paths import (
    original_chapter_json_path,
    original_lock_path,
    production_book_path,
)
from app.book_authorial_voice_4b218.policy import authorial_voice_policy
from app.book_authorial_voice_4b218.prompt_candidate import prompt_bundle
from app.book_authorial_voice_4b218.runner import run_phase
from app.book_authorial_voice_4b218.scenarios import evaluate_offline_scenarios
from app.book_generation.constants import BOOK_GENERATOR_PROMPT_VERSION
from app.book_generation.prompt import FROZEN_PROMPT_SHA256, prompt_bundle as frozen_v10
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation.prompt_v101 import prompt_bundle as frozen_v101
from app.book_editorial_alignment_4b216.prompt_candidate import (
    prompt_bundle as faithful_1_0,
)


def test_historical_labels_and_prompts_stay_put():
    assert HISTORICAL_PROMPT_V101 == BOOK_GENERATOR_PROMPT_VERSION == "book-generator-1.0.1"
    assert HISTORICAL_PROMPT_V10 == "book-generator-1.0"
    assert frozen_v10()["prompt_sha256"] == FROZEN_PROMPT_SHA256
    assert frozen_v101()["version"] == "book-generator-1.0.1"
    assert faithful_1_0()["version"] == FAITHFUL_PROMPT_1_0_VERSION
    assert HISTORICAL_4B216_STATUS == "PASS"
    assert HISTORICAL_4B217_STATUS == "PARTIAL"
    assert PUBLICATION_AUTHORIZED is False
    assert AUTHORIZED_ANTHROPIC_CALLS == 0
    assert AUTHORIZED_OPENAI_CALLS == 0
    assert AUTHORIZED_SONNET_CALLS == 0
    assert AUTHORIZED_TERRA_CALLS == 0
    assert_offline_only()
    with pytest.raises(ValueError):
        resolve_prompt_module(FAITHFUL_PROMPT_1_1_VERSION)
    with pytest.raises(ValueError):
        resolve_prompt_module(FAITHFUL_PROMPT_1_0_VERSION)


def test_consumed_4b217_authorization_cannot_be_reused():
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    with pytest.raises(BookAuthorialVoice4218Error):
        validate_authorization_scope(CONSUMED_4B217_SCOPE)
    with pytest.raises(BookAuthorialVoice4218Error):
        validate_authorization_scope("WRONG")


def test_clear_personal_testimony_and_external_narration():
    frames = detect_external_frames(
        "The speaker recounted a personal experience. He had prayed."
    )
    assert any("speaker recounted" in item.lower() for item in frames)
    assert "I had prayed so intensely" in P000008_CORRECTED
    assert "The speaker recounted" not in P000008_CORRECTED


def test_third_person_biblical_and_other_voices_are_not_forced():
    catalog = {row["paragraph_id"]: row for row in correction_catalog()}
    assert "God spoke to me" in catalog["P000009"]["corrected"]
    assert "God further said" in catalog["P000009"]["corrected"]
    assert catalog["P000001"]["applied"] is False
    assert catalog["P000001"]["original"] == P000001_ORIGINAL


def test_original_chapter_ids_and_unc029():
    chapter = load_original_chapter()
    assert chapter["chapter_id"] == TARGET_CHAPTER_ID
    assert paragraph_ids(chapter) == EXPECTED_PARAGRAPH_IDS
    assert section_ids(chapter) == EXPECTED_SECTION_IDS
    revised = apply_corrections(chapter)
    assert paragraph_ids(revised) == EXPECTED_PARAGRAPH_IDS
    assert section_ids(revised) == EXPECTED_SECTION_IDS
    unc = [
        paragraph
        for section in revised["sections"]
        for paragraph in section["paragraphs"]
        if EXPECTED_UNCERTAINTY_ID in (paragraph.get("uncertainty_refs") or [])
    ]
    assert unc
    assert "unclear" in unc[0]["text"]
    for original_section, revised_section in zip(chapter["sections"], revised["sections"]):
        for before, after in zip(original_section["paragraphs"], revised_section["paragraphs"]):
            assert before["source_refs"] == after["source_refs"]
            assert before["idea_refs"] == after["idea_refs"]
            assert before["paragraph_id"] == after["paragraph_id"]


def test_no_global_rewrite_and_uncertain_left_alone():
    chapter = load_original_chapter()
    revised = apply_corrections(chapter)
    changed = []
    for before_section, after_section in zip(chapter["sections"], revised["sections"]):
        for before, after in zip(before_section["paragraphs"], after_section["paragraphs"]):
            if before["text"] != after["text"]:
                changed.append(before["paragraph_id"])
    assert changed == ["P000003", "P000004", "P000008", "P000009"]
    p1_before = chapter["sections"][0]["paragraphs"][0]["text"]
    p1_after = revised["sections"][0]["paragraphs"][0]["text"]
    assert p1_before == p1_after == P000001_ORIGINAL
    assert apply_corrections(chapter) == revised


def test_policy_and_prompt_1_1():
    policy = authorial_voice_policy()
    assert policy["version"] == AUTHORIAL_VOICE_POLICY_VERSION
    assert policy["activated_in_production"] is False
    bundle = prompt_bundle()
    assert bundle["version"] == FAITHFUL_PROMPT_1_1_VERSION
    assert bundle["activated"] is False
    assert bundle["authorial_voice_present"] is True
    assert bundle["idea_handle_instruction_present"] is True
    assert bundle["forbids_invented_idea_correspondence"] is True
    assert "Stylistic expansion is allowed." not in bundle["system"]
    assert "High stylistic freedom" not in bundle["system"]


def test_canonical_hashes_and_original_lock():
    snap = snapshot()
    assert snap["canonical_match_expected"] is True
    assert production_book_path().is_file() is False
    assert original_chapter_json_path().is_file()
    assert original_lock_path().is_file()
    assert snap["original_chapter"]["provider_lock"]["exists"] is True


def test_offline_scenarios_pass():
    report = evaluate_offline_scenarios()
    assert report["failed"] == 0
    assert report["failed_ids"] == []
    assert report["real_provider_calls"] == 0
    assert report["not_a_terra_validation"] is True


def test_phase_writes_isolated_audits(tmp_path: Path):
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=True,
        run_tests=False,
        root=tmp_path,
    )
    assert result.accepted is True
    header = result.bundle["header"]
    assert header["result"] == "PASS"
    assert header["provider_calls"] == 0
    assert header["corrections_applied"] == 4
    audit = tmp_path / "audit" / "book_authorial_voice_4b218"
    assert (audit / "chapter_candidate_authorial_v2.json").is_file()
    assert (audit / "chapter_candidate_authorial_v2.md").is_file()
    assert (audit / "chapter_diff.md").is_file()
    assert (audit / "authorial_voice_policy.json").is_file()
    assert not (tmp_path / "audit" / "real" / "book_generation_4b217_ch012" / "chapter_candidate.json").exists()
    assert original_chapter_json_path().is_file()
