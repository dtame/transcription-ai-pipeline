"""
Modèles de production de Transcriptor-ia — Phase 2B.

Ce module ne teste aucune architecture nouvelle : il VERROUILLE une
configuration. La Phase 2 a construit la couche IA en refusant d'inscrire le
moindre modèle ou tarif cloud ; la Phase 2B inscrit les quatre décisions
produit et les gèle par des tests.

    source_analysis       Anthropic / Claude Sonnet 5
    editorial_planning    Anthropic / Claude Opus 5
    book_generation       Anthropic / Claude Sonnet 5
    book_validation       OpenAI    / GPT-5.6 Terra

Trois propriétés comptent plus que les valeurs elles-mêmes :

    hors ligne      toute la configuration (provider, modèle, capacités,
                    tarif) s'inspecte sans clé API et sans réseau. La clé
                    n'est exigée qu'au moment d'un véritable appel.

    daté et sourcé  capacités et tarifs portent leur provenance et leur date.
                    known=True et verified=True ne sont pas décoratifs : ils
                    distinguent un fait vérifié d'une hypothèse de repli.

    pas de chiffre  GPT-5.6 Terra applique des règles tarifaires au-delà de
    trop confiant   certains seuils de contexte, que ce catalogue ne modélise
                    pas. Son coût ressort donc en "base_estimate", jamais en
                    "known" — voir TestTerraLongContext.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

import app.config as config

from app.ai.capabilities import resolve_capabilities
from app.ai.contracts import AIResponse
from app.ai.cost import COST_STATUS_PARTIAL, CostTracker
from app.ai.errors import AIConfigurationError
from app.ai.pricing import (
    COST_STATUS_BASE_ESTIMATE,
    COST_STATUS_KNOWN,
    CURRENCY_USD,
    REGIME_LONG_CONTEXT,
    UNIT_TOKENS,
    build_default_catalog,
)
from app.ai.providers import AnthropicEngine, OpenAIEngine
from app.ai.registry import get_engine_for_stage
from app.ai.settings import resolve_stage_settings
from app.ai.usage_store import append_tracker, build_ai_usage_report

SONNET = ("anthropic", "claude-sonnet-5")
OPUS = ("anthropic", "claude-opus-5")
TERRA = ("openai", "gpt-5.6-terra")

# Matrice produit imposée. Toute divergence du code doit faire échouer un test.
MATRICE_ETAPES = [
    ("source_analysis", "anthropic", "claude-sonnet-5", AnthropicEngine),
    ("editorial_planning", "anthropic", "claude-opus-5", AnthropicEngine),
    ("book_generation", "anthropic", "claude-sonnet-5", AnthropicEngine),
    ("book_validation", "openai", "gpt-5.6-terra", OpenAIEngine),
]

MODELES = [SONNET, OPUS, TERRA]


@pytest.fixture
def catalogue():
    """Catalogue réel du dépôt : alimenté par config.AI_PRICING_ENTRIES."""
    return build_default_catalog()


# ---------------------------------------------------------------------------
# Capacités
# ---------------------------------------------------------------------------

class TestCapacitesDesModelesDeProduction:

    @pytest.mark.parametrize("provider, model", MODELES)
    def test_capacites_connues_et_non_devinees(self, provider, model):
        """known=True : ces trois modèles ne doivent plus tomber sur le repli."""
        caps = resolve_capabilities(provider, model)

        assert caps.known is True
        assert caps.context_window != config.AI_FALLBACK_CONTEXT_WINDOW

    @pytest.mark.parametrize(
        "provider, model, context_window",
        [
            (*SONNET, 1_000_000),
            (*OPUS, 1_000_000),
            (*TERRA, 1_050_000),
        ],
    )
    def test_fenetre_de_contexte(self, provider, model, context_window):
        assert resolve_capabilities(provider, model).context_window == context_window

    @pytest.mark.parametrize("provider, model", MODELES)
    def test_plafond_de_sortie(self, provider, model):
        assert resolve_capabilities(provider, model).max_output_tokens == 128_000

    @pytest.mark.parametrize("provider, model", MODELES)
    def test_sortie_structuree_et_system_prompt(self, provider, model):
        caps = resolve_capabilities(provider, model)

        assert caps.supports_structured_output is True
        assert caps.supports_system_prompt is True

    @pytest.mark.parametrize("provider, model", [SONNET, OPUS])
    def test_temperature_supportee_par_les_claude(self, provider, model):
        assert resolve_capabilities(provider, model).supports_temperature is True

    def test_temperature_non_revendiquee_pour_terra(self):
        """
        Le relevé de capacités de Terra mentionne la sortie structurée et le
        system prompt, pas le réglage de température : on ne l'affirme donc
        pas. Aucun code ne consulte encore ce drapeau ; il existe pour qu'une
        étape future confirme avant d'envoyer `temperature`.
        """
        assert resolve_capabilities(*TERRA).supports_temperature is False

    @pytest.mark.parametrize(
        "provider, model, fournisseur",
        [(*SONNET, "Anthropic"), (*OPUS, "Anthropic"), (*TERRA, "OpenAI")],
    )
    def test_provenance_identifiable(self, provider, model, fournisseur):
        source = resolve_capabilities(provider, model).source

        assert fournisseur in source
        assert "2026-09-18" in source

    @pytest.mark.parametrize("provider", ["anthropic", "openai"])
    def test_aucune_fuite_vers_les_modeles_non_configures(self, provider):
        """
        Aucune entrée « provider:* » n'est créée par la Phase 2B.

        Un modèle voisin ne doit pas hériter des capacités de Sonnet ou de
        Terra : il reste explicitement inconnu.
        """
        caps = resolve_capabilities(provider, "un-modele-non-catalogue")

        assert caps.known is False
        assert caps.context_window == config.AI_FALLBACK_CONTEXT_WINDOW

    @pytest.mark.parametrize("provider, model", MODELES)
    def test_capacites_serialisables(self, provider, model):
        data = resolve_capabilities(provider, model).to_dict()

        assert data["known"] is True
        assert data["source"]


# ---------------------------------------------------------------------------
# Budget de contexte
# ---------------------------------------------------------------------------

class TestBudgetDeContexte:
    """
    Vérifie les FORMULES de la Phase 2 sur les nouvelles fenêtres, sans rien
    décider de l'usage réel du budget : c'est le sujet de la Phase 3.
    """

    def test_ratio_de_securite_inchange(self):
        assert config.AI_CONTEXT_SAFETY_RATIO == 0.70

    @pytest.mark.parametrize("provider, model", [SONNET, OPUS])
    def test_contexte_utilisable_claude(self, provider, model):
        assert resolve_capabilities(provider, model).usable_context() == 700_000

    def test_contexte_utilisable_terra(self):
        assert resolve_capabilities(*TERRA).usable_context() == 735_000

    @pytest.mark.parametrize("provider, model", [SONNET, OPUS])
    def test_contexte_d_entree_claude_reserve_la_sortie(self, provider, model):
        """700 000 utilisables moins les 128 000 réservés à la génération."""
        assert resolve_capabilities(provider, model).usable_input_context() == 572_000

    def test_contexte_d_entree_terra_reserve_la_sortie(self):
        assert resolve_capabilities(*TERRA).usable_input_context() == 607_000

    @pytest.mark.parametrize("provider, model", MODELES)
    def test_budget_d_entree_strictement_positif(self, provider, model):
        """
        Le plafond de sortie n'absorbe pas tout le budget sur ces modèles :
        une étape éditoriale a réellement de la place pour ses sources.
        """
        assert resolve_capabilities(provider, model).usable_input_context() > 0

    def test_ratio_reste_un_defaut_surchargeable(self):
        """0.70 est un défaut technique, pas une constante gravée."""
        caps = resolve_capabilities(*SONNET)

        assert caps.usable_context(0.5) == 500_000
        assert caps.usable_context(1.0) == 1_000_000


# ---------------------------------------------------------------------------
# Configuration par étape
# ---------------------------------------------------------------------------

class TestConfigurationParEtape:

    @pytest.mark.parametrize(
        "stage, provider, model",
        [(s, p, m) for s, p, m, _ in MATRICE_ETAPES],
    )
    def test_matrice_de_production(self, stage, provider, model):
        settings = resolve_stage_settings(stage)

        assert settings.provider == provider
        assert settings.model == model

    @pytest.mark.parametrize("stage", [s for s, _, _, _ in MATRICE_ETAPES])
    def test_parametres_de_generation_laisses_aux_etapes(self, stage):
        """
        La Phase 2B verrouille provider et modèle, rien de plus.

        Température, plafond de sortie et schéma de réponse dépendront des
        prompts des Phases 3 à 5 et arriveront par AIRequest : inventer une
        valeur ici la figerait sans raison.
        """
        settings = resolve_stage_settings(stage)

        assert settings.temperature is None
        assert settings.max_output_tokens is None

    @pytest.mark.parametrize("stage", [s for s, _, _, _ in MATRICE_ETAPES])
    def test_ratio_de_contexte_herite_du_global(self, stage):
        assert resolve_stage_settings(stage).context_safety_ratio == 0.70

    @pytest.mark.parametrize(
        "stage", ["visual_design", "image_generation", "document_rendering"]
    )
    def test_etapes_futures_non_configurees(self, stage, monkeypatch):
        """Le contrat Phase 2 tient : une étape non configurée suit AI_PROVIDER."""
        monkeypatch.setattr(config, "AI_PROVIDER", "fake")

        settings = resolve_stage_settings(stage)

        assert settings.provider == "fake"
        assert settings.model is None

    def test_etape_inconnue_suit_toujours_ai_provider(self, monkeypatch):
        monkeypatch.setattr(config, "AI_PROVIDER", "ollama")

        settings = resolve_stage_settings("une_etape_qui_n_existe_pas")

        assert settings.provider == "ollama"
        assert settings.model is None

    def test_configuration_serialisable(self):
        assert resolve_stage_settings("book_validation").to_dict() == {
            "stage": "book_validation",
            "provider": "openai",
            "model": "gpt-5.6-terra",
            "temperature": None,
            "max_output_tokens": None,
            "context_safety_ratio": 0.70,
            "connect_timeout_seconds": None,
            "read_timeout_seconds": None,
        }


# ---------------------------------------------------------------------------
# Routage des étapes
# ---------------------------------------------------------------------------

class TestRoutageDesEtapes:

    @pytest.mark.parametrize("stage, provider, model, classe", MATRICE_ETAPES)
    def test_get_engine_for_stage(self, stage, provider, model, classe, no_ai_network):
        """
        Résolution complète d'une étape : classe de moteur, nom de provider et
        modèle effectif. `no_ai_network` garantit qu'aucun octet ne sort.
        """
        engine, settings = get_engine_for_stage(stage)

        assert isinstance(engine, classe)
        assert engine.provider_name == provider
        assert engine.resolve_model() == model
        assert settings.provider == provider
        assert settings.model == model

    @pytest.mark.parametrize("stage, provider, model, _classe", MATRICE_ETAPES)
    def test_le_moteur_route_connait_ses_capacites(self, stage, provider, model, _classe):
        caps = get_engine_for_stage(stage)[0].capabilities()

        assert caps.known is True
        assert caps.model == model
        assert caps.max_output_tokens == 128_000

    @pytest.mark.parametrize("stage, _p, _m, _c", MATRICE_ETAPES)
    def test_resolution_sans_aucune_cle_api(self, stage, _p, _m, _c, monkeypatch):
        """
        §14 : inspecter provider, modèle et capacités ne demande aucune clé.

        Les variables d'environnement sont déjà retirées par la fixture
        autouse de conftest ; ce test le redit explicitement pour que la
        garantie soit lisible ici.
        """
        for variable in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(variable, raising=False)

        engine, settings = get_engine_for_stage(stage)

        assert settings.model
        assert engine.resolve_model()
        assert engine.capabilities().known is True

    @pytest.mark.parametrize("stage, _p, _m, _c", MATRICE_ETAPES)
    def test_la_cle_n_est_exigee_qu_a_l_appel(self, stage, _p, _m, _c):
        """
        Le moteur se construit sans clé, mais refuse de partir sans elle.

        C'est la frontière exacte demandée : configuration inspectable hors
        ligne, appel réel impossible sans credentials.
        """
        engine, _ = get_engine_for_stage(stage)

        with pytest.raises(AIConfigurationError, match="Clé API absente"):
            engine.resolve_api_key()

    def test_les_quatre_etapes_couvrent_deux_fournisseurs(self):
        providers = {
            get_engine_for_stage(stage)[0].provider_name
            for stage, _, _, _ in MATRICE_ETAPES
        }

        assert providers == {"anthropic", "openai"}


# ---------------------------------------------------------------------------
# Catalogue tarifaire
# ---------------------------------------------------------------------------

class TestConfigurationTarifaire:

    @pytest.mark.parametrize("provider, model", MODELES)
    def test_tarif_present(self, catalogue, provider, model):
        assert catalogue.get(provider, model) is not None

    @pytest.mark.parametrize("provider, model", MODELES)
    def test_tarif_verifie_date_et_source(self, catalogue, provider, model):
        tarif = catalogue.get(provider, model)

        assert tarif.verified is True
        assert tarif.effective_date == "2026-09-18"
        assert "pricing" in tarif.source
        assert tarif.currency == CURRENCY_USD
        assert tarif.unit == UNIT_TOKENS
        assert tarif.is_local is False

    @pytest.mark.parametrize(
        "provider, model, entree, sortie",
        [
            (*SONNET, Decimal("2.00"), Decimal("10.00")),
            (*OPUS, Decimal("5.00"), Decimal("25.00")),
            (*TERRA, Decimal("2.00"), Decimal("12.00")),
        ],
    )
    def test_montants_par_million_de_tokens(
        self, catalogue, provider, model, entree, sortie
    ):
        tarif = catalogue.get(provider, model)

        assert tarif.input_cost_per_1m_tokens == entree
        assert tarif.output_cost_per_1m_tokens == sortie

    @pytest.mark.parametrize(
        "provider, fournisseur", [("anthropic", "Anthropic"), ("openai", "OpenAI")]
    )
    def test_aucun_tarif_generique_par_fournisseur(
        self, catalogue, provider, fournisseur
    ):
        """
        Un modèle non listé reste non tarifé, donc rapporté « unknown ».

        Ajouter une entrée « provider:* » aurait facturé au hasard tout modèle
        futur au tarif d'un de ses voisins.
        """
        assert catalogue.get(provider, "un-modele-non-tarife") is None

    def test_les_runtimes_locaux_restent_intacts(self, catalogue):
        assert catalogue.get("ollama", "qwen3:8b").is_local is True
        assert catalogue.get("lmstudio", "local-model").is_local is True


class TestMontantsExacts:
    """
    Montants calculés en Decimal, comme toute la comptabilité de la Phase 2 :
    additionner des centièmes en binaire finit par produire des rapports faux.
    """

    @pytest.mark.parametrize(
        "provider, model, attendu",
        [
            (*SONNET, Decimal("12.00")),
            (*OPUS, Decimal("30.00")),
            # Terra : TARIF STANDARD DE BASE uniquement. Ce montant ne couvre
            # pas les régimes de long contexte, que le catalogue ne modélise
            # pas — c'est d'ailleurs pourquoi son statut n'est pas "known".
            (*TERRA, Decimal("14.00")),
        ],
    )
    def test_un_million_en_entree_et_en_sortie(
        self, catalogue, provider, model, attendu
    ):
        cout = catalogue.estimate_cost(provider, model, 1_000_000, 1_000_000)

        assert cout.total_cost == attendu
        assert cout.currency == CURRENCY_USD

    @pytest.mark.parametrize(
        "provider, model, entree, sortie, total",
        [
            (*SONNET, Decimal("0.20"), Decimal("0.10"), Decimal("0.30")),
            (*OPUS, Decimal("0.50"), Decimal("0.25"), Decimal("0.75")),
            (*TERRA, Decimal("0.20"), Decimal("0.12"), Decimal("0.32")),
        ],
    )
    def test_appel_realiste_100k_entree_10k_sortie(
        self, catalogue, provider, model, entree, sortie, total
    ):
        cout = catalogue.estimate_cost(provider, model, 100_000, 10_000)

        assert cout.input_cost == entree
        assert cout.output_cost == sortie
        assert cout.total_cost == total

    @pytest.mark.parametrize("provider, model", MODELES)
    def test_usage_absent_ne_produit_pas_un_cout_nul(
        self, catalogue, provider, model
    ):
        """Un tarif connu ne suffit pas : sans compteur, le coût reste inconnu."""
        cout = catalogue.estimate_cost(provider, model, None, None)

        assert cout.total_cost is None


# ---------------------------------------------------------------------------
# Terra : régime de long contexte non modélisé
# ---------------------------------------------------------------------------

class TestTerraLongContext:
    """
    Ce que le catalogue modélise pour GPT-5.6 Terra : le tarif standard de
    base, 2,00 / 12,00 USD par million de tokens.

    Ce qu'il ne modélise pas : les règles tarifaires applicables aux très
    grands contextes. Leur seuil exact n'est pas inscrit ici — inventer un
    palier plausible serait plus dangereux que de ne pas en avoir.

    Conséquence retenue (option A du cahier des charges) : tout coût Terra
    ressort en "base_estimate". Le montant reste calculé et affichable, mais
    ni le CostTracker ni report.json ne le présentent comme exact.
    """

    def test_le_cout_terra_n_est_pas_annonce_comme_exact(self, catalogue):
        cout = catalogue.estimate_cost(*TERRA, 500_000, 20_000)

        assert cout.status == COST_STATUS_BASE_ESTIMATE
        assert cout.status != COST_STATUS_KNOWN

    def test_le_montant_reste_disponible(self, catalogue):
        """« Incomplet » ne veut pas dire « absent » : le chiffre existe."""
        cout = catalogue.estimate_cost(*TERRA, 1_000_000, 1_000_000)

        assert cout.total_cost == Decimal("14.00")
        assert cout.is_known is True

    def test_la_limitation_est_recuperable(self, catalogue):
        cout = catalogue.estimate_cost(*TERRA, 100_000, 10_000)

        assert cout.is_complete is False
        assert cout.unmodeled_regimes == REGIME_LONG_CONTEXT
        assert "Long-context" in cout.notes
        assert cout.to_dict()["unmodeled_regimes"] == REGIME_LONG_CONTEXT

    def test_la_limitation_est_portee_par_la_ligne_tarifaire(self, catalogue):
        tarif = catalogue.get(*TERRA)

        assert tarif.unmodeled_regimes == REGIME_LONG_CONTEXT
        assert tarif.cost_status == COST_STATUS_BASE_ESTIMATE
        assert "not modeled" in tarif.notes
        assert tarif.to_dict()["unmodeled_regimes"] == REGIME_LONG_CONTEXT

    @pytest.mark.parametrize("provider, model", [SONNET, OPUS])
    def test_les_claude_restent_pleinement_tarifes(self, catalogue, provider, model):
        """La prudence appliquée à Terra ne contamine pas les autres modèles."""
        cout = catalogue.estimate_cost(provider, model, 100_000, 10_000)

        assert cout.status == COST_STATUS_KNOWN
        assert cout.is_complete is True
        assert cout.unmodeled_regimes == ""

    def test_un_appel_terra_declasse_l_agregat(self):
        """
        Un total qui contient un base_estimate ne peut plus dire « known ».

        C'est la protection demandée : le rapport n'annonce pas silencieusement
        un coût standard comme exact.
        """
        tracker = CostTracker()
        tracker.record_response(_reponse(*SONNET, "source_analysis", 100_000, 10_000))
        tracker.record_response(_reponse(*TERRA, "book_validation", 100_000, 10_000))

        bloc = tracker.aggregate()

        assert bloc["cost_status"] == COST_STATUS_BASE_ESTIMATE
        assert bloc["by_provider"]["anthropic"]["cost_status"] == COST_STATUS_KNOWN
        assert bloc["by_provider"]["openai"]["cost_status"] == COST_STATUS_BASE_ESTIMATE

    def test_un_cout_inconnu_reste_prioritaire_sur_base_estimate(self):
        """Mélanger « inconnu » et « estimation de base » donne « partial »."""
        tracker = CostTracker()
        tracker.record_response(_reponse(*TERRA, "book_validation", 100_000, 10_000))
        tracker.record_response(
            _reponse("openai", "modele-non-tarife", "book_validation", 1_000, 100)
        )

        assert tracker.aggregate()["cost_status"] == COST_STATUS_PARTIAL


# ---------------------------------------------------------------------------
# Scénario complet : quatre étapes, quatre appels
# ---------------------------------------------------------------------------

def _reponse(provider, model, stage, input_tokens, output_tokens) -> AIResponse:
    """Réponse fictive : aucun provider n'est appelé, aucun réseau touché."""
    return AIResponse(
        text="contenu généré",
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=3_000,
        finish_reason="stop",
        metadata={"stage": stage},
    )


# (stage, provider, model, tokens entrée, tokens sortie, coût attendu)
SCENARIO = [
    ("source_analysis", *SONNET, 200_000, 20_000, Decimal("0.60")),
    ("editorial_planning", *OPUS, 100_000, 40_000, Decimal("1.50")),
    ("book_generation", *SONNET, 300_000, 120_000, Decimal("1.80")),
    ("book_validation", *TERRA, 400_000, 30_000, Decimal("1.16")),
]

TOTAL_ENTREE = 1_000_000
TOTAL_SORTIE = 210_000
TOTAL_COUT = Decimal("5.06")


@pytest.fixture
def tracker_quatre_etapes():
    """
    Un pipeline éditorial complet simulé avec les vrais tarifs configurés.

    CostTracker() sans argument construit le catalogue par défaut, donc celui
    du dépôt : ce scénario chiffre bien la configuration de production, pas un
    tarif de test.
    """
    tracker = CostTracker()

    for stage, provider, model, entree, sortie, _ in SCENARIO:
        tracker.record_response(_reponse(provider, model, stage, entree, sortie))

    return tracker


class TestCostTrackerQuatreEtapes:

    def test_quatre_appels_enregistres(self, tracker_quatre_etapes):
        assert tracker_quatre_etapes.call_count == 4
        assert tracker_quatre_etapes.aggregate()["calls"] == 4
        assert tracker_quatre_etapes.aggregate()["failed_calls"] == 0

    @pytest.mark.parametrize(
        "index, stage, provider, model, cout",
        [(i, s, p, m, c) for i, (s, p, m, _e, _s, c) in enumerate(SCENARIO)],
    )
    def test_cout_par_appel(
        self, tracker_quatre_etapes, index, stage, provider, model, cout
    ):
        record = tracker_quatre_etapes.records[index]

        assert record.stage == stage
        assert record.provider == provider
        assert record.model == model
        assert record.cost.total_cost == cout

    def test_agregation_par_stage(self, tracker_quatre_etapes):
        par_stage = tracker_quatre_etapes.aggregate()["by_stage"]

        assert set(par_stage) == {
            "source_analysis",
            "editorial_planning",
            "book_generation",
            "book_validation",
        }
        assert all(bucket["calls"] == 1 for bucket in par_stage.values())
        assert par_stage["book_generation"]["input_tokens"] == 300_000
        assert par_stage["editorial_planning"]["estimated_cost"] == pytest.approx(1.50)

    def test_agregation_par_provider(self, tracker_quatre_etapes):
        par_provider = tracker_quatre_etapes.aggregate()["by_provider"]

        assert set(par_provider) == {"anthropic", "openai"}
        assert par_provider["anthropic"]["calls"] == 3
        assert par_provider["openai"]["calls"] == 1
        assert par_provider["anthropic"]["estimated_cost"] == pytest.approx(3.90)
        assert par_provider["openai"]["estimated_cost"] == pytest.approx(1.16)

    def test_agregation_par_model(self, tracker_quatre_etapes):
        par_model = tracker_quatre_etapes.aggregate()["by_model"]

        assert set(par_model) == {
            "anthropic:claude-sonnet-5",
            "anthropic:claude-opus-5",
            "openai:gpt-5.6-terra",
        }
        # Sonnet 5 sert deux étapes : ses appels s'additionnent.
        assert par_model["anthropic:claude-sonnet-5"]["calls"] == 2
        assert par_model["anthropic:claude-sonnet-5"]["estimated_cost"] == pytest.approx(
            2.40
        )

    def test_totaux_de_tokens(self, tracker_quatre_etapes):
        bloc = tracker_quatre_etapes.aggregate()

        assert bloc["input_tokens"] == TOTAL_ENTREE
        assert bloc["output_tokens"] == TOTAL_SORTIE
        assert bloc["total_tokens"] == TOTAL_ENTREE + TOTAL_SORTIE

    def test_cout_total_et_devise(self, tracker_quatre_etapes):
        bloc = tracker_quatre_etapes.aggregate()

        assert Decimal(str(bloc["estimated_cost"])) == TOTAL_COUT
        assert bloc["currency"] == CURRENCY_USD
        assert bloc["unknown_cost_calls"] == 0

    def test_le_total_signale_l_estimation_de_base(self, tracker_quatre_etapes):
        """Terra fait partie du scénario : le total est une estimation de base."""
        assert (
            tracker_quatre_etapes.aggregate()["cost_status"]
            == COST_STATUS_BASE_ESTIMATE
        )

    def test_aucun_tarif_fictif_employe(self, tracker_quatre_etapes):
        """Chaque appel est chiffré avec un tarif vérifié et daté du dépôt."""
        for record in tracker_quatre_etapes.records:
            assert record.cost.verified is True
            assert record.cost.effective_date == "2026-09-18"


# ---------------------------------------------------------------------------
# report.json
# ---------------------------------------------------------------------------

class TestReportJson:

    @pytest.fixture
    def bloc(self, tracker_quatre_etapes):
        """Bloc `ai_usage` obtenu par le vrai chemin : tracker -> state -> rapport."""
        state: dict = {}
        append_tracker(state, tracker_quatre_etapes)

        return build_ai_usage_report(state)

    def test_les_quatre_etapes_sont_representees(self, bloc):
        assert bloc["calls"] == 4
        assert bloc["completed_calls"] == 4
        assert set(bloc["by_stage"]) == {
            "source_analysis",
            "editorial_planning",
            "book_generation",
            "book_validation",
        }

    def test_les_deux_fournisseurs_sont_representes(self, bloc):
        assert set(bloc["by_provider"]) == {"anthropic", "openai"}

    def test_les_trois_modeles_sont_representes(self, bloc):
        assert set(bloc["by_model"]) == {
            "anthropic:claude-sonnet-5",
            "anthropic:claude-opus-5",
            "openai:gpt-5.6-terra",
        }

    def test_totaux_du_rapport(self, bloc):
        assert bloc["total_tokens"] == TOTAL_ENTREE + TOTAL_SORTIE
        assert Decimal(str(bloc["estimated_cost"])) == TOTAL_COUT
        assert bloc["currency"] == CURRENCY_USD

    def test_le_rapport_ne_pretend_pas_a_l_exactitude(self, bloc):
        assert bloc["cost_status"] == COST_STATUS_BASE_ESTIMATE

    def test_le_detail_porte_la_limitation_terra(self, bloc):
        terra = [
            detail
            for detail in bloc["details"]
            if detail["model"] == "gpt-5.6-terra"
        ]

        assert len(terra) == 1
        assert terra[0]["cost"]["status"] == COST_STATUS_BASE_ESTIMATE
        assert terra[0]["cost"]["unmodeled_regimes"] == REGIME_LONG_CONTEXT

    def test_aucun_contenu_de_projet_dans_le_rapport(self, bloc):
        """Le bloc reste métrique : ni prompt, ni texte généré."""
        for detail in bloc["details"]:
            assert "text" not in detail
            assert "prompt" not in detail
            assert "contenu généré" not in str(detail)

    def test_rapport_complet_toujours_valide(self, tmp_path, monkeypatch):
        """
        Le rapport d'un projet réel reste additif : les champs V1 sont intacts
        et `ai_usage` s'ajoute sans en déplacer aucun.
        """
        import json

        import app.project_state as project_state
        import app.report_service as report_service

        sortie = tmp_path / "sortie"
        (sortie / "demo").mkdir(parents=True)
        monkeypatch.setattr(project_state, "SORTIE_DIR", sortie)
        monkeypatch.setattr(report_service, "SORTIE_DIR", sortie)

        tracker = CostTracker()
        tracker.record_response(
            _reponse(*TERRA, "book_validation", 400_000, 30_000)
        )

        state = project_state.load_project_state("demo")
        append_tracker(state, tracker)
        project_state.save_project_state("demo", state)

        rapport = json.loads(
            report_service.build_project_report("demo").read_text(encoding="utf-8")
        )

        assert rapport["project"] == "demo"
        assert rapport["ai_usage"]["calls"] == 1
        assert rapport["ai_usage"]["by_model"]["openai:gpt-5.6-terra"]["calls"] == 1
        assert rapport["ai_usage"]["cost_status"] == COST_STATUS_BASE_ESTIMATE
