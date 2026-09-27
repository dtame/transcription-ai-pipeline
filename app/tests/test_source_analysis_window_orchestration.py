"""
Phase 3B.7.3 — window cache / resume / validation orchestration.

Aucun réseau. Aucun engine.generate() vers un fournisseur réel.
Aucun source_map de production. Aucune consolidation. Aucun Attempt #3.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.ai.errors import AITimeoutError
from app.ai.providers.fake import FakeReply
from app.ai.settings import resolve_stage_settings
from app.source_analysis.errors import WindowsIncompleteError
from app.source_analysis.orchestration_models import (
    CACHE_HIT,
    CACHE_INVALID,
    CACHE_MISS,
    CACHE_STALE,
    READINESS_FAILED,
    READINESS_PENDING,
    READINESS_READY,
    assert_all_windows_ready,
)
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.window_analyzer import WindowAnalysisHooks
from app.source_analysis.window_cache import expected_window_signature
from app.source_analysis.window_fixtures import (
    WindowMappedFakeAI,
    mapped_minimal_engine,
    minimal_transport,
    three_window_fixture,
    window_plan_from_inputs,
)
from app.source_analysis.window_models import STAGE_WINDOW, make_window_input
from app.source_analysis.window_orchestrator import orchestrate_windows
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis.window_writer import (
    leftover_partial,
    metadata_path,
    result_path,
    transport_path,
    window_dir,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis_window_orchestration.cli import main as orch_cli
from app.source_analysis_window_orchestration.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_window_orchestration.runner import (
    run_real_preflight,
    run_window_orchestration,
)
from app.source_analysis_window_pipeline.offline import (
    assert_analyzer_not_wired as assert_window_not_wired,
)

REAL_PROJECT = "pastoral_retreat_v2_validation"
REAL_CLEAN = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
    r"\transcripts\clean\transcript_data.json"
)


def _run(tmp_path, plan, transcript, engine=None, **kwargs):
    root = tmp_path / "windows"
    result = orchestrate_windows(
        plan,
        transcript,
        engine=engine if engine is not None else mapped_minimal_engine(plan),
        windows_root=root,
        **kwargs,
    )
    return result, root


def _plant_cache(tmp_path, plan, transcript):
    result, root = _run(tmp_path, plan, transcript)
    assert result.all_windows_ready
    return root


class TestColdAndWarm:
    def test_cold_run_three_ready(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        engine = mapped_minimal_engine(plan)
        result, root = _run(tmp_path, plan, transcript, engine)
        assert engine.call_count == 3
        assert result.all_windows_ready is True
        assert [status.window_id for status in result.statuses] == [
            "WIN001",
            "WIN002",
            "WIN003",
        ]
        assert all(status.readiness == READINESS_READY for status in result.statuses)
        for window in plan.windows:
            assert transport_path("fixture", window.window_id, root=root).is_file()
            assert result_path("fixture", window.window_id, root=root).is_file()
            assert metadata_path("fixture", window.window_id, root=root).is_file()
            assert leftover_partial(
                result_path("fixture", window.window_id, root=root)
            ) is None

    def test_warm_cache_zero_calls(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        _plant_cache(tmp_path, plan, transcript)
        engine = mapped_minimal_engine(plan)
        result, _ = _run(tmp_path, plan, transcript, engine)
        assert engine.call_count == 0
        assert result.new_calls_consumed == 0
        assert result.cache_hit_windows == 3
        assert result.all_windows_ready is True
        assert_all_windows_ready(result)
        handed = result.get_ready_results_in_plan_order()
        assert [item.window_id for item in handed] == ["WIN001", "WIN002", "WIN003"]


class TestFailureResume:
    def test_stop_on_first_failure_and_resume(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        fail_engine = WindowMappedFakeAI(
            {
                "WIN001": FakeReply(parsed=minimal_transport(owned_src="SRC000001")),
                "WIN002": AITimeoutError("win002"),
                "WIN003": FakeReply(parsed=minimal_transport(owned_src="SRC000003")),
            }
        )
        first, root = _run(tmp_path, plan, transcript, fail_engine)
        assert first.statuses[0].readiness == READINESS_READY
        assert first.statuses[1].readiness == READINESS_FAILED
        assert first.statuses[2].readiness == READINESS_PENDING
        assert first.all_windows_ready is False
        assert fail_engine.call_count == 2
        assert result_path("fixture", "WIN001", root=root).is_file()
        assert not result_path("fixture", "WIN002", root=root).is_file()

        resume_engine = WindowMappedFakeAI(
            {
                "WIN002": FakeReply(parsed=minimal_transport(owned_src="SRC000002")),
                "WIN003": FakeReply(parsed=minimal_transport(owned_src="SRC000003")),
            }
        )
        second, _ = _run(tmp_path, plan, transcript, resume_engine)
        assert resume_engine.call_count == 2
        assert second.statuses[0].cache_state == CACHE_HIT
        assert second.all_windows_ready is True

    def test_failed_call_consumes_budget(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        engine = WindowMappedFakeAI(
            {
                "WIN001": AITimeoutError("boom"),
                "WIN002": FakeReply(parsed=minimal_transport(owned_src="SRC000002")),
            }
        )
        result, _ = _run(tmp_path, plan, transcript, engine, max_new_calls=1)
        assert result.new_calls_consumed == 1
        assert engine.call_count == 1
        assert result.statuses[0].readiness == READINESS_FAILED
        assert result.statuses[1].readiness == READINESS_PENDING
        assert result.statuses[2].readiness == READINESS_PENDING


class TestTransportRecovery:
    def test_missing_result_recovers_without_generate(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        root = _plant_cache(tmp_path, plan, transcript)
        for window in plan.windows:
            result_path("fixture", window.window_id, root=root).unlink()
        engine = mapped_minimal_engine(plan)
        result, _ = _run(tmp_path, plan, transcript, engine)
        assert engine.call_count == 0
        assert result.transport_recovered_windows == 3
        assert result.all_windows_ready is True

    def test_crash_after_transport_single_window(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()

        def crash(result):
            if result.window_id == "WIN002":
                raise RuntimeError("crash after transport")

        engine = mapped_minimal_engine(plan)
        first, root = _run(
            tmp_path,
            plan,
            transcript,
            engine,
            hooks=WindowAnalysisHooks(before_result_write=crash),
        )
        assert first.statuses[0].readiness == READINESS_READY
        assert first.statuses[1].readiness == READINESS_FAILED
        assert first.statuses[2].readiness == READINESS_PENDING
        assert transport_path("fixture", "WIN002", root=root).is_file()
        assert not result_path("fixture", "WIN002", root=root).is_file()

        resume = mapped_minimal_engine(plan)
        second, _ = _run(tmp_path, plan, transcript, resume)
        assert resume.call_count == 1
        assert second.statuses[0].cache_state == CACHE_HIT
        assert second.statuses[1].execution_kind == "TRANSPORT_RECOVERED"
        assert second.statuses[2].execution_kind == "GENERATED"
        assert second.all_windows_ready is True

    def test_result_corruption_recovers(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        root = _plant_cache(tmp_path, plan, transcript)
        path = result_path("fixture", "WIN002", root=root)
        path.write_text("{not-json", encoding="utf-8")
        engine = mapped_minimal_engine(plan)
        result, _ = _run(tmp_path, plan, transcript, engine)
        assert engine.call_count == 0
        assert result.all_windows_ready is True
        assert result.statuses[1].execution_kind == "TRANSPORT_RECOVERED"


class TestInvalidation:
    def test_signature_change_only_win002(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        _plant_cache(tmp_path, plan, transcript)
        mutated, mutated_plan = three_window_fixture(
            texts=(
                "Faith changes the crossing of a trial.",
                "Trust is shown now during hardship.",
                "Keep walking through the valley.",
            ),
            content_sha256=transcript.content_sha256,
        )
        engine = mapped_minimal_engine(mutated_plan)
        result, _ = _run(
            tmp_path, mutated_plan, mutated, engine, max_new_calls=0
        )
        assert result.statuses[0].cache_state == CACHE_HIT
        assert result.statuses[1].cache_state == CACHE_STALE
        assert result.statuses[2].cache_state == CACHE_HIT
        assert engine.call_count == 0

    def test_prompt_change_stales_all(self, tmp_path, no_ai_network, monkeypatch):
        transcript, plan = three_window_fixture()
        _plant_cache(tmp_path, plan, transcript)
        monkeypatch.setattr(
            "app.source_analysis.window_prompt.WINDOW_ANALYSIS_PROMPT_VERSION",
            "window-analysis-1.0",
        )
        result, _ = _run(tmp_path, plan, transcript, max_new_calls=0)
        assert all(status.cache_state == CACHE_STALE for status in result.statuses)

    def test_model_change_stales(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        _plant_cache(tmp_path, plan, transcript)
        engine = WindowMappedFakeAI(
            {
                window.window_id: FakeReply(
                    parsed=minimal_transport(owned_src=window.owned_src_refs[0])
                )
                for window in plan.windows
            },
            model="other-fake-model",
        )
        result, _ = _run(tmp_path, plan, transcript, engine, max_new_calls=0)
        assert all(status.cache_state == CACHE_STALE for status in result.statuses)

    def test_max_output_change_stales(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        _plant_cache(tmp_path, plan, transcript)
        settings = replace(
            resolve_stage_settings(STAGE_WINDOW), max_output_tokens=16000
        )
        result, _ = _run(
            tmp_path, plan, transcript, settings=settings, max_new_calls=0
        )
        assert all(status.cache_state == CACHE_STALE for status in result.statuses)

    def test_language_change_stales(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        _plant_cache(tmp_path, plan, transcript)
        fr_transcript, fr_plan = three_window_fixture(language="fr")
        result, _ = _run(tmp_path, fr_plan, fr_transcript, max_new_calls=0)
        assert all(status.cache_state == CACHE_STALE for status in result.statuses)

    def test_planner_version_stales(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        _plant_cache(tmp_path, plan, transcript)
        changed = []
        for window in plan.windows:
            changed.append(
                make_window_input(
                    transcript,
                    owned_src_refs=window.owned_src_refs,
                    window_id=window.window_id,
                    planner_version="window-planner-v9.9",
                    estimated_input_tokens=window.estimated_input_tokens,
                )
            )
        new_plan = window_plan_from_inputs(transcript, tuple(changed))
        result, _ = _run(tmp_path, new_plan, transcript, max_new_calls=0)
        assert all(status.cache_state == CACHE_STALE for status in result.statuses)


class TestCorruption:
    def test_transport_corruption_not_hit(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        root = _plant_cache(tmp_path, plan, transcript)
        transport_path("fixture", "WIN001", root=root).write_text(
            "{broken", encoding="utf-8"
        )
        result, _ = _run(tmp_path, plan, transcript, max_new_calls=0)
        assert result.statuses[0].cache_state != CACHE_HIT
        assert result.statuses[0].readiness != READINESS_READY

    def test_missing_transport_not_hit(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        root = _plant_cache(tmp_path, plan, transcript)
        transport_path("fixture", "WIN001", root=root).unlink()
        result, _ = _run(tmp_path, plan, transcript, max_new_calls=0)
        assert result.statuses[0].cache_state == CACHE_INVALID
        assert result.statuses[0].readiness == READINESS_PENDING

    def test_wrong_window_result(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        root = _plant_cache(tmp_path, plan, transcript)
        win2 = json.loads(
            result_path("fixture", "WIN002", root=root).read_text(encoding="utf-8")
        )
        result_path("fixture", "WIN001", root=root).write_text(
            json.dumps(win2, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result, _ = _run(tmp_path, plan, transcript, max_new_calls=0)
        assert result.statuses[0].cache_state != CACHE_HIT

    def test_wrong_input_hash(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        root = _plant_cache(tmp_path, plan, transcript)
        payload = json.loads(
            result_path("fixture", "WIN001", root=root).read_text(encoding="utf-8")
        )
        payload["window_input_hash"] = "0" * 64
        result_path("fixture", "WIN001", root=root).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result, _ = _run(tmp_path, plan, transcript, max_new_calls=0)
        assert result.statuses[0].cache_state != CACHE_HIT

    def test_wrong_signature(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        root = _plant_cache(tmp_path, plan, transcript)
        payload = json.loads(
            result_path("fixture", "WIN001", root=root).read_text(encoding="utf-8")
        )
        payload["window_analysis_signature"] = "f" * 64
        result_path("fixture", "WIN001", root=root).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        meta = json.loads(
            metadata_path("fixture", "WIN001", root=root).read_text(encoding="utf-8")
        )
        meta["identity"]["window_analysis_signature"] = "f" * 64
        metadata_path("fixture", "WIN001", root=root).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result, _ = _run(tmp_path, plan, transcript, max_new_calls=0)
        assert result.statuses[0].cache_state == CACHE_STALE

    def test_invalid_src_in_cache(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        root = _plant_cache(tmp_path, plan, transcript)
        payload = json.loads(
            result_path("fixture", "WIN001", root=root).read_text(encoding="utf-8")
        )
        payload["records"][0]["source_refs"] = ["SRC999999"]
        result_path("fixture", "WIN001", root=root).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result, _ = _run(tmp_path, plan, transcript, max_new_calls=0)
        assert result.statuses[0].cache_state != CACHE_HIT

    def test_invalid_intermediate_id(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        root = _plant_cache(tmp_path, plan, transcript)
        payload = json.loads(
            result_path("fixture", "WIN001", root=root).read_text(encoding="utf-8")
        )
        payload["records"][0]["record_id"] = "WIN002:R0001"
        result_path("fixture", "WIN001", root=root).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result, _ = _run(tmp_path, plan, transcript, max_new_calls=0)
        assert result.statuses[0].cache_state != CACHE_HIT

    def test_editorial_leakage_cache(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        root = _plant_cache(tmp_path, plan, transcript)
        payload = json.loads(
            result_path("fixture", "WIN001", root=root).read_text(encoding="utf-8")
        )
        payload["chapters"] = [{"title": "Chapter 1"}]
        result_path("fixture", "WIN001", root=root).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result, _ = _run(tmp_path, plan, transcript, max_new_calls=0)
        assert result.statuses[0].cache_state != CACHE_HIT

    def test_partial_file_not_cache(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        root = tmp_path / "windows"
        directory = window_dir("fixture", "WIN001", root=root)
        directory.mkdir(parents=True)
        (directory / "result.json.partial").write_text("{}", encoding="utf-8")
        result, _ = _run(tmp_path, plan, transcript, max_new_calls=0)
        assert result.statuses[0].cache_state == CACHE_MISS

    def test_ambiguous_result_files(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        root = _plant_cache(tmp_path, plan, transcript)
        extra = window_dir("fixture", "WIN001", root=root) / "result.alt.json"
        extra.write_text("{}", encoding="utf-8")
        result, _ = _run(tmp_path, plan, transcript, max_new_calls=0)
        assert result.statuses[0].error_classification == "CACHE_AMBIGUOUS"
        assert result.statuses[0].readiness == READINESS_FAILED


class TestBudgetGateOrder:
    def test_budget_zero(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        engine = mapped_minimal_engine(plan)
        result, _ = _run(tmp_path, plan, transcript, engine, max_new_calls=0)
        assert engine.call_count == 0
        assert result.pending_windows == 3
        assert result.all_windows_ready is False

    def test_budget_one(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        engine = mapped_minimal_engine(plan)
        result, _ = _run(tmp_path, plan, transcript, engine, max_new_calls=1)
        assert engine.call_count == 1
        assert result.ready_windows == 1
        assert result.pending_windows == 2
        assert result.statuses[0].window_id == "WIN001"

    def test_gate_rejects_partial(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        result, _ = _run(tmp_path, plan, transcript, max_new_calls=2)
        assert result.ready_windows == 2
        with pytest.raises(WindowsIncompleteError):
            assert_all_windows_ready(result)

    def test_source_order_not_filesystem(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        root = tmp_path / "windows"
        for window_id in ("WIN003", "WIN001", "WIN002"):
            window_dir("fixture", window_id, root=root).mkdir(parents=True)
        engine = mapped_minimal_engine(plan)
        result = orchestrate_windows(
            plan, transcript, engine=engine, windows_root=root, max_new_calls=1
        )
        assert [status.window_id for status in result.statuses] == [
            "WIN001",
            "WIN002",
            "WIN003",
        ]
        assert engine.requests[0].metadata["window_id"] == "WIN001"

    def test_handoff_no_merge(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()
        result, _ = _run(tmp_path, plan, transcript)
        handed = result.get_ready_results_in_plan_order()
        assert [item.window_id for item in handed] == [
            window.window_id for window in plan.windows
        ]
        assert "source_map" not in result.to_dict()
        assert result.to_dict().get("generated_at") is None

    def test_keyboard_interrupt_not_success(self, tmp_path, no_ai_network):
        transcript, plan = three_window_fixture()

        def boom(_response):
            raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            _run(
                tmp_path,
                plan,
                transcript,
                hooks=WindowAnalysisHooks(after_generate=boom),
            )


class TestIntegrity:
    def test_prompt_1_3_unchanged(self):
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V10 == "window-analysis-1.0"
        assert WINDOW_ANALYSIS_PROMPT_VERSION == "window-analysis-1.1"

    def test_generation_c_unchanged(self):
        hashes = generation_c_hashes()
        assert hashes["raw_matches_historical"] is True
        assert hashes["anthropic_matches_historical"] is True

    def test_analyzer_not_wired(self):
        assert_window_not_wired()
        assert_analyzer_not_wired()
        assert_offline_package()

    def test_rejects_real_call(self):
        assert orch_cli(["demo", "--real-call"]) == 2

    def test_signature_formula_reused(self):
        transcript, plan = three_window_fixture()
        engine = mapped_minimal_engine(plan)
        first = expected_window_signature(plan.windows[0], transcript, engine=engine)
        second = expected_window_signature(plan.windows[0], transcript, engine=engine)
        assert first == second
        assert first != plan.windows[0].window_id


@pytest.mark.skipif(not REAL_CLEAN.is_file(), reason="real clean transcript absent")
class TestRealPreflight:
    def test_zero_call_preflight(self, no_ai_network):
        from app.source_analysis_execution_strategy.windows import load_clean_transcript

        transcript = load_clean_transcript(REAL_PROJECT)
        plan = plan_windows_v2(transcript)
        assert plan.window_count == 3
        assert [window.owned_src_count for window in plan.windows] == [2787, 2771, 2740]
        preflight = run_real_preflight(REAL_PROJECT)
        assert preflight["stopped"] is False
        assert preflight["window_count"] == 3
        assert preflight["max_new_calls"] == 0
        assert preflight["new_calls"] == 0
        assert preflight["all_windows_ready"] is False
        assert preflight["real_provider_calls"] == 0
        assert preflight["cache_states"] == [CACHE_MISS, CACHE_MISS, CACHE_MISS]
        assert not source_map_path(REAL_PROJECT).exists()
        assert Path(
            r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
            r"\analysis\windows"
        ).exists() is False

    def test_runner_writes_audit_only(self, no_ai_network):
        result = run_window_orchestration(REAL_PROJECT)
        assert result.outcome in {"PASS", "PARTIAL"}
        assert result.deterministic is True
        assert result.protected_unchanged is True
        assert result.artifact["execution"]["anthropic_calls"] == 0
        assert result.artifact["execution"]["source_map_published"] is False
        assert result.artifact["execution"]["global_consolidation"] is False
        assert not source_map_path(REAL_PROJECT).exists()
        assert result.project_state_status not in {"SUCCESS", "completed"}
        again = run_window_orchestration(REAL_PROJECT)
        assert again.artifact_sha256 == result.artifact_sha256
