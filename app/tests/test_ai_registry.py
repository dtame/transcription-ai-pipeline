"""
Registre unique, configuration par étape, et compatibilité V1.

La partie compatibilité est la plus sensible du lot : `send_prompt()` doit
retourner exactement ce qu'il retournait avant la Phase 2. Les chaînes
attendues sont écrites en dur dans ce module, telles qu'elles figuraient dans
l'ancien app/ai_engine.py, pour que toute dérive se voie immédiatement.
"""

from __future__ import annotations

import pytest

import app.config as config

from app.ai.providers import (
    AnthropicEngine,
    BaseAIEngine,
    FakeAIEngine,
    LMStudioEngine,
    OllamaEngine,
    OpenAIEngine,
)
from app.ai.registry import (
    available_providers,
    get_ai_engine,
    get_ai_provider,
    get_engine_for_stage,
    register_ai_engine,
    unregister_ai_engine,
)

# Sortie historique de FakeAIEngine.send_prompt(), reprise mot pour mot.
V1_SEND_PROMPT_HEADER = (
    "# Document traité (simulation)\n\n"
    "> Ce document a été traité par le moteur IA simulé (FakeAIEngine).\n"
    "> Aucune transformation réelle n'a été appliquée.\n\n"
)


class TestRegistre:

    def test_tous_les_providers_attendus(self):
        assert available_providers() == [
            "anthropic",
            "fake",
            "lmstudio",
            "ollama",
            "openai",
        ]

    @pytest.mark.parametrize(
        "nom, classe",
        [
            ("ollama", OllamaEngine),
            ("lmstudio", LMStudioEngine),
            ("openai", OpenAIEngine),
            ("anthropic", AnthropicEngine),
            ("fake", FakeAIEngine),
        ],
    )
    def test_creation_par_nom(self, nom, classe):
        assert isinstance(get_ai_engine(nom), classe)

    def test_suit_ai_provider_de_la_configuration(self, monkeypatch):
        monkeypatch.setattr(config, "AI_PROVIDER", "fake")

        assert isinstance(get_ai_engine(), FakeAIEngine)

    def test_ai_provider_lu_a_l_appel(self, monkeypatch):
        """Un test peut changer AI_PROVIDER sans recharger le module."""
        monkeypatch.setattr(config, "AI_PROVIDER", "lmstudio")
        assert isinstance(get_ai_engine(), LMStudioEngine)

        monkeypatch.setattr(config, "AI_PROVIDER", "fake")
        assert isinstance(get_ai_engine(), FakeAIEngine)

    def test_casse_et_espaces_tolerés(self):
        assert isinstance(get_ai_engine("  FAKE  "), FakeAIEngine)

    def test_provider_inconnu_leve_valueerror_comme_en_v1(self):
        with pytest.raises(ValueError, match="AI_PROVIDER inconnu"):
            get_ai_engine("provider-inexistant")

    def test_message_liste_les_valeurs_acceptees(self):
        with pytest.raises(ValueError) as exc:
            get_ai_engine("provider-inexistant")

        assert "fake" in str(exc.value)
        assert "ollama" in str(exc.value)

    def test_alias_get_ai_provider(self):
        assert get_ai_provider is get_ai_engine

    def test_arguments_transmis_au_moteur(self):
        engine = get_ai_engine("fake", model="fake-editor")

        assert engine.resolve_model() == "fake-editor"

    def test_un_seul_registre(self):
        """Le registre de app.ai et celui de app.ai_engine sont le même objet."""
        import app.ai_engine as facade

        assert facade.get_ai_engine is get_ai_engine


class TestEnregistrementDeProviders:

    def test_ajout_et_retrait(self):
        class MonMoteur(FakeAIEngine):
            provider_name = "mon-moteur"

        try:
            register_ai_engine("mon-moteur", MonMoteur)
            assert isinstance(get_ai_engine("mon-moteur"), MonMoteur)
        finally:
            unregister_ai_engine("mon-moteur")

        with pytest.raises(ValueError):
            get_ai_engine("mon-moteur")

    def test_ecrasement_refuse_par_defaut(self):
        with pytest.raises(ValueError, match="déjà enregistré"):
            register_ai_engine("fake", FakeAIEngine)

    def test_classe_non_conforme_refusee(self):
        class PasUnMoteur:
            pass

        with pytest.raises(TypeError, match="BaseAIEngine"):
            register_ai_engine("bidon", PasUnMoteur)


class TestConfigurationParEtape:

    def test_etape_non_configuree_herite_du_provider_global(self, monkeypatch):
        monkeypatch.setattr(config, "AI_PROVIDER", "fake")
        monkeypatch.setattr(config, "AI_STAGE_SETTINGS", {})

        engine, settings = get_engine_for_stage("source_analysis")

        assert isinstance(engine, FakeAIEngine)
        assert settings.provider == "fake"
        assert settings.model is None

    def test_etape_configuree(self, monkeypatch):
        monkeypatch.setattr(config, "AI_PROVIDER", "ollama")
        monkeypatch.setattr(
            config,
            "AI_STAGE_SETTINGS",
            {
                "source_analysis": {
                    "provider": "fake",
                    "model": "fake-analyste",
                    "temperature": 0.1,
                    "max_output_tokens": 4000,
                }
            },
        )

        engine, settings = get_engine_for_stage("source_analysis")

        assert isinstance(engine, FakeAIEngine)
        assert settings.model == "fake-analyste"
        assert settings.temperature == 0.1
        assert settings.max_output_tokens == 4000
        assert engine.resolve_model() == "fake-analyste"

    def test_etapes_differentes_providers_differents(self, monkeypatch):
        monkeypatch.setattr(config, "AI_PROVIDER", "ollama")
        monkeypatch.setattr(
            config,
            "AI_STAGE_SETTINGS",
            {
                "source_analysis": {"provider": "fake"},
                "book_generation": {"provider": "lmstudio"},
            },
        )

        assert isinstance(get_engine_for_stage("source_analysis")[0], FakeAIEngine)
        assert isinstance(get_engine_for_stage("book_generation")[0], LMStudioEngine)
        assert isinstance(get_engine_for_stage("book_validation")[0], OllamaEngine)

    def test_ratio_de_contexte_surchargeable_par_etape(self, monkeypatch):
        monkeypatch.setattr(config, "AI_CONTEXT_SAFETY_RATIO", 0.70)
        monkeypatch.setattr(
            config,
            "AI_STAGE_SETTINGS",
            {"book_generation": {"provider": "fake", "context_safety_ratio": 0.5}},
        )

        _, global_stage = get_engine_for_stage("source_analysis")
        _, surcharge = get_engine_for_stage("book_generation")

        assert global_stage.context_safety_ratio == 0.70
        assert surcharge.context_safety_ratio == 0.5

    def test_ratio_invalide_refuse(self, monkeypatch):
        monkeypatch.setattr(
            config,
            "AI_STAGE_SETTINGS",
            {"source_analysis": {"provider": "fake", "context_safety_ratio": 1.5}},
        )

        with pytest.raises(ValueError, match="safety ratio"):
            get_engine_for_stage("source_analysis")

    def test_etapes_non_editoriales_non_configurees(self):
        """
        Phase 2B ne configure QUE les quatre étapes éditoriales.

        Remplace l'assertion « AI_STAGE_SETTINGS est vide » de la Phase 2 :
        les quatre étapes éditoriales sont désormais verrouillées (voir
        test_ai_production_models.py), mais les étapes visuelles et de rendu
        n'ont toujours aucun modèle supposé.
        """
        for stage in ("visual_design", "image_generation", "document_rendering"):
            assert stage not in config.AI_STAGE_SETTINGS

    def test_reglages_serialisables(self, monkeypatch):
        monkeypatch.setattr(config, "AI_PROVIDER", "fake")

        _, settings = get_engine_for_stage("visual_design")

        assert settings.to_dict()["stage"] == "visual_design"


class TestCompatibiliteV1:

    def test_send_prompt_retourne_une_chaine(self):
        resultat = FakeAIEngine().send_prompt("mon prompt")

        assert isinstance(resultat, str)

    def test_send_prompt_fake_identique_a_la_v1(self):
        prompt = "Voici le texte du chunk à traiter."

        assert FakeAIEngine().send_prompt(prompt) == (
            V1_SEND_PROMPT_HEADER + prompt[-1000:]
        )

    def test_send_prompt_fake_tronque_a_1000_caracteres(self):
        prompt = "x" * 3000

        assert FakeAIEngine().send_prompt(prompt) == (
            V1_SEND_PROMPT_HEADER + "x" * 1000
        )

    def test_process_fake_identique_a_la_v1(self):
        texte = "Contenu original du chunk."
        attendu = f"""# Traitement IA simulé

> Ce chunk a été traité par le moteur IA simulé (FakeAIEngine).
> Aucune transformation réelle n'a été appliquée.

## Contenu original

{texte}
"""

        assert FakeAIEngine().process(texte) == attendu

    def test_build_prompt_delegue_au_prompt_manager(self, monkeypatch):
        appels = []

        def _faux_build(task_name, text, project_name=None):
            appels.append((task_name, text, project_name))
            return "PROMPT CONSTRUIT"

        import app.ai.providers.base as base_module

        monkeypatch.setattr(base_module, "_build_prompt", _faux_build)

        resultat = FakeAIEngine().build_prompt("texte brut", project_name="mon_projet")

        assert resultat == "PROMPT CONSTRUIT"
        assert appels == [(config.AI_TASK, "texte brut", "mon_projet")]

    def test_build_prompt_reel_retourne_une_chaine(self):
        prompt = FakeAIEngine().build_prompt("texte de transcription")

        assert isinstance(prompt, str)
        assert "texte de transcription" in prompt

    def test_interface_v1_toujours_presente(self):
        engine = FakeAIEngine()

        for methode in ("send_prompt", "build_prompt", "process"):
            assert callable(getattr(engine, methode))

    def test_send_prompt_disponible_sur_tous_les_moteurs(self):
        for nom in available_providers():
            engine = get_ai_engine(nom)

            assert isinstance(engine, BaseAIEngine)
            assert callable(engine.send_prompt)

    def test_facade_ai_engine_exporte_l_api_v1(self):
        import app.ai_engine as facade

        for nom in (
            "BaseAIEngine",
            "FakeAIEngine",
            "OllamaEngine",
            "LMStudioEngine",
            "OpenAIEngine",
            "get_ai_engine",
        ):
            assert hasattr(facade, nom)

    def test_facade_expose_aussi_les_nouveautes(self):
        import app.ai_engine as facade

        assert hasattr(facade, "AIRequest")
        assert hasattr(facade, "AIResponse")
        assert hasattr(facade, "AnthropicEngine")

    def test_import_v1_des_consommateurs_inchange(self):
        """Les 3 appelants V1 importent toujours le même symbole."""
        from app.ai_engine import get_ai_engine as depuis_facade

        assert depuis_facade("fake") is not None

    def test_send_prompt_passe_par_generate(self):
        """Un seul transport : send_prompt n'a pas sa propre implémentation."""
        engine = FakeAIEngine()
        engine.send_prompt("prompt legacy")

        assert engine.call_count == 1
        assert engine.last_request.prompt == "prompt legacy"
