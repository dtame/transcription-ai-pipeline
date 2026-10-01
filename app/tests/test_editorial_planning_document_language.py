"""Generic canonical document language + prompt 1.0.1 tests. 0 provider calls."""

from __future__ import annotations

import pytest

from app.editorial_planning.constants import EDITORIAL_PLANNER_PROMPT_VERSION
from app.editorial_planning.errors import DocumentLanguageBlocked
from app.editorial_planning.fixtures import tiny_source_map
from app.editorial_planning.language_policy import (
    DOCUMENT_LANGUAGE_POLICY,
    STATUS_BLOCKED_MISMATCH,
    STATUS_BLOCKED_UNKNOWN,
    STATUS_RESOLVED,
    SUCCESSOR_PROMPT_VERSION,
    resolve_document_language,
)
from app.editorial_planning.language_validate import (
    FUTURE_PUBLICATION_GATE,
    FUTURE_PUBLICATION_REQUIRED,
    future_publication_eligibility_requirements,
    validate_editorial_language,
)
from app.editorial_planning.payload_v101 import build_planner_request_v101
from app.editorial_planning.prompt import prompt_bundle as prompt_bundle_v10
from app.editorial_planning.prompt_v101 import language_rule, prompt_bundle
from app.editorial_planner_canary_4a1.constants import PHASE_4A_PROMPT_SHA256
from app.editorial_planning.settings import frozen_production_settings


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestResolveDocumentLanguage:
    def test_english_primary_resolves_to_en(self):
        result = resolve_document_language(
            transcript_primary_language="en",
            source_map_primary_language="en",
        )
        assert result.canonical_document_language == "en"
        assert result.status == STATUS_RESOLVED
        assert result.blocked is False
        assert result.policy == DOCUMENT_LANGUAGE_POLICY

    def test_french_primary_resolves_to_fr(self):
        result = resolve_document_language(
            transcript_primary_language="FR",
            source_map_primary_language="fr",
        )
        assert result.canonical_document_language == "fr"
        assert result.status == STATUS_RESOLVED

    def test_spanish_primary_resolves_to_es(self):
        result = resolve_document_language(
            transcript_primary_language="es",
            source_map_primary_language="es",
        )
        assert result.canonical_document_language == "es"
        assert result.blocked is False

    def test_unknown_blocks(self):
        result = resolve_document_language(
            transcript_primary_language="",
            source_map_primary_language="unknown",
        )
        assert result.status == STATUS_BLOCKED_UNKNOWN
        assert result.blocked is True
        assert result.canonical_document_language == ""
        with pytest.raises(DocumentLanguageBlocked):
            result.require()

    def test_mismatch_blocks(self):
        result = resolve_document_language(
            transcript_primary_language="en",
            source_map_primary_language="fr",
        )
        assert result.status == STATUS_BLOCKED_MISMATCH
        assert result.blocked is True
        with pytest.raises(DocumentLanguageBlocked):
            result.require()

    def test_no_silent_english_or_french_default(self):
        result = resolve_document_language()
        assert result.canonical_document_language not in {"en", "fr"}
        assert result.blocked is True


class TestPromptVersions:
    def test_historical_1_0_unchanged(self):
        bundle = prompt_bundle_v10()
        assert EDITORIAL_PLANNER_PROMPT_VERSION == "editorial-planner-1.0"
        assert bundle["version"] == "editorial-planner-1.0"
        assert bundle["prompt_sha256"] == PHASE_4A_PROMPT_SHA256
        assert "LANGUE DE SORTIE OBLIGATOIRE" not in bundle["system"]
        assert "canonical_document_language" not in bundle["instructions"]

    def test_successor_1_0_1_has_language_rule(self):
        assert SUCCESSOR_PROMPT_VERSION == "editorial-planner-1.0.1"
        bundle = prompt_bundle("en")
        assert bundle["version"] == "editorial-planner-1.0.1"
        assert "LANGUE DE SORTIE OBLIGATOIRE" in bundle["system"]
        assert "canonical_document_language" in bundle["instructions"]
        assert bundle["prompt_sha256"] != PHASE_4A_PROMPT_SHA256
        assert "anglais" in language_rule("en")
        assert "français" in language_rule("fr")
        assert "espagnol" in language_rule("es")


class TestPlannerRequestLanguage:
    def test_english_request_requires_en(self):
        source_map = tiny_source_map(primary_language="en")
        request = build_planner_request_v101(
            source_map,
            canonical_document_language="en",
            settings=frozen_production_settings(),
        )
        assert "CANONICAL_DOCUMENT_LANGUAGE\nen\n" in request.prompt
        assert "code « en »" in (request.system_prompt or "")
        assert request.metadata["canonical_document_language"] == "en"

    def test_french_request_requires_fr(self):
        source_map = tiny_source_map(primary_language="fr")
        request = build_planner_request_v101(
            source_map,
            canonical_document_language="fr",
            settings=frozen_production_settings(),
        )
        assert "CANONICAL_DOCUMENT_LANGUAGE\nfr\n" in request.prompt
        assert "code « fr »" in (request.system_prompt or "")

    def test_spanish_request_requires_es(self):
        source_map = tiny_source_map(primary_language="es")
        request = build_planner_request_v101(
            source_map,
            canonical_document_language="es",
            settings=frozen_production_settings(),
        )
        assert "CANONICAL_DOCUMENT_LANGUAGE\nes\n" in request.prompt
        assert "code « es »" in (request.system_prompt or "")


class TestLanguageValidation:
    def test_english_prose_passes_for_en(self):
        plan = {
            "selected_title": "Already heirs",
            "subtitle": "The gift that is already yours",
            "editorial_angle": "The teaching is for the people who are already in the family.",
            "target_reader": "Pastors and the people in the congregation",
            "editorial_strategy": "Move from identity to practice with the same English voice.",
            "book_concept": {
                "purpose": "Help the reader live from the inheritance they already have.",
                "core_subject": "Identity in Christ as a present gift",
                "reader_journey": "From fear and performance toward rest and authority",
                "editorial_progression": "Identity, then authority, then practice",
            },
            "title_candidates": [{"title": "Already heirs"}],
            "chapters": [
                {
                    "working_title": "The gift is already given",
                    "purpose": "Establish the inheritance as present, not future.",
                    "sections": [
                        {
                            "working_title": "You are already in the family",
                            "purpose": "Name the identity before the work.",
                        }
                    ],
                }
            ],
        }
        result = validate_editorial_language(plan, canonical_document_language="en")
        assert result["status"] == "PASS"
        assert result["editorial_language_match"] == "PASS"

    def test_french_prose_fails_for_en(self):
        plan = {
            "selected_title": "Déjà héritiers",
            "subtitle": "Le don qui est déjà là",
            "editorial_angle": "L'enseignement s'adresse à ceux qui sont déjà dans la famille.",
            "target_reader": "Les pasteurs et les personnes de l'assemblée",
            "editorial_strategy": "Aller de l'identité à la pratique avec la même voix.",
            "book_concept": {
                "purpose": "Aider le lecteur à vivre de l'héritage qu'il possède déjà.",
                "core_subject": "L'identité en Christ comme don présent",
                "reader_journey": "De la peur et de la performance vers le repos",
                "editorial_progression": "Identité, puis autorité, puis pratique",
            },
            "title_candidates": [{"title": "Déjà héritiers"}],
            "chapters": [
                {
                    "working_title": "Le don est déjà donné",
                    "purpose": "Établir l'héritage comme présent et non futur.",
                    "sections": [
                        {
                            "working_title": "Vous êtes déjà dans la famille",
                            "purpose": "Nommer l'identité avant le travail.",
                        }
                    ],
                }
            ],
        }
        result = validate_editorial_language(plan, canonical_document_language="en")
        assert result["status"] == "FAIL"

    def test_unsupported_language_is_review(self):
        plan = {"selected_title": "Hola", "chapters": []}
        result = validate_editorial_language(plan, canonical_document_language="es")
        assert result["status"] == "REVIEW"
        assert result["detector_supports_canonical"] is False

    def test_future_gate_name(self):
        assert FUTURE_PUBLICATION_GATE == "EDITORIAL_LANGUAGE_MATCH"
        gates = future_publication_eligibility_requirements()
        assert gates[FUTURE_PUBLICATION_GATE] == FUTURE_PUBLICATION_REQUIRED == "PASS"
        assert gates["automatic_publication"] is False
