"""
CostTracker — enregistrement et agrégations.

Le tracker relie stage → appel → usage → coût. Ce module vérifie les quatre
axes d'agrégation demandés (appel, étape, fournisseur, modèle, total) et, de
nouveau, que l'inconnu reste inconnu : un agrégat partiellement tarifé
n'annonce pas un total complet.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.ai.contracts import AIResponse, USAGE_UNAVAILABLE
from app.ai.cost import (
    CALL_STATUS_FAILED,
    COST_STATUS_NO_CALLS,
    COST_STATUS_PARTIAL,
    CostTracker,
    aggregate_records,
    cost_per_1000_words,
    empty_usage_block,
    format_call_id,
)
from app.ai.errors import AITimeoutError
from app.ai.pricing import (
    COST_STATUS_KNOWN,
    COST_STATUS_LOCAL,
    COST_STATUS_UNKNOWN,
    ModelPricing,
    PricingCatalog,
)

TARIF_FICTIF = ModelPricing(
    provider="fake",
    model="fake-editor",
    input_cost_per_1m_tokens=Decimal("1.00"),
    output_cost_per_1m_tokens=Decimal("2.00"),
    source="Tarif FICTIF de test.",
)


@pytest.fixture
def tracker():
    return CostTracker(PricingCatalog([TARIF_FICTIF]))


def _response(
    provider="fake",
    model="fake-editor",
    input_tokens=12_000,
    output_tokens=2_000,
    stage="source_analysis",
    latency_ms=4_200,
):
    return AIResponse(
        text="contenu",
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        finish_reason="stop",
        metadata={"stage": stage} if stage else {},
    )


class TestIdentifiants:

    def test_format_sequentiel(self):
        assert format_call_id(1) == "CALL000001"
        assert format_call_id(42) == "CALL000042"

    def test_attribution_sequentielle(self, tracker):
        tracker.record_response(_response())
        tracker.record_response(_response())

        assert [r.call_id for r in tracker.records] == ["CALL000001", "CALL000002"]

    def test_pas_d_uuid_aleatoire(self, tracker):
        record = tracker.record_response(_response())

        assert record.call_id.startswith("CALL")
        assert "-" not in record.call_id


class TestEnregistrement:

    def test_appel_reussi(self, tracker):
        record = tracker.record_response(_response())

        assert record.stage == "source_analysis"
        assert record.provider == "fake"
        assert record.model == "fake-editor"
        assert record.input_tokens == 12_000
        assert record.output_tokens == 2_000
        assert record.total_tokens == 14_000
        assert record.latency_ms == 4_200
        assert record.usage_source == "provider"
        assert record.cost.total_cost == Decimal("0.016")

    def test_stage_explicite_prioritaire(self, tracker):
        record = tracker.record_response(_response(stage="source_analysis"), stage="autre")

        assert record.stage == "autre"

    def test_stage_absent_devient_unknown(self, tracker):
        record = tracker.record_response(_response(stage=None))

        assert record.stage == "unknown"

    def test_echec_ne_fabrique_aucun_usage(self, tracker):
        record = tracker.record_failure(
            provider="fake",
            model="fake-editor",
            stage="book_generation",
            error=AITimeoutError("trop lent"),
            latency_ms=900,
        )

        assert record.status == CALL_STATUS_FAILED
        assert record.input_tokens is None
        assert record.output_tokens is None
        assert record.total_tokens is None
        assert record.error_type == "AITimeoutError"
        assert record.latency_ms == 900

    def test_echec_ne_coute_pas_zero(self, tracker):
        record = tracker.record_failure(provider="fake", model="fake-editor")

        assert record.cost.total_cost is None
        assert record.cost.status == COST_STATUS_UNKNOWN

    def test_echec_avec_usage_provider_conserve_le_cout(self, tracker):
        """
        Phase 3B.2 — un appel dont le transport a réussi (usage RÉEL rapporté)
        mais dont la sortie structurée échoue ENSUITE ne doit pas perdre son
        coût : l'appel a probablement été facturé, et le prétendre gratuit
        serait aussi faux que lui inventer un montant.
        """
        response = _response(
            input_tokens=1_000, output_tokens=200, stage="source_analysis"
        )

        record = tracker.record_failure(
            provider="fake",
            model="fake-editor",
            stage="source_analysis",
            error="AIStructuredOutputError",
            response=response,
        )

        assert record.status == CALL_STATUS_FAILED
        assert record.usage_source == "provider"
        assert record.input_tokens == 1_000
        assert record.output_tokens == 200
        assert record.total_tokens == 1_200
        assert record.cost.total_cost == Decimal("0.0014")
        assert record.error_type == "AIStructuredOutputError"

    def test_echec_sans_usage_provider_ne_fabrique_rien(self, tracker):
        """
        Sans usage rapporté (échec de transport, ou fournisseur qui n'a
        réellement rien renvoyé), rien ne change par rapport à avant : aucun
        token inventé, coût explicitement inconnu.
        """
        record = tracker.record_failure(
            provider="fake",
            model="fake-editor",
            stage="source_analysis",
            error="AIConnectionError",
            response=None,
        )

        assert record.input_tokens is None
        assert record.output_tokens is None
        assert record.total_tokens is None
        assert record.usage_source == USAGE_UNAVAILABLE
        assert record.cost.total_cost is None
        assert record.cost.status == COST_STATUS_UNKNOWN

    def test_echec_avec_reponse_sans_aucun_usage_reste_inconnu(self, tracker):
        """Une AIResponse attachée mais sans le moindre compteur n'invente rien."""
        response = AIResponse(
            text="",
            provider="fake",
            model="fake-editor",
            latency_ms=120,
            metadata={"stage": "source_analysis"},
        )

        record = tracker.record_failure(
            provider="fake",
            model="fake-editor",
            error="AIStructuredOutputError",
            response=response,
        )

        assert record.input_tokens is None
        assert record.cost.status == COST_STATUS_UNKNOWN

    def test_echec_avec_usage_reprend_le_stage_de_la_reponse(self, tracker):
        """Le stage explicite reste prioritaire, comme pour record_response."""
        response = _response(stage="source_analysis")

        record = tracker.record_failure(
            provider="fake", model="fake-editor", error="x", response=response
        )

        assert record.stage == "source_analysis"

    def test_appel_a_l_unite(self, tracker):
        record = tracker.record_units(
            provider="fake-image", model="fake-diffusion",
            unit="image", unit_count=3, stage="image_generation",
        )

        assert record.unit == "image"
        assert record.unit_count == 3
        assert record.stage == "image_generation"

    def test_serialisation_sans_contenu(self, tracker):
        tracker.record_response(_response())

        assert "contenu" not in str(tracker.serialize())


class TestAgregations:

    def test_bloc_vide(self):
        bloc = empty_usage_block()

        assert bloc["calls"] == 0
        assert bloc["input_tokens"] == 0
        assert bloc["estimated_cost"] == 0.0
        assert bloc["cost_status"] == COST_STATUS_NO_CALLS
        assert bloc["by_stage"] == {}

    def test_total_d_un_appel(self, tracker):
        tracker.record_response(_response())
        bloc = tracker.aggregate()

        assert bloc["calls"] == 1
        assert bloc["input_tokens"] == 12_000
        assert bloc["output_tokens"] == 2_000
        assert bloc["total_tokens"] == 14_000
        assert bloc["estimated_cost"] == pytest.approx(0.016)
        assert bloc["cost_status"] == COST_STATUS_KNOWN

    def test_plusieurs_appels_s_additionnent(self, tracker):
        tracker.record_response(_response())
        tracker.record_response(_response(input_tokens=1_000, output_tokens=500))

        bloc = tracker.aggregate()

        assert bloc["calls"] == 2
        assert bloc["input_tokens"] == 13_000
        assert bloc["output_tokens"] == 2_500
        assert bloc["estimated_cost"] == pytest.approx(0.016 + 0.001 + 0.001)

    def test_agregation_par_stage(self, tracker):
        tracker.record_response(_response(stage="source_analysis"))
        tracker.record_response(_response(stage="editorial_planning"))
        tracker.record_response(_response(stage="editorial_planning"))

        par_stage = tracker.aggregate()["by_stage"]

        assert set(par_stage) == {"source_analysis", "editorial_planning"}
        assert par_stage["source_analysis"]["calls"] == 1
        assert par_stage["editorial_planning"]["calls"] == 2
        assert par_stage["editorial_planning"]["input_tokens"] == 24_000

    def test_agregation_par_provider(self, tracker):
        tracker.record_response(_response(provider="fake"))
        tracker.record_response(_response(provider="ollama", model="qwen3:8b"))

        par_provider = tracker.aggregate()["by_provider"]

        assert set(par_provider) == {"fake", "ollama"}
        assert par_provider["fake"]["calls"] == 1

    def test_agregation_par_model(self, tracker):
        tracker.record_response(_response(model="fake-editor"))
        tracker.record_response(_response(model="fake-analyste"))

        par_model = tracker.aggregate()["by_model"]

        assert set(par_model) == {"fake:fake-editor", "fake:fake-analyste"}

    def test_appels_echoues_comptes_a_part(self, tracker):
        tracker.record_response(_response())
        tracker.record_failure(provider="fake", model="fake-editor", stage="source_analysis")

        bloc = tracker.aggregate()

        assert bloc["calls"] == 2
        assert bloc["completed_calls"] == 1
        assert bloc["failed_calls"] == 1


class TestStatutDeCout:

    def test_tout_inconnu_donne_un_cout_null(self, tracker):
        tracker.record_response(_response(provider="openai", model="non-tarife"))

        bloc = tracker.aggregate()

        assert bloc["estimated_cost"] is None
        assert bloc["cost_status"] == COST_STATUS_UNKNOWN
        assert bloc["unknown_cost_calls"] == 1

    def test_melange_donne_partial(self, tracker):
        tracker.record_response(_response())
        tracker.record_response(_response(provider="openai", model="non-tarife"))

        bloc = tracker.aggregate()

        assert bloc["cost_status"] == COST_STATUS_PARTIAL
        assert bloc["estimated_cost"] == pytest.approx(0.016)
        assert bloc["unknown_cost_calls"] == 1

    def test_tout_local(self):
        tracker = CostTracker()
        tracker.record_response(_response(provider="ollama", model="qwen3:8b"))

        bloc = tracker.aggregate()

        assert bloc["cost_status"] == COST_STATUS_LOCAL
        assert bloc["estimated_cost"] == 0.0
        assert bloc["local_calls"] == 1
        assert bloc["compute_cost_tracked"] is False

    def test_inconnu_jamais_confondu_avec_zero(self, tracker):
        tracker.record_response(_response(provider="openai", model="non-tarife"))

        assert tracker.aggregate()["estimated_cost"] is not 0.0  # noqa: F632
        assert tracker.aggregate()["estimated_cost"] is None


class TestAgregationPure:

    def test_fonction_pure_sur_des_dicts(self, tracker):
        tracker.record_response(_response())
        lignes = tracker.serialize()

        assert aggregate_records(lignes) == tracker.aggregate()

    def test_liste_vide(self):
        assert aggregate_records([])["cost_status"] == COST_STATUS_NO_CALLS

    def test_to_report_dict_contient_le_detail(self, tracker):
        tracker.record_response(_response())
        bloc = tracker.to_report_dict()

        assert len(bloc["details"]) == 1
        assert bloc["details"][0]["call_id"] == "CALL000001"

    def test_detail_omissible(self, tracker):
        tracker.record_response(_response())

        assert "details" not in tracker.to_report_dict(include_details=False)


class TestCoutPourMilleMots:

    def test_calcul(self):
        assert cost_per_1000_words(2.0, 10_000) == pytest.approx(0.2)

    def test_aucun_livre_encore_aucune_valeur(self):
        """Tant que book.json n'existe pas, aucune valeur n'est fabriquée."""
        assert cost_per_1000_words(2.0, 0) is None

    def test_cout_inconnu(self):
        assert cost_per_1000_words(None, 10_000) is None
