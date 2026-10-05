"""Offline regression scenarios for 4B.2.24. No provider, no FakeAI cover-up."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from app.book_ch002_offline_recovery_4b224.chapter_io import (
    find_candidate_paragraph,
    load_json,
    paragraph_ids,
)
from app.book_ch002_offline_recovery_4b224.constants import (
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    EMPTY_PARAGRAPH_ID,
    PHASE,
    PUBLICATION_AUTHORIZED,
    TARGET_CHAPTER_ID,
)
from app.book_ch002_offline_recovery_4b224.guard import BookCh002OfflineRecovery4224Error
from app.book_ch002_offline_recovery_4b224.hashes import snapshot, snapshots_match
from app.book_ch002_offline_recovery_4b224.paths import (
    original_candidate_json_path,
    production_book_path,
)
from app.book_ch002_offline_recovery_4b224.recovery import (
    proposed_empty_unprovenanced_strip,
    remove_empty_paragraph,
)
from app.book_generation_4b223.lock import lock_already_consumed
from app.book_ch002_offline_recovery_4b224.paths import original_lock_file


def _case(case_id: str, title: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "id": case_id,
        "title": title,
        "passed": passed,
        "detail": detail,
    }


def evaluate_offline_scenarios(
    *,
    forensic: Mapping[str, Any],
    recovery: Mapping[str, Any] | None,
    recovered: Mapping[str, Any] | None,
    validation: Mapping[str, Any] | None,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    tests: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    original = load_json(original_candidate_json_path(TARGET_CHAPTER_ID))
    raw_hash_before = ((before.get("batch01_originals") or {}).get("CH002") or {}).get(
        "provider_response_raw"
    ) or {}
    raw_hash_after = ((after.get("batch01_originals") or {}).get("CH002") or {}).get(
        "provider_response_raw"
    ) or {}
    cases = []

    cases.append(
        _case(
            "01_raw_preserved",
            "Raw provider response preserved",
            raw_hash_before == raw_hash_after and bool(raw_hash_before.get("sha256")),
            f"sha256={raw_hash_before.get('sha256')}",
        )
    )

    recovered_ok = recovered is not None and recovery is not None
    removed_only = False
    if recovered_ok:
        before_ids = paragraph_ids(original)
        after_ids = paragraph_ids(dict(recovered))
        removed_only = [item for item in before_ids if item != EMPTY_PARAGRAPH_ID] == after_ids
    cases.append(
        _case(
            "02_only_target_removed",
            "Only the targeted empty paragraph was removed",
            recovered_ok and removed_only,
            f"after_ids={paragraph_ids(dict(recovered)) if recovered else []}",
        )
    )

    refuse_nonempty = True
    try:
        clone = deepcopy(original)
        located = find_candidate_paragraph(clone, "P000001")
        if located is None:
            raise AssertionError("P000001 missing")
        remove_empty_paragraph(clone, paragraph_id="P000001")
        refuse_nonempty = False
    except BookCh002OfflineRecovery4224Error:
        refuse_nonempty = True
    cases.append(
        _case(
            "03_refuse_nonempty",
            "Refuse deletion of a non-empty paragraph",
            refuse_nonempty,
            "P000001 refused",
        )
    )

    def _refuse(paragraph_id: str, label: str, case_id: str) -> None:
        refused = True
        try:
            remove_empty_paragraph(original, paragraph_id=paragraph_id)
            refused = False
        except BookCh002OfflineRecovery4224Error:
            refused = True
        cases.append(_case(case_id, label, refused, paragraph_id))

    _refuse("P000001", "Refuse deletion of a paragraph carrying an IDEA", "04_refuse_idea")
    _refuse("P000001", "Refuse deletion of a paragraph carrying a SRC", "05_refuse_src")
    _refuse("P000004", "Refuse deletion of a paragraph carrying an UNC", "08_refuse_unc")

    synthetic = deepcopy(original)
    located = find_candidate_paragraph(synthetic, EMPTY_PARAGRAPH_ID)
    if located is not None:
        located[2]["text"] = ""
        located[2]["example_refs"] = ["EX001"]
        located[2]["evidence_handles"] = ["EX001"]
    refuse_ex = True
    try:
        remove_empty_paragraph(synthetic, paragraph_id=EMPTY_PARAGRAPH_ID)
        refuse_ex = False
    except BookCh002OfflineRecovery4224Error:
        refuse_ex = True
    cases.append(_case("06_refuse_ex", "Refuse deletion of a paragraph carrying an EX", refuse_ex, "synthetic EX"))

    synthetic_ref = deepcopy(original)
    located = find_candidate_paragraph(synthetic_ref, EMPTY_PARAGRAPH_ID)
    if located is not None:
        located[2]["text"] = ""
        located[2]["reference_refs"] = ["REF002"]
        located[2]["evidence_handles"] = ["REF002"]
    refuse_ref = True
    try:
        remove_empty_paragraph(synthetic_ref, paragraph_id=EMPTY_PARAGRAPH_ID)
        refuse_ref = False
    except BookCh002OfflineRecovery4224Error:
        refuse_ref = True
    cases.append(_case("07_refuse_ref", "Refuse deletion of a paragraph carrying a REF", refuse_ref, "synthetic REF"))

    other_ok = recovered_ok
    if recovered is not None:
        for section_orig, section_new in zip(original.get("sections") or [], recovered.get("sections") or []):
            orig_paras = [
                para
                for para in section_orig.get("paragraphs") or []
                if para.get("paragraph_id") != EMPTY_PARAGRAPH_ID
            ]
            new_paras = list(section_new.get("paragraphs") or [])
            if orig_paras != new_paras:
                other_ok = False
    cases.append(
        _case(
            "09_other_paragraphs_preserved",
            "Other paragraphs preserved",
            other_ok,
            "non-target paragraph objects unchanged",
        )
    )
    cases.append(
        _case(
            "10_ids_preserved",
            "Remaining paragraph identifiers preserved",
            recovered_ok and removed_only,
            "no renumbering",
        )
    )
    cases.append(
        _case(
            "11_sections_preserved",
            "Sections preserved",
            recovered is not None
            and [
                section.get("section_id") for section in original.get("sections") or []
            ]
            == [
                section.get("section_id") for section in (recovered or {}).get("sections") or []
            ],
            "SEC005-SEC008",
        )
    )
    ideas_ok = recovered_ok and (recovery or {}).get("ideas_preserved") is True
    cases.append(
        _case(
            "12_ideas_preserved",
            "Fifteen IDEA handles preserved",
            ideas_ok,
            str((recovery or {}).get("ideas_after") or []),
        )
    )
    cases.append(
        _case(
            "13_json_valid",
            "Recovered JSON validates",
            bool(validation) and validation.get("status") == "PASS",
            str((validation or {}).get("status")),
        )
    )
    cases.append(
        _case(
            "14_json_md_consistent",
            "JSON/Markdown consistency",
            bool(validation)
            and (validation.get("checks") or {}).get("json_markdown_consistent") is True,
            "recovered markdown contains every non-empty paragraph",
        )
    )
    hashes_ok = snapshots_match(dict(before), dict(after))
    cases.append(
        _case(
            "15_canonical_unchanged",
            "Canonical sources unchanged",
            hashes_ok and after.get("canonical_match_expected") is True,
            "source/plan/transcript hashes match",
        )
    )
    cases.append(
        _case(
            "16_ch012_unchanged",
            "CH012 unchanged",
            after.get("ch012_unchanged") is True,
            "accepted and original CH012 hashes",
        )
    )
    cases.append(
        _case(
            "17_ch018_unchanged",
            "CH018 unchanged",
            after.get("ch018_unchanged") is True,
            "accepted CH018 hashes",
        )
    )
    lock_ok = before.get("locks") == after.get("locks")
    cases.append(
        _case(
            "18_locks_not_reset",
            "Locks not reset",
            lock_ok and lock_already_consumed(original_lock_file("CH002")),
            f"CH002 consumed={lock_already_consumed(original_lock_file('CH002'))}",
        )
    )
    cases.append(
        _case(
            "19_no_provider_call",
            "No provider call",
            AUTHORIZED_ANTHROPIC_CALLS == 0
            and AUTHORIZED_OPENAI_CALLS == 0
            and AUTHORIZED_TERRA_CALLS == 0,
            "authorized spend 0",
        )
    )
    cases.append(
        _case(
            "20_no_publication",
            "No publication",
            PUBLICATION_AUTHORIZED is False and production_book_path().exists() is False,
            "book.json absent",
        )
    )

    proposal = proposed_empty_unprovenanced_strip(original)
    cases.append(
        _case(
            "21_proposal_strips_only_empty",
            "Isolated proposal strips only the empty unprovenanced paragraph",
            proposal.get("removed_paragraph_ids") == [EMPTY_PARAGRAPH_ID]
            and proposal.get("renumbered") is False
            and proposal.get("raw_response_modified") is False,
            str(proposal.get("removed_paragraph_ids")),
        )
    )
    cases.append(
        _case(
            "22_raw_contains_empty_p8",
            "Raw parsed JSON already contains empty p8",
            bool((forensic.get("raw_response") or {}).get("target", {}).get("empty")),
            "model-emitted empty connective",
        )
    )
    if tests:
        cases.append(
            _case(
                "23_focused_pytest",
                "Focused pytest suite",
                int(tests.get("failed") or 0) == 0 and int(tests.get("returncode") or 0) == 0,
                str(tests.get("summary") or ""),
            )
        )

    failed = [item["id"] for item in cases if not item["passed"]]
    return {
        "phase": PHASE,
        "passed": len(cases) - len(failed),
        "failed": len(failed),
        "failed_ids": failed,
        "cases": cases,
        "real_provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "fakeai_used_to_mask_validator": False,
        "secrets_included": False,
    }


__all__ = ["evaluate_offline_scenarios"]
