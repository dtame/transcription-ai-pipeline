"""Phase 4A.3.1 — offline forensics. 0 provider calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.editorial_planner_forensics_4a31.assignments import (
    ALIGN_CHAPTER,
    ALIGN_NONE,
    ALIGN_SECTION,
    FIT_ACCEPTABLE,
    FIT_QUESTIONABLE,
    FIT_STRONG,
    classify_assignment,
    default_fit_from_alignment,
    topic_alignment,
)
from app.editorial_planner_forensics_4a31.constants import (
    EXPECTED_CANDIDATE_SHA256,
    EXPECTED_SOURCE_MAP_SHA256,
    PHASE,
    REAL_PROVIDER_CALLS,
)
from app.editorial_planner_forensics_4a31.guard import (
    assert_no_book_generator,
    assert_zero_provider_imports,
)
from app.editorial_planner_forensics_4a31.identity import file_sha256
from app.editorial_planner_forensics_4a31.paths import (
    candidate_path,
    production_editorial_plan_path,
    production_source_map_path,
    report_path,
    repo_root,
)
from app.editorial_planner_forensics_4a31.runner import run_forensics
from app.editorial_planning.constants import (
    EDITORIAL_PLANNER_PROMPT_VERSION,
    PUBLICATION_AUTHORIZED,
)
from app.editorial_planning.guard import assert_analyzer_untouched, assert_offline_package


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOfflineGuards:
    def test_zero_provider_and_no_book(self):
        assert REAL_PROVIDER_CALLS == 0
        assert PUBLICATION_AUTHORIZED is False
        assert_zero_provider_imports()
        assert_no_book_generator()
        assert_offline_package()
        assert_analyzer_untouched()
        assert EDITORIAL_PLANNER_PROMPT_VERSION == "editorial-planner-1.0"


class TestAssignmentClassifier:
    def test_section_topic_is_strong(self):
        result = classify_assignment(
            idea_id="IDEA999",
            idea_topics={"TOP001"},
            section_topics={"TOP001"},
            chapter_topics={"TOP001", "TOP002"},
            overlays={},
        )
        assert topic_alignment({"TOP001"}, {"TOP001"}, {"TOP002"}) == ALIGN_SECTION
        assert result["fit"] == FIT_STRONG
        assert result["overlay_applied"] is False

    def test_chapter_only_is_acceptable(self):
        result = classify_assignment(
            idea_id="IDEA998",
            idea_topics={"TOP002"},
            section_topics={"TOP001"},
            chapter_topics={"TOP002"},
            overlays={},
        )
        assert result["alignment"] == ALIGN_CHAPTER
        assert result["fit"] == FIT_ACCEPTABLE

    def test_no_hit_is_questionable_until_overlay(self):
        assert default_fit_from_alignment(ALIGN_NONE) == FIT_QUESTIONABLE
        result = classify_assignment(
            idea_id="IDEA997",
            idea_topics={"TOP009"},
            section_topics={"TOP001"},
            chapter_topics={"TOP002"},
            overlays={"IDEA997": (FIT_ACCEPTABLE, "purpose match")},
        )
        assert result["fit"] == FIT_ACCEPTABLE
        assert result["overlay_applied"] is True


class TestHistoricalCandidateUnchanged:
    def test_stored_hashes(self):
        candidate = candidate_path(root=repo_root())
        source = production_source_map_path(root=repo_root())
        if not candidate.is_file():
            pytest.skip("A.3 candidate absent")
        assert file_sha256(candidate) == EXPECTED_CANDIDATE_SHA256
        assert file_sha256(source) == EXPECTED_SOURCE_MAP_SHA256
        assert not production_editorial_plan_path(root=repo_root()).is_file()

    def test_forensics_does_not_mutate_candidate(self):
        candidate = candidate_path(root=repo_root())
        if not candidate.is_file():
            pytest.skip("A.3 candidate absent")
        before = candidate.read_bytes()
        raw = Path("audit/real/editorial_planner_4a3/editorial_planner_4a3_raw_structured_response.json")
        raw_before = raw.read_bytes() if raw.is_file() else b""
        source_before = production_source_map_path(root=repo_root()).read_bytes()
        result = run_forensics(write_artifacts=True)
        assert result.provider_calls == 0
        header = result.bundle["header"]
        assert header["phase"] == PHASE
        assert header["result"] == "PASS"
        assert header["real_provider_calls"] == 0
        assert header["a3_candidate_unchanged"] == "YES"
        assert header["a3_raw_response_unchanged"] == "YES"
        assert header["source_map_unchanged"] == "YES"
        assert header["semantic_review"] == "REVIEW_REQUIRED"
        assert header["publication_eligible"] == "NO"
        assert header["final_title_approved"] == "NO"
        assert header["book_language_requires_human_decision"] == "YES"
        assert header["new_grammar_canary_required"] == "NO"
        assert header["future_prompt_change_required"] == "YES"
        assert header["ideas_reviewed"] == 286
        assert header["strong_fit"] == 278
        assert header["acceptable_fit"] == 1
        assert header["questionable_fit"] == 7
        assert header["likely_should_defer"] == 0
        assert header["likely_should_exclude"] == 0
        assert header["assignment_result"] == "CREDIBLE_WITH_MINOR_REVIEW"
        assert header["chapter_architecture"] == "PASS"
        assert header["section_architecture"] == "PASS"
        assert header["language_contract_result"] == "UNSPECIFIED_POLICY"
        assert header["title_status"] == "SUPPORTED_BUT_HUMAN_REVIEW"
        assert header["editorial_plan_json"] == "NOT PUBLISHED"
        flagged = {
            item["idea_id"]
            for item in result.bundle["assignments"]["flagged"]
        }
        assert flagged == {
            "IDEA054",
            "IDEA100",
            "IDEA112",
            "IDEA113",
            "IDEA168",
            "IDEA283",
            "IDEA286",
        }
        assert candidate.read_bytes() == before
        if raw_before:
            assert raw.read_bytes() == raw_before
        assert production_source_map_path(root=repo_root()).read_bytes() == source_before
        assert not production_editorial_plan_path(root=repo_root()).is_file()
        audit = Path("audit")
        for name in (
            "editorial_planner_4a31_candidate_identity.json",
            "editorial_planner_4a31_language_forensics.json",
            "editorial_planner_4a31_language_policy_recommendation.json",
            "editorial_planner_4a31_title_review.json",
            "editorial_planner_4a31_assignment_review.json",
            "editorial_planner_4a31_chapter_semantic_review.json",
            "editorial_planner_4a31_section_semantic_review.json",
            "editorial_planner_4a31_publication_eligibility.json",
            "editorial_planner_post_4a31_readiness.json",
        ):
            assert (audit / name).is_file(), name
        assert report_path(root=repo_root()).is_file()
        identity = json.loads(
            (audit / "editorial_planner_4a31_candidate_identity.json").read_text(
                encoding="utf-8"
            )
        )
        assert identity["candidate_sha256"] == EXPECTED_CANDIDATE_SHA256


class TestCli:
    def test_cli_help(self):
        from app.editorial_planner_forensics_4a31.__main__ import main

        assert main(["--help"]) == 0

    def test_cli_rejects_unknown(self):
        from app.editorial_planner_forensics_4a31.__main__ import main

        assert main(["--execute-real"]) == 2
