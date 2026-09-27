"""
Phase 3B.7 — design offline hybrid window + consolidation.

Aucun réseau. Aucun engine.generate() vers un fournisseur réel.
Aucun source_map de production. Aucun Attempt #3.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.transcript_input import (
    TranscriptInputMode,
    load_transcript_input,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_global_clean.writer import production_source_map_path
from app.source_analysis_hybrid_design.architecture import (
    assert_offline_package,
    package_calls_generate_or_post,
)
from app.source_analysis_hybrid_design.cli import main as hybrid_cli
from app.source_analysis_hybrid_design.cli import run_hybrid_design
from app.source_analysis_hybrid_design.constants import (
    HARD_MAX_INPUT_TOKENS,
    OVERLAP_POLICY,
    PHASE,
    PLANNER_VERSION,
    STRATEGY,
    TARGET_INPUT_TOKENS,
    WINDOW_TRANSPORT_VERSION,
)
from app.source_analysis_hybrid_design.planner_v2 import (
    _apply_tiny_tail,
    _balanced_cuts,
    plan_windows_v2,
)
from app.source_analysis_hybrid_design.simulation import (
    build_deterministic_simulation,
    current_planner_pathology,
    simulate_planner_v2,
)
from app.source_analysis_hybrid_design.writer import (
    architecture_design_path,
    consolidation_design_path,
    planner_simulation_path,
    report_path,
    window_design_path,
)
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.tests.source_analysis_fixtures import (  # noqa: F401
    analysis_env,
    drop_segments,
    write_cleanup_provenance,
    write_transcript,
)

SPARSE_DROP = ("SRC000006", "SRC000007", "SRC000008")
REAL_PROJECT = "pastoral_retreat_v2_validation"
REAL_CLEAN = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
    r"\transcripts\clean\transcript_data.json"
)


def _sparse_env(env):
    original = env.document
    removed = [segment for segment in original.segments if segment.id in SPARSE_DROP]
    clean = drop_segments(original, set(SPARSE_DROP))
    clean_path = write_transcript(env.transcripts_dir / "clean", clean)
    provenance_path = env.sortie / env.project_name / "audit" / "cleanup_application.json"
    write_cleanup_provenance(
        provenance_path,
        original_path=env.transcript_path,
        clean_path=clean_path,
        original=original,
        clean=clean,
        removed=removed,
    )
    return clean_path, provenance_path


def _load_source(env):
    return load_transcript_input(
        env.transcript_path,
        project_name=env.project_name,
        mode=TranscriptInputMode.SOURCE,
    )


class TestOfflinePackage:
    def test_package_has_no_generate_or_post(self):
        assert package_calls_generate_or_post() == []
        assert_offline_package()

    def test_modules_do_not_import_network_clients(self):
        root = Path(__file__).resolve().parents[1] / "source_analysis_hybrid_design"
        forbidden = {"requests", "urllib", "httpx", "openai", "anthropic"}
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {alias.name.split(".")[0] for alias in node.names}
                    assert names.isdisjoint(forbidden), path.name
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module.split(".")[0] not in forbidden, path.name


class TestPlannerV2Unit:
    def test_balanced_cuts_are_contiguous_and_complete(self):
        cuts = _balanced_cuts((10, 10, 10, 10, 10, 10), 3)
        assert cuts[0] == 0
        assert cuts[-1] == 6
        assert cuts == sorted(cuts)
        assert all(later > earlier for earlier, later in zip(cuts, cuts[1:]))

    def test_tiny_tail_merges_when_hard_max_allows(self):
        weights = (40, 40, 40, 1)
        cuts = [0, 2, 3, 4]
        merged = _apply_tiny_tail(cuts, weights, min_content=10, hard_content=100)
        assert merged[-1] == 4
        assert merged[-2] < 3 or len(merged) == 3

    def test_plan_is_deterministic_and_owns_each_src_once(self, analysis_env):
        transcript = _load_source(analysis_env)
        first = plan_windows_v2(
            transcript,
            target_input_tokens=80,
            hard_max_input_tokens=200,
            overhead=0,
            remeasure=False,
        )
        second = plan_windows_v2(
            transcript,
            target_input_tokens=80,
            hard_max_input_tokens=200,
            overhead=0,
            remeasure=False,
        )
        assert [window.window_id for window in first] == [
            window.window_id for window in second
        ]
        assert [window.owned_src_ids for window in first] == [
            window.owned_src_ids for window in second
        ]
        owned = [src for window in first for src in window.owned_src_ids]
        assert owned == list(transcript.src_ids())
        assert len(owned) == len(set(owned))
        assert all(not window.context_src_ids for window in first)

    def test_sparse_src_preserved_and_not_renumbered(self, analysis_env):
        _sparse_env(analysis_env)
        clean_path = analysis_env.transcripts_dir / "clean" / "transcript_data.json"
        transcript = load_transcript_input(
            clean_path,
            project_name=analysis_env.project_name,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=analysis_env.sortie
            / analysis_env.project_name
            / "audit"
            / "cleanup_application.json",
            original_transcript_path=analysis_env.transcript_path,
        )
        windows = plan_windows_v2(
            transcript,
            target_input_tokens=80,
            hard_max_input_tokens=200,
            overhead=0,
            remeasure=False,
        )
        owned = [src for window in windows for src in window.owned_src_ids]
        assert "SRC000006" not in owned
        assert "SRC000001" in owned
        assert "SRC000008" not in owned
        assert owned == list(transcript.src_ids())


class TestCurrentPlannerPathology:
    def test_current_planner_still_creates_documented_tail(self, analysis_env):
        transcript = _load_source(analysis_env)
        pathology = current_planner_pathology(
            transcript,
            estimated_global_tokens=1000,
            budget_tokens=250,
            overlap_segments=1,
        )
        assert pathology["planner"] == "plan_windows"
        assert pathology["forced_minimum_parts"] == 2
        assert "stop-overlap" in pathology["cause"]


class TestSimulationAndContracts:
    def test_simulation_selects_production_policy(self, analysis_env, no_ai_network):
        transcript = _load_source(analysis_env)
        payload = simulate_planner_v2(transcript)
        assert payload["phase"] == PHASE
        assert payload["planner_version"] == PLANNER_VERSION
        selected = payload["selected_policy"]
        assert selected["target_input_tokens"] == TARGET_INPUT_TOKENS
        assert selected["hard_max_input_tokens"] == HARD_MAX_INPUT_TOKENS
        assert selected["overlap_policy"] == OVERLAP_POLICY
        assert selected["all_present_owned_exactly_once"] is True
        assert selected["sparse_ids_preserved"] is True
        assert selected["any_hard_max_violation"] is False
        for row in payload["results"]:
            assert row["all_present_owned_exactly_once"] is True
            assert row["owned_src_duplicates"] == []
            assert row["missing_src"] == []

    def test_simulation_deterministic(self, analysis_env, no_ai_network):
        transcript = _load_source(analysis_env)
        payload, sha1, sha2 = build_deterministic_simulation(transcript)
        assert sha1 == sha2
        assert payload["determinism"]["identical"] is True
        encoded = json.dumps(payload, ensure_ascii=False).lower()
        assert "updated_at" not in encoded
        assert payload["determinism"]["uuid"] is False


class TestCliAndPublication:
    def test_cli_writes_offline_artifacts_only(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = run_hybrid_design(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert result.outcome == "PASS"
        assert result.deterministic is True
        assert result.protected_unchanged is True
        assert result.architecture["strategy"] == STRATEGY
        assert result.window["window_analyzer"]["transport"] == WINDOW_TRANSPORT_VERSION
        assert result.window["window_analyzer"]["generation_c_reused"] is True
        assert result.window["window_analyzer"]["prompt_1_3_modified"] is False
        assert result.consolidation["required"] is True
        assert result.consolidation["input_contract"]["contains_full_transcript"] is False
        assert result.consolidation["transport"]["returns_canonical_sourcemap"] is False
        assert result.consolidation["transport"]["drop_records_v1"] is False
        assert result.architecture["publication"]["canonical_contract_unchanged"] is True
        assert result.architecture["future_execution"]["provider_calls_this_phase"] == 0
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        assert not source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        assert planner_simulation_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).is_file()
        assert window_design_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).is_file()
        assert consolidation_design_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).is_file()
        assert architecture_design_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).is_file()
        assert report_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).is_file()
        again = run_hybrid_design(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert again.simulation_sha256 == result.simulation_sha256
        assert again.architecture_sha256 == result.architecture_sha256

    def test_cli_does_not_mark_success(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = run_hybrid_design(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert result.project_state_status != "SUCCESS"
        assert result.project_state_status != "completed"

    def test_cli_rejects_real_call(self):
        assert hybrid_cli(["demo", "--real-call"]) == 2


class TestIntegrity:
    def test_generation_c_unchanged(self):
        hashes = generation_c_hashes()
        assert hashes["raw_matches_historical"] is True
        assert hashes["anthropic_matches_historical"] is True

    def test_prompt_version_unchanged(self):
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"


@pytest.mark.skipif(not REAL_CLEAN.is_file(), reason="real clean transcript absent")
class TestRealCleanPlannerV2:
    def test_selected_policy_covers_all_src_exactly_once(self, no_ai_network):
        from app.source_analysis_hybrid_design.simulation import load_clean_transcript

        transcript = load_clean_transcript(REAL_PROJECT)
        assert transcript.segment_count == 8298
        payload = simulate_planner_v2(transcript)
        selected = payload["selected_policy"]
        assert selected["expected_windows"] >= 2
        assert selected["all_present_owned_exactly_once"] is True
        assert selected["sparse_ids_preserved"] is True
        assert selected["any_hard_max_violation"] is False
        assert selected["owned_src_duplicates"] == [] if "owned_src_duplicates" in selected else True
        coverage = next(
            row["src_coverage"]
            for row in payload["results"]
            if row["target_input_tokens"] == TARGET_INPUT_TOKENS
        )
        assert coverage["present_src_count"] == 8298
        assert coverage["owned_src_duplicates"] == []
        assert coverage["missing_src_ids"] == []
        assert selected["overlap_policy"] == OVERLAP_POLICY
