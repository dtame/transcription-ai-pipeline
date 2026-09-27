"""
Catalogue tarifaire et arithmétique du coût.

Les tarifs employés ici sont FICTIFS et volontairement ronds (1.00 et 2.00
par million de tokens) : l'objet du test est la formule, pas le prix du
marché. Un test qui codait de vrais tarifs deviendrait faux au premier
changement de grille.

Deux comportements sont protégés plus que les autres :

    un modèle sans tarif ne coûte pas 0.00, il coûte « inconnu » ;
    un modèle local a un coût API nul mais un coût de calcul non valorisé.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

import app.config as config

from app.ai.pricing import (
    COST_STATUS_KNOWN,
    COST_STATUS_LOCAL,
    COST_STATUS_UNKNOWN,
    CURRENCY_USD,
    UNIT_IMAGE,
    ModelPricing,
    PricingCatalog,
    build_default_catalog,
    round_cost_for_display,
)

TARIF_FICTIF = ModelPricing(
    provider="fake-provider",
    model="fake-model",
    input_cost_per_1m_tokens=Decimal("1.00"),
    output_cost_per_1m_tokens=Decimal("2.00"),
    currency=CURRENCY_USD,
    effective_date="2026-01-01",
    source="Tarif FICTIF de test — ne correspond à aucun fournisseur réel.",
    verified=False,
)


@pytest.fixture
def catalogue():
    return PricingCatalog([TARIF_FICTIF])


class TestArithmetique:

    def test_cas_de_reference(self, catalogue):
        """1 000 000 entrée à 1.00 + 500 000 sortie à 2.00 = 2.00."""
        cout = catalogue.estimate_cost(
            "fake-provider", "fake-model",
            input_tokens=1_000_000, output_tokens=500_000,
        )

        assert cout.input_cost == Decimal("1.00")
        assert cout.output_cost == Decimal("1.00")
        assert cout.total_cost == Decimal("2.00")
        assert cout.status == COST_STATUS_KNOWN
        assert cout.currency == CURRENCY_USD

    def test_zero_token(self, catalogue):
        cout = catalogue.estimate_cost("fake-provider", "fake-model", 0, 0)

        assert cout.total_cost == Decimal(0)
        assert cout.status == COST_STATUS_KNOWN

    def test_precision_conservee(self, catalogue):
        """Aucun arrondi prématuré : 1 token reste facturable."""
        cout = catalogue.estimate_cost("fake-provider", "fake-model", 1, 0)

        assert cout.total_cost == Decimal("1") / Decimal(1_000_000)
        assert cout.total_cost > 0

    def test_petites_quantites(self, catalogue):
        cout = catalogue.estimate_cost("fake-provider", "fake-model", 12_000, 2_000)

        assert cout.input_cost == Decimal("0.012")
        assert cout.output_cost == Decimal("0.004")
        assert cout.total_cost == Decimal("0.016")

    def test_une_seule_moitie_rapportee(self, catalogue):
        cout = catalogue.estimate_cost("fake-provider", "fake-model", 1_000_000, None)

        assert cout.total_cost == Decimal("1.00")

    def test_serialisation(self, catalogue):
        data = catalogue.estimate_cost(
            "fake-provider", "fake-model", 1_000_000, 500_000
        ).to_dict()

        assert data["total_cost"] == 2.0
        assert data["status"] == COST_STATUS_KNOWN
        assert data["compute_cost_tracked"] is True


class TestTarifInconnu:

    def test_modele_inconnu_n_est_pas_gratuit(self, catalogue):
        cout = catalogue.estimate_cost("openai", "un-modele-non-tarife", 10_000, 1_000)

        assert cout.total_cost is None
        assert cout.status == COST_STATUS_UNKNOWN
        assert cout.is_known is False
        assert "Aucun tarif" in cout.notes

    def test_tarif_connu_mais_usage_absent(self, catalogue):
        """Sans compteur, on ne devine pas le coût."""
        cout = catalogue.estimate_cost("fake-provider", "fake-model", None, None)

        assert cout.total_cost is None
        assert cout.status == COST_STATUS_UNKNOWN
        assert "usage" in cout.notes


class TestProvidersLocaux:

    def test_ollama_cout_api_nul_mais_calcul_non_valorise(self):
        cout = build_default_catalog().estimate_cost("ollama", "qwen3:8b", 50_000, 10_000)

        assert cout.status == COST_STATUS_LOCAL
        assert cout.total_cost == Decimal(0)
        assert cout.compute_cost_tracked is False
        assert "calcul" in cout.notes

    def test_lmstudio_identique(self):
        cout = build_default_catalog().estimate_cost("lmstudio", "local-model", 10, 10)

        assert cout.status == COST_STATUS_LOCAL
        assert cout.compute_cost_tracked is False

    def test_local_distinct_de_gratuit(self):
        """« coût API 0 » et « gratuit » ne sont pas le même statut."""
        cout = build_default_catalog().estimate_cost("ollama", "m", 1, 1)

        assert cout.status != COST_STATUS_KNOWN
        assert cout.status == COST_STATUS_LOCAL


class TestCatalogueParDefaut:

    def test_aucun_tarif_cloud_invente(self):
        """Phase 2 n'inscrit aucun prix OpenAI ou Anthropic de mémoire."""
        catalogue = build_default_catalog()

        assert catalogue.get("openai", "gpt-4o-mini") is None
        assert catalogue.get("anthropic", "n-importe-lequel") is None

    def test_contient_les_runtimes_locaux(self):
        catalogue = build_default_catalog()

        assert catalogue.get("ollama", "n-importe-lequel").is_local is True
        assert catalogue.get("lmstudio", "n-importe-lequel").is_local is True

    def test_entrees_de_configuration_chargees(self, monkeypatch):
        monkeypatch.setattr(
            config,
            "AI_PRICING_ENTRIES",
            [
                {
                    "provider": "openai",
                    "model": "mon-modele",
                    "input_cost_per_1m_tokens": 3.0,
                    "output_cost_per_1m_tokens": 15.0,
                    "currency": "USD",
                    "effective_date": "2026-02-01",
                    "source": "page de tarification consultée",
                    "verified": True,
                }
            ],
        )

        tarif = build_default_catalog().get("openai", "mon-modele")

        assert tarif.input_cost_per_1m_tokens == Decimal("3.0")
        assert tarif.verified is True
        assert tarif.effective_date == "2026-02-01"

    def test_provenance_tracable(self):
        """Chaque ligne tarifaire sait dire d'où elle vient."""
        for tarif in build_default_catalog():
            assert tarif.source
            assert tarif.currency


class TestResolution:

    def test_modele_exact_prioritaire_sur_generique(self):
        catalogue = PricingCatalog(
            [
                ModelPricing(provider="p", model="*", input_cost_per_1m_tokens=1),
                ModelPricing(provider="p", model="precis", input_cost_per_1m_tokens=9),
            ]
        )

        assert catalogue.get("p", "precis").input_cost_per_1m_tokens == Decimal(9)
        assert catalogue.get("p", "autre").input_cost_per_1m_tokens == Decimal(1)

    def test_provider_insensible_a_la_casse(self, catalogue):
        assert catalogue.get("FAKE-PROVIDER", "fake-model") is not None

    def test_enregistrement_sans_ecrasement(self, catalogue):
        with pytest.raises(ValueError, match="déjà enregistré"):
            catalogue.register(TARIF_FICTIF, overwrite=False)

    def test_tarif_negatif_refuse(self):
        with pytest.raises(ValueError, match="négatif"):
            ModelPricing(provider="p", model="m", input_cost_per_1m_tokens=-1)

    def test_champs_obligatoires_du_catalogue(self):
        data = TARIF_FICTIF.to_dict()

        for champ in (
            "provider",
            "model",
            "input_cost_per_1m_tokens",
            "output_cost_per_1m_tokens",
            "currency",
            "effective_date",
            "source",
        ):
            assert champ in data


class TestUnitesNonTokenisees:

    def test_cout_a_l_unite(self):
        """Le catalogue n'est pas exclusivement tokenisé (Phase 7 : images)."""
        catalogue = PricingCatalog(
            [
                ModelPricing(
                    provider="fake-image",
                    model="fake-diffusion",
                    unit=UNIT_IMAGE,
                    cost_per_unit=Decimal("0.04"),
                    source="Tarif FICTIF de test.",
                )
            ]
        )

        cout = catalogue.estimate_unit_cost("fake-image", "fake-diffusion", 5, UNIT_IMAGE)

        assert cout.total_cost == Decimal("0.20")
        assert cout.status == COST_STATUS_KNOWN

    def test_unite_incoherente_reste_inconnue(self):
        catalogue = PricingCatalog(
            [
                ModelPricing(
                    provider="p", model="m", cost_per_unit=Decimal("1"), source="test"
                )
            ]
        )

        cout = catalogue.estimate_unit_cost("p", "m", 3, UNIT_IMAGE)

        assert cout.status == COST_STATUS_UNKNOWN


class TestAffichage:

    def test_arrondi_d_affichage(self):
        assert round_cost_for_display(Decimal("0.0123456"), 4) == 0.0123

    def test_none_reste_none(self):
        assert round_cost_for_display(None) is None
