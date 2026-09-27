"""
Estimation de tokens — et surtout, sa séparation d'avec l'usage réel.

Une estimation ne peut pas, par construction, se faire passer pour une
consommation : elle est portée par un TokenEstimate qui annonce sa méthode
et son caractère estimé, là où un usage réel est un entier nu sur AIResponse.
"""

from __future__ import annotations

import pytest

from app.ai.capabilities import ModelCapabilities
from app.ai.contracts import AIRequest, AIResponse
from app.ai.estimation import (
    CHARS_PER_TOKEN,
    METHOD_HEURISTIC,
    METHOD_TIKTOKEN,
    TokenEstimate,
    estimate_request_tokens,
    estimate_tokens,
    fits_in_context,
    heuristic_token_count,
)


class TestTokenEstimate:

    def test_toujours_marque_comme_estime(self):
        estimate = estimate_tokens("un texte quelconque")

        assert estimate.estimated is True
        assert estimate.method in (METHOD_TIKTOKEN, METHOD_HEURISTIC)
        assert estimate.tokens > 0

    def test_impossible_de_pretendre_a_un_usage_reel(self):
        with pytest.raises(ValueError, match="estimation"):
            TokenEstimate(tokens=10, method="quelconque", estimated=False)

    def test_to_dict_porte_la_methode(self):
        data = estimate_tokens("abc", model="un-modele").to_dict()

        assert data["estimated"] is True
        assert data["model"] == "un-modele"
        assert "method" in data


class TestHeuristique:

    def test_texte_vide_vaut_zero(self):
        assert heuristic_token_count("") == 0
        assert estimate_tokens("").tokens == 0

    def test_approximation_par_caracteres(self):
        texte = "a" * 400

        assert heuristic_token_count(texte) == int(400 / CHARS_PER_TOKEN)

    def test_arrondi_au_superieur(self):
        assert heuristic_token_count("ab") == 1

    def test_methode_heuristique_quand_tiktoken_absent(self, monkeypatch):
        """Sans tiktoken, la méthode est annoncée explicitement."""
        monkeypatch.setattr(
            "app.ai.estimation._tiktoken_count", lambda text, model: None
        )

        estimate = estimate_tokens("un texte de test")

        assert estimate.method == METHOD_HEURISTIC

    def test_tiktoken_prioritaire_quand_disponible(self, monkeypatch):
        monkeypatch.setattr(
            "app.ai.estimation._tiktoken_count", lambda text, model: 42
        )

        estimate = estimate_tokens("peu importe")

        assert estimate.tokens == 42
        assert estimate.method == METHOD_TIKTOKEN

    def test_none_traite_comme_vide(self):
        assert estimate_tokens(None).tokens == 0


class TestEstimationDeRequete:

    def test_prend_en_compte_le_system_prompt(self):
        sans = estimate_request_tokens(AIRequest(prompt="a" * 400))
        avec = estimate_request_tokens(
            AIRequest(prompt="a" * 400, system_prompt="b" * 400)
        )

        assert avec.tokens > sans.tokens

    def test_modele_repercute(self):
        estimate = estimate_request_tokens(AIRequest(prompt="x", model="mon-modele"))

        assert estimate.model == "mon-modele"


class TestBudgetDeContexte:

    def _caps(self, context_window=10_000, max_output=1_000):
        return ModelCapabilities(
            provider="fake",
            model="m",
            context_window=context_window,
            max_output_tokens=max_output,
        )

    def test_requete_qui_tient(self):
        verdict, estimate = fits_in_context(
            AIRequest(prompt="a" * 100), self._caps(), safety_ratio=0.7
        )

        assert verdict is True
        assert estimate.estimated is True

    def test_requete_qui_deborde(self):
        verdict, estimate = fits_in_context(
            AIRequest(prompt="a" * 100_000), self._caps(), safety_ratio=0.7
        )

        assert verdict is False
        assert estimate.tokens > 0


class TestSeparationEstimeReel:

    def test_une_reponse_sans_usage_ne_recoit_pas_l_estimation(self):
        """
        Le fournisseur n'a rien rapporté : l'estimation existe mais ne vient
        JAMAIS combler les compteurs de la réponse.
        """
        texte = "a" * 4000
        estimation = estimate_tokens(texte)
        response = AIResponse(text=texte, provider="fake", model="m")

        assert estimation.tokens > 0
        assert response.input_tokens is None
        assert response.output_tokens is None
        assert response.has_usage is False

    def test_usage_reel_n_est_pas_un_token_estimate(self):
        response = AIResponse(
            text="x", provider="fake", model="m", input_tokens=100, output_tokens=20
        )

        assert isinstance(response.input_tokens, int)
        assert not isinstance(response.input_tokens, TokenEstimate)
        assert response.usage_source == "provider"
