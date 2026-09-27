"""
Contrat source_map.json : identifiants, sérialisation, relecture, frontière.

Tests unitaires des modèles seuls — aucun appel IA, aucun fichier.
"""

from __future__ import annotations

import pytest

from app.source_analysis.models import (
    FORBIDDEN_EDITORIAL_FIELDS,
    SOURCE_MAP_SCHEMA_VERSION,
    AnalysisProvenance,
    AuthorVoiceProfile,
    Example,
    Idea,
    IdeaRelation,
    IntentStatement,
    Reference,
    Repetition,
    SourceAnalysisHeader,
    SourceMap,
    SourceMapStats,
    Topic,
    Uncertainty,
    forbidden_editorial_fields,
    format_example_id,
    format_idea_id,
    format_reference_id,
    format_repetition_id,
    format_topic_id,
    format_uncertainty_id,
)
from app.transcript_models import SCHEMA_VERSION as TRANSCRIPT_SCHEMA_VERSION


def _source_map() -> SourceMap:
    return SourceMap(
        transcript_id="TR001",
        project_name="demo",
        primary_language="fr",
        source_analysis=SourceAnalysisHeader(
            main_theme="Le rôle de la foi dans l'épreuve",
            author_intent=IntentStatement(
                summary="Enseigner", confidence="high", kinds=("enseigner",)
            ),
            target_audience=IntentStatement(
                summary="Audience croyante", confidence="medium"
            ),
        ),
        topics=(
            Topic(
                topic_id="TOP001",
                label="Foi",
                summary="Résumé",
                source_refs=("SRC000001",),
            ),
        ),
        ideas=(
            Idea(
                idea_id="IDEA001",
                summary="Une idée",
                kind="claim",
                importance="central",
                topic_refs=("TOP001",),
                relations=(IdeaRelation(relation="supports", to_idea="IDEA001"),),
                source_refs=("SRC000001", "SRC000002"),
            ),
        ),
        examples=(
            Example(
                example_id="EX001",
                kind="anecdote",
                summary="Une anecdote",
                supports_idea_refs=("IDEA001",),
                source_refs=("SRC000003",),
            ),
        ),
        references=(
            Reference(
                reference_id="REF001",
                kind="biblical",
                raw_reference="Paul dit quelque part",
                normalized_reference="",
                completeness="vague",
                source_refs=("SRC000004",),
            ),
        ),
        uncertainties=(
            Uncertainty(
                uncertainty_id="UNC001",
                kind="incomplete_reference",
                description="Référence non située",
                severity="medium",
                source_refs=("SRC000004",),
            ),
        ),
        repetitions=(
            Repetition(
                repetition_id="REP001",
                character="development",
                description="Reprise développée",
                idea_refs=("IDEA001",),
                source_refs=("SRC000002",),
            ),
        ),
        author_voice_profile=AuthorVoiceProfile(
            tone=("didactique",),
            register="langue parlée",
        ),
        stats=SourceMapStats(
            topic_count=1,
            idea_count=1,
            example_count=1,
            reference_count=1,
            uncertainty_count=1,
            repetition_count=1,
            source_segment_count=8,
            referenced_source_segments=4,
            source_coverage_ratio=0.5,
        ),
        analysis=AnalysisProvenance(
            prompt_version="1.0",
            schema_version="1.0",
            provider="fake",
            model="fake-model",
            strategy="global",
            signature="sig",
        ),
    )


class TestSchemaVersion:
    """Le contrat du Source Map est indépendant de celui du transcript."""

    def test_la_version_est_declaree(self):
        assert SOURCE_MAP_SCHEMA_VERSION == "1.0"

    def test_la_version_n_est_pas_empruntee_au_transcript(self):
        import app.source_analysis.models as models
        import app.transcript_models as transcript_models

        # Les deux valent « 1.0 » aujourd'hui, mais ce sont deux constantes
        # distinctes : la version du Source Map ne doit pas être dérivée de
        # celle du transcript.
        assert models.SOURCE_MAP_SCHEMA_VERSION is not getattr(
            transcript_models, "SCHEMA_VERSION"
        ) or SOURCE_MAP_SCHEMA_VERSION == TRANSCRIPT_SCHEMA_VERSION

        source = __import__("inspect").getsource(models)

        assert "from app.transcript_models import" not in source


class TestIdentifiers:
    """Séquentiels, préfixés, à largeur fixe — comme SRC et AUDIO."""

    @pytest.mark.parametrize(
        "formatter, expected",
        [
            (format_topic_id, "TOP001"),
            (format_idea_id, "IDEA001"),
            (format_example_id, "EX001"),
            (format_reference_id, "REF001"),
            (format_uncertainty_id, "UNC001"),
            (format_repetition_id, "REP001"),
        ],
    )
    def test_le_premier_identifiant_de_chaque_categorie(self, formatter, expected):
        assert formatter(1) == expected

    def test_la_largeur_est_de_trois_chiffres(self):
        assert format_idea_id(17) == "IDEA017"
        assert format_idea_id(999) == "IDEA999"

    def test_les_prefixes_sont_distincts(self):
        prefixes = {
            format_topic_id(1)[:-3],
            format_idea_id(1)[:-3],
            format_example_id(1)[:-3],
            format_reference_id(1)[:-3],
            format_uncertainty_id(1)[:-3],
            format_repetition_id(1)[:-3],
        }

        assert len(prefixes) == 6


class TestSerialization:
    """L'ordre des clés du fichier publié est un contrat."""

    def test_l_ordre_des_cles_de_premier_niveau(self):
        assert list(_source_map().to_dict()) == [
            "schema_version",
            "transcript_id",
            "project",
            "language",
            "source_analysis",
            "topics",
            "ideas",
            "examples",
            "references",
            "uncertainties",
            "repetitions",
            "author_voice_profile",
            "stats",
            "analysis",
        ]

    def test_aucun_champ_d_horodatage(self):
        payload = _source_map().to_dict()

        assert "generated_at" not in payload
        assert "generated_at" not in payload["analysis"]
        assert "updated_at" not in payload["stats"]

    def test_les_tuples_deviennent_des_listes_json(self):
        payload = _source_map().to_dict()

        assert isinstance(payload["topics"][0]["source_refs"], list)
        assert isinstance(payload["author_voice_profile"]["tone"], list)

    def test_la_provenance_est_complete(self):
        analysis = _source_map().to_dict()["analysis"]

        assert set(analysis) == {
            "prompt_version",
            "schema_version",
            "provider",
            "model",
            "strategy",
            "signature",
        }


class TestRoundTrip:
    """Un source_map.json publié doit pouvoir être relu à l'identique."""

    def test_la_relecture_reproduit_le_dictionnaire(self):
        original = _source_map().to_dict()

        assert SourceMap.from_dict(original).to_dict() == original

    def test_la_relecture_d_un_payload_vide_ne_leve_pas(self):
        relu = SourceMap.from_dict({})

        assert relu.topics == ()
        assert relu.ideas == ()
        assert relu.source_analysis.main_theme == ""
        assert relu.stats.idea_count == 0

    def test_la_relecture_ne_complete_rien(self):
        """Un lecteur ne doit pas rendre valide un fichier qui ne l'est pas."""
        relu = SourceMap.from_dict({"transcript_id": "TR001"})

        assert relu.schema_version == ""
        assert relu.primary_language == ""

    def test_les_relations_survivent_a_la_relecture(self):
        original = _source_map().to_dict()

        assert SourceMap.from_dict(original).ideas[0].relations == (
            IdeaRelation(relation="supports", to_idea="IDEA001"),
        )


class TestHelpers:
    """Utilitaires d'agrégation du Source Map."""

    def test_tous_les_src_cites_sont_dedoublonnes(self):
        refs = _source_map().all_source_refs()

        assert refs == ("SRC000001", "SRC000002", "SRC000003", "SRC000004")

    def test_les_identifiants_sont_listes_par_categorie(self):
        declared = _source_map().declared_ids()

        assert declared["ideas"] == ("IDEA001",)
        assert set(declared) == {
            "topics",
            "ideas",
            "examples",
            "references",
            "uncertainties",
            "repetitions",
        }


class TestEditorialBoundary:
    """Le vocabulaire de structure de livre est refusé par contrat."""

    def test_la_liste_des_champs_interdits_couvre_l_essentiel(self):
        for name in (
            "chapters",
            "sections",
            "book_title",
            "book_subtitle",
            "table_of_contents",
            "editorial_plan",
        ):
            assert name in FORBIDDEN_EDITORIAL_FIELDS

    def test_les_champs_interdits_sont_detectes(self):
        assert forbidden_editorial_fields({"chapters": [], "ideas": []}) == (
            "chapters",
        )

    def test_l_ordre_de_detection_est_stable(self):
        detected = forbidden_editorial_fields(
            {"toc": [], "chapters": [], "book_title": ""}
        )

        assert detected == ("book_title", "chapters", "toc")

    def test_un_source_map_nominal_ne_declenche_rien(self):
        assert forbidden_editorial_fields(_source_map().to_dict()) == ()

    def test_un_mapping_invalide_ne_leve_pas(self):
        assert forbidden_editorial_fields(None) == ()
        assert forbidden_editorial_fields("chapters") == ()

    def test_aucun_concept_de_livre_dans_le_module(self):
        """
        Frontière architecturale : le paquet source_analysis ne définit ni Book,
        ni Chapter, ni Section, ni TOC, ni Cover.
        """
        import inspect

        import app.source_analysis.models as models

        classes = {
            name
            for name, obj in inspect.getmembers(models, inspect.isclass)
            if obj.__module__ == models.__name__
        }

        for forbidden in ("Book", "Chapter", "Section", "TableOfContents", "Cover"):
            assert forbidden not in classes
