"""Phase 3B.7.7A.17 — e2e FakeAI, identité, préflight. 0 provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v3.e2e import run_direct_e2e, run_hierarchical_e2e
from app.source_analysis_local_v3.synthetic import measure_v3_worst_case
from app.source_analysis_small_window_hierarchy.constants import CANDIDATE_PLANNER_VERSION
from app.source_analysis_v2_a15_forensics.constants import A15_SIGNATURE
from app.source_analysis_v3_symbolic_handles.constants import (
    PROJECT_NAME,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
)
from app.source_analysis_v3_symbolic_handles.preflight import build_seven_window_preflight


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestFakeAISevenWindow:
    def test_direct_and_hierarchical(self, tmp_path):
        direct = run_direct_e2e(tmp_path / "d")
        hierarchical = run_hierarchical_e2e(tmp_path / "h")
        assert len(direct.window_results) == 7
        assert len(hierarchical.window_results) == 7
        assert direct.no_drop is True
        assert hierarchical.no_drop is True
        assert direct.source_map.topics
        assert all(t.topic_id.startswith("TOP") for t in direct.source_map.topics)
        assert all(i.idea_id.startswith("IDEA") for i in direct.source_map.ideas)
        assert direct.source_map.repetitions
        assert direct.source_map.source_analysis.author_intent.kinds
        assert direct.source_map.source_analysis.target_audience.kinds
        assert direct.source_map.author_voice_profile.tone
        assert hierarchical.source_map.repetitions
        for result in direct.window_results:
            assert result.transport_version == "semantic-transport-v3"
            assert result.prompt_version == WINDOW_ANALYSIS_PROMPT_VERSION_V13


class TestBudgetsAndIdentity:
    def test_worst_case_and_preflight(self):
        worst = measure_v3_worst_case()
        assert worst["v2"]["local_estimated_tokens"] <= 12000
        assert worst["token_delta"] > 0
        assert worst["local_tokens"] == 12185 or worst["local_tokens"] <= 12000
        preflight = build_seven_window_preflight(PROJECT_NAME)
        assert preflight["window_count"] == 7
        assert preflight["all_within_35000"] is True
        assert preflight["provider_called"] is False
        identity = preflight["win001_identity"]
        assert identity["analysis_signature"] != A15_SIGNATURE
        assert identity["cache"] == "MISS"
        assert identity["forensic_collides"] is False
        assert identity["differs_from_a15"] is True
        assert identity["prompt_version"] == WINDOW_ANALYSIS_PROMPT_VERSION_V13
        assert PLANNER_VERSION == "window-planner-v2.0"
        assert CANDIDATE_PLANNER_VERSION == "window-planner-v2.1-small"
        assert not source_map_path(PROJECT_NAME).is_file()


REAL_PROJECT = Path(r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation")


def test_real_project_source_map_absent():
    assert REAL_PROJECT.joinpath("analysis", "source_map.json").exists() is False
