"""
Intégration Phase 2 — chaîne complète, entièrement simulée.

    AIRequest
       ↓
    FakeAIEngine.generate()
       ↓
    AIResponse            texte, usage réel, modèle, latence
       ↓
    CostTracker           coût par appel, étape, fournisseur, modèle
       ↓
    project_state.json
       ↓
    report.json["ai_usage"]

Aucun réseau, aucun SDK, aucun crédit consommé. Le tarif employé est FICTIF
(1.00 / 2.00 par million de tokens) : ce scénario valide la plomberie et
l'arithmétique, pas une grille tarifaire réelle.

C'est le scénario que les Phases 3 à 5 rejoueront avec leurs propres étapes.
"""

from __future__ import annotations

import json

import pytest

from app.ai.contracts import AIRequest
from app.ai.cost import COST_STATUS_PARTIAL, CostTracker
from app.ai.pricing import COST_STATUS_KNOWN, ModelPricing, build_default_catalog
from app.ai.providers import FakeAIEngine, FakeReply
from app.ai.usage_store import append_tracker

TARIF_FICTIF = ModelPricing(
    provider="fake",
    model="fake-editor",
    input_cost_per_1m_tokens=1,
    output_cost_per_1m_tokens=2,
    currency="USD",
    effective_date="2026-01-01",
    source="Tarif FICTIF de test — ne correspond à aucun fournisseur réel.",
    verified=False,
)

TARIF_PLANIFICATEUR = ModelPricing(
    provider="fake",
    model="fake-planificateur",
    input_cost_per_1m_tokens=4,
    output_cost_per_1m_tokens=8,
    currency="USD",
    source="Tarif FICTIF de test.",
)


@pytest.fixture
def projet(tmp_path, monkeypatch):
    import app.project_state as project_state
    import app.report_service as report_service

    sortie = tmp_path / "sortie"
    (sortie / "demo").mkdir(parents=True)

    monkeypatch.setattr(project_state, "SORTIE_DIR", sortie)
    monkeypatch.setattr(report_service, "SORTIE_DIR", sortie)

    return "demo"


@pytest.fixture
def tracker():
    """
    Catalogue par défaut (runtimes locaux inclus) enrichi des tarifs fictifs.

    Reproduit la configuration réelle : les entrées Ollama / LM Studio
    viennent du catalogue de base, les tarifs cloud sont ajoutés par-dessus.
    """
    catalogue = build_default_catalog()
    catalogue.register(TARIF_FICTIF)
    catalogue.register(TARIF_PLANIFICATEUR)

    return CostTracker(catalogue)


def _persister(projet, tracker):
    from app.project_state import load_project_state, save_project_state

    state = load_project_state(projet)
    append_tracker(state, tracker)
    save_project_state(projet, state)


def _rapport(projet) -> dict:
    from app.report_service import build_project_report

    return json.loads(build_project_report(projet).read_text(encoding="utf-8"))


class TestScenarioUnAppel:
    """stage=source_analysis, provider=fake, model=fake-editor, 12000/2000."""

    @pytest.fixture
    def execute(self, projet, tracker):
        engine = FakeAIEngine(
            model="fake-editor",
            script=[
                FakeReply(
                    text='{"resume": "analyse de la source"}',
                    input_tokens=12_000,
                    output_tokens=2_000,
                    finish_reason="stop",
                    request_id="fake-req-1",
                    latency_seconds=4.2,
                )
            ],
        )

        response = engine.generate(
            AIRequest(
                prompt="Analyse cette transcription.",
                system_prompt="Tu es un analyste de source.",
                temperature=0.1,
                response_schema={"type": "object"},
                metadata={"stage": "source_analysis"},
            )
        )

        tracker.record_response(response)
        _persister(projet, tracker)

        return response

    def test_reponse_normalisee(self, execute):
        response = execute

        assert response.provider == "fake"
        assert response.model == "fake-editor"
        assert response.input_tokens == 12_000
        assert response.output_tokens == 2_000
        assert response.total_tokens == 14_000
        assert response.latency_ms == 4_200
        assert response.finish_reason == "stop"
        assert response.request_id == "fake-req-1"
        assert response.usage_source == "provider"

    def test_sortie_structuree_decodee(self, execute):
        assert execute.parsed == {"resume": "analyse de la source"}
        assert execute.text == '{"resume": "analyse de la source"}'

    def test_ligne_de_cout(self, tracker, execute):
        record = tracker.records[0]

        assert record.call_id == "CALL000001"
        assert record.stage == "source_analysis"
        assert record.provider == "fake"
        assert record.model == "fake-editor"
        assert record.cost.status == COST_STATUS_KNOWN
        # 12 000 / 1M × 1.00 + 2 000 / 1M × 2.00 = 0.016
        assert float(record.cost.total_cost) == pytest.approx(0.016)

    def test_rapport_final(self, projet, execute):
        bloc = _rapport(projet)["ai_usage"]

        assert bloc["calls"] == 1
        assert bloc["completed_calls"] == 1
        assert bloc["failed_calls"] == 0
        assert bloc["input_tokens"] == 12_000
        assert bloc["output_tokens"] == 2_000
        assert bloc["total_tokens"] == 14_000
        assert bloc["estimated_cost"] == pytest.approx(0.016)
        assert bloc["currency"] == "USD"
        assert bloc["cost_status"] == COST_STATUS_KNOWN

    def test_rapport_par_axe(self, projet, execute):
        bloc = _rapport(projet)["ai_usage"]

        assert bloc["by_stage"]["source_analysis"]["calls"] == 1
        assert bloc["by_provider"]["fake"]["total_tokens"] == 14_000
        assert bloc["by_model"]["fake:fake-editor"]["estimated_cost"] == pytest.approx(
            0.016
        )

    def test_tracabilite_stage_appel_usage_cout(self, projet, execute):
        detail = _rapport(projet)["ai_usage"]["details"][0]

        assert detail["call_id"] == "CALL000001"
        assert detail["stage"] == "source_analysis"
        assert detail["input_tokens"] == 12_000
        assert detail["latency_ms"] == 4_200
        assert detail["cost"]["total_cost"] == pytest.approx(0.016)

    def test_champs_v1_preserves(self, projet, execute):
        rapport = _rapport(projet)

        for cle in ("project", "audio", "chunks", "publication", "cover", "exports"):
            assert cle in rapport


class TestScenarioDeuxEtapes:
    """Un second appel d'une autre étape doit s'agréger proprement."""

    @pytest.fixture
    def execute(self, projet, tracker):
        premier = FakeAIEngine(
            model="fake-editor",
            script=[FakeReply(text="analyse", input_tokens=12_000, output_tokens=2_000)],
        )
        second = FakeAIEngine(
            model="fake-planificateur",
            script=[FakeReply(text="plan", input_tokens=5_000, output_tokens=1_000)],
        )

        tracker.record_response(
            premier.generate(
                AIRequest(prompt="analyse", metadata={"stage": "source_analysis"})
            )
        )
        tracker.record_response(
            second.generate(
                AIRequest(prompt="planifie", metadata={"stage": "editorial_planning"})
            )
        )

        _persister(projet, tracker)

    def test_total_agrege(self, projet, execute):
        bloc = _rapport(projet)["ai_usage"]

        assert bloc["calls"] == 2
        assert bloc["input_tokens"] == 17_000
        assert bloc["output_tokens"] == 3_000
        assert bloc["total_tokens"] == 20_000

    def test_cout_total(self, projet, execute):
        # source_analysis  : 12 000×1 + 2 000×2 par million = 0.016
        # editorial_planning : 5 000×4 + 1 000×8 par million = 0.028
        bloc = _rapport(projet)["ai_usage"]

        assert bloc["estimated_cost"] == pytest.approx(0.044)

    def test_par_stage(self, projet, execute):
        par_stage = _rapport(projet)["ai_usage"]["by_stage"]

        assert par_stage["source_analysis"]["estimated_cost"] == pytest.approx(0.016)
        assert par_stage["editorial_planning"]["estimated_cost"] == pytest.approx(0.028)

    def test_par_model(self, projet, execute):
        par_model = _rapport(projet)["ai_usage"]["by_model"]

        assert set(par_model) == {"fake:fake-editor", "fake:fake-planificateur"}
        assert par_model["fake:fake-planificateur"]["input_tokens"] == 5_000

    def test_identifiants_sequentiels(self, projet, execute):
        details = _rapport(projet)["ai_usage"]["details"]

        assert [d["call_id"] for d in details] == ["CALL000001", "CALL000002"]


class TestScenarioMixte:
    """Un appel tarifé, un non tarifé, un local et un échec."""

    @pytest.fixture
    def execute(self, projet, tracker):
        from app.ai.contracts import AIResponse
        from app.ai.errors import AITimeoutError

        tracker.record_response(
            FakeAIEngine(
                model="fake-editor",
                script=[FakeReply(text="ok", input_tokens=12_000, output_tokens=2_000)],
            ).generate(AIRequest(prompt="x", metadata={"stage": "source_analysis"}))
        )

        tracker.record_response(
            AIResponse(
                text="ok",
                provider="openai",
                model="modele-non-tarife",
                input_tokens=1_000,
                output_tokens=100,
                metadata={"stage": "book_validation"},
            )
        )

        tracker.record_response(
            AIResponse(
                text="ok",
                provider="ollama",
                model="qwen3:8b",
                input_tokens=9_000,
                output_tokens=800,
                metadata={"stage": "book_generation"},
            )
        )

        tracker.record_failure(
            provider="fake",
            model="fake-editor",
            stage="visual_design",
            error=AITimeoutError("trop lent"),
            latency_ms=1_500,
        )

        _persister(projet, tracker)

    def test_cout_partiel_et_non_nul_par_defaut(self, projet, execute):
        bloc = _rapport(projet)["ai_usage"]

        assert bloc["cost_status"] == COST_STATUS_PARTIAL
        assert bloc["unknown_cost_calls"] == 2  # le modèle non tarifé + l'échec
        # Seuls les appels réellement tarifés entrent dans le total : l'appel
        # local compte 0, l'inconnu et l'échec ne comptent pas du tout.
        assert bloc["estimated_cost"] == pytest.approx(0.016)

    def test_provider_local_distingue(self, projet, execute):
        par_provider = _rapport(projet)["ai_usage"]["by_provider"]

        assert par_provider["ollama"]["estimated_cost"] == 0.0
        assert par_provider["ollama"]["cost_status"] == "local_no_api_cost"

    def test_cout_inconnu_n_est_pas_zero(self, projet, execute):
        par_provider = _rapport(projet)["ai_usage"]["by_provider"]

        assert par_provider["openai"]["estimated_cost"] is None
        assert par_provider["openai"]["cost_status"] == "unknown"

    def test_echec_sans_usage_fabrique(self, projet, execute):
        details = _rapport(projet)["ai_usage"]["details"]
        echec = [d for d in details if d["status"] == "failed"][0]

        assert echec["input_tokens"] is None
        assert echec["output_tokens"] is None
        assert echec["cost"]["total_cost"] is None
        assert echec["error_type"] == "AITimeoutError"
        assert echec["latency_ms"] == 1_500

    def test_comptes(self, projet, execute):
        bloc = _rapport(projet)["ai_usage"]

        assert bloc["calls"] == 4
        assert bloc["completed_calls"] == 3
        assert bloc["failed_calls"] == 1
        assert bloc["local_calls"] == 1


class TestAucunAppelReel:

    def test_le_scenario_complet_n_utilise_aucun_reseau(self, no_ai_network, projet, tracker):
        """Preuve directe : le scénario tourne avec le réseau condamné."""
        engine = FakeAIEngine(
            model="fake-editor",
            script=[FakeReply(text="ok", input_tokens=100, output_tokens=10)],
        )

        tracker.record_response(
            engine.generate(AIRequest(prompt="x", metadata={"stage": "source_analysis"}))
        )
        _persister(projet, tracker)

        assert _rapport(projet)["ai_usage"]["calls"] == 1
