"""
Phase 3B.6 — revue offline de stratégie d'exécution.

Aucun réseau. Aucun engine.generate() vers un fournisseur réel.
Aucun source_map de production. Aucun Attempt #3.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from app.source_analysis.context_strategy import plan_windows
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.transcript_input import (
    TranscriptInputMode,
    load_transcript_input,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_execution_strategy.architecture import (
    assert_offline_package,
    inspect_async_batch,
    inspect_plan_windows,
    inspect_streaming,
    package_calls_generate_or_post,
)
from app.source_analysis_execution_strategy.cli import main as strategy_cli
from app.source_analysis_execution_strategy.cli import run_strategy_review
from app.source_analysis_execution_strategy.constants import (
    CANDIDATE_WINDOW_INPUT_BUDGETS,
    EXTERNAL_PROVIDER_RESEARCH_REQUIRED,
    FORBIDDEN_TIMEOUT_ESCALATIONS,
    PHASE,
    PRIMARY_CLASSIFICATION,
    RECOMMENDED_STRATEGY,
    SECONDARY_CLASSIFICATIONS,
    THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED,
)
from app.source_analysis_execution_strategy.review import (
    build_deterministic_review,
    build_review_audit,
)
from app.source_analysis_execution_strategy.windows import (
    build_deterministic_simulation,
    detect_oversized_srcs,
    simulate_window_strategy,
)
from app.source_analysis_execution_strategy.writer import (
    report_path,
    review_path,
    simulation_path,
)
from app.source_analysis_global_clean.writer import production_source_map_path
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
        root = Path(__file__).resolve().parents[1] / "source_analysis_execution_strategy"
        forbidden = {"requests", "urllib", "httpx", "openai", "anthropic"}
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {alias.name.split(".")[0] for alias in node.names}
                    assert names.isdisjoint(forbidden), path.name
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module.split(".")[0] not in forbidden, path.name


class TestStreamingAndBatchAudit:
    def test_streaming_is_absent(self, no_ai_network):
        facts = inspect_streaming()
        assert facts["anthropic_engine_supports_streaming_now"] is False
        assert facts["stream_field_in_http_payload"] is False
        assert facts["semantic_structured_output_path_supports_streaming"] is False
        assert facts["partial_bytes_or_tokens_observable"] is False
        assert facts["native_json_schema_streaming_guarantees"] == (
            "EXTERNAL_VERIFICATION_REQUIRED"
        )
        assert facts["can_be_proven_offline"] is False

    def test_async_batch_not_implemented(self):
        facts = inspect_async_batch()
        assert facts["repository_support"] == "NOT_IMPLEMENTED"
        assert facts["anthropic_message_batches"] == "NOT_IMPLEMENTED"
        assert facts["local_semantic_batch_is_unrelated"] is True
        assert facts["current_anthropic_batch_capabilities"] == (
            "EXTERNAL_VERIFICATION_REQUIRED"
        )


class TestPlanWindowsAudit:
    def test_plan_windows_exists_and_is_deterministic(self, analysis_env):
        audit = inspect_plan_windows()
        assert audit["exists"] is True
        assert audit["determinism"] is True
        assert audit["sparse_src_supported"] is True
        assert audit["production_ready_for_execution"] is False
        assert audit["historical_multi_window_limitation_still_true"] is True
        transcript = _load_source(analysis_env)
        first = plan_windows(
            transcript, estimated_tokens=1000, budget_tokens=250, overlap_segments=0
        )
        second = plan_windows(
            transcript, estimated_tokens=1000, budget_tokens=250, overlap_segments=0
        )
        assert [window.to_dict() for window in first] == [
            window.to_dict() for window in second
        ]

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
        windows = plan_windows(
            transcript, estimated_tokens=800, budget_tokens=200, overlap_segments=0
        )
        seen = [segment.src_id for window in windows for segment in window.segments]
        assert "SRC000006" not in seen
        assert "SRC000001" in seen
        assert "SRC000008" not in seen
        assert len(seen) == len(set(seen))
        assert set(seen) == set(transcript.src_ids())


class TestWindowSimulation:
    def test_candidate_budgets_and_coverage(self, analysis_env, no_ai_network):
        transcript = _load_source(analysis_env)
        payload = simulate_window_strategy(transcript, overlap_segments=0)
        assert payload["candidate_budgets"] == list(CANDIDATE_WINDOW_INPUT_BUDGETS)
        present = set(transcript.src_ids())
        for row in payload["results"]:
            coverage = row["src_coverage"]
            assert coverage["all_present_covered"] is True
            assert coverage["sparse_ids_preserved"] is True
            assert coverage["present_src_count"] == len(present)
            assert coverage["union_src_count"] == len(present)
            assert coverage["missing_src_ids"] == []
            assert coverage["duplicate_src_ids_outside_documented_overlap"] == []
            assert row["window_count"] >= 2
            assert row["overlap_segments"] == 0

    def test_overlap_is_documented_not_semantic(self, analysis_env, no_ai_network):
        transcript = _load_source(analysis_env)
        payload = simulate_window_strategy(transcript, overlap_segments=1)
        for row in payload["results"]:
            assert row["semantic_overlap_added"] is False
            assert row["overlap_kind"] == "technical_src_overlap"
            assert row["src_coverage"]["all_present_covered"] is True

    def test_oversized_src_detection(self, analysis_env, no_ai_network):
        transcript = _load_source(analysis_env)
        detected = detect_oversized_srcs(transcript, budget_tokens=1)
        assert detected["any_src_exceeds_budget"] is True
        assert detected["count"] >= 1
        none = detect_oversized_srcs(transcript, budget_tokens=10_000_000)
        assert none["any_src_exceeds_budget"] is False
        assert none["count"] == 0

    def test_simulation_deterministic(self, analysis_env, no_ai_network):
        transcript = _load_source(analysis_env)
        payload, sha1, sha2 = build_deterministic_simulation(transcript)
        assert sha1 == sha2
        assert payload["determinism"]["identical"] is True
        encoded = json.dumps(payload, ensure_ascii=False).lower()
        assert payload["determinism"]["timestamps"] is False
        assert payload["determinism"]["uuid"] is False
        assert payload["determinism"]["randomness"] is False
        assert "updated_at" not in encoded


class TestClassificationAndDecision:
    def test_review_classifies_and_forbids_third_timeout(self, analysis_env, no_ai_network):
        transcript = _load_source(analysis_env)
        simulation = simulate_window_strategy(transcript)
        review = build_review_audit(simulation=simulation)
        assert review["phase"] == PHASE
        assert review["current_problem"]["primary_classification"] == (
            PRIMARY_CLASSIFICATION
        )
        assert review["current_problem"]["secondary_classifications"] == list(
            SECONDARY_CLASSIFICATIONS
        )
        assert review["current_problem"]["third_global_timeout_retry"] == "PROHIBITED"
        assert THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED is False
        assert review["current_problem"]["context_capacity_is_the_blocker"] is False
        assert review["global_context"]["fits"] is True
        assert review["recommended_strategy"] == RECOMMENDED_STRATEGY
        assert review["external_provider_research_required"] is (
            EXTERNAL_PROVIDER_RESEARCH_REQUIRED
        )
        assert review["options"]["global_sync"]["disposition"] == (
            "NOT_RECOMMENDED_AS_NEXT_EXECUTION_STRATEGY"
        )
        for value in FORBIDDEN_TIMEOUT_ESCALATIONS:
            assert value in review["options"]["global_sync"]["forbidden_candidates"]
        assert review["execution"]["provider_calls"] == 0
        assert review["execution"]["source_map_published"] is False
        assert review["execution"]["attempt_3_executed"] is False
        assert review["network"]["anthropic"] == 0
        assert review["consolidation"]["topics"]["exact_string_dedupe_sufficient"] is False
        assert (
            review["consolidation"]["source_refs"]["never_renumber_transcript_srcs"]
            is True
        )

    def test_review_deterministic(self, analysis_env, no_ai_network):
        transcript = _load_source(analysis_env)
        simulation = simulate_window_strategy(transcript)
        payload, sha1, sha2 = build_deterministic_review(simulation)
        assert sha1 == sha2
        assert payload["determinism"]["identical"] is True


class TestNoPublicationAndState:
    def test_cli_writes_offline_artifacts_only(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = run_strategy_review(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert result.outcome == "PASS"
        assert result.deterministic is True
        assert result.protected_unchanged is True
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        assert not source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        assert simulation_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).is_file()
        assert review_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).is_file()
        assert report_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).is_file()
        loaded = json.loads(
            review_path(
                analysis_env.project_name, sortie_dir=analysis_env.sortie
            ).read_text(encoding="utf-8")
        )
        assert loaded["network"]["anthropic"] == 0
        assert loaded["execution"]["provider_calls"] == 0
        assert loaded["recommended_strategy"] == RECOMMENDED_STRATEGY
        again = run_strategy_review(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert again.review_sha256 == result.review_sha256
        assert again.simulation_sha256 == result.simulation_sha256

    def test_cli_does_not_mark_success(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = run_strategy_review(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert result.project_state_status != "SUCCESS"
        assert result.project_state_status != "completed"

    def test_cli_rejects_real_call(self):
        assert strategy_cli(["demo", "--real-call"]) == 2


class TestIntegrity:
    def test_generation_c_unchanged(self):
        hashes = generation_c_hashes()
        assert hashes["raw_matches_historical"] is True
        assert hashes["anthropic_matches_historical"] is True

    def test_prompt_version_unchanged(self):
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"

    def test_cost_unknown_output_is_not_zero(self, analysis_env, no_ai_network):
        transcript = _load_source(analysis_env)
        simulation = simulate_window_strategy(transcript)
        review = build_review_audit(simulation=simulation)
        pricing = review["cost"]["pricing"]
        assert pricing["unknown_must_not_become_zero"] is True
        assert pricing["long_context_regime_modeled"] is False
        assert review["cost"]["global_sync_or_streaming_or_batch"]["output_cost"] is None
        assert review["cost"]["global_sync_or_streaming_or_batch"]["total_cost"] is None


@pytest.mark.skipif(not REAL_CLEAN.is_file(), reason="real clean transcript absent")
class TestRealCleanCoverage:
    def test_real_transcript_full_src_coverage(self, no_ai_network):
        from app.source_analysis_execution_strategy.windows import load_clean_transcript

        transcript = load_clean_transcript(REAL_PROJECT)
        assert transcript.segment_count == 8298
        present = set(transcript.src_ids())
        payload = simulate_window_strategy(transcript, overlap_segments=1)
        assert payload["global_estimate"]["estimated_input_tokens"] > 0
        for row in payload["results"]:
            coverage = row["src_coverage"]
            assert coverage["all_present_covered"] is True
            assert coverage["missing_src_ids"] == []
            assert coverage["extra_src_ids"] == []
            assert coverage["sparse_ids_preserved"] is True
            assert coverage["present_src_count"] == len(present)
            assert row["oversized_src"]["any_src_exceeds_budget"] is False
