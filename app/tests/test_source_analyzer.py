"""
Source Analyzer de bout en bout — Phase 3.

Aucun test de ce fichier ne touche au réseau : la fixture `no_ai_network`
interdit tout POST dans la couche IA, et le moteur est toujours FakeAIEngine —
sauf la classe `TestAnthropicStructuredOutputIntegration` (Phase 3B.3), qui
exerce le VRAI AnthropicEngine avec un double de `requests.post`, pour
vérifier que le schéma réel du Source Analyzer atteint bien
output_config.format.schema. Ce double reste un remplaçant explicite de
transport, jamais un socket réel : aucun appel Anthropic, OpenAI, Ollama ou
LM Studio réel n'a lieu dans ce fichier, donc aucun coût réel.
"""

from __future__ import annotations

import json

import pytest

from app.ai.errors import AIConnectionError, AIStructuredOutputError
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.ai.providers.fake import FakeReply
from app.ai.retry import no_delay_policy
from app.report_service import build_project_report
from app.source_analysis.analyzer import STAGE, analyze_source
from app.source_analysis.errors import (
    SourceAnalysisContextExceeded,
    SourceMapEditorialLeakError,
    SourceMapValidationError,
    SourceTranscriptNotSubstantial,
)
from app.source_analysis.models import SOURCE_MAP_SCHEMA_VERSION
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.compact_schema import build_compact_response_schema
from app.source_analysis.schema import build_response_schema
from app.source_analysis.ultra_compact_schema import build_ultra_compact_response_schema
from app.source_analysis.state import STATE_KEY, STATUS_COMPLETED, STATUS_FAILED
from app.tests.ai_fakes import RecordingPost, anthropic_response
from app.tests.source_analysis_fixtures import (  # noqa: F401 — fixture pytest
    analysis_env,
    build_transcript_document,
    fake_analysis_payload,
    fake_analysis_text,
    fake_engine,
    fake_ultra_analysis_payload,
)


# ---------------------------------------------------------------------------
# Scénario de référence
# ---------------------------------------------------------------------------

class TestSourceMapMinimal:
    """Une analyse nominale produit un Source Map complet et valide."""

    def test_publie_un_source_map_conforme(self, analysis_env, no_ai_network):
        engine = fake_engine()

        result = analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 1
        assert result.cached is False
        assert result.path == analysis_env.source_map_path
        assert result.path.exists()

        payload = analysis_env.source_map()

        assert payload["schema_version"] == SOURCE_MAP_SCHEMA_VERSION
        assert payload["transcript_id"] == "TR001"
        assert payload["project"]["name"] == analysis_env.project_name
        assert payload["language"]["primary"] == "fr"

    def test_le_source_map_porte_toutes_les_sections_du_contrat(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        payload = analysis_env.source_map()

        assert list(payload) == [
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

    def test_main_theme_intention_et_audience_sont_renseignes(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        header = analysis_env.source_map()["source_analysis"]

        assert header["main_theme"] == (
            "Le rôle de la foi dans la manière de traverser les épreuves"
        )
        assert header["author_intent"]["confidence"] == "high"
        assert header["target_audience"]["confidence"] == "medium"

    def test_les_compteurs_correspondent_au_contenu(self, analysis_env, no_ai_network):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        stats = analysis_env.source_map()["stats"]

        assert stats["topic_count"] == 1
        assert stats["idea_count"] == 2
        assert stats["example_count"] == 1
        assert stats["reference_count"] == 0
        assert stats["uncertainty_count"] == 0
        assert stats["repetition_count"] == 1
        assert stats["source_segment_count"] == 8

    def test_le_profil_de_voix_est_descriptif(self, analysis_env, no_ai_network):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        profile = analysis_env.source_map()["author_voice_profile"]

        assert profile["tone"] == ["didactique", "encourageant"]
        assert profile["register"] == "langue parlée accessible"
        assert profile["rhetorical_patterns"]

    def test_la_provenance_est_embarquee_dans_le_fichier(
        self, analysis_env, no_ai_network
    ):
        result = analyze_source(analysis_env.project_name, engine=fake_engine())

        analysis = analysis_env.source_map()["analysis"]

        assert analysis["prompt_version"] == SOURCE_ANALYZER_PROMPT_VERSION
        assert analysis["schema_version"] == SOURCE_MAP_SCHEMA_VERSION
        assert analysis["provider"] == "fake"
        assert analysis["strategy"] == "global"
        assert analysis["signature"] == result.signature

    def test_la_requete_ia_demande_une_sortie_structuree(
        self, analysis_env, no_ai_network
    ):
        engine = fake_engine()

        analyze_source(analysis_env.project_name, engine=engine)

        request = engine.last_request

        assert request.wants_structured_output is True
        assert request.response_schema["required"][0] == "theme"
        assert request.metadata["stage"] == STAGE


# ---------------------------------------------------------------------------
# Traçabilité
# ---------------------------------------------------------------------------

class TestTraceability:
    """Chaque élément est rattaché à des SRC existants, et à eux seuls."""

    def test_les_idees_citent_les_src_attendus(self, analysis_env, no_ai_network):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        ideas = analysis_env.source_map()["ideas"]

        assert ideas[0]["idea_id"] == "IDEA001"
        assert ideas[0]["source_refs"] == ["SRC000001", "SRC000002"]
        assert ideas[1]["idea_id"] == "IDEA002"
        assert ideas[1]["source_refs"] == ["SRC000004", "SRC000005"]

    def test_un_src_inexistant_fait_echouer_la_validation(
        self, analysis_env, no_ai_network
    ):
        payload = fake_analysis_payload()
        payload["ideas"][1]["source_refs"] = ["SRC999999"]

        with pytest.raises(SourceMapValidationError) as excinfo:
            analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        assert any("SRC999999" in error for error in excinfo.value.errors)

    def test_un_src_inexistant_ne_publie_rien(self, analysis_env, no_ai_network):
        payload = fake_analysis_payload()
        payload["topics"][0]["source_refs"] = ["SRC000001", "SRC999999"]

        with pytest.raises(SourceMapValidationError):
            analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        assert not analysis_env.source_map_path.exists()

    def test_un_src_inexistant_n_est_pas_supprime_en_silence(
        self, analysis_env, no_ai_network
    ):
        payload = fake_analysis_payload()
        payload["ideas"][0]["source_refs"] = ["SRC000001", "SRC999999"]

        with pytest.raises(SourceMapValidationError):
            analyze_source(analysis_env.project_name, engine=fake_engine(payload))


# ---------------------------------------------------------------------------
# Références internes
# ---------------------------------------------------------------------------

class TestInternalRefs:
    """Aucune référence interne ne doit mener nulle part."""

    def test_un_exemple_pointe_vers_une_idee_normalisee(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        example = analysis_env.source_map()["examples"][0]

        assert example["example_id"] == "EX001"
        assert example["supports_idea_refs"] == ["IDEA001"]

    def test_supports_idea_refs_pendante_echoue(self, analysis_env, no_ai_network):
        payload = fake_analysis_payload()
        payload["examples"][0]["supports_idea_refs"] = ["IDEA999"]

        with pytest.raises(SourceMapValidationError) as excinfo:
            analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        assert any("hors plage" in error for error in excinfo.value.errors)
        assert not analysis_env.source_map_path.exists()

    def test_topic_refs_pendante_echoue(self, analysis_env, no_ai_network):
        payload = fake_analysis_payload()
        payload["ideas"][0]["topic_refs"] = ["TOP999"]

        with pytest.raises(SourceMapValidationError) as excinfo:
            analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        assert any("hors plage" in error for error in excinfo.value.errors)

    def test_relation_pendante_echoue(self, analysis_env, no_ai_network):
        payload = fake_analysis_payload()
        payload["ideas"][1]["relations"] = [
            {"relation": "supports", "to_idea": "inconnue"}
        ]

        with pytest.raises(SourceMapValidationError) as excinfo:
            analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        assert any("hors plage" in error for error in excinfo.value.errors)

    def test_repetition_pointant_vers_une_idee_absente_echoue(
        self, analysis_env, no_ai_network
    ):
        payload = fake_analysis_payload()
        payload["repetitions"][0]["idea_refs"] = ["idea_7", "IDEA999"]

        with pytest.raises(SourceMapValidationError) as excinfo:
            analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        assert any("hors plage" in error for error in excinfo.value.errors)

    def test_les_relations_sont_reecrites_vers_les_ids_canoniques(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        ideas = analysis_env.source_map()["ideas"]

        assert ideas[1]["relations"] == [
            {"relation": "supports", "to_idea": "IDEA001"}
        ]


# ---------------------------------------------------------------------------
# Frontière Phase 3 / Phase 4
# ---------------------------------------------------------------------------

class TestNoEditorialStructure:
    """Un Source Map ne contient jamais de structure de livre."""

    @pytest.mark.parametrize(
        "field, value",
        [
            ("chapters", []),
            ("sections", []),
            ("book_title", "Traverser l'épreuve"),
            ("book_subtitle", "Un guide de la foi"),
            ("table_of_contents", []),
            ("editorial_plan", {}),
            ("outline", []),
        ],
    )
    def test_un_champ_editorial_fait_echouer_l_analyse(
        self, analysis_env, no_ai_network, field, value
    ):
        payload = fake_analysis_payload()
        payload[field] = value

        with pytest.raises(SourceMapEditorialLeakError) as excinfo:
            analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        assert field in excinfo.value.fields
        assert not analysis_env.source_map_path.exists()

    def test_un_titre_de_livre_cache_dans_source_analysis_echoue(
        self, analysis_env, no_ai_network
    ):
        payload = fake_analysis_payload()
        payload["source_analysis"]["book_title"] = "Traverser l'épreuve"

        with pytest.raises(SourceMapEditorialLeakError):
            analyze_source(analysis_env.project_name, engine=fake_engine(payload))

    def test_le_source_map_publie_ne_contient_aucun_champ_editorial(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        payload = analysis_env.source_map()
        serialized = json.dumps(payload, ensure_ascii=False)

        for forbidden in (
            "chapters",
            "sections",
            "book_title",
            "table_of_contents",
            "editorial_plan",
        ):
            assert forbidden not in payload
            assert f'"{forbidden}"' not in serialized

    def test_aucun_identifiant_de_chapitre_ou_de_section(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        serialized = analysis_env.source_map_path.read_text(encoding="utf-8")

        assert "CH001" not in serialized
        assert "SEC001" not in serialized


# ---------------------------------------------------------------------------
# Déterminisme
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Les identifiants et l'ordre viennent du code et de la source, pas du LLM."""

    def test_les_ids_du_llm_sont_renumerotes(self, analysis_env, no_ai_network):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        payload = analysis_env.source_map()

        assert [idea["idea_id"] for idea in payload["ideas"]] == ["IDEA001", "IDEA002"]
        assert [topic["topic_id"] for topic in payload["topics"]] == ["TOP001"]
        assert [item["example_id"] for item in payload["examples"]] == ["EX001"]
        assert [item["repetition_id"] for item in payload["repetitions"]] == ["REP001"]

    def test_trois_ids_farfelus_deviennent_une_serie_continue(
        self, analysis_env, no_ai_network
    ):
        payload = fake_analysis_payload()
        payload["ideas"].append(
            {
                "idea_id": "42",
                "summary": "Traverser signifie avancer malgré tout, pas contourner.",
                "kind": "principle",
                "importance": "supporting",
                "topic_refs": ["t_foi"],
                "relations": [],
                "source_refs": ["SRC000005"],
            }
        )

        analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        ideas = analysis_env.source_map()["ideas"]

        assert [idea["idea_id"] for idea in ideas] == [
            "IDEA001",
            "IDEA002",
            "IDEA003",
        ]

    def test_deux_executions_identiques_donnent_le_meme_fichier(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())
        first = analysis_env.source_map_path.read_bytes()

        analysis_env.source_map_path.unlink()

        analyze_source(analysis_env.project_name, engine=fake_engine(), force=True)
        second = analysis_env.source_map_path.read_bytes()

        assert first == second

    def test_l_ordre_de_la_reponse_ne_change_pas_le_resultat(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())
        ordered = analysis_env.source_map_path.read_bytes()

        shuffled = fake_analysis_payload()
        shuffled["ideas"] = list(reversed(shuffled["ideas"]))

        analysis_env.source_map_path.unlink()
        analyze_source(
            analysis_env.project_name, engine=fake_engine(shuffled), force=True
        )

        assert analysis_env.source_map_path.read_bytes() == ordered

    def test_les_source_refs_desordonnees_sont_remises_en_ordre(
        self, analysis_env, no_ai_network
    ):
        payload = fake_analysis_payload()
        payload["ideas"][0]["source_refs"] = ["SRC000008", "SRC000002", "SRC000005"]

        analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        idea = analysis_env.source_map()["ideas"][0]

        assert idea["source_refs"] == ["SRC000002", "SRC000005", "SRC000008"]

    def test_aucune_reference_n_est_perdue_lors_du_reordonnancement(
        self, analysis_env, no_ai_network
    ):
        payload = fake_analysis_payload()
        payload["ideas"][0]["source_refs"] = ["SRC000008", "SRC000002", "SRC000005"]

        analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        idea = analysis_env.source_map()["ideas"][0]

        assert set(idea["source_refs"]) == {"SRC000002", "SRC000005", "SRC000008"}


# ---------------------------------------------------------------------------
# Couverture et complétude
# ---------------------------------------------------------------------------

class TestCoverage:
    """La couverture est une métrique descriptive, jamais un seuil à atteindre."""

    def test_la_couverture_reflete_les_segments_reellement_cites(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        stats = analysis_env.source_map()["stats"]

        # SRC000001 à SRC000005 sont cités ; les trois hésitations finales
        # (« Euh voilà. », « Bon. », « Hmm oui. ») ne le sont pas.
        assert stats["referenced_source_segments"] == 5
        # source_segment_count EST le total de segments de la source.
        assert stats["source_segment_count"] == 8
        assert stats["source_coverage_ratio"] == pytest.approx(0.625)

    def test_une_couverture_partielle_n_est_pas_un_echec(
        self, analysis_env, no_ai_network
    ):
        result = analyze_source(analysis_env.project_name, engine=fake_engine())

        assert result.stats["source_coverage_ratio"] < 1.0
        assert analysis_env.state()[STATE_KEY]["status"] == STATUS_COMPLETED

    def test_une_couverture_complete_est_possible(self, analysis_env, no_ai_network):
        payload = fake_analysis_payload()
        payload["topics"][0]["source_refs"] = [
            f"SRC{index:06d}" for index in range(1, 9)
        ]

        analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        stats = analysis_env.source_map()["stats"]

        assert stats["referenced_source_segments"] == 8
        assert stats["source_coverage_ratio"] == pytest.approx(1.0)


class TestCompleteness:
    """Une source substantielle ne peut pas produire zéro idée."""

    def test_zero_idee_sur_une_source_substantielle_echoue(
        self, analysis_env, no_ai_network
    ):
        payload = fake_analysis_payload()
        payload["ideas"] = []
        payload["examples"] = []
        payload["repetitions"] = []

        with pytest.raises(SourceMapValidationError) as excinfo:
            analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        assert any("aucune idée" in error for error in excinfo.value.errors)
        assert not analysis_env.source_map_path.exists()

    def test_un_transcript_non_substantiel_est_refuse_avant_tout_appel(
        self, analysis_env, no_ai_network
    ):
        analysis_env.rewrite_transcript(
            build_transcript_document(
                project_name=analysis_env.project_name,
                texts=("Euh.", "Bon."),
            )
        )
        engine = fake_engine()

        with pytest.raises(SourceTranscriptNotSubstantial) as excinfo:
            analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 0
        assert excinfo.value.word_count == 2
        assert not analysis_env.source_map_path.exists()


# ---------------------------------------------------------------------------
# Publication atomique
# ---------------------------------------------------------------------------

class TestAtomicPublication:
    """Un Source Map invalide ou interrompu n'est jamais publié."""

    def test_aucun_partial_ne_subsiste_apres_succes(self, analysis_env, no_ai_network):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        assert analysis_env.source_map_path.exists()
        assert not analysis_env.partial_path.exists()

    def test_aucun_partial_ne_subsiste_apres_echec_de_validation(
        self, analysis_env, no_ai_network
    ):
        payload = fake_analysis_payload()
        payload["ideas"][0]["source_refs"] = ["SRC999999"]

        with pytest.raises(SourceMapValidationError):
            analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        assert not analysis_env.partial_path.exists()
        assert not analysis_env.source_map_path.exists()

    def test_un_echec_d_ecriture_ne_laisse_pas_de_partial(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        import app.file_utils as file_utils

        original = file_utils.Path.replace

        def _boom(self, target):
            raise OSError("disque plein simulé")

        monkeypatch.setattr(file_utils.Path, "replace", _boom)

        with pytest.raises(OSError):
            analyze_source(analysis_env.project_name, engine=fake_engine())

        monkeypatch.setattr(file_utils.Path, "replace", original)

        assert not analysis_env.partial_path.exists()
        assert not analysis_env.source_map_path.exists()

    def test_une_interruption_clavier_ne_laisse_pas_de_partial(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        import app.file_utils as file_utils

        original = file_utils.Path.replace

        def _interrupt(self, target):
            raise KeyboardInterrupt

        monkeypatch.setattr(file_utils.Path, "replace", _interrupt)

        with pytest.raises(KeyboardInterrupt):
            analyze_source(analysis_env.project_name, engine=fake_engine())

        monkeypatch.setattr(file_utils.Path, "replace", original)

        assert not analysis_env.partial_path.exists()

    def test_un_source_map_valide_survit_a_une_analyse_ratee(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())
        published = analysis_env.source_map_path.read_bytes()

        broken = fake_analysis_payload()
        broken["ideas"][0]["source_refs"] = ["SRC999999"]

        with pytest.raises(SourceMapValidationError):
            analyze_source(
                analysis_env.project_name, engine=fake_engine(broken), force=True
            )

        assert analysis_env.source_map_path.read_bytes() == published


# ---------------------------------------------------------------------------
# Échecs
# ---------------------------------------------------------------------------

class TestProviderFailure:
    """Un fournisseur qui tombe ne produit ni analyse, ni faux succès."""

    def test_une_erreur_de_connexion_fait_echouer_l_etape(
        self, analysis_env, no_ai_network
    ):
        engine = fake_engine(script=[AIConnectionError("réseau injoignable")])

        with pytest.raises(AIConnectionError):
            analyze_source(analysis_env.project_name, engine=engine)

        assert not analysis_env.source_map_path.exists()

    def test_l_etat_passe_en_echec(self, analysis_env, no_ai_network):
        engine = fake_engine(script=[AIConnectionError("réseau injoignable")])

        with pytest.raises(AIConnectionError):
            analyze_source(analysis_env.project_name, engine=engine)

        block = analysis_env.state()[STATE_KEY]

        assert block["status"] == STATUS_FAILED
        assert block["error"] == "AIConnectionError"
        assert block["path"] is None

    def test_l_echec_est_comptabilise_sans_tokens_inventes(
        self, analysis_env, no_ai_network
    ):
        engine = fake_engine(script=[AIConnectionError("réseau injoignable")])

        with pytest.raises(AIConnectionError):
            analyze_source(analysis_env.project_name, engine=engine)

        records = analysis_env.state()["ai_usage"]["records"]

        assert len(records) == 1
        assert records[0]["stage"] == STAGE
        assert records[0]["status"] == "failed"
        assert records[0]["input_tokens"] is None
        assert records[0]["output_tokens"] is None

    def test_une_ancienne_analyse_incompatible_n_est_pas_reutilisee(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        analysis_env.rewrite_transcript(
            build_transcript_document(
                project_name=analysis_env.project_name,
                texts=(
                    "Un enseignement entièrement différent sur la patience au travail.",
                    "La patience se construit dans les tâches les plus ordinaires.",
                    "Personne ne devient patient en une seule décision soudaine.",
                    "Cela demande des mois de répétitions discrètes et obstinées.",
                ),
            )
        )

        engine = fake_engine(script=[AIConnectionError("réseau injoignable")])

        with pytest.raises(AIConnectionError):
            analyze_source(analysis_env.project_name, engine=engine)

        assert analysis_env.state()[STATE_KEY]["status"] == STATUS_FAILED


class TestStructuredOutputFailure:
    """Une sortie structurée cassée doit se voir, pas se réparer."""

    def test_un_json_invalide_echoue(self, analysis_env, no_ai_network):
        engine = fake_engine("{ ceci n'est pas du JSON")

        with pytest.raises(AIStructuredOutputError):
            analyze_source(analysis_env.project_name, engine=engine)

        assert not analysis_env.source_map_path.exists()

    def test_un_json_valide_mais_hors_schema_echoue(self, analysis_env, no_ai_network):
        engine = fake_engine({"source_analysis": {"main_theme": "Un thème"}})

        with pytest.raises(AIStructuredOutputError):
            analyze_source(analysis_env.project_name, engine=engine)

        assert not analysis_env.source_map_path.exists()

    def test_aucune_reparation_automatique_n_est_tentee(
        self, analysis_env, no_ai_network
    ):
        engine = fake_engine("{ ceci n'est pas du JSON")

        with pytest.raises(AIStructuredOutputError):
            analyze_source(analysis_env.project_name, engine=engine)

        # Un seul appel : pas de second appel « correctif » au modèle.
        assert engine.call_count == 1

    def test_une_erreur_metier_n_est_pas_rejouee_comme_un_incident_reseau(
        self, analysis_env, no_ai_network
    ):
        engine = fake_engine("pas du JSON du tout")

        with pytest.raises(AIStructuredOutputError):
            analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 1

    def test_un_appel_facture_mais_inexploitable_reste_comptabilise(
        self, analysis_env, no_ai_network
    ):
        payload = fake_analysis_payload()
        payload["ideas"][0]["source_refs"] = ["SRC999999"]

        with pytest.raises(SourceMapValidationError):
            analyze_source(analysis_env.project_name, engine=fake_engine(payload))

        records = analysis_env.state()["ai_usage"]["records"]

        assert len(records) == 1
        assert records[0]["status"] == "completed"
        assert records[0]["input_tokens"] == 12_000
        assert analysis_env.state()[STATE_KEY]["status"] == STATUS_FAILED


class TestStructuredOutputObservability:
    """
    Phase 3B.2 — un appel facturé dont la sortie structurée échoue ENSUITE
    conserve son usage réel et son coût, au lieu de les perdre avec
    l'exception. C'est la correction directe de l'incident réel de la
    validation `pastoral_retreat_v2` : usage Anthropic perdu parce que
    `AIStructuredOutputError` était levée avant la création d'AIResponse.
    """

    def test_usage_provider_survit_a_un_echec_de_schema(
        self, analysis_env, no_ai_network
    ):
        payload = fake_ultra_analysis_payload()
        # Champ requis du transport ultra : son absence échoue au parse, mais
        # ne doit plus effacer l'usage (Phase 3B.2).
        del payload["records"]

        engine = fake_engine(payload, input_tokens=1_000, output_tokens=200)

        with pytest.raises(AIStructuredOutputError):
            analyze_source(analysis_env.project_name, engine=engine)

        records = analysis_env.state()["ai_usage"]["records"]

        assert len(records) == 1
        assert records[0]["status"] == "failed"
        assert records[0]["usage_source"] == "provider"
        assert records[0]["input_tokens"] == 1_000
        assert records[0]["output_tokens"] == 200
        assert records[0]["total_tokens"] == 1_200
        assert not analysis_env.source_map_path.exists()
        assert analysis_env.state()[STATE_KEY]["status"] == STATUS_FAILED

    def test_usage_provider_survit_egalement_a_un_json_invalide(
        self, analysis_env, no_ai_network
    ):
        """Même un JSON simplement mal formé ne doit pas faire perdre l'usage."""
        engine = fake_engine(
            "{ ceci n'est pas du JSON", input_tokens=1_500, output_tokens=90
        )

        with pytest.raises(AIStructuredOutputError):
            analyze_source(analysis_env.project_name, engine=engine)

        records = analysis_env.state()["ai_usage"]["records"]

        assert records[0]["input_tokens"] == 1_500
        assert records[0]["output_tokens"] == 90
        assert records[0]["usage_source"] == "provider"

    def test_sans_usage_rapporte_rien_n_est_invente(
        self, analysis_env, no_ai_network
    ):
        """Sans usage rapporté par le fournisseur, le coût reste explicitement inconnu."""
        engine = fake_engine(
            "{ ceci n'est pas du JSON", input_tokens=None, output_tokens=None
        )

        with pytest.raises(AIStructuredOutputError):
            analyze_source(analysis_env.project_name, engine=engine)

        records = analysis_env.state()["ai_usage"]["records"]

        assert records[0]["input_tokens"] is None
        assert records[0]["output_tokens"] is None
        assert records[0]["usage_source"] == "unavailable"
        assert records[0]["cost"]["status"] == "unknown"

    def test_un_echec_structure_ne_publie_rien_et_ne_met_rien_en_cache(
        self, analysis_env, no_ai_network
    ):
        """
        Une analyse dont le structured output échoue ne publie jamais de
        source_map.json et ne laisse rien réutiliser comme cache valide : la
        tentative suivante réinterroge le moteur.
        """
        payload = fake_ultra_analysis_payload()
        del payload["records"]
        engine = fake_engine(payload, input_tokens=1_000, output_tokens=200)

        with pytest.raises(AIStructuredOutputError):
            analyze_source(analysis_env.project_name, engine=engine)

        assert not analysis_env.source_map_path.exists()
        assert not analysis_env.partial_path.exists()
        assert analysis_env.state()[STATE_KEY]["status"] == STATUS_FAILED

        second_engine = fake_engine(input_tokens=1_000, output_tokens=200)
        analyze_source(analysis_env.project_name, engine=second_engine)

        assert second_engine.call_count == 1
        assert analysis_env.source_map_path.exists()

    def test_un_retry_transitoire_puis_succes_ne_double_compte_pas(
        self, analysis_env, no_ai_network
    ):
        """Doctrine Phase 2 existante : un rejeu réussi ne produit qu'un seul enregistrement."""
        from app.ai.retry import no_delay_policy
        from app.tests.source_analysis_fixtures import fake_analysis_text

        engine = fake_engine(
            script=[
                AIConnectionError("premier essai injoignable"),
                FakeReply(
                    text=fake_analysis_text(),
                    input_tokens=1_000,
                    output_tokens=200,
                ),
            ],
            retry_policy=no_delay_policy(max_attempts=3),
        )

        analyze_source(analysis_env.project_name, engine=engine)

        records = analysis_env.state()["ai_usage"]["records"]

        assert len(records) == 1
        assert records[0]["status"] == "completed"
        assert records[0]["input_tokens"] == 1_000
        assert engine.call_count == 2

    def test_un_echec_structure_non_retryable_ne_declenche_aucun_second_appel(
        self, analysis_env, no_ai_network
    ):
        engine = fake_engine("pas du JSON", input_tokens=1_000, output_tokens=200)

        with pytest.raises(AIStructuredOutputError):
            analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 1


# ---------------------------------------------------------------------------
# Coût, état, rapport
# ---------------------------------------------------------------------------

class TestCostTracking:
    """Le coût vient de l'usage rapporté, et d'un seul endroit."""

    def test_l_appel_est_enregistre_pour_l_etape_source_analysis(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        records = analysis_env.state()["ai_usage"]["records"]

        assert len(records) == 1
        assert records[0]["stage"] == STAGE
        assert records[0]["provider"] == "fake"
        assert records[0]["model"] == "fake-model"

    def test_les_tokens_sont_ceux_du_fournisseur(self, analysis_env, no_ai_network):
        analyze_source(
            analysis_env.project_name,
            engine=fake_engine(input_tokens=9_100, output_tokens=1_300),
        )

        record = analysis_env.state()["ai_usage"]["records"][0]

        assert record["input_tokens"] == 9_100
        assert record["output_tokens"] == 1_300
        assert record["total_tokens"] == 10_400
        assert record["usage_source"] == "provider"

    def test_le_rapport_expose_l_usage_par_etape(self, analysis_env, no_ai_network):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        build_project_report(analysis_env.project_name)
        report = json.loads(
            (analysis_env.sortie / analysis_env.project_name / "report.json").read_text(
                encoding="utf-8"
            )
        )

        assert report["ai_usage"]["calls"] == 1
        assert STAGE in report["ai_usage"]["by_stage"]
        assert report["ai_usage"]["by_stage"][STAGE]["calls"] == 1

    def test_la_section_source_analysis_du_rapport_est_descriptive(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        build_project_report(analysis_env.project_name)
        report = json.loads(
            (analysis_env.sortie / analysis_env.project_name / "report.json").read_text(
                encoding="utf-8"
            )
        )
        section = report["source_analysis"]

        assert section["status"] == STATUS_COMPLETED
        assert section["cached"] is False
        assert section["provider"] == "fake"
        assert section["topics"] == 1
        assert section["ideas"] == 2
        assert section["source_coverage_ratio"] == pytest.approx(0.625)

        # La comptabilité financière ne vit que dans ai_usage.
        assert "input_tokens" not in section
        assert "cost" not in section

    def test_un_projet_sans_analyse_affiche_pending(self, analysis_env, no_ai_network):
        build_project_report(analysis_env.project_name)
        report = json.loads(
            (analysis_env.sortie / analysis_env.project_name / "report.json").read_text(
                encoding="utf-8"
            )
        )

        assert report["source_analysis"]["status"] == "pending"
        assert report["ai_usage"]["calls"] == 0


class TestProjectState:
    """L'étape s'inscrit dans project_state.json sans perturber la V1."""

    def test_le_bloc_source_analysis_est_complet(self, analysis_env, no_ai_network):
        result = analyze_source(analysis_env.project_name, engine=fake_engine())

        block = analysis_env.state()[STATE_KEY]

        assert block["status"] == STATUS_COMPLETED
        assert block["signature"] == result.signature
        assert block["path"] == str(analysis_env.source_map_path)
        assert block["provider"] == "fake"
        assert block["model"] == "fake-model"
        assert block["strategy"] == "global"
        assert block["prompt_version"] == SOURCE_ANALYZER_PROMPT_VERSION
        assert block["schema_version"] == SOURCE_MAP_SCHEMA_VERSION
        assert block["error"] is None

    def test_les_sections_v1_de_l_etat_restent_intactes(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        state = analysis_env.state()

        assert state["files"] == {}
        assert state["chunks"] == {}
        assert state["publication"] == {}


# ---------------------------------------------------------------------------
# Budget de contexte
# ---------------------------------------------------------------------------

class TestContextBudget:
    """Aucune troncature silencieuse, jamais."""

    def test_un_transcript_qui_tient_est_analyse_globalement(
        self, analysis_env, no_ai_network
    ):
        result = analyze_source(analysis_env.project_name, engine=fake_engine())

        assert result.plan.strategy == "global"
        assert result.plan.window_count == 0
        assert result.plan.estimated_input_tokens < result.plan.usable_input_context

    def test_un_transcript_trop_grand_echoue_explicitement(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        import app.config as config

        monkeypatch.setattr(
            config,
            "AI_MODEL_CAPABILITIES",
            {
                "fake:fake-model": {
                    "context_window": 2_000,
                    "max_output_tokens": 500,
                    "supports_structured_output": True,
                    "known": True,
                }
            },
        )
        engine = fake_engine()

        with pytest.raises(SourceAnalysisContextExceeded) as excinfo:
            analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 0
        assert excinfo.value.plan.strategy == "windowed"
        assert excinfo.value.plan.window_count >= 2
        assert not analysis_env.source_map_path.exists()

    def test_l_erreur_de_budget_porte_les_chiffres(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        import app.config as config

        monkeypatch.setattr(
            config,
            "AI_MODEL_CAPABILITIES",
            {
                "fake:fake-model": {
                    "context_window": 2_000,
                    "max_output_tokens": 500,
                    "supports_structured_output": True,
                    "known": True,
                }
            },
        )

        with pytest.raises(SourceAnalysisContextExceeded) as excinfo:
            analyze_source(analysis_env.project_name, engine=fake_engine())

        message = str(excinfo.value)

        assert "tokens estimés" in message
        assert "budget d'entrée utilisable" in message
        assert "Aucune troncature" in message

    def test_le_budget_vient_des_capacites_du_modele(
        self, analysis_env, no_ai_network
    ):
        result = analyze_source(analysis_env.project_name, engine=fake_engine())

        # fake:* -> 128 000 de contexte, 8 000 de sortie, ratio 0.70.
        assert result.plan.context_window == 128_000
        assert result.plan.max_output_tokens == 8_000
        assert result.plan.usable_input_context == int(128_000 * 0.70) - 8_000


# ---------------------------------------------------------------------------
# Routage du modèle
# ---------------------------------------------------------------------------

class TestStageRouting:
    """L'étape passe par app.ai et par la configuration de la Phase 2B."""

    def test_l_etape_est_routee_vers_claude_sonnet_5(self):
        from app.ai.settings import resolve_stage_settings

        settings = resolve_stage_settings(STAGE)

        assert settings.provider == "anthropic"
        assert settings.model == "claude-sonnet-5"

    def test_sans_moteur_injecte_le_registre_est_interroge_pour_l_etape(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        import app.source_analysis.analyzer as analyzer

        asked = []
        engine = fake_engine()

        def _spy(stage, **kwargs):
            asked.append(stage)
            from app.ai.settings import resolve_stage_settings

            return engine, resolve_stage_settings(stage)

        monkeypatch.setattr(analyzer, "get_engine_for_stage", _spy)

        analyze_source(analysis_env.project_name)

        assert asked == [STAGE]

    def test_le_moteur_de_production_se_construit_sans_cle_ni_reseau(
        self, no_ai_network
    ):
        from app.ai.registry import get_engine_for_stage

        engine, settings = get_engine_for_stage(STAGE)

        assert engine.provider_name == "anthropic"
        assert engine.resolve_model() == "claude-sonnet-5"
        assert settings.model == "claude-sonnet-5"

    def test_le_reglage_max_output_tokens_de_l_etape_est_transmis(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        import app.config as config

        monkeypatch.setitem(
            config.AI_STAGE_SETTINGS,
            STAGE,
            {
                "provider": "anthropic",
                "model": "claude-sonnet-5",
                "max_output_tokens": 32_000,
                "temperature": 0.2,
            },
        )
        engine = fake_engine()

        analyze_source(analysis_env.project_name, engine=engine)

        assert engine.last_request.max_output_tokens == 32_000
        assert engine.last_request.temperature == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# Lisibilité humaine
# ---------------------------------------------------------------------------

class TestHumanReadable:
    """Le Source Map est relu par des humains avant la phase suivante."""

    def test_le_fichier_est_en_utf8_sans_echappement(self, analysis_env, no_ai_network):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        raw = analysis_env.source_map_path.read_text(encoding="utf-8")

        assert "épreuves" in raw
        assert "\\u00e9" not in raw

    def test_le_fichier_est_indente_et_termine_par_un_retour_ligne(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        raw = analysis_env.source_map_path.read_text(encoding="utf-8")

        assert '\n  "transcript_id"' in raw
        assert raw.endswith("\n")

    def test_aucun_horodatage_dans_le_contrat(self, analysis_env, no_ai_network):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        payload = analysis_env.source_map()

        assert "generated_at" not in payload
        assert "updated_at" not in payload
        assert "generated_at" not in payload["analysis"]


# ---------------------------------------------------------------------------
# Latence simulée : aucune attente réelle
# ---------------------------------------------------------------------------

def test_la_latence_rapportee_vient_du_moteur(analysis_env, no_ai_network):
    from app.tests.source_analysis_fixtures import fake_analysis_text

    engine = fake_engine(
        script=[
            FakeReply(
                text=fake_analysis_text(),
                input_tokens=100,
                output_tokens=50,
                latency_seconds=3.5,
            )
        ]
    )

    analyze_source(analysis_env.project_name, engine=engine)

    record = analysis_env.state()["ai_usage"]["records"][0]

    assert record["latency_ms"] == 3_500


# ---------------------------------------------------------------------------
# Structured Outputs natif Anthropic — Phase 3B.3
# ---------------------------------------------------------------------------
#
# Ces tests exercent le VRAI AnthropicEngine (pas FakeAIEngine) pour vérifier
# que le VRAI schéma produit par build_response_schema() traverse toute la
# chaîne :
#
#     SourceAnalyzer -> AIRequest.response_schema -> AnthropicEngine
#     -> output_config.format.schema
#
# `requests.post` reste un double explicite (RecordingPost) : aucun socket
# n'est ouvert, conformément à `no_ai_network`.

class TestAnthropicStructuredOutputIntegration:

    def _install_post(self, monkeypatch, *responses):
        import app.ai.providers._http as http_module

        recorder = RecordingPost(responses)
        monkeypatch.setattr(http_module.requests, "post", recorder)
        return recorder

    def _anthropic_engine(self):
        return AnthropicEngine(
            model="claude-sonnet-5",
            api_key="cle-de-test",
            retry_policy=no_delay_policy(max_attempts=1),
        )

    def test_le_schema_reel_du_source_analyzer_atteint_output_config(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        """
        Le schéma effectivement construit pour CE transcript (via
        build_response_schema(), le même que celui utilisé par
        `analyze_source`) doit arriver dans output_config.format.schema de la
        requête HTTP envoyée à Anthropic, adapté à la frontière Anthropic
        (additionalProperties: false ajouté sur chaque objet, Phase 3B.3.1)
        mais sans autre altération.
        """
        recorder = self._install_post(
            monkeypatch, anthropic_response(text=fake_analysis_text())
        )

        result = analyze_source(
            analysis_env.project_name, engine=self._anthropic_engine()
        )

        assert result.cached is False
        assert recorder.call_count == 1

        sent_schema = recorder.last_payload["output_config"]["format"]["schema"]
        assert sent_schema == prepare_anthropic_json_schema(
            build_ultra_compact_response_schema()
        )
        assert sent_schema != prepare_anthropic_json_schema(build_compact_response_schema())
        assert sent_schema != prepare_anthropic_json_schema(build_response_schema())
        assert recorder.last_payload["output_config"]["format"]["type"] == "json_schema"

        # Le Source Map publié est bien celui décodé depuis la réponse HTTP.
        payload = analysis_env.source_map()
        assert payload["source_analysis"]["main_theme"] == (
            "Le rôle de la foi dans la manière de traverser les épreuves"
        )

    def test_json_syntaxiquement_invalide_reste_rejete_localement(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        """
        Reproduit la forme de l'échec réel n°2 (Tentative 2 du rapport) :
        HTTP réussi, JSON tronqué/invalide. Attendu : AIStructuredOutputError,
        usage et coût conservés, aucune publication, aucun cache.
        """
        recorder = self._install_post(
            monkeypatch,
            anthropic_response(
                text='{"source_analysis": {"main_theme": "incomplet"',
                input_tokens=311_362,
                output_tokens=14_494,
            ),
        )

        with pytest.raises(AIStructuredOutputError):
            analyze_source(analysis_env.project_name, engine=self._anthropic_engine())

        assert recorder.call_count == 1
        assert not analysis_env.source_map_path.exists()

        record = analysis_env.state()["ai_usage"]["records"][0]
        assert record["input_tokens"] == 311_362
        assert record["output_tokens"] == 14_494

        state = analysis_env.state()[STATE_KEY]
        assert state["status"] == STATUS_FAILED

    def test_json_valide_mais_champ_requis_absent_reste_rejete_localement(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        """
        Reproduit la forme de l'échec réel n°1 : JSON syntaxiquement valide,
        mais un champ REQUIS du schéma (pas un identifiant local optionnel,
        voir Phase 3B.2) est absent. Attendu : rejet local maintenu.
        """
        from app.tests.source_analysis_fixtures import fake_ultra_analysis_payload

        payload = fake_ultra_analysis_payload()
        del payload["records"]  # champ requis au niveau racine

        recorder = self._install_post(
            monkeypatch, anthropic_response(text=json.dumps(payload, ensure_ascii=False))
        )

        with pytest.raises(AIStructuredOutputError, match="records"):
            analyze_source(analysis_env.project_name, engine=self._anthropic_engine())

        assert recorder.call_count == 1
        assert not analysis_env.source_map_path.exists()

    def test_capabilities_sonnet_5_activent_bien_le_mecanisme_natif(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        """
        La capability supports_structured_output=True de claude-sonnet-5
        correspond maintenant à un comportement réel de l'engine, pas
        seulement à une déclaration de configuration.
        """
        engine = self._anthropic_engine()
        assert engine.capabilities("claude-sonnet-5").supports_structured_output is True

        recorder = self._install_post(
            monkeypatch, anthropic_response(text=fake_analysis_text())
        )

        analyze_source(analysis_env.project_name, engine=engine)

        assert "output_config" in recorder.last_payload
        # Capability native => aucune consigne JSON annexée au prompt utilisateur.
        user_message = recorder.last_payload["messages"][0]["content"]
        assert "Réponds UNIQUEMENT avec un objet JSON valide" not in user_message
