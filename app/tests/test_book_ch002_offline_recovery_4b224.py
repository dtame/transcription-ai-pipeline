"""Phase 4B.2.24 — offline CH002 recovery and CH001 review. Network is not used."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from app.book_ch002_offline_recovery_4b224.chapter_io import (
    find_candidate_paragraph,
    load_json,
    paragraph_ids,
)
from app.book_ch002_offline_recovery_4b224.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_TERRA_CALLS,
    CH001_FLAGGED_SENTENCE,
    CH001_STATUS,
    CONSUMED_4B217_SCOPE,
    CONSUMED_4B218_SCOPE,
    CONSUMED_4B219_SCOPE,
    CONSUMED_4B220_SCOPE,
    CONSUMED_4B221_SCOPE,
    CONSUMED_4B222_SCOPE,
    CONSUMED_4B223_SCOPE,
    EMPTY_PARAGRAPH_ID,
    EXPECTED_CH002_IDEA_COUNT,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    PUBLICATION_AUTHORIZED,
    RECOVERED_STATUS,
    RESUME_CHAPTER_IDS,
    TARGET_CHAPTER_ID,
)
from app.book_ch002_offline_recovery_4b224.forensic import inspect_ch002
from app.book_ch002_offline_recovery_4b224.guard import (
    BookCh002OfflineRecovery4224Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_ch002_offline_recovery_4b224.hashes import snapshot
from app.book_ch002_offline_recovery_4b224.paths import (
    accepted_chapter_json_path,
    batch01_lock_path,
    ch018_json_path,
    original_candidate_json_path,
    original_lock_file,
    original_raw_response_path,
    production_book_path,
)
from app.book_ch002_offline_recovery_4b224.recovery import (
    proposed_empty_unprovenanced_strip,
    remove_empty_paragraph,
)
from app.book_ch002_offline_recovery_4b224.runner import run_phase
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_generation_4b223.constants import FAITHFUL_PROMPT_1_1
from app.book_generation_4b223.lock import lock_already_consumed


def test_offline_authorizations_and_prompt_isolation():
    assert PUBLICATION_AUTHORIZED is False
    assert AUTHORIZED_ANTHROPIC_CALLS == 0
    assert AUTHORIZED_OPENAI_CALLS == 0
    assert AUTHORIZED_SONNET_CALLS == 0
    assert AUTHORIZED_TERRA_CALLS == 0
    assert FAITHFUL_PROMPT_1_1_ACTIVATED is False
    assert_offline_only()
    with pytest.raises(ValueError):
        resolve_prompt_module(FAITHFUL_PROMPT_1_1)


def test_consumed_authorizations_cannot_be_reused():
    validate_authorization_scope(AUTHORIZATION_SCOPE)
    for scope in (
        CONSUMED_4B217_SCOPE,
        CONSUMED_4B218_SCOPE,
        CONSUMED_4B219_SCOPE,
        CONSUMED_4B220_SCOPE,
        CONSUMED_4B221_SCOPE,
        CONSUMED_4B222_SCOPE,
        CONSUMED_4B223_SCOPE,
        "WRONG",
    ):
        with pytest.raises(BookCh002OfflineRecovery4224Error):
            validate_authorization_scope(scope)


def test_canonical_ch012_ch018_and_locks():
    snap = snapshot()
    assert snap["canonical_match_expected"] is True
    assert snap["original_match_expected"] is True
    assert snap["accepted_match_expected"] is True
    assert snap["ch018_match_expected"] is True
    assert production_book_path().is_file() is False
    assert accepted_chapter_json_path().is_file()
    assert ch018_json_path().is_file()
    assert lock_already_consumed(original_lock_file("CH001")) is True
    assert lock_already_consumed(original_lock_file("CH002")) is True
    assert lock_already_consumed(original_lock_file("CH003")) is False
    assert lock_already_consumed(original_lock_file("CH004")) is False
    assert batch01_lock_path().is_file()


def test_forensic_empty_paragraph_is_model_emitted():
    forensic = inspect_ch002()
    raw_target = (forensic.get("raw_response") or {}).get("target") or {}
    cand_target = (forensic.get("candidate") or {}).get("target") or {}
    assert raw_target.get("exists") is True
    assert raw_target.get("empty") is True
    assert raw_target.get("contains_idea") is False
    assert raw_target.get("contains_src") is False
    assert cand_target.get("paragraph_id") == EMPTY_PARAGRAPH_ID
    assert cand_target.get("empty") is True
    assert forensic.get("recovery_admissible_from_forensics") is True
    assert (forensic.get("introduction") or {}).get("introduced_by_model") is True
    assert (forensic.get("introduction") or {}).get("introduced_by_parsing") is False
    assert (forensic.get("structural_validation") or {}).get("status") == "FAIL"


def test_recovery_rules_refuse_protected_paragraphs():
    original = load_json(original_candidate_json_path(TARGET_CHAPTER_ID))
    with pytest.raises(BookCh002OfflineRecovery4224Error):
        remove_empty_paragraph(original, paragraph_id="P000001")
    with pytest.raises(BookCh002OfflineRecovery4224Error):
        remove_empty_paragraph(original, paragraph_id="P000004")
    synthetic = deepcopy(original)
    located = find_candidate_paragraph(synthetic, EMPTY_PARAGRAPH_ID)
    assert located is not None
    located[2]["example_refs"] = ["EX001"]
    located[2]["evidence_handles"] = ["EX001"]
    with pytest.raises(BookCh002OfflineRecovery4224Error):
        remove_empty_paragraph(synthetic, paragraph_id=EMPTY_PARAGRAPH_ID)
    synthetic_ref = deepcopy(original)
    located = find_candidate_paragraph(synthetic_ref, EMPTY_PARAGRAPH_ID)
    assert located is not None
    located[2]["reference_refs"] = ["REF002"]
    located[2]["evidence_handles"] = ["REF002"]
    with pytest.raises(BookCh002OfflineRecovery4224Error):
        remove_empty_paragraph(synthetic_ref, paragraph_id=EMPTY_PARAGRAPH_ID)


def test_recovery_removes_only_p000008_and_keeps_ids():
    original = load_json(original_candidate_json_path(TARGET_CHAPTER_ID))
    result = remove_empty_paragraph(original)
    recovered = result["recovered"]
    assert EMPTY_PARAGRAPH_ID not in paragraph_ids(recovered)
    assert result["other_paragraph_ids_unchanged"] is True
    assert result["ideas_preserved"] is True
    assert len(result["ideas_after"]) == EXPECTED_CH002_IDEA_COUNT
    assert find_candidate_paragraph(original, EMPTY_PARAGRAPH_ID) is not None
    raw = load_json(original_raw_response_path(TARGET_CHAPTER_ID))
    assert any(
        para.get("h") == "p8" and para.get("t") == ""
        for section in (raw.get("parsed") or {}).get("sections") or []
        for para in section.get("paras") or []
    )


def test_isolated_proposal_does_not_touch_raw_or_renumber():
    original = load_json(original_candidate_json_path(TARGET_CHAPTER_ID))
    proposal = proposed_empty_unprovenanced_strip(original)
    assert proposal["removed_paragraph_ids"] == [EMPTY_PARAGRAPH_ID]
    assert proposal["renumbered"] is False
    assert proposal["raw_response_modified"] is False
    assert proposal["production_pipeline_modified"] is False
    raw = load_json(original_raw_response_path(TARGET_CHAPTER_ID))
    assert any(para.get("h") == "p8" for section in (raw.get("parsed") or {}).get("sections") or [] for para in section.get("paras") or [])


def test_offline_phase_recovers_without_provider(tmp_path: Path):
    before = snapshot()
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=False,
        run_tests=False,
    )
    after = snapshot()
    header = result.bundle["header"]
    assert result.mode == "OFFLINE"
    assert header["result"] == "PASS"
    assert header["provider_calls"] == 0
    assert header["ch001_status"] == CH001_STATUS
    assert header["ch002_recovery"] == RECOVERED_STATUS
    assert header["ch002_recovered_contract"] == "PASS"
    assert header["ch002_idea_coverage"] == f"{EXPECTED_CH002_IDEA_COUNT} / {EXPECTED_CH002_IDEA_COUNT}"
    assert header["ready_for_ch001_human_review"] == "YES"
    assert header["ready_for_ch002_human_review"] == "YES"
    review = result.bundle["ch001_human_editorial_review_packet"]
    assert CH001_FLAGGED_SENTENCE in (review.get("passages_requiring_attention") or [{}])[0].get(
        "text", ""
    )
    assert review["automatic_editorial_correction"] is False
    resume = result.bundle["batch01_resume_plan"]
    assert resume["resume_chapters"] == list(RESUME_CHAPTER_IDS)
    assert resume["executed_this_phase"] is False
    assert resume["this_plan_is_not_authorization"] is True
    assert resume["historical_facts_unmodified"]["ledger_remaining_budget_usd"] is not None
    assert resume["updated_forecast"]["historical_remaining_budget_is_authorization"] is False
    assert before["canonical"] == after["canonical"]
    assert before["batch01_originals"] == after["batch01_originals"]
    assert before["locks"] == after["locks"]
    assert production_book_path().is_file() is False
    del tmp_path


def test_phase_writes_isolated_audits(tmp_path: Path):
    before = snapshot()
    result = run_phase(
        authorization_scope=AUTHORIZATION_SCOPE,
        write_artifacts=True,
        run_tests=False,
        root=tmp_path,
    )
    after = snapshot()
    assert result.accepted is True
    audit = tmp_path / "audit" / "book_ch002_offline_recovery_4b224"
    assert (audit / "preflight.json").is_file()
    assert (audit / "ch002_empty_paragraph_forensic_review.json").is_file()
    assert (audit / "chapter_candidate_recovered.json").is_file()
    assert (audit / "chapter_candidate_recovered.md").is_file()
    assert (audit / "recovery_diff.json").is_file()
    assert (audit / "recovery_manifest.json").is_file()
    assert (audit / "recovery_validation.json").is_file()
    assert (audit / "ch001_human_editorial_review_packet.md").is_file()
    assert (audit / "batch01_resume_plan.json").is_file()
    assert (audit / "empty_paragraph_prevention_analysis.md").is_file()
    assert (tmp_path / "audit" / "PHASE_4B224_CH002_OFFLINE_RECOVERY_AND_CH001_REVIEW_REPORT.md").is_file()
    assert before["canonical"] == after["canonical"]
    assert before["batch01_originals"] == after["batch01_originals"]
    assert before["locks"] == after["locks"]
    assert lock_already_consumed(original_lock_file("CH002")) is True
    assert production_book_path().is_file() is False
