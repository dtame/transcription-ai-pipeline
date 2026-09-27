"""
Cache et idempotence de l'analyse de source.

Enjeu concret : un appel au Source Analyzer est payant. Relancer la Phase 3 sur
un projet inchangé doit coûter zéro, et la relancer sur un projet changé doit
coûter un appel — jamais l'inverse.

Ces tests couvrent surtout la faiblesse identifiée par l'audit V1 : une
signature qui ignore la version du prompt et du code laisse un cache valide
alors que le résultat ne correspond plus à ce que produirait le programme.
"""

from __future__ import annotations

import pytest

from app.source_analysis.analyzer import STAGE, analyze_source
from app.source_analysis.cache import (
    SignatureInputs,
    build_signature,
    is_cache_valid,
    prompt_fingerprint,
    published_signature,
)
from app.source_analysis.state import STATE_KEY, STATUS_COMPLETED
from app.tests.source_analysis_fixtures import (  # noqa: F401 — fixture pytest
    analysis_env,
    build_transcript_document,
    fake_analysis_payload,
    fake_engine,
)

_OTHER_TEXTS = (
    "La patience se construit dans les tâches les plus ordinaires du quotidien.",
    "Personne ne devient patient au terme d'une seule décision soudaine.",
    "Cela demande des mois de répétitions discrètes, obstinées et peu glorieuses.",
    "Ce qui se répète finit par former ce que nous sommes devenus.",
    "Traverser ne veut pas dire contourner, cela veut dire avancer malgré tout.",
)


def _signature_inputs(**overrides) -> SignatureInputs:
    base = {
        "transcript_sha256": "a" * 64,
        "transcript_id": "TR001",
        "prompt_version": "1.0",
        "prompt_sha256": "b" * 64,
        "schema_version": "1.0",
        "response_schema_sha256": "c" * 64,
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "temperature": None,
        "max_output_tokens": None,
        "context_safety_ratio": 0.70,
        "output_language": "fr",
    }
    base.update(overrides)

    return SignatureInputs(**base)


class TestSignature:
    """La signature couvre les données, le contrat, le code et le routage."""

    def test_deux_entrees_identiques_donnent_la_meme_signature(self):
        assert build_signature(_signature_inputs()) == build_signature(
            _signature_inputs()
        )

    @pytest.mark.parametrize(
        "field, value",
        [
            ("transcript_sha256", "d" * 64),
            ("transcript_id", "TR002"),
            ("prompt_version", "1.1"),
            ("prompt_sha256", "e" * 64),
            ("schema_version", "2.0"),
            ("response_schema_sha256", "f" * 64),
            ("provider", "openai"),
            ("model", "claude-opus-5"),
            ("temperature", 0.3),
            ("max_output_tokens", 32_000),
            ("context_safety_ratio", 0.5),
            ("output_language", "en"),
        ],
    )
    def test_chaque_entree_influence_la_signature(self, field, value):
        reference = build_signature(_signature_inputs())

        assert build_signature(_signature_inputs(**{field: value})) != reference

    def test_l_empreinte_de_prompt_distingue_systeme_et_utilisateur(self):
        """
        Déplacer du texte du prompt système vers le prompt utilisateur change
        l'appel, donc doit changer l'empreinte.
        """
        assert prompt_fingerprint("AB", "C") != prompt_fingerprint("A", "BC")

    def test_la_signature_est_lisible_dans_le_fichier_publie(self):
        assert published_signature({"analysis": {"signature": "abc"}}) == "abc"
        assert published_signature({"analysis": {}}) == ""
        assert published_signature({}) == ""
        assert published_signature(None) == ""


class TestCacheValidity:
    """Trois concordances sont exigées, pas deux."""

    def test_un_cache_concordant_est_valide(self):
        assert is_cache_valid(
            signature="sig",
            state_block={"status": STATUS_COMPLETED, "signature": "sig"},
            published_payload={"analysis": {"signature": "sig"}},
        )

    def test_un_etat_en_echec_invalide_le_cache(self):
        assert not is_cache_valid(
            signature="sig",
            state_block={"status": "failed", "signature": "sig"},
            published_payload={"analysis": {"signature": "sig"}},
        )

    def test_un_fichier_absent_invalide_le_cache(self):
        assert not is_cache_valid(
            signature="sig",
            state_block={"status": STATUS_COMPLETED, "signature": "sig"},
            published_payload=None,
        )

    def test_un_fichier_d_une_autre_analyse_invalide_le_cache(self):
        assert not is_cache_valid(
            signature="sig",
            state_block={"status": STATUS_COMPLETED, "signature": "sig"},
            published_payload={"analysis": {"signature": "autre"}},
        )

    def test_un_etat_absent_invalide_le_cache(self):
        assert not is_cache_valid(
            signature="sig",
            state_block={},
            published_payload={"analysis": {"signature": "sig"}},
        )


class TestCacheHit:
    """Deuxième exécution identique : aucun appel, aucun coût."""

    def test_le_premier_run_appelle_le_modele_une_fois(
        self, analysis_env, no_ai_network
    ):
        engine = fake_engine()

        analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 1

    def test_le_second_run_identique_n_appelle_pas_le_modele(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        second = fake_engine()
        result = analyze_source(analysis_env.project_name, engine=second)

        assert second.call_count == 0
        assert result.cached is True

    def test_le_source_map_est_reutilise_tel_quel(self, analysis_env, no_ai_network):
        analyze_source(analysis_env.project_name, engine=fake_engine())
        published = analysis_env.source_map_path.read_bytes()

        result = analyze_source(analysis_env.project_name, engine=fake_engine())

        assert analysis_env.source_map_path.read_bytes() == published
        assert result.payload["stats"]["idea_count"] == 2

    def test_un_cache_hit_n_ajoute_aucun_cout(self, analysis_env, no_ai_network):
        analyze_source(analysis_env.project_name, engine=fake_engine())
        analyze_source(analysis_env.project_name, engine=fake_engine())

        records = analysis_env.state()["ai_usage"]["records"]

        assert len(records) == 1
        assert records[0]["stage"] == STAGE

    def test_force_ignore_un_cache_valide(self, analysis_env, no_ai_network):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        engine = fake_engine()
        result = analyze_source(
            analysis_env.project_name, engine=engine, force=True
        )

        assert engine.call_count == 1
        assert result.cached is False

    def test_un_fichier_supprime_provoque_une_nouvelle_analyse(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())
        analysis_env.source_map_path.unlink()

        engine = fake_engine()
        analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 1

    def test_un_fichier_corrompu_provoque_une_nouvelle_analyse(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())
        analysis_env.source_map_path.write_text("{ cassé", encoding="utf-8")

        engine = fake_engine()
        analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 1

    def test_un_fichier_edite_a_la_main_et_devenu_invalide_est_rejete(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        payload = analysis_env.source_map()
        payload["ideas"][0]["source_refs"] = ["SRC999999"]
        analysis_env.source_map_path.write_text(
            __import__("json").dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

        engine = fake_engine()
        analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 1


class TestCacheInvalidation:
    """Chaque invalidateur doit réellement invalider."""

    def test_un_transcript_modifie_invalide_le_cache(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())
        first_signature = analysis_env.state()[STATE_KEY]["signature"]

        analysis_env.rewrite_transcript(
            build_transcript_document(
                project_name=analysis_env.project_name,
                texts=_OTHER_TEXTS,
            )
        )

        payload = fake_analysis_payload()
        payload["topics"][0]["source_refs"] = ["SRC000001", "SRC000002"]
        payload["ideas"][0]["source_refs"] = ["SRC000001"]
        payload["ideas"][1]["source_refs"] = ["SRC000004"]
        payload["examples"][0]["source_refs"] = ["SRC000003"]
        payload["repetitions"][0]["source_refs"] = ["SRC000002", "SRC000004"]

        engine = fake_engine(payload)
        analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 1
        assert analysis_env.state()[STATE_KEY]["signature"] != first_signature

    def test_une_version_de_prompt_modifiee_invalide_le_cache(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        import app.source_analysis.prompt as prompt_module

        analyze_source(analysis_env.project_name, engine=fake_engine())

        monkeypatch.setattr(prompt_module, "SOURCE_ANALYZER_PROMPT_VERSION", "1.4")

        engine = fake_engine()
        analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 1
        assert analysis_env.state()[STATE_KEY]["prompt_version"] == "1.4"

    def test_un_texte_de_prompt_modifie_invalide_le_cache_sans_bump(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        """
        Correction exacte de la faiblesse relevée par l'audit V1 : le texte du
        prompt change, la version non, et le cache doit malgré tout s'invalider.
        """
        import app.source_analysis.prompt as prompt_module

        analyze_source(analysis_env.project_name, engine=fake_engine())

        original = prompt_module.build_system_prompt

        monkeypatch.setattr(
            prompt_module,
            "build_system_prompt",
            lambda language: original(language) + "\n\nConsigne supplémentaire.",
        )

        engine = fake_engine()
        analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 1
        assert analysis_env.state()[STATE_KEY]["prompt_version"] == "1.3"

    def test_un_schema_modifie_invalide_le_cache(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        import app.source_analysis.analyzer as analyzer
        import app.source_analysis.models as models

        analyze_source(analysis_env.project_name, engine=fake_engine())

        monkeypatch.setattr(models, "SOURCE_MAP_SCHEMA_VERSION", "1.1")
        monkeypatch.setattr(analyzer, "SOURCE_MAP_SCHEMA_VERSION", "1.1")

        engine = fake_engine()

        # Le validateur attend désormais la version 1.1 : l'analyse est bien
        # relancée, ce qui est le comportement testé ici.
        try:
            analyze_source(analysis_env.project_name, engine=engine)
        except Exception:
            pass

        assert engine.call_count == 1

    def test_un_modele_different_invalide_le_cache(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())

        engine = fake_engine(model="fake-model-xl")
        analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 1
        assert analysis_env.state()[STATE_KEY]["model"] == "fake-model-xl"

    def test_un_ratio_de_securite_different_invalide_le_cache(
        self, analysis_env, no_ai_network, monkeypatch
    ):
        import app.config as config

        analyze_source(analysis_env.project_name, engine=fake_engine())

        monkeypatch.setitem(
            config.AI_STAGE_SETTINGS,
            STAGE,
            {
                "provider": "anthropic",
                "model": "claude-sonnet-5",
                "context_safety_ratio": 0.5,
            },
        )

        engine = fake_engine()
        analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 1

    def test_une_langue_de_sortie_differente_invalide_le_cache(
        self, analysis_env, no_ai_network
    ):
        analyze_source(analysis_env.project_name, engine=fake_engine())
        first_signature = analysis_env.state()[STATE_KEY]["signature"]

        analysis_env.rewrite_transcript(
            build_transcript_document(
                project_name=analysis_env.project_name,
                language="en",
            )
        )

        engine = fake_engine()
        analyze_source(analysis_env.project_name, engine=engine)

        assert engine.call_count == 1
        assert analysis_env.state()[STATE_KEY]["signature"] != first_signature
