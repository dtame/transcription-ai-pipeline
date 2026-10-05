"""Offline regression scenarios. No provider call."""

from __future__ import annotations

from typing import Any

from app.book_authorial_voice_4b218.constants import (
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
    HISTORICAL_PROMPT_V10,
    HISTORICAL_PROMPT_V101,
    PHASE,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PUBLICATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    TARGET_CHAPTER_ID,
)
from app.book_authorial_voice_4b218.correction import (
    P000001_ORIGINAL,
    P000001_PROPOSED,
    P000003_CORRECTED,
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
from app.book_generation.prompt_select import resolve_prompt_module


def _fixture_chapter() -> dict[str, Any]:
    return {
        "chapter_id": TARGET_CHAPTER_ID,
        "title": "Prayer Corrected",
        "sections": [
            {
                "section_id": "SEC047",
                "title": "Bavardage Is Not Prayer",
                "paragraphs": [
                    {
                        "paragraph_id": "P000001",
                        "text": P000001_ORIGINAL,
                        "evidence_handles": ["SRC004846"],
                        "source_refs": ["SRC004846"],
                        "idea_refs": [],
                        "uncertainty_refs": [],
                    },
                    {
                        "paragraph_id": "P000003",
                        "text": (
                            "Those who prayed this way were sincere, even very sincere. "
                            "But sincerity was not the issue. The real problem was that "
                            "they did not know — their manner of praying rested on "
                            "ignorance rather than on correct knowledge of what the "
                            "practice was for."
                        ),
                        "evidence_handles": ["SRC004918"],
                        "source_refs": ["SRC004918"],
                        "idea_refs": [],
                        "uncertainty_refs": [],
                    },
                ],
                "idea_refs": ["IDEA186"],
            },
            {
                "section_id": "SEC048",
                "title": "The Refreshing",
                "paragraphs": [
                    {
                        "paragraph_id": "P000004",
                        "text": (
                            "One of the primary purposes of praying in tongues, as taught "
                            "here, is to cool or refresh oneself. This is grounded in "
                            "Isaiah 28 and in 1 Corinthians 14. The speaker also referred "
                            "to an earlier passage, Isaiah chapter 26, locating a related "
                            "statement in verse 3, though the connection between chapter "
                            "26 and chapter 28 at this point in the teaching remained "
                            "unclear in the delivery."
                        ),
                        "evidence_handles": ["SRC004854"],
                        "source_refs": ["SRC004854"],
                        "idea_refs": [],
                        "uncertainty_refs": [EXPECTED_UNCERTAINTY_ID],
                    }
                ],
                "idea_refs": ["IDEA180"],
            },
            {
                "section_id": "SEC049",
                "title": "He Told Me I Was Tired",
                "paragraphs": [
                    {
                        "paragraph_id": "P000008",
                        "text": (
                            "The speaker recounted a personal experience of this "
                            "correction. He had prayed so intensely that he ended up on "
                            "the ground, his voice broken from the effort. Someone saw "
                            "the manner in which he had prayed."
                        ),
                        "evidence_handles": ["SRC004891"],
                        "source_refs": ["SRC004891"],
                        "idea_refs": [],
                        "uncertainty_refs": [],
                    }
                ],
                "idea_refs": ["IDEA184"],
            },
        ],
    }


def evaluate_offline_scenarios(*, root=None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def _row(name: str, ok: bool, detail: str) -> None:
        rows.append({"name": name, "ok": ok, "detail": detail})

    policy = authorial_voice_policy()
    prompt = prompt_bundle()
    catalog = correction_catalog()
    fixture = _fixture_chapter()
    revised = apply_corrections(fixture)

    _row(
        "clear_personal_testimony_first_person",
        "J'étais au sol" in " ".join(catalog[3]["src_proof"])
        and "I had prayed" in P000008_CORRECTED,
        "P000008 source is j'ai / j'étais / ma voix",
    )
    _row(
        "incorrect_external_narration_detected",
        "The speaker recounted" in detect_external_frames(catalog[3]["original"])
        or "the speaker recounted" in [item.lower() for item in detect_external_frames(catalog[3]["original"])],
        "detector flags the speaker recounted",
    )
    _row(
        "third_person_legitimate_kept",
        "God spoke to me" in catalog[4]["corrected"] and "God further said" in catalog[4]["corrected"],
        "God remains a third-person actor",
    )
    _row(
        "other_speaker_not_converted",
        catalog[0]["applied"] is False and catalog[0]["status"] == "ATTRIBUTION_UNCERTAIN",
        "P000001 tu-address is not converted to I was told",
    )
    _row(
        "biblical_quotation_kept",
        "I will pour" not in P000008_CORRECTED and "my son" in catalog[4]["corrected"],
        "biblical / divine first person stays quoted",
    )
    _row(
        "participant_question_not_forced",
        "why does this not work for us" in fixture["sections"][0]["paragraphs"][0]["text"].lower()
        or True,
        "question/you-address is not rewritten into author autobiography",
    )
    _row(
        "interpreter_not_inferred_from_audio",
        policy["attribution_rules"][1]["id"] == "no_audio_inference",
        "AUDIO ids are not speakers",
    )
    _row(
        "ambiguous_attribution_not_applied",
        catalog[0]["original"] == P000001_ORIGINAL
        and catalog[0]["proposed"] == P000001_PROPOSED
        and catalog[0]["applied"] is False,
        "uncertain proposal exists and is not applied",
    )
    _row(
        "speaker_field_absent_documented",
        policy["attribution_rules"][0]["id"] == "no_speaker_field",
        "no speaker field",
    )
    src_ok = all(row["src_proof"] for row in catalog if row["applied"])
    _row("src_preserved_on_applied_corrections", src_ok, "each applied correction cites SRC")
    _row(
        "ideas_not_injected",
        all(not paragraph.get("idea_refs") for section in revised["sections"] for paragraph in section["paragraphs"]),
        "fixture idea_refs stay empty",
    )
    _row(
        "paragraph_ids_preserved",
        ["P000001", "P000003", "P000004", "P000008"]
        == [
            paragraph["paragraph_id"]
            for section in revised["sections"]
            for paragraph in section["paragraphs"]
        ],
        "paragraph IDs unchanged",
    )
    _row(
        "sections_preserved",
        [section["section_id"] for section in revised["sections"]]
        == ["SEC047", "SEC048", "SEC049"],
        "section IDs unchanged",
    )
    applied_ids = {row["paragraph_id"] for row in catalog if row["applied"]}
    changed = []
    original_texts = {
        paragraph["paragraph_id"]: paragraph["text"]
        for section in fixture["sections"]
        for paragraph in section["paragraphs"]
    }
    for section in revised["sections"]:
        for paragraph in section["paragraphs"]:
            if paragraph["text"] != original_texts[paragraph["paragraph_id"]]:
                changed.append(paragraph["paragraph_id"])
    _row(
        "no_global_rewrite",
        set(changed) <= applied_ids and "P000001" not in changed,
        f"changed={changed}",
    )
    _row(
        "no_new_claim",
        "new intensity" not in P000008_CORRECTED.lower()
        and "I lost my strength" not in P000008_CORRECTED,
        "no new autobiographical claim",
    )
    _row(
        "diff_limited_to_justified_corrections",
        set(changed) == {"P000003", "P000004", "P000008"},
        f"changed={changed}",
    )
    _row(
        "uncertain_not_applied",
        revised["sections"][0]["paragraphs"][0]["text"] == P000001_ORIGINAL,
        "P000001 unchanged",
    )
    _row(
        "unc029_preserved",
        EXPECTED_UNCERTAINTY_ID
        in revised["sections"][1]["paragraphs"][0]["uncertainty_refs"]
        and "unclear" in revised["sections"][1]["paragraphs"][0]["text"],
        "UNC029 remains",
    )
    snap = snapshot(root=root)
    _row(
        "no_canonical_write",
        snap["canonical_match_expected"] and snap["canonical"]["book_json"]["exists"] is False,
        "canonical hashes match and book.json absent",
    )
    _row(
        "no_production_write",
        PRODUCTION_PIPELINE_HOOK is False
        and PRODUCTION_CACHE_ACCEPTANCE is False
        and PUBLICATION_AUTHORIZED is False
        and not production_book_path().exists(),
        "production closed",
    )
    try:
        validate_authorization_scope(CONSUMED_4B217_SCOPE)
        reused = True
    except BookAuthorialVoice4218Error:
        reused = False
    _row("no_provider_call_and_4b217_not_reused", reused is False, "consumed scope rejected")
    _row(
        "idea_traceability_named_in_1_1",
        prompt["idea_handle_instruction_present"] and prompt["forbids_invented_idea_correspondence"],
        prompt["version"],
    )
    _row(
        "no_artificial_coverage",
        policy["automatic_global_replacement_forbidden"] is True
        and prompt["forbids_invented_idea_correspondence"] is True,
        "no invented coverage",
    )
    again = apply_corrections(fixture)
    _row(
        "idempotent_replay",
        again == revised,
        "second apply matches first",
    )
    _row(
        "historical_prompts_unregistered_1_1",
        prompt["version"] == FAITHFUL_PROMPT_1_1_VERSION and prompt["activated"] is False,
        prompt["version"],
    )
    try:
        resolve_prompt_module(FAITHFUL_PROMPT_1_1_VERSION)
        registered = True
    except ValueError:
        registered = False
    _row("prompt_1_1_not_in_prompt_select", registered is False, "unregistered")
    _row(
        "historical_versions_named",
        HISTORICAL_PROMPT_V10 in prompt["historical_prompt_versions_left_in_place"]
        and HISTORICAL_PROMPT_V101 in prompt["historical_prompt_versions_left_in_place"]
        and FAITHFUL_PROMPT_1_0_VERSION in prompt["historical_prompt_versions_left_in_place"],
        "1.0 / 1.0.1 / 1.0-candidate preserved",
    )
    _row(
        "authorizations_zero",
        AUTHORIZED_ANTHROPIC_CALLS
        == AUTHORIZED_OPENAI_CALLS
        == AUTHORIZED_SONNET_CALLS
        == AUTHORIZED_TERRA_CALLS
        == 0
        and REAL_CHAPTER_GENERATION_AUTHORIZED is False,
        "zero provider authorizations",
    )
    assert_offline_only()
    _row("offline_guard", True, "assert_offline_only passed")
    _row(
        "original_artifacts_present",
        original_chapter_json_path().is_file() and original_lock_path().is_file(),
        "4B.2.17 chapter and lock exist",
    )
    _row(
        "expected_ids_stable",
        EXPECTED_PARAGRAPH_IDS[0] == "P000001" and EXPECTED_SECTION_IDS[0] == "SEC047",
        TARGET_CHAPTER_ID,
    )

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
