"""Phase 3B.7.7A.6 — simulations offline. 0 réseau. 0 WIN001."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.source_analysis.consolidation_models import CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS
from app.source_analysis.errors import ConsolidationContextExceeded
from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_models import WINDOW_MAX_OUTPUT_TOKENS
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis_hybrid.constants import HARD_MAX_INPUT_TOKENS, TARGET_INPUT_TOKENS
from app.source_analysis_hybrid.planner import WindowPlannerV2
from app.source_analysis_post_canary_architecture.constants import (
    CALL2_COST,
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SELECTED_ARCHITECTURE,
    THIRD_WIN001_CALL_AUTHORIZED,
)
from app.source_analysis_post_canary_architecture.cost_model import build_cost_artifact
from app.source_analysis_post_canary_architecture.hierarchy import (
    simulate_hierarchy_traceability,
)
from app.source_analysis_post_canary_architecture.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
    package_imports_network_clients,
    package_invokes_provider,
)
from app.source_analysis_post_canary_architecture.response_mode import review_response_modes
from app.source_analysis_post_canary_architecture.simulate import (
    estimate_window_11_overhead,
    simulate_pair,
)
from app.source_analysis_post_canary_architecture.synthetic import (
    fakeai_compatible_transport_json,
    remap_transport_to_window,
    result_from_transport,
    transport_for_scenario,
)
from app.source_analysis_hybrid.tokens import content_weights_for
from app.tests.test_source_analysis_window_planner_v2 import _make_transcript


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOfflineGuards:
    def test_package_has_no_network_imports(self):
        assert package_imports_network_clients() == []
        assert package_invokes_provider() == []
        assert_offline_package()
        assert_analyzer_not_wired()

    def test_phase_authorizes_zero_calls(self):
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert THIRD_WIN001_CALL_AUTHORIZED is False
        assert PHASE == "3B.7.7A.6"


class TestProductionFreeze:
    def test_production_planner_defaults_unchanged(self):
        config = WindowPlannerV2().config
        assert config.target_input_tokens == TARGET_INPUT_TOKENS == 50000
        assert config.hard_max_input_tokens == HARD_MAX_INPUT_TOKENS == 60000
        assert WINDOW_ANALYSIS_PROMPT_VERSION == "window-analysis-1.1"
        assert POLICY_VERSION == "window-granularity-1.0"
        assert WINDOW_MAX_OUTPUT_TOKENS == 32000


class TestPlannerSimulationFixture:
    def test_balanced_coverage_no_stub_no_renumber(self):
        texts = tuple(f"word{index} " * 20 for index in range(12))
        src_ids = tuple(f"SRC{index:06d}" for index in (1, 2, 3, 5, 6, 8, 9, 10, 12, 13, 14, 16))
        transcript = _make_transcript(texts, src_ids=src_ids)
        overhead = estimate_window_11_overhead(transcript)
        weights = content_weights_for(transcript)
        row = simulate_pair(
            transcript,
            target=max(overhead + 40, 80),
            hard_max=max(overhead + 80, 160),
            overhead_11=overhead,
            content_weights=weights,
        )
        assert row["feasible"] is True
        assert row["coverage"]["every_present_src_owned_once"] is True
        assert row["coverage"]["duplicate_owned_src"] == []
        assert row["coverage"]["missing_src"] == []
        assert row["coverage"]["source_order_preserved"] is True
        assert row["coverage"]["sparse_ids_preserved"] is True
        owned = [src for window in row["windows"] for src in [window["first_owned_src_ref"], window["last_owned_src_ref"]]]
        assert "SRC000004" not in owned
        assert row["context_src_refs_empty"] is True


class TestCostUnknownNotZero:
    def test_call_2_cost_is_unknown_not_zero(self):
        assert CALL2_COST == "UNKNOWN"
        costs = build_cost_artifact(
            {
                "current_three_window": {
                    "label": "50000/60000",
                    "feasible": True,
                    "window_count": 3,
                    "words": {"mean": 12745, "max": 12849},
                    "owned_src": {"max": 2787},
                    "local_estimated_request": {"max": 50299},
                    "windows": [
                        {"local_estimated_request_1_1": 50000},
                        {"local_estimated_request_1_1": 49600},
                        {"local_estimated_request_1_1": 49600},
                    ],
                },
                "candidates": [],
            }
        )
        historical = costs["historical_spend"]
        assert historical["call_2_usd"] == "UNKNOWN"
        assert historical["call_2_counted_as_zero"] is False
        assert historical["unknown_is_not_zero"] is True
        assert historical["total_actual_usd"] == "UNKNOWN"
        assert historical["known_minimum_usd"] == "0.533946"


class TestFakeAICompatibleTransport:
    def test_fakeai_emits_medium_transport_without_network(self):
        transport = transport_for_scenario("MEDIUM")
        payload = fakeai_compatible_transport_json(transport)
        engine = FakeAIEngine(script=[FakeReply(text=payload)])
        from app.ai.contracts import AIRequest

        response = engine.generate(AIRequest(prompt="offline-synthetic", model="fake-model"))
        loaded = json.loads(response.text)
        assert loaded["records"]
        assert engine.provider_name == "fake"


class TestHierarchyAccounting:
    def test_no_drop_and_src_survive_without_python_merge(self):
        texts = ("Faith changes a trial.", "Trust is revealed in hardship.")
        transcript = _make_transcript(texts)
        overhead = estimate_window_11_overhead(transcript)
        weights = content_weights_for(transcript)
        row = simulate_pair(
            transcript,
            target=max(overhead + 20, 40),
            hard_max=max(overhead + 60, 120),
            overhead_11=overhead,
            content_weights=weights,
        )
        transport = transport_for_scenario("SMALL")
        results = [
            result_from_transport(
                window,
                remap_transport_to_window(transport, window),
                signature=f"{index:064x}"[-64:],
            )
            for index, window in enumerate(row["plan"].windows, start=1)
        ]
        groups = [[window.window_id for window in row["plan"].windows]]
        trace = simulate_hierarchy_traceability(results, groups=groups)
        assert trace["python_semantic_merge"] is False
        assert trace["ai_semantic_merge"] is True
        assert trace["no_drop"] is True
        assert trace["src_refs_survive_local_regional_global"] is True
        assert trace["generated_range_expansion"] is False


class TestResponseMode:
    def test_streaming_not_verified_and_not_required(self):
        review = review_response_modes()
        assert review["current_mode"] == "synchronous_non_streaming_http"
        assert review["streaming"]["anthropic_engine_supports_streaming_now"] is False
        assert review["streaming"]["provider_streaming_support_verified"] is False
        assert review["async_batch"]["provider_async_batch_verified"] is False
        assert review["decision"] == "OPTIONAL_FUTURE_IMPROVEMENT"
        assert review["forensics"]["improves_generation_reliability"] is False


class TestConsolidationGuard:
    def test_guard_is_80000_and_fail_closed(self):
        assert CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS == 80000
        assert issubclass(ConsolidationContextExceeded, Exception)


class TestSelectedArchitectureName:
    def test_selected_family_is_adaptive_hierarchical(self):
        assert SELECTED_ARCHITECTURE == "SMALLER_WINDOWS_ADAPTIVE_HIERARCHICAL"
        assert PROJECT_NAME == "pastoral_retreat_v2_validation"
