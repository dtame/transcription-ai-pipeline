"""
Phase 3B.7.7A.2 — window output bounding / granularity redesign.

Aucun réseau réel. Aucun retry WIN001.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.consolidation_input import build_consolidation_input_from_plan
from app.source_analysis.errors import (
    WindowGranularityLimitExceeded,
    WindowSemanticCapacityExceeded,
)
from app.source_analysis.hybrid_e2e_fixtures import e2e_engine, plan_e2e_windows
from app.source_analysis.hybrid_service import run_hybrid_source_analysis
from app.source_analysis.validator import validate_source_map
from app.source_analysis.window_analyzer import (
    analyze_window,
    build_window_ai_request,
)
from app.source_analysis.window_cache import inspect_window_cache
from app.source_analysis.window_fixtures import make_transcript, window_for
from app.source_analysis.window_granularity import (
    GRANULARITY_PRINCIPLE,
    HARD_CEILINGS,
    IDEA_HARD_CEILING,
    IDEA_SOFT_TARGET,
    LOCAL_SEMANTIC_MERGE,
    LOCAL_STRING_TRUNCATION,
    OVERFLOW_TOKEN,
    RELATION_HARD_CEILING,
    SOFT_TARGETS,
    TOTAL_HARD_CEILING,
    granularity_policy,
)
from app.source_analysis.window_granularity_fixtures import (
    bounded_success_transport,
    default_window,
    idea_hard_limit_transport,
    multi_src_idea_transport,
    overflow_signal_transport,
    oversized_idea_text_transport,
    relation_explosion_transport,
    repetition_grouped_transport,
    sparse_relations_transport,
    total_limit_transport,
    two_similar_ideas_transport,
)
from app.source_analysis.window_models import WINDOW_MAX_OUTPUT_TOKENS
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    build_window_system_prompt,
    build_window_system_prompt_v10,
)
from app.source_analysis.window_writer import result_path, transport_path
from app.source_analysis_hybrid.constants import (
    HARD_MAX_INPUT_TOKENS,
    TARGET_INPUT_TOKENS,
    WINDOW_TRANSPORT_VERSION,
)
from app.source_analysis_window_output_bounding.constants import (
    PHASE,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_VERSION,
    WIN001_RETRIED,
)
from app.source_analysis_window_output_bounding.integrity import protected_hashes
from app.source_analysis_window_output_bounding.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
    package_imports_network_clients,
    package_invokes_provider,
)
from app.source_analysis_window_output_bounding.runner import run_window_output_bounding
from app.source_analysis.writer import source_map_path

REAL_AUDIT = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation\audit"
)
PROTECTED_BEFORE = protected_hashes(PROJECT_NAME)


def _engine(transport: dict) -> FakeAIEngine:
    return FakeAIEngine(
        script=[FakeReply(parsed=transport)],
        retry_policy=no_delay_policy(max_attempts=1),
    )


def _analyze(tmp_path, transport, transcript=None, window=None):
    if transcript is None or window is None:
        transcript, window = default_window()
    root = tmp_path / "windows"
    result = analyze_window(
        window,
        transcript,
        _engine(transport),
        windows_root=root,
    )
    return result, root, window, transcript


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
        assert WIN001_RETRIED is False
        assert WINDOW_MAX_OUTPUT_TOKENS == 32000
        assert TARGET_INPUT_TOKENS == 50000
        assert HARD_MAX_INPUT_TOKENS == 60000


class TestPolicyAndPrompt:
    def test_soft_and_hard_present(self):
        policy = granularity_policy()
        assert policy["soft_targets"] == SOFT_TARGETS
        assert policy["hard_ceilings"] == HARD_CEILINGS
        assert policy["total_hard_ceiling"] == TOTAL_HARD_CEILING
        assert SOFT_TARGETS["IDEA"] == IDEA_SOFT_TARGET
        assert HARD_CEILINGS["IDEA"] == IDEA_HARD_CEILING
        assert HARD_CEILINGS["RELATION"] == RELATION_HARD_CEILING
        assert GRANULARITY_PRINCIPLE == (
            "ONE_RECORD_PER_DISTINCT_SUBSTANTIVE_SEMANTIC_UNIT"
        )
        assert LOCAL_SEMANTIC_MERGE is False
        assert LOCAL_STRING_TRUNCATION is False

    def test_prompt_versioning(self):
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V10 == "window-analysis-1.0"
        assert WINDOW_ANALYSIS_PROMPT_VERSION == "window-analysis-1.1"
        v10 = build_window_system_prompt_v10("en")
        v11 = build_window_system_prompt("en")
        assert v10 == build_window_system_prompt(
            "en", version=WINDOW_ANALYSIS_PROMPT_VERSION_V10
        )
        assert "GRANULARITÉ SÉMANTIQUE" not in v10
        assert "GRANULARITÉ SÉMANTIQUE" in v11
        assert "analysis_capacity_exceeded" in v11
        assert v10 != v11

    def test_historical_prompt_byte_identical_across_calls(self):
        assert build_window_system_prompt_v10("en") == build_window_system_prompt_v10(
            "en"
        )


class TestFakeAIFixtures:
    def test_bounded_success(self, tmp_path):
        transcript, window = default_window()
        result, root, _, _ = _analyze(
            tmp_path,
            bounded_success_transport(owned=window.owned_src_refs),
            transcript,
            window,
        )
        assert result.prompt_version == WINDOW_ANALYSIS_PROMPT_VERSION
        assert transport_path("fixture", window.window_id, root=root).is_file()
        assert result_path("fixture", window.window_id, root=root).is_file()

    def test_multi_src_grouping(self, tmp_path):
        transcript, window = default_window()
        result, _, _, _ = _analyze(
            tmp_path,
            multi_src_idea_transport(owned=window.owned_src_refs),
            transcript,
            window,
        )
        ideas = [record for record in result.records if record.kind == "IDEA"]
        assert len(ideas) == 1
        assert len(ideas[0].source_refs) >= 2

    def test_no_local_semantic_merge(self, tmp_path):
        transcript, window = default_window()
        result, _, _, _ = _analyze(
            tmp_path,
            two_similar_ideas_transport(owned=window.owned_src_refs),
            transcript,
            window,
        )
        ideas = [record for record in result.records if record.kind == "IDEA"]
        assert len(ideas) == 2
        assert ideas[0].value != ideas[1].value

    def test_repetition_grouping(self, tmp_path):
        transcript, window = default_window()
        result, _, _, _ = _analyze(
            tmp_path,
            repetition_grouped_transport(owned=window.owned_src_refs),
            transcript,
            window,
        )
        reps = [record for record in result.records if record.kind == "REPETITION"]
        assert len(reps) == 1

    def test_relation_sparsity(self, tmp_path):
        transcript, window = default_window()
        result, _, _, _ = _analyze(
            tmp_path,
            sparse_relations_transport(owned=window.owned_src_refs, idea_count=8),
            transcript,
            window,
        )
        ideas = [record for record in result.records if record.kind == "IDEA"]
        rels = [record for record in result.records if record.kind == "RELATION"]
        assert len(ideas) == 8
        assert len(rels) == 2
        assert len(rels) < len(ideas) * (len(ideas) - 1) / 2

    def test_idea_hard_limit_transport_first(self, tmp_path):
        transcript, window = default_window()
        root = tmp_path / "windows"
        engine = _engine(idea_hard_limit_transport(owned=window.owned_src_refs))
        with pytest.raises(WindowGranularityLimitExceeded):
            analyze_window(window, transcript, engine, windows_root=root)
        assert engine.call_count == 1
        assert transport_path("fixture", window.window_id, root=root).is_file()
        assert not result_path("fixture", window.window_id, root=root).exists()

    def test_total_limit_fail_closed(self, tmp_path):
        transcript, window = default_window()
        root = tmp_path / "windows"
        with pytest.raises(WindowGranularityLimitExceeded):
            analyze_window(
                window,
                transcript,
                _engine(total_limit_transport(owned=window.owned_src_refs)),
                windows_root=root,
            )
        assert transport_path("fixture", window.window_id, root=root).is_file()
        assert not result_path("fixture", window.window_id, root=root).exists()

    def test_relation_explosion_fail_closed(self, tmp_path):
        transcript, window = default_window()
        root = tmp_path / "windows"
        with pytest.raises(WindowGranularityLimitExceeded) as excinfo:
            analyze_window(
                window,
                transcript,
                _engine(relation_explosion_transport(owned=window.owned_src_refs)),
                windows_root=root,
            )
        assert "RELATION" in str(excinfo.value)
        assert transport_path("fixture", window.window_id, root=root).is_file()
        assert not result_path("fixture", window.window_id, root=root).exists()

    def test_overflow_signal_not_ready(self, tmp_path):
        transcript, window = default_window()
        root = tmp_path / "windows"
        with pytest.raises(WindowSemanticCapacityExceeded):
            analyze_window(
                window,
                transcript,
                _engine(overflow_signal_transport(owned=window.owned_src_refs)),
                windows_root=root,
            )
        raw = json.loads(
            transport_path("fixture", window.window_id, root=root).read_text(
                encoding="utf-8"
            )
        )
        assert any(item.get("v") == OVERFLOW_TOKEN for item in raw["records"])
        assert not result_path("fixture", window.window_id, root=root).exists()

    def test_no_local_truncation(self, tmp_path):
        transcript, window = default_window()
        root = tmp_path / "windows"
        transport = oversized_idea_text_transport(owned=window.owned_src_refs)
        long_value = transport["records"][1]["v"]
        with pytest.raises(WindowGranularityLimitExceeded):
            analyze_window(window, transcript, _engine(transport), windows_root=root)
        persisted = json.loads(
            transport_path("fixture", window.window_id, root=root).read_text(
                encoding="utf-8"
            )
        )
        assert persisted["records"][1]["v"] == long_value
        assert not result_path("fixture", window.window_id, root=root).exists()


class TestSignatureAndCache:
    def test_signature_invalidates_between_versions(self):
        transcript = make_transcript(("Faith changes the crossing.",))
        window = window_for(transcript)
        old = build_window_ai_request(
            window, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10
        )
        new = build_window_ai_request(
            window, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION
        )
        assert old.signature != new.signature
        assert old.signature_inputs.prompt_version == "window-analysis-1.0"
        assert new.signature_inputs.prompt_version == "window-analysis-1.1"

    def test_cache_distinguishes_versions(self, tmp_path):
        transcript, window = default_window()
        root = tmp_path / "windows"
        engine = _engine(bounded_success_transport(owned=window.owned_src_refs))
        analyze_window(
            window,
            transcript,
            engine,
            windows_root=root,
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
        )
        v11 = build_window_ai_request(
            window,
            transcript,
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
            provider=engine.provider_name,
            model=engine.resolve_model(),
        )
        v10 = build_window_ai_request(
            window,
            transcript,
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10,
            provider=engine.provider_name,
            model=engine.resolve_model(),
        )
        hit = inspect_window_cache(
            window,
            transcript,
            windows_root=root,
            expected_signature=v11.signature,
            engine=engine,
        )
        miss = inspect_window_cache(
            window,
            transcript,
            windows_root=root,
            expected_signature=v10.signature,
            engine=engine,
        )
        assert hit.cache_state == "HIT"
        assert miss.cache_state != "HIT"


class TestCompatibility:
    def test_consolidation_accepts_bounded_result(self, tmp_path):
        from app.source_analysis.window_fixtures import three_window_fixture
        from app.source_analysis.window_granularity_fixtures import (
            bounded_success_transport,
        )

        transcript, plan = three_window_fixture()
        results = []
        for window in plan.windows:
            owned = window.owned_src_refs
            result = analyze_window(
                window,
                transcript,
                _engine(bounded_success_transport(owned=owned)),
                windows_root=tmp_path / "w",
            )
            results.append(result)
        built = build_consolidation_input_from_plan(plan, results)
        assert len(built.windows) == 3

    def test_reconstructor_e2e_with_successor(self, tmp_path):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        assert run.source_map is not None
        assert run.all_windows_ready
        for result in run.orchestration.get_ready_results_in_plan_order():
            assert result.prompt_version == WINDOW_ANALYSIS_PROMPT_VERSION
        validate_source_map(run.source_map, transcript)


class TestArtifacts:
    def test_real_project_offline_artifacts_deterministic(self):
        first = run_window_output_bounding(PROJECT_NAME)
        assert first["real_provider_calls"] == 0
        assert first["result"] in {"PASS", "PARTIAL"}
        policy = json.loads(
            (REAL_AUDIT / "source_analysis_window_granularity_policy.json").read_text(
                encoding="utf-8"
            )
        )
        study = json.loads(
            (REAL_AUDIT / "source_analysis_window_output_size_study.json").read_text(
                encoding="utf-8"
            )
        )
        pre = json.loads(
            (
                REAL_AUDIT / "source_analysis_win001_bounded_prompt_preflight.json"
            ).read_text(encoding="utf-8")
        )
        impl = json.loads(
            (
                REAL_AUDIT
                / "source_analysis_window_output_bounding_implementation.json"
            ).read_text(encoding="utf-8")
        )
        report = (
            REAL_AUDIT
            / "PHASE_3B77A2_WINDOW_OUTPUT_BOUNDING_GRANULARITY_REDESIGN_REPORT.md"
        ).read_text(encoding="utf-8")
        assert policy["schema_version"] == SCHEMA_VERSION
        assert policy["phase"] == PHASE
        assert study["phase"] == PHASE
        assert pre["real_calls"] == 0
        assert pre["win001_retried"] is False
        assert pre["signatures_differ"] is True
        assert impl["generation_c_changed"] is False
        assert impl["network"] == 0
        assert "REAL PROVIDER CALLS =" in report
        assert "WIN001 RETRIED =" in report
        after = protected_hashes(PROJECT_NAME)
        assert after == PROTECTED_BEFORE
        assert not source_map_path(PROJECT_NAME).exists()
        win001 = Path(
            r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
            r"\analysis\windows\WIN001"
        )
        assert not (win001 / "transport.json").exists()
        assert not (win001 / "result.json").exists()

    def test_generation_c_unchanged(self):
        assert WINDOW_TRANSPORT_VERSION == "semantic-transport-v1"
        from app.source_analysis_timeout_config.audit import generation_c_hashes

        hashes = generation_c_hashes()
        assert hashes["raw_matches_historical"] is True
