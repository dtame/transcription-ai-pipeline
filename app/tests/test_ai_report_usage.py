"""
Bloc `ai_usage` de report.json.

Deux exigences opposées à tenir en même temps :

    l'ajout est ADDITIF — aucun champ V1 ne disparaît, ne change de nom
    ni de type, et un projet purement transcrit produit un rapport valide ;

    le bloc dit la vérité — coût inconnu représenté comme tel, agrégations
    correctes par étape, fournisseur et modèle.
"""

from __future__ import annotations

import json

import pytest

from app.ai.cost import COST_STATUS_NO_CALLS, COST_STATUS_PARTIAL, CostTracker
from app.ai.contracts import AIResponse
from app.ai.pricing import (
    COST_STATUS_KNOWN,
    COST_STATUS_UNKNOWN,
    ModelPricing,
    PricingCatalog,
)
from app.ai.usage_store import (
    append_tracker,
    build_ai_usage_report,
    ensure_usage_section,
    load_records,
    record_call,
)

# Clés du rapport V1, telles qu'elles existaient avant la Phase 2.
CLES_V1 = {
    "project",
    "generated_at",
    "metadata",
    "audio",
    "chunks",
    "final_document",
    "exports",
    "publication",
    "cover",
    "harmonization",
    "client_export",
    "publication_quality",
}

# Sections ajoutées par V2, purement additives.
SECTIONS_V2 = {
    "ai_usage",          # Phase 2
    "source_analysis",   # Phase 3
}

TARIF_FICTIF = ModelPricing(
    provider="fake",
    model="fake-editor",
    input_cost_per_1m_tokens=1,
    output_cost_per_1m_tokens=2,
    source="Tarif FICTIF de test.",
)


def _response(provider="fake", model="fake-editor", stage="source_analysis",
              input_tokens=12_000, output_tokens=2_000):
    return AIResponse(
        text="contenu",
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=4_200,
        metadata={"stage": stage},
    )


@pytest.fixture
def projet(tmp_path, monkeypatch):
    """Projet isolé : project_state.json et report.json vivent dans tmp_path."""
    import app.project_state as project_state
    import app.report_service as report_service

    sortie = tmp_path / "sortie"
    (sortie / "demo").mkdir(parents=True)

    monkeypatch.setattr(project_state, "SORTIE_DIR", sortie)
    monkeypatch.setattr(report_service, "SORTIE_DIR", sortie)

    return "demo"


def _construire_rapport(nom_projet) -> dict:
    from app.report_service import build_project_report

    chemin = build_project_report(nom_projet)

    return json.loads(chemin.read_text(encoding="utf-8"))


class TestCompatibiliteV1:

    def test_aucun_champ_v1_supprime(self, projet):
        rapport = _construire_rapport(projet)

        assert CLES_V1.issubset(set(rapport))

    def test_ai_usage_ajoute(self, projet):
        rapport = _construire_rapport(projet)

        assert "ai_usage" in rapport
        assert set(rapport) == CLES_V1 | SECTIONS_V2

    def test_structure_v1_intacte(self, projet):
        rapport = _construire_rapport(projet)

        assert set(rapport["audio"]) == {"total", "transcribed", "pending", "error"}
        assert set(rapport["chunks"]) == {"total", "processed", "pending"}
        assert rapport["publication_quality"]["status"] == "not_validated"

    def test_rapport_valide_sans_aucun_appel_ia(self, projet):
        """Le cas de tous les projets existants."""
        bloc = _construire_rapport(projet)["ai_usage"]

        assert bloc["calls"] == 0
        assert bloc["input_tokens"] == 0
        assert bloc["output_tokens"] == 0
        assert bloc["total_tokens"] == 0
        assert bloc["estimated_cost"] == 0.0
        assert bloc["cost_status"] == COST_STATUS_NO_CALLS
        assert bloc["by_stage"] == {}
        assert bloc["by_provider"] == {}
        assert bloc["by_model"] == {}

    def test_forme_du_bloc_constante(self, projet):
        """Le rapport ne change pas de forme selon qu'une étape IA a tourné."""
        sans_appel = set(_construire_rapport(projet)["ai_usage"])

        tracker = CostTracker(PricingCatalog([TARIF_FICTIF]))
        tracker.record_response(_response())
        record_call(projet, tracker.records[0])

        avec_appel = set(_construire_rapport(projet)["ai_usage"])

        assert sans_appel.issubset(avec_appel)


class TestAgregationDansLeRapport:

    def _enregistrer(self, projet, tracker):
        from app.project_state import load_project_state, save_project_state

        state = load_project_state(projet)
        append_tracker(state, tracker)
        save_project_state(projet, state)

    def test_un_appel(self, projet):
        tracker = CostTracker(PricingCatalog([TARIF_FICTIF]))
        tracker.record_response(_response())
        self._enregistrer(projet, tracker)

        bloc = _construire_rapport(projet)["ai_usage"]

        assert bloc["calls"] == 1
        assert bloc["input_tokens"] == 12_000
        assert bloc["output_tokens"] == 2_000
        assert bloc["total_tokens"] == 14_000
        assert bloc["estimated_cost"] == pytest.approx(0.016)
        assert bloc["cost_status"] == COST_STATUS_KNOWN
        assert bloc["currency"] == "USD"

    def test_plusieurs_stages_providers_models(self, projet):
        tracker = CostTracker(PricingCatalog([TARIF_FICTIF]))
        tracker.record_response(_response(stage="source_analysis"))
        tracker.record_response(
            _response(stage="editorial_planning", model="fake-planificateur")
        )
        tracker.record_response(
            _response(stage="book_generation", provider="ollama", model="qwen3:8b")
        )
        self._enregistrer(projet, tracker)

        bloc = _construire_rapport(projet)["ai_usage"]

        assert bloc["calls"] == 3
        assert set(bloc["by_stage"]) == {
            "source_analysis",
            "editorial_planning",
            "book_generation",
        }
        assert set(bloc["by_provider"]) == {"fake", "ollama"}
        assert set(bloc["by_model"]) == {
            "fake:fake-editor",
            "fake:fake-planificateur",
            "ollama:qwen3:8b",
        }

    def test_cout_inconnu_represente_explicitement(self, projet):
        tracker = CostTracker(PricingCatalog([TARIF_FICTIF]))
        tracker.record_response(_response(provider="openai", model="non-tarife"))
        self._enregistrer(projet, tracker)

        bloc = _construire_rapport(projet)["ai_usage"]

        assert bloc["estimated_cost"] is None
        assert bloc["cost_status"] == COST_STATUS_UNKNOWN
        assert bloc["unknown_cost_calls"] == 1
        assert bloc["by_provider"]["openai"]["estimated_cost"] is None

    def test_cout_partiel(self, projet):
        tracker = CostTracker(PricingCatalog([TARIF_FICTIF]))
        tracker.record_response(_response())
        tracker.record_response(_response(provider="openai", model="non-tarife"))
        self._enregistrer(projet, tracker)

        bloc = _construire_rapport(projet)["ai_usage"]

        assert bloc["cost_status"] == COST_STATUS_PARTIAL
        assert bloc["estimated_cost"] == pytest.approx(0.016)

    def test_detail_sans_contenu_du_projet(self, projet):
        tracker = CostTracker(PricingCatalog([TARIF_FICTIF]))
        tracker.record_response(_response())
        self._enregistrer(projet, tracker)

        rapport_brut = json.dumps(_construire_rapport(projet), ensure_ascii=False)

        assert "contenu" not in rapport_brut
        assert "CALL000001" in rapport_brut

    def test_rapport_serialisable_en_json(self, projet):
        tracker = CostTracker(PricingCatalog([TARIF_FICTIF]))
        tracker.record_response(_response())
        tracker.record_failure(provider="fake", model="fake-editor", stage="x")
        self._enregistrer(projet, tracker)

        # Lever ici signalerait un Decimal non converti dans les agrégats.
        json.dumps(_construire_rapport(projet))


class TestMagasinDUsage:

    def test_section_creee_a_la_demande(self):
        state = {}
        ensure_usage_section(state)

        assert state["ai_usage"] == {"records": []}

    def test_section_idempotente(self):
        state = {"ai_usage": {"records": [{"call_id": "CALL000001"}]}}
        ensure_usage_section(state)

        assert len(state["ai_usage"]["records"]) == 1

    def test_section_corrompue_reinitialisee(self):
        state = {"ai_usage": "n'importe quoi"}
        ensure_usage_section(state)

        assert state["ai_usage"] == {"records": []}

    def test_state_sans_section(self):
        assert load_records({}) == []
        assert build_ai_usage_report({})["cost_status"] == COST_STATUS_NO_CALLS

    def test_record_call_persiste(self, projet):
        tracker = CostTracker(PricingCatalog([TARIF_FICTIF]))
        record_call(projet, tracker.record_response(_response()))
        record_call(projet, tracker.record_response(_response()))

        from app.project_state import load_project_state

        assert len(load_records(load_project_state(projet))) == 2

    def test_ensure_state_structure_ajoute_la_section(self):
        from app.project_state import ensure_state_structure

        state = {}
        ensure_state_structure(state)

        assert "ai_usage" in state
        # Les sections V1 restent créées.
        assert "files" in state
        assert "chunks" in state
