"""Phase 4B.2.16 — offline editorial alignment. Network is not used."""

from __future__ import annotations

import pytest

from app.book_editorial_alignment_4b216.constants import (
    COVERAGE_CONTROL_ACTIVATED,
    EDITORIAL_POLICY_ACTIVATED,
    FAITHFUL_PROMPT_ACTIVATED,
    FAITHFUL_PROMPT_VERSION,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_4B212_STATUS,
    HISTORICAL_4B213_STATUS,
    HISTORICAL_4B214_STATUS,
    HISTORICAL_4B215_STATUS,
    HISTORICAL_GENERATOR_PROMPT,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    HISTORICAL_SEMANTIC_CONTRACT,
)
from app.book_editorial_alignment_4b216.coverage import assess_coverage
from app.book_editorial_alignment_4b216.guard import (
    BookEditorialAlignment4216Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_editorial_alignment_4b216.human_resolution import (
    DECISION_CONFIRM_FALSE_REJECTION,
    DECISION_MAINTAIN_BLOCK,
    build_resolution,
)
from app.book_editorial_alignment_4b216.pilot import select_pilot
from app.book_editorial_alignment_4b216.policy import editorial_policy
from app.book_editorial_alignment_4b216.prompt_candidate import prompt_bundle
from app.book_editorial_alignment_4b216.prompt_review import current_prompt_review
from app.book_editorial_alignment_4b216.risk_map import analyze_editorial_plan
from app.book_editorial_alignment_4b216.scenarios import evaluate_offline_scenarios
from app.book_generation.constants import BOOK_GENERATOR_PROMPT_VERSION
from app.book_generation.prompt import FROZEN_PROMPT_SHA256, prompt_bundle as frozen_bundle
from app.book_generation.prompt_select import resolve_prompt_module


def test_historical_statuses_and_prompts_stay_put():
    assert HISTORICAL_H01_STATUS == "PARTIAL"
    assert HISTORICAL_H02_STATUS == "PARTIAL"
    assert HISTORICAL_H11_STATUS == "PARTIAL"
    assert HISTORICAL_4B211_STATUS == "PARTIAL"
    assert HISTORICAL_4B212_STATUS == "PASS"
    assert HISTORICAL_4B213_STATUS == "PASS"
    assert HISTORICAL_4B214_STATUS == "PASS"
    assert HISTORICAL_4B215_STATUS == "PARTIAL"
    assert HISTORICAL_GENERATOR_PROMPT == "book-generator-1.0.1"
    assert BOOK_GENERATOR_PROMPT_VERSION == "book-generator-1.0.1"
    assert frozen_bundle()["prompt_sha256"] == FROZEN_PROMPT_SHA256
    assert HISTORICAL_SEMANTIC_CONTRACT == "book-semantic-validator-2.0.2-candidate"
    assert FAITHFUL_PROMPT_ACTIVATED is False
    assert EDITORIAL_POLICY_ACTIVATED is False
    assert COVERAGE_CONTROL_ACTIVATED is False
    assert_offline_only()


def test_policy_lists_authorized_and_forbidden_transformations():
    policy = editorial_policy()
    assert len(policy["allowed_transformations"]) == 12
    assert len(policy["forbidden_transformations"]) == 14
    assert [rule["id"] for rule in policy["thematic_rules"]] == list("ABCDEF")
    assert policy["responsibility_split"]["editorial_planner"]["moved_into_book_generator"] is False
    assert policy["activated_in_production"] is False


def test_historical_prompt_review_finds_every_cited_clause():
    review = current_prompt_review()
    assert review["review_complete"] is True
    assert review["clauses_not_found"] == []
    assert review["book_generator_1_0"]["matches_frozen_prompt"] is True
    assert review["historical_prompts_modified"] is False
    assert review["editorial_planner"]["responsibility_left_in_place"] is True


def test_faithful_prompt_is_not_registered():
    bundle = prompt_bundle()
    assert bundle["activated"] is False
    assert bundle["fundamental_rule_present"] is True
    assert bundle["replaces_historical_prompt"] is False
    assert "Stylistic expansion is allowed." not in bundle["system"]
    with pytest.raises(ValueError):
        resolve_prompt_module(FAITHFUL_PROMPT_VERSION)


def test_identifier_alone_is_not_coverage():
    result = assess_coverage(
        [{"id": "IDEA9", "kind": "idea", "text": "Prayer is a conversation."}],
        "This paragraph talks about fasting only.",
        ["IDEA9"],
    )
    assert result["pass"] is False
    assert result["units"][0]["status"] == "IDENTIFIER_ONLY"
    assert result["activated_in_production"] is False


def test_offline_scenarios_pass_and_are_not_terra():
    report = evaluate_offline_scenarios()
    assert report["scenario_count"] == 20
    assert report["failed"] == 0
    assert report["failed_ids"] == []
    assert report["not_a_terra_validation"] is True
    assert report["automatic_unsupported_to_supported"] is False
    assert report["historical_h11_human_label"] == "UNSUPPORTED"
    reviewed = next(row for row in report["scenarios"] if row["id"] == "S20")
    assert reviewed["human_resolution"]["terra_verdict"] == "UNSUPPORTED"
    assert reviewed["human_resolution"]["publication_authorized"] is False
    omitted = next(row for row in report["scenarios"] if row["id"] == "S15")
    assert "IDEA-S15B" in omitted["coverage_missing"]


def test_human_resolution_cannot_publish_or_rewrite_terra():
    record = build_resolution(
        {
            "exact_text": "Prayer is a conversation.",
            "unit_id": "U1",
            "terra_verdict": "UNSUPPORTED",
            "reasons": ["NEW_CONCLUSION"],
            "evidence": ["IDEA1"],
            "sources": ["Prayer is a conversation."],
            "contract_version": HISTORICAL_SEMANTIC_CONTRACT,
            "hashes": {"prose_sha256": "abc"},
            "human_decision": DECISION_CONFIRM_FALSE_REJECTION,
            "justification": "The sentence repeats the source.",
        }
    )
    assert record["publication_authorized"] is False
    assert record["terra_verdict_immutable"] is True
    blocked = build_resolution(
        {
            "exact_text": "Prayer always guarantees victory.",
            "unit_id": "U2",
            "terra_verdict": "UNSUPPORTED",
            "reasons": ["NEW_GUARANTEE"],
            "evidence": ["IDEA1"],
            "sources": ["Prayer is a conversation."],
            "contract_version": HISTORICAL_SEMANTIC_CONTRACT,
            "hashes": {"prose_sha256": "def"},
            "human_decision": DECISION_MAINTAIN_BLOCK,
            "justification": "The guarantee is not in the source, and the case is not settled.",
        }
    )
    assert blocked["human_decision"] == DECISION_MAINTAIN_BLOCK
    with pytest.raises(BookEditorialAlignment4216Error):
        build_resolution(
            {
                "exact_text": "x",
                "unit_id": "U3",
                "terra_verdict": "UNSUPPORTED",
                "reasons": ["NEW_FACT"],
                "evidence": ["IDEA1"],
                "sources": ["source"],
                "contract_version": HISTORICAL_SEMANTIC_CONTRACT,
                "hashes": {"prose_sha256": "g"},
                "human_decision": DECISION_CONFIRM_FALSE_REJECTION,
                "justification": "no",
                "publication_authorized": True,
            }
        )


def test_bad_scope_is_rejected():
    with pytest.raises(BookEditorialAlignment4216Error):
        validate_authorization_scope("GENERATE_THE_BOOK")


def test_real_plan_selects_a_bounded_pilot_other_than_ch001_and_ch016():
    risk_map = analyze_editorial_plan()
    assignment = risk_map["structural_assignment"]
    assert assignment["structurally_complete"] is True
    assert assignment["assigned_idea_count"] == 286
    assert assignment["chapter_count"] == 19
    assert assignment["section_count"] == 72
    assert assignment["semantic_fitness_proven"] is False
    assert risk_map["limits_of_the_evidence"]["idea_relation_count"] == 0
    selection = select_pilot(risk_map)
    selected = selection["selected"]
    assert selected["chapter_id"] == "CH012"
    assert selected["section_count"] == 4
    assert selected["idea_count"] == 11
    assert selected["generation_executed"] is False
    assert "CH001" not in selection["eligible_ranking"]
    assert "CH016" not in selection["eligible_ranking"]
    assert selected["audio_sources"] == ["AUDIO003", "AUDIO004"]
    assert selected["ready_to_generate"] is False
