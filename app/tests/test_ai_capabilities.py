"""
Capacités de modèle et budget de contexte.

Ce que ce module protège surtout : l'absence de fenêtre de contexte
universelle. Après la Phase 2, `4096` n'est plus une vérité applicative mais
le num_ctx d'Ollama d'un côté, et un repli explicitement marqué known=False
de l'autre.
"""

from __future__ import annotations

import pytest

import app.config as config

from app.ai.capabilities import (
    SOURCE_BUILTIN,
    SOURCE_CONFIG,
    SOURCE_FALLBACK,
    ModelCapabilities,
    default_safety_ratio,
    resolve_capabilities,
    validate_safety_ratio,
)


class TestModelCapabilitiesValidation:

    def test_construction_valide(self):
        caps = ModelCapabilities(
            provider="fake",
            model="m",
            context_window=128_000,
            max_output_tokens=8_000,
            supports_structured_output=True,
        )

        assert caps.context_window == 128_000
        assert caps.max_output_tokens == 8_000
        assert caps.supports_structured_output is True
        assert caps.supports_system_prompt is True

    @pytest.mark.parametrize("context_window", [0, -1])
    def test_context_window_invalide(self, context_window):
        with pytest.raises(ValueError, match="context_window"):
            ModelCapabilities(
                provider="p", model="m",
                context_window=context_window, max_output_tokens=10,
            )

    @pytest.mark.parametrize("max_output", [0, -5])
    def test_max_output_invalide(self, max_output):
        with pytest.raises(ValueError, match="max_output_tokens"):
            ModelCapabilities(
                provider="p", model="m",
                context_window=1000, max_output_tokens=max_output,
            )

    def test_max_output_superieur_au_contexte_refuse(self):
        with pytest.raises(ValueError, match="dépasser context_window"):
            ModelCapabilities(
                provider="p", model="m",
                context_window=1000, max_output_tokens=2000,
            )


class TestSafetyRatio:

    def test_ratio_valide(self):
        assert validate_safety_ratio(0.7) == 0.7
        assert validate_safety_ratio(1.0) == 1.0

    @pytest.mark.parametrize("ratio", [0, -0.1, 1.2, 2])
    def test_ratio_invalide(self, ratio):
        with pytest.raises(ValueError, match="safety ratio"):
            validate_safety_ratio(ratio)

    def test_usable_context_applique_le_ratio(self):
        caps = ModelCapabilities(
            provider="p", model="m",
            context_window=128_000, max_output_tokens=8_000,
        )

        assert caps.usable_context(0.70) == 89_600

    def test_usable_context_utilise_le_defaut_global(self, monkeypatch):
        monkeypatch.setattr(config, "AI_CONTEXT_SAFETY_RATIO", 0.5)

        caps = ModelCapabilities(
            provider="p", model="m",
            context_window=100_000, max_output_tokens=1_000,
        )

        assert default_safety_ratio() == 0.5
        assert caps.usable_context() == 50_000

    def test_usable_context_ratio_invalide(self):
        caps = ModelCapabilities(
            provider="p", model="m", context_window=1000, max_output_tokens=100
        )

        with pytest.raises(ValueError, match="safety ratio"):
            caps.usable_context(1.5)

    def test_usable_input_context_reserve_la_sortie(self):
        caps = ModelCapabilities(
            provider="p", model="m",
            context_window=100_000, max_output_tokens=10_000,
        )

        assert caps.usable_input_context(0.80) == 70_000

    def test_usable_input_context_jamais_negatif(self):
        """Si la sortie absorbe tout le budget, on retourne 0, pas un négatif."""
        caps = ModelCapabilities(
            provider="p", model="m",
            context_window=10_000, max_output_tokens=9_000,
        )

        assert caps.usable_input_context(0.5) == 0


class TestResolution:

    def test_ollama_herite_du_num_ctx_reel_de_la_configuration(self):
        """La valeur n'est pas inventée : c'est celle que la V1 envoie déjà."""
        caps = resolve_capabilities("ollama", "qwen3:8b")

        assert caps.context_window == config.OLLAMA_OPTIONS["num_ctx"]
        assert caps.known is True
        assert caps.source == SOURCE_BUILTIN

    def test_ollama_suit_un_changement_de_configuration(self, monkeypatch):
        monkeypatch.setattr(
            config, "OLLAMA_OPTIONS", {"temperature": 0.2, "num_ctx": 32_768}
        )

        assert resolve_capabilities("ollama", "qwen3:8b").context_window == 32_768

    def test_modele_inconnu_retourne_un_repli_marque(self):
        caps = resolve_capabilities("openai", "un-modele-non-catalogue")

        assert caps.known is False
        assert caps.source == SOURCE_FALLBACK
        assert caps.context_window == config.AI_FALLBACK_CONTEXT_WINDOW

    def test_aucune_capacite_cloud_inventee(self):
        """Phase 2 ne prétend connaître aucune fenêtre de contexte cloud."""
        for provider, model in (("openai", "gpt-4o-mini"), ("anthropic", "un-modele")):
            assert resolve_capabilities(provider, model).known is False

    def test_override_par_modele_exact(self, monkeypatch):
        monkeypatch.setattr(
            config,
            "AI_MODEL_CAPABILITIES",
            {
                "openai:mon-modele": {
                    "context_window": 200_000,
                    "max_output_tokens": 16_000,
                    "supports_structured_output": True,
                    "source": "tarification vérifiée le 2026-01-01",
                }
            },
        )

        caps = resolve_capabilities("openai", "mon-modele")

        assert caps.context_window == 200_000
        assert caps.max_output_tokens == 16_000
        assert caps.supports_structured_output is True
        assert caps.known is True
        assert caps.source == "tarification vérifiée le 2026-01-01"

    def test_override_generique_du_provider(self, monkeypatch):
        monkeypatch.setattr(
            config,
            "AI_MODEL_CAPABILITIES",
            {"anthropic:*": {"context_window": 64_000, "max_output_tokens": 4_000}},
        )

        caps = resolve_capabilities("anthropic", "n-importe-lequel")

        assert caps.context_window == 64_000
        assert caps.source == SOURCE_CONFIG

    def test_modele_exact_prioritaire_sur_generique(self, monkeypatch):
        monkeypatch.setattr(
            config,
            "AI_MODEL_CAPABILITIES",
            {
                "openai:*": {"context_window": 8_000, "max_output_tokens": 1_000},
                "openai:precis": {"context_window": 32_000, "max_output_tokens": 2_000},
            },
        )

        assert resolve_capabilities("openai", "precis").context_window == 32_000
        assert resolve_capabilities("openai", "autre").context_window == 8_000

    def test_aucune_fenetre_universelle(self, monkeypatch):
        """Deux providers peuvent avoir des fenêtres différentes simultanément."""
        monkeypatch.setattr(
            config,
            "AI_MODEL_CAPABILITIES",
            {
                "anthropic:*": {"context_window": 200_000, "max_output_tokens": 8_000},
                "lmstudio:*": {"context_window": 8_192, "max_output_tokens": 1_024},
            },
        )

        assert resolve_capabilities("anthropic", "a").context_window == 200_000
        assert resolve_capabilities("lmstudio", "b").context_window == 8_192
        assert resolve_capabilities("ollama", "c").context_window == (
            config.OLLAMA_OPTIONS["num_ctx"]
        )

    def test_provider_insensible_a_la_casse(self):
        assert resolve_capabilities("OLLAMA", "m").known is True

    def test_to_dict(self):
        data = resolve_capabilities("fake", "fake-model").to_dict()

        assert data["provider"] == "fake"
        assert data["supports_structured_output"] is True
        assert data["known"] is True
