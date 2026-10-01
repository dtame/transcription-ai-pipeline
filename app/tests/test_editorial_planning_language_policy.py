"""Generic language-policy tests. No pastoral hard-coding, 0 provider calls."""

from __future__ import annotations

import pytest

from app.editorial_planning.constants import EDITORIAL_PLANNER_PROMPT_VERSION
from app.editorial_planning.language_policy import (
    INHERIT_PROJECT,
    INHERIT_REQUIRE_EXPLICIT,
    INHERIT_SOURCE,
    RECOMMENDED_ALIGNMENT,
    RECOMMENDED_DEFAULT_MODE,
    STATUS_EXPLICIT_BOOK,
    STATUS_INHERITED_PROJECT,
    STATUS_INHERITED_SOURCE,
    STATUS_UNRESOLVED,
    SUCCESSOR_PROMPT_VERSION,
    languages_differ,
    normalize_language_code,
    plan_must_match_book_language,
    resolve_book_language,
)
from app.editorial_planning.prompt import prompt_bundle
from app.editorial_planner_canary_4a1.constants import PHASE_4A_PROMPT_SHA256


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestLanguageNormalization:
    def test_empty_and_case(self):
        assert normalize_language_code(None) == ""
        assert normalize_language_code("  EN ") == "en"
        assert normalize_language_code("fr") == "fr"

    def test_languages_differ(self):
        assert languages_differ("en", "fr") is True
        assert languages_differ("EN", "en") is False
        assert languages_differ("", "fr") is False


class TestExplicitBookLanguage:
    def test_explicit_wins_over_source_and_project(self):
        result = resolve_book_language(
            book_language="es",
            project_language="fr",
            source_primary_language="en",
        )
        assert result.book_language == "es"
        assert result.status == STATUS_EXPLICIT_BOOK
        assert result.requires_human_decision is False
        assert result.source == "book_language"


class TestMissingBookLanguage:
    def test_recommended_default_requires_explicit(self):
        result = resolve_book_language(
            book_language=None,
            project_language="fr",
            source_primary_language="en",
            inherit_missing=RECOMMENDED_DEFAULT_MODE,
        )
        assert RECOMMENDED_DEFAULT_MODE == INHERIT_REQUIRE_EXPLICIT
        assert result.book_language == ""
        assert result.status == STATUS_UNRESOLVED
        assert result.requires_human_decision is True


class TestSourceDiffersFromBook:
    def test_explicit_book_may_differ_from_source(self):
        result = resolve_book_language(
            book_language="fr",
            source_primary_language="en",
        )
        assert result.book_language == "fr"
        assert result.source_primary_language == "en"
        assert any("differs" in note for note in result.notes)


class TestDeterministicResolution:
    def test_inherit_source_mode(self):
        result = resolve_book_language(
            book_language="",
            source_primary_language="de",
            inherit_missing=INHERIT_SOURCE,
        )
        assert result.status == STATUS_INHERITED_SOURCE
        assert result.book_language == "de"
        assert result.requires_human_decision is False

    def test_inherit_project_mode(self):
        result = resolve_book_language(
            book_language=None,
            project_language="it",
            source_primary_language="en",
            inherit_missing=INHERIT_PROJECT,
        )
        assert result.status == STATUS_INHERITED_PROJECT
        assert result.book_language == "it"

    def test_same_inputs_same_output(self):
        kwargs = {
            "book_language": None,
            "project_language": "nl",
            "source_primary_language": "pt",
            "inherit_missing": INHERIT_REQUIRE_EXPLICIT,
        }
        first = resolve_book_language(**kwargs)
        second = resolve_book_language(**kwargs)
        assert first.to_dict() == second.to_dict()

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError):
            resolve_book_language(inherit_missing="invented_mode")


class TestPromptNotMutated:
    def test_active_prompt_remains_1_0(self):
        assert EDITORIAL_PLANNER_PROMPT_VERSION == "editorial-planner-1.0"
        assert SUCCESSOR_PROMPT_VERSION == "editorial-planner-1.0.1"
        assert SUCCESSOR_PROMPT_VERSION != EDITORIAL_PLANNER_PROMPT_VERSION
        bundle = prompt_bundle()
        assert bundle["prompt_sha256"] == PHASE_4A_PROMPT_SHA256
        assert "LANGUE DE SORTIE OBLIGATOIRE" not in bundle["system"]
        assert "LANGUE DE SORTIE OBLIGATOIRE" not in bundle["instructions"]

    def test_alignment_recommendation(self):
        alignment = plan_must_match_book_language()
        assert alignment["policy"] == RECOMMENDED_ALIGNMENT
        assert alignment["mismatch_architecturally_safe"] is False
        assert alignment["new_grammar_canary_required_for_language_instruction_only"] is False
        assert alignment["schema_change_required_for_language_policy"] is False
