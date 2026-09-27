"""
Contrats AIRequest / AIResponse.

Point le plus important de ce module : vérifier qu'un usage ABSENT reste
None et ne devient jamais 0. Un rapport qui affiche « 0 token consommé »
pour un appel dont le fournisseur n'a rien rapporté est un rapport faux.
"""

from __future__ import annotations

import pytest

from app.ai.contracts import (
    AIRequest,
    AIResponse,
    USAGE_FROM_PROVIDER,
    USAGE_UNAVAILABLE,
)


class TestAIRequest:

    def test_champs_minimaux(self):
        request = AIRequest(prompt="Analyse ce texte.")

        assert request.prompt == "Analyse ce texte."
        assert request.system_prompt is None
        assert request.model is None
        assert request.temperature is None
        assert request.max_output_tokens is None
        assert request.response_schema is None
        assert request.metadata == {}

    def test_champs_complets(self):
        request = AIRequest(
            prompt="texte",
            system_prompt="Tu es un éditeur.",
            model="fake-editor",
            temperature=0.2,
            max_output_tokens=4000,
            response_schema={"type": "object"},
            timeout_seconds=30,
            metadata={"stage": "source_analysis"},
        )

        assert request.model == "fake-editor"
        assert request.temperature == 0.2
        assert request.max_output_tokens == 4000
        assert request.timeout_seconds == 30

    def test_stage_vient_des_metadonnees(self):
        assert AIRequest(prompt="x", metadata={"stage": "book_generation"}).stage == (
            "book_generation"
        )
        assert AIRequest(prompt="x").stage is None

    def test_wants_structured_output(self):
        assert AIRequest(prompt="x").wants_structured_output is False
        assert AIRequest(prompt="x", response_schema={"type": "object"}).wants_structured_output

    def test_prompt_vide_refuse(self):
        with pytest.raises(ValueError, match="prompt"):
            AIRequest(prompt="")

        with pytest.raises(ValueError, match="prompt"):
            AIRequest(prompt="   \n  ")

    @pytest.mark.parametrize("temperature", [-0.1, 2.5])
    def test_temperature_hors_plage_refusee(self, temperature):
        with pytest.raises(ValueError, match="temperature"):
            AIRequest(prompt="x", temperature=temperature)

    @pytest.mark.parametrize("max_output", [0, -10])
    def test_max_output_tokens_invalide_refuse(self, max_output):
        with pytest.raises(ValueError, match="max_output_tokens"):
            AIRequest(prompt="x", max_output_tokens=max_output)

    def test_timeout_invalide_refuse(self):
        with pytest.raises(ValueError, match="timeout"):
            AIRequest(prompt="x", timeout_seconds=0)

    def test_with_prompt_conserve_les_autres_champs(self):
        original = AIRequest(
            prompt="original",
            system_prompt="sys",
            model="m",
            temperature=0.3,
            max_output_tokens=100,
            response_schema={"type": "object"},
            timeout_seconds=12,
            metadata={"stage": "editorial_planning"},
        )

        copie = original.with_prompt("réécrit")

        assert copie.prompt == "réécrit"
        assert copie.system_prompt == "sys"
        assert copie.model == "m"
        assert copie.temperature == 0.3
        assert copie.max_output_tokens == 100
        assert copie.response_schema == {"type": "object"}
        assert copie.timeout_seconds == 12
        assert copie.stage == "editorial_planning"


class TestAIResponse:

    def test_tous_les_champs_du_contrat(self):
        response = AIResponse(
            text="contenu",
            parsed={"ok": True},
            provider="openai",
            model="un-modele",
            input_tokens=12450,
            output_tokens=2180,
            latency_ms=4210,
            finish_reason="stop",
            request_id="req-1",
            raw_usage={"prompt_tokens": 12450},
            metadata={"stage": "source_analysis"},
        )

        assert response.text == "contenu"
        assert response.parsed == {"ok": True}
        assert response.provider == "openai"
        assert response.model == "un-modele"
        assert response.input_tokens == 12450
        assert response.output_tokens == 2180
        assert response.total_tokens == 14630
        assert response.latency_ms == 4210
        assert response.finish_reason == "stop"
        assert response.request_id == "req-1"
        assert response.raw_usage == {"prompt_tokens": 12450}
        assert response.stage == "source_analysis"

    def test_total_derive_des_deux_moities(self):
        response = AIResponse(
            text="x", provider="fake", model="m", input_tokens=10, output_tokens=5
        )

        assert response.total_tokens == 15

    def test_total_non_derive_si_une_moitie_manque(self):
        """Une somme partielle serait un chiffre faux : on préfère None."""
        response = AIResponse(
            text="x", provider="fake", model="m", input_tokens=10, output_tokens=None
        )

        assert response.total_tokens is None

    def test_total_explicite_non_ecrase(self):
        response = AIResponse(
            text="x",
            provider="fake",
            model="m",
            input_tokens=10,
            output_tokens=5,
            total_tokens=99,
        )

        assert response.total_tokens == 99

    def test_usage_absent_reste_none_et_jamais_zero(self):
        response = AIResponse(text="x", provider="fake", model="m")

        assert response.input_tokens is None
        assert response.output_tokens is None
        assert response.total_tokens is None
        assert response.has_usage is False
        assert response.usage_source == USAGE_UNAVAILABLE

    def test_usage_present_marque_sa_provenance(self):
        response = AIResponse(
            text="x", provider="fake", model="m", input_tokens=1, output_tokens=2
        )

        assert response.has_usage is True
        assert response.usage_source == USAGE_FROM_PROVIDER

    def test_to_dict_n_expose_ni_texte_ni_prompt(self):
        response = AIResponse(
            text="contenu confidentiel du projet",
            provider="fake",
            model="m",
            input_tokens=3,
            output_tokens=4,
        )

        serialise = response.to_dict()

        assert "contenu confidentiel" not in str(serialise)
        assert serialise["text_chars"] == len("contenu confidentiel du projet")
        assert serialise["input_tokens"] == 3
        assert serialise["output_tokens"] == 4
        assert serialise["total_tokens"] == 7

    def test_stage_absent(self):
        assert AIResponse(text="x", provider="fake", model="m").stage is None
