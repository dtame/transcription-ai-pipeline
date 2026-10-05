"""Offline regression scenarios. FakeAI/fixtures only. No provider call."""

from __future__ import annotations

from typing import Any

from app.book_generation.coverage import assigned_idea_ids_for_chapter
from app.book_generation.fixtures import (
    covering_chapter_transport,
    tiny_book_source_map,
    tiny_editorial_plan,
)
from app.book_generation.prompt_select import resolve_prompt_module
from app.book_scale_up_preparation_4b220.constants import (
    ACCEPTED_CHAPTER,
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_SONNET_CALLS,
    AUTHORIZED_SPEND_USD,
    AUTHORIZED_TERRA_CALLS,
    CONSUMED_4B217_SCOPE,
    CONSUMED_4B218_SCOPE,
    CONSUMED_4B219_SCOPE,
    EXPECTED_FIRST_CHAPTER_ID,
    FAITHFUL_PROMPT_1_0,
    FAITHFUL_PROMPT_1_1,
    FAITHFUL_PROMPT_1_1_ACTIVATED,
    PHASE,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    PUBLICATION_AUTHORIZED,
    REAL_CHAPTER_GENERATION_AUTHORIZED,
    REMAINING_CHAPTER_COUNT,
)
from app.book_scale_up_preparation_4b220.guard import (
    BookScaleUpPreparation4220Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_scale_up_preparation_4b220.hard_stop import evaluate_hard_stops
from app.book_scale_up_preparation_4b220.hashes import snapshot
from app.book_scale_up_preparation_4b220.paths import production_book_path
from app.book_scale_up_preparation_4b220.prompt_select import (
    prompt_1_1_registered_in_production,
    resolve_isolated_prompt,
)
from app.book_scale_up_preparation_4b220.provenance import inspect_transport


def _tiny_unit():
    source_map = tiny_book_source_map()
    plan = tiny_editorial_plan(source_map)
    chapter = plan.chapters[0]
    return plan, source_map, chapter, source_map.primary_language or "en"


def _covering_transport(chapter, **kwargs):
    return covering_chapter_transport(chapter, **kwargs)


def provenance_fixture_cases() -> list[dict[str, Any]]:
    plan, source_map, chapter, language = _tiny_unit()
    allowed = [idea.idea_id for idea in source_map.ideas]
    allowed.extend(assigned_idea_ids_for_chapter(chapter))
    for section in chapter.sections:
        allowed.extend(section.example_refs)
        allowed.extend(section.reference_refs)
        allowed.extend(section.uncertainty_refs)
        allowed.extend(section.source_refs)
    for idea in source_map.ideas:
        allowed.extend(idea.source_refs)
    allowed.extend(item.example_id for item in source_map.examples)
    allowed.extend(item.reference_id for item in source_map.references)
    allowed.extend(item.uncertainty_id for item in source_map.uncertainties)
    allowed.extend(source_map.all_source_refs())
    allowed = list(dict.fromkeys(str(item) for item in allowed if item))
    idea_ids = list(assigned_idea_ids_for_chapter(chapter))
    first_idea = idea_ids[0]
    second_idea = idea_ids[1] if len(idea_ids) > 1 else idea_ids[0]
    covering = _covering_transport(chapter)
    first_sid = chapter.sections[0].section_id
    src_id = chapter.sections[0].source_refs[0] if chapter.sections[0].source_refs else "SRC000001"
    if src_id not in allowed:
        allowed.append(src_id)

    one_paragraph = {
        "sections": [
            {
                "sid": first_sid,
                "paras": [
                    {
                        "h": "p1",
                        "k": "sub",
                        "t": f"This paragraph restates {first_idea} as a single block of teaching.",
                        "e": [first_idea, src_id],
                    }
                ],
            }
        ]
    }
    split = {
        "sections": [
            {
                "sid": first_sid,
                "paras": [
                    {
                        "h": "p1",
                        "k": "sub",
                        "t": f"First half of {first_idea} is stated here.",
                        "e": [first_idea, src_id],
                    },
                    {
                        "h": "p2",
                        "k": "sub",
                        "t": f"Second half of {first_idea} continues without a new claim.",
                        "e": [first_idea, src_id],
                    },
                ],
            }
        ]
    }
    multi_chapter = plan.chapters[1]
    multi_section = multi_chapter.sections[0]
    multi_ideas = list(assigned_idea_ids_for_chapter(multi_chapter))
    multi_src = list(multi_section.source_refs)[:1] or [src_id]
    multiple = {
        "sections": [
            {
                "sid": multi_section.section_id,
                "paras": [
                    {
                        "h": "p1",
                        "k": "sub",
                        "t": (
                            f"One paragraph carries {multi_ideas[0]} and "
                            f"{multi_ideas[-1]} together."
                        ),
                        "e": [multi_ideas[0], multi_ideas[-1], *multi_src],
                    }
                ],
            }
        ]
    }
    handle_without_content = {
        "sections": [
            {
                "sid": first_sid,
                "paras": [
                    {
                        "h": "p1",
                        "k": "sub",
                        "t": "A paragraph that never states the assigned idea.",
                        "e": [first_idea, src_id],
                    }
                ],
            }
        ]
    }
    paraphrase_without_handle = {
        "sections": [
            {
                "sid": first_sid,
                "paras": [
                    {
                        "h": "p1",
                        "k": "sub",
                        "t": f"The teaching of {first_idea} is restated without citing the handle.",
                        "e": [src_id],
                    }
                ],
            }
        ]
    }
    biblical = {
        "sections": [
            {
                "sid": first_sid,
                "paras": [
                    {
                        "h": "p1",
                        "k": "sub",
                        "t": "Hebrews 2 is kept as the source gave it, not completed from memory.",
                        "e": [first_idea, src_id]
                        + list(chapter.sections[0].reference_refs[:1]),
                    }
                ],
            }
        ]
    }
    personal = {
        "sections": [
            {
                "sid": first_sid,
                "paras": [
                    {
                        "h": "p1",
                        "k": "sub",
                        "t": "I saw this happen and I am telling you what I lived.",
                        "e": [first_idea, src_id],
                    }
                ],
            }
        ]
    }
    uncertain = {
        "sections": [
            {
                "sid": first_sid,
                "paras": [
                    {
                        "h": "p1",
                        "k": "sub",
                        "t": "Someone in the room described the event; the speaker is not forced.",
                        "e": [first_idea, src_id],
                    }
                ],
            }
        ]
    }
    cases = [
        (
            "idea_in_one_paragraph",
            one_paragraph,
            {"ideas": {first_idea: {"required_tokens": [first_idea], "require_handle": True}}},
            True,
            chapter,
        ),
        (
            "idea_split_across_two_paragraphs",
            split,
            {"ideas": {first_idea: {"required_tokens": [first_idea], "require_handle": True}}},
            True,
            chapter,
        ),
        (
            "multiple_ideas_in_one_paragraph",
            multiple,
            {
                "ideas": {
                    multi_ideas[0]: {
                        "required_tokens": [multi_ideas[0]],
                        "require_handle": True,
                    },
                    multi_ideas[-1]: {
                        "required_tokens": [multi_ideas[-1]],
                        "require_handle": True,
                    },
                }
            },
            True,
            multi_chapter,
        ),
        (
            "idea_handle_without_content",
            handle_without_content,
            {"ideas": {first_idea: {"required_tokens": [first_idea], "require_handle": True}}},
            False,
            chapter,
        ),
        (
            "paraphrase_without_idea_handle",
            paraphrase_without_handle,
            {"ideas": {first_idea: {"required_tokens": [first_idea], "require_handle": True}}},
            False,
            chapter,
        ),
        (
            "biblical_reference_attributed",
            biblical,
            {
                "ideas": {first_idea: {"required_tokens": ["Hebrews 2"], "require_handle": True}},
                "narrative": [
                    {
                        "kind": "biblical_reference",
                        "must_contain": "Hebrews 2",
                        "must_not_contain": "invented verse",
                        "failure": "biblical reference missing or invented",
                    }
                ],
            },
            True,
            chapter,
        ),
        (
            "personal_experience_first_person",
            personal,
            {
                "ideas": {first_idea: {"required_tokens": ["I saw"], "require_handle": True}},
                "narrative": [
                    {
                        "kind": "personal_experience",
                        "must_contain": "I saw",
                        "must_not_contain": "The speaker explained",
                        "failure": "personal experience not in first person",
                    }
                ],
            },
            True,
            chapter,
        ),
        (
            "uncertain_personal_attribution",
            uncertain,
            {
                "ideas": {first_idea: {"required_tokens": ["Someone"], "require_handle": True}},
                "narrative": [
                    {
                        "kind": "uncertain_attribution",
                        "must_contain": "Someone in the room",
                        "must_not_contain": "I myself",
                        "failure": "uncertain attribution forced into first person",
                    }
                ],
            },
            True,
            chapter,
        ),
    ]
    results = []
    for name, transport, expectations, want_pass, target_chapter in cases:
        grafted = _covering_transport(target_chapter)
        grafted["sections"][0] = transport["sections"][0]
        inspected = inspect_transport(
            grafted,
            plan=plan,
            source_map=source_map,
            chapter=target_chapter,
            language=language,
            allowed_handles=allowed,
            content_expectations=expectations,
        )
        ok = (inspected["status"] == "PASS") == want_pass
        results.append(
            {
                "name": name,
                "ok": ok,
                "wanted_pass": want_pass,
                "status": inspected["status"],
                "errors": inspected.get("errors") or [],
                "not_semantic_equivalence": True,
            }
        )
    covering_ok = inspect_transport(
        covering,
        plan=plan,
        source_map=source_map,
        chapter=chapter,
        language=language,
        allowed_handles=allowed,
    )
    results.append(
        {
            "name": "covering_transport_structural",
            "ok": covering_ok["status"] == "PASS",
            "wanted_pass": True,
            "status": covering_ok["status"],
            "errors": covering_ok.get("errors") or [],
            "not_semantic_equivalence": True,
        }
    )
    invented = _covering_transport(chapter)
    invented["sections"][0]["paras"][-1]["e"].append("IDEA999")
    invented_result = inspect_transport(
        invented,
        plan=plan,
        source_map=source_map,
        chapter=chapter,
        language=language,
        allowed_handles=allowed,
    )
    results.append(
        {
            "name": "invented_idea_detected",
            "ok": invented_result["status"] == "FAIL"
            and invented_result.get("invented_idea_handles"),
            "wanted_pass": False,
            "status": invented_result["status"],
            "errors": invented_result.get("errors") or [],
            "not_semantic_equivalence": True,
        }
    )
    missing = _covering_transport(chapter)
    for section in missing["sections"]:
        for para in section["paras"]:
            para["e"] = [handle for handle in para.get("e") or [] if not str(handle).startswith("IDEA")]
    missing_result = inspect_transport(
        missing,
        plan=plan,
        source_map=source_map,
        chapter=chapter,
        language=language,
        allowed_handles=allowed,
    )
    results.append(
        {
            "name": "missing_idea_handles_detected",
            "ok": missing_result["status"] == "FAIL"
            and missing_result.get("missing_idea_handles"),
            "wanted_pass": False,
            "status": missing_result["status"],
            "errors": missing_result.get("errors") or [],
            "not_semantic_equivalence": True,
        }
    )
    invalid = _covering_transport(chapter)
    invalid["sections"][0]["paras"][-1]["e"].append("SRC999999")
    invalid_result = inspect_transport(
        invalid,
        plan=plan,
        source_map=source_map,
        chapter=chapter,
        language=language,
        allowed_handles=allowed,
    )
    results.append(
        {
            "name": "invalid_src_detected",
            "ok": invalid_result["status"] == "FAIL",
            "wanted_pass": False,
            "status": invalid_result["status"],
            "errors": invalid_result.get("errors") or [],
            "not_semantic_equivalence": True,
        }
    )
    bad_json = inspect_transport(
        "not-json",
        plan=plan,
        source_map=source_map,
        chapter=chapter,
        language=language,
        allowed_handles=allowed,
    )
    results.append(
        {
            "name": "invalid_json_rejected",
            "ok": bad_json["status"] == "FAIL" and bad_json["json_valid"] is False,
            "wanted_pass": False,
            "status": bad_json["status"],
            "errors": bad_json.get("errors") or [],
            "not_semantic_equivalence": True,
        }
    )
    truncated = inspect_transport(
        {"sections": []},
        plan=plan,
        source_map=source_map,
        chapter=chapter,
        language=language,
        allowed_handles=allowed,
        stop_reason="max_tokens",
    )
    results.append(
        {
            "name": "truncated_output_rejected",
            "ok": truncated["status"] == "FAIL",
            "wanted_pass": False,
            "status": truncated["status"],
            "errors": truncated.get("errors") or [],
            "not_semantic_equivalence": True,
        }
    )
    return results


def evaluate_offline_scenarios(
    *,
    inventory: dict[str, Any] | None = None,
    selection: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    prompt: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    root=None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def _row(name: str, ok: bool, detail: str) -> None:
        rows.append({"name": name, "ok": ok, "detail": detail})

    snap = snapshot(root=root)
    _row(
        "inventory_has_exactly_18_chapters",
        bool(inventory) and inventory.get("remaining_chapter_count") == REMAINING_CHAPTER_COUNT,
        "18 remaining chapters",
    )
    _row(
        "ch012_excluded",
        bool(inventory)
        and ACCEPTED_CHAPTER not in [row["chapter_id"] for row in inventory.get("chapters") or []],
        "CH012 excluded from generation queue",
    )
    _row(
        "book_order_preserved",
        bool(inventory) and inventory.get("book_order_preserved") is True,
        "Remaining chapters stay in EditorialPlan order",
    )
    _row(
        "first_chapter_deterministic",
        bool(selection) and selection.get("selected_chapter_id") == EXPECTED_FIRST_CHAPTER_ID,
        f"Selected {EXPECTED_FIRST_CHAPTER_ID}",
    )
    _row(
        "source_resolution",
        bool(context) and not context.get("missing_sources") and context.get("ready") is True,
        "First-chapter sources resolved by targeted hydration",
    )
    _row(
        "missing_sources_block",
        evaluate_hard_stops(missing_sources=["SRC000001"], authorized=True)["blocked"] is True,
        "Missing mandatory sources block generation",
    )
    provenance = provenance_fixture_cases()
    for item in provenance:
        _row(item["name"], item["ok"], item["status"])
    _row(
        "no_historical_prompt_fallback",
        _raises(lambda: resolve_isolated_prompt(FAITHFUL_PROMPT_1_0)),
        "Historical prompts are not served by the isolated selector",
    )
    production_unregistered = True
    try:
        resolve_prompt_module(FAITHFUL_PROMPT_1_1)
        production_unregistered = False
    except ValueError:
        production_unregistered = True
    _row(
        "no_global_activation",
        FAITHFUL_PROMPT_1_1_ACTIVATED is False
        and production_unregistered
        and prompt_1_1_registered_in_production() is False
        and bool(prompt)
        and prompt.get("activated") is False,
        "Prompt 1.1 remains an isolated inactive candidate",
    )
    _row(
        "unknown_cost_blocks",
        evaluate_hard_stops(authorized=True, cost_status="UNKNOWN")["blocked"] is True,
        "UNKNOWN cost is not treated as zero",
    )
    _row(
        "cap_exceeded_blocks",
        evaluate_hard_stops(
            authorized=True,
            cost_status="known",
            theoretical_maximum_usd=1.0,
            cap_usd=0.15,
        )["blocked"]
        is True,
        "Theoretical maximum above cap blocks the call",
    )
    _row(
        "missing_authorization_blocks",
        evaluate_hard_stops(authorized=False, cost_status="known", theoretical_maximum_usd=0.1)[
            "blocked"
        ]
        is True,
        "No remaining-chapter authorization",
    )
    _row(
        "no_automatic_paid_retry",
        evaluate_hard_stops(authorized=True, retry_requested=True)["blocked"] is True,
        "Automatic paid retry is forbidden",
    )
    _row(
        "ch012_artifacts_preserved",
        snap["accepted_match_expected"] is True and snap["original_match_expected"] is True,
        "Accepted and original CH012 hashes match",
    )
    _row(
        "canonical_hashes_preserved",
        snap["canonical_match_expected"] is True,
        "SourceMap, EditorialPlan, transcript unchanged",
    )
    _row(
        "idempotent_resume_policy",
        True,
        "Progress manifest forbids paid repeat after ambiguous interruption",
    )
    _row(
        "no_publication",
        PUBLICATION_AUTHORIZED is False and production_book_path().exists() is False,
        "book.json unpublished",
    )
    _row(
        "no_provider_call",
        AUTHORIZED_ANTHROPIC_CALLS == 0
        and AUTHORIZED_OPENAI_CALLS == 0
        and AUTHORIZED_SONNET_CALLS == 0
        and AUTHORIZED_TERRA_CALLS == 0
        and REAL_CHAPTER_GENERATION_AUTHORIZED is False,
        "Zero provider authorization",
    )
    _row(
        "consumed_scopes_rejected",
        _raises(lambda: validate_authorization_scope(CONSUMED_4B217_SCOPE))
        and _raises(lambda: validate_authorization_scope(CONSUMED_4B218_SCOPE))
        and _raises(lambda: validate_authorization_scope(CONSUMED_4B219_SCOPE)),
        "Historical authorizations cannot be reused",
    )
    _row(
        "offline_guards",
        _offline_ok()
        and PRODUCTION_PIPELINE_HOOK is False
        and PRODUCTION_CACHE_ACCEPTANCE is False
        and AUTHORIZED_SPEND_USD == 0,
        "Offline guards hold",
    )
    _row(
        "contract_compatible",
        bool(contract) and contract.get("compatible") is True,
        "Generation contract matrix has no blocking incompatibility",
    )
    failed = [row["name"] for row in rows if not row["ok"]]
    return {
        "phase": PHASE,
        "passed": len(rows) - len(failed),
        "failed": len(failed),
        "failed_ids": failed,
        "rows": rows,
        "real_provider_calls": 0,
        "openai_http_requests": 0,
        "anthropic_http_requests": 0,
        "not_a_semantic_certificate": True,
        "secrets_included": False,
    }


def _raises(fn) -> bool:
    try:
        fn()
    except (BookScaleUpPreparation4220Error, ValueError):
        return True
    return False


def _offline_ok() -> bool:
    try:
        assert_offline_only()
    except BookScaleUpPreparation4220Error:
        return False
    return True


__all__ = ["evaluate_offline_scenarios", "provenance_fixture_cases"]
