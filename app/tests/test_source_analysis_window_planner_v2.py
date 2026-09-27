"""
Phase 3B.7.1 — WindowPlannerV2 & hybrid contracts.

Aucun réseau. Aucun engine.generate() vers un fournisseur réel.
Aucun source_map de production. Aucun Attempt #3.
"""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import pytest

from app.source_analysis.context_strategy import plan_windows
from app.source_analysis.errors import (
    SourceAnalysisEmptyTranscript,
    SourceAnalysisWindowPlanError,
    SourceAnalysisWindowPlannerConfigError,
    SourceAnalysisWindowTooLarge,
)
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.transcript_input import (
    SourceSegment,
    TranscriptInput,
    TranscriptInputMode,
    load_transcript_input,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_global_clean.writer import production_source_map_path
from app.source_analysis_hybrid.cli import main as hybrid_cli
from app.source_analysis_hybrid.runner import run_window_planner_implementation
from app.source_analysis_hybrid.config import WindowPlannerConfig
from app.source_analysis_hybrid.constants import (
    HARD_MAX_INPUT_TOKENS,
    OVERLAP_POLICY,
    PHASE,
    PLANNER_VERSION,
    TARGET_INPUT_TOKENS,
    WINDOW_PROMPT_VERSION,
)
from app.source_analysis_hybrid.contracts import (
    ConsolidationContractSkeleton,
    WindowAnalysisPromptContract,
    WindowInputSignature,
    assert_allowed_consolidation_operation,
    format_intermediate_record_id,
    format_window_id,
)
from app.source_analysis_hybrid.materialize import materialize_window_content
from app.source_analysis_hybrid.offline import (
    analyzer_wires_window_planner,
    assert_analyzer_not_wired,
    assert_offline_package,
    package_calls_generate_or_post,
    package_imports_network_clients,
)
from app.source_analysis_hybrid.planner import (
    apply_tiny_tail,
    balanced_cuts,
    plan_windows_v2,
)
from app.source_analysis_hybrid.writer import (
    implementation_artifact_path,
    report_path,
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


def _make_transcript(
    texts: tuple[str, ...],
    *,
    src_ids: tuple[str, ...] | None = None,
    transcript_id: str = "TR001",
    language: str = "en",
) -> TranscriptInput:
    segments: list[SourceSegment] = []
    for index, text in enumerate(texts):
        src_id = src_ids[index] if src_ids is not None else f"SRC{index + 1:06d}"
        segments.append(
            SourceSegment(
                src_id=src_id,
                source_id="AUD001",
                start=float(index),
                end=float(index + 1),
                text=text,
                source_order=index + 1,
            )
        )
    return TranscriptInput(
        project_name="fixture",
        transcript_id=transcript_id,
        primary_language=language,
        detected_languages=(language,),
        segments=tuple(segments),
        path=Path("fixture.json"),
        content_sha256="a" * 64,
        schema_version="1.0",
        duration_seconds=float(len(segments)),
        mode=TranscriptInputMode.SOURCE,
    )


def _plan(
    transcript: TranscriptInput,
    *,
    weights: tuple[int, ...],
    target: int = 100,
    hard_max: int = 200,
    overhead: int = 0,
    remeasure: bool = False,
):
    config = WindowPlannerConfig(
        target_input_tokens=target,
        hard_max_input_tokens=hard_max,
    )
    return plan_windows_v2(
        transcript,
        config=config,
        content_weights=weights,
        overhead=overhead,
        remeasure=remeasure,
    )


def _naive_greedy_cuts(weights: tuple[int, ...], target: int) -> list[int]:
    cuts = [0]
    acc = 0
    for index, weight in enumerate(weights):
        if acc and acc + weight > target:
            cuts.append(index)
            acc = weight
        else:
            acc += weight
    cuts.append(len(weights))
    return cuts


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


def _replace_text(transcript: TranscriptInput, src_id: str, text: str) -> TranscriptInput:
    segments = []
    for segment in transcript.segments:
        if segment.src_id == src_id:
            segment = SourceSegment(
                src_id=segment.src_id,
                source_id=segment.source_id,
                start=segment.start,
                end=segment.end,
                text=text,
                source_order=segment.source_order,
            )
        segments.append(segment)
    return TranscriptInput(
        project_name=transcript.project_name,
        transcript_id=transcript.transcript_id,
        primary_language=transcript.primary_language,
        detected_languages=transcript.detected_languages,
        segments=tuple(segments),
        path=transcript.path,
        content_sha256=transcript.content_sha256,
        schema_version=transcript.schema_version,
        duration_seconds=transcript.duration_seconds,
        mode=transcript.mode,
    )


class TestOfflinePackage:
    def test_package_has_no_generate_or_post(self):
        assert package_calls_generate_or_post() == []
        assert package_imports_network_clients() == []
        assert_offline_package()

    def test_analyzer_not_wired(self):
        assert analyzer_wires_window_planner() == []
        assert_analyzer_not_wired()

    def test_modules_do_not_import_network_clients(self):
        root = Path(__file__).resolve().parents[1] / "source_analysis_hybrid"
        forbidden = {"requests", "urllib", "httpx", "openai", "anthropic"}
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {alias.name.split(".")[0] for alias in node.names}
                    assert names.isdisjoint(forbidden), path.name
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module.split(".")[0] not in forbidden, path.name


class TestConfigValidation:
    def test_defaults_are_approved_policy(self):
        config = WindowPlannerConfig()
        assert config.version == PLANNER_VERSION == "window-planner-v2.0"
        assert config.target_input_tokens == TARGET_INPUT_TOKENS == 50000
        assert config.hard_max_input_tokens == HARD_MAX_INPUT_TOKENS == 60000
        assert config.overlap_policy == OVERLAP_POLICY == "NO_OWNED_OVERLAP"

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"target_input_tokens": 0},
            {"target_input_tokens": -1},
            {"hard_max_input_tokens": 0},
            {"hard_max_input_tokens": -5},
            {"target_input_tokens": 60001, "hard_max_input_tokens": 60000},
            {"target_input_tokens": True},
            {"hard_max_input_tokens": False},
            {"target_input_tokens": float("nan")},
            {"hard_max_input_tokens": float("inf")},
            {"target_input_tokens": 50000.0},
            {"target_input_tokens": "50000"},
            {"overlap_policy": "OWNED_OVERLAP"},
            {"overlap_policy": ""},
            {"version": ""},
            {"version": "   "},
            {"version": None},
        ],
    )
    def test_invalid_config_rejected(self, kwargs):
        with pytest.raises(SourceAnalysisWindowPlannerConfigError):
            WindowPlannerConfig(**kwargs)

    def test_nan_and_inf_explicit(self):
        assert math.isnan(float("nan"))
        with pytest.raises(SourceAnalysisWindowPlannerConfigError):
            WindowPlannerConfig(target_input_tokens=float("nan"))
        with pytest.raises(SourceAnalysisWindowPlannerConfigError):
            WindowPlannerConfig(hard_max_input_tokens=float("-inf"))


class TestPlannerFixtures:
    def test_empty_transcript_fails(self):
        transcript = _make_transcript(())
        with pytest.raises(SourceAnalysisEmptyTranscript):
            _plan(transcript, weights=())

    def test_single_src_one_window(self):
        transcript = _make_transcript(("hello world",))
        plan = _plan(transcript, weights=(20,), target=50, hard_max=200)
        assert plan.window_count == 1
        assert plan.windows[0].window_id == "WIN001"
        assert plan.windows[0].owned_src_refs == ("SRC000001",)

    def test_small_transcript_does_not_force_two_windows(self):
        transcript = _make_transcript(("a", "b", "c"))
        plan = _plan(transcript, weights=(10, 10, 10), target=100, hard_max=200)
        assert plan.window_count == 1

    def test_exact_target_is_one_window(self):
        transcript = _make_transcript(("a", "b"))
        plan = _plan(transcript, weights=(40, 60), target=100, hard_max=200)
        assert plan.window_count == 1
        assert plan.windows[0].estimated_input_tokens == 100

    def test_between_target_and_hard_max_may_be_single_window(self):
        transcript = _make_transcript(("long",))
        plan = _plan(transcript, weights=(120,), target=100, hard_max=200)
        assert plan.window_count == 1
        assert plan.windows[0].estimated_input_tokens == 120
        assert plan.windows[0].estimated_input_tokens <= 200

    def test_above_hard_max_partitions(self):
        transcript = _make_transcript(("a", "b", "c"))
        plan = _plan(transcript, weights=(80, 80, 80), target=100, hard_max=150)
        assert plan.window_count == 3
        assert all(window.estimated_input_tokens <= 150 for window in plan.windows)

    def test_exact_hard_max_is_valid(self):
        transcript = _make_transcript(("edge",))
        plan = _plan(transcript, weights=(200,), target=100, hard_max=200)
        assert plan.window_count == 1
        assert plan.windows[0].estimated_input_tokens == 200

    def test_oversized_src_fails_without_split(self):
        transcript = _make_transcript(("huge",))
        with pytest.raises(SourceAnalysisWindowTooLarge) as caught:
            _plan(transcript, weights=(201,), target=100, hard_max=200)
        assert caught.value.src_id == "SRC000001"
        assert caught.value.estimated_tokens == 201
        assert caught.value.hard_max_input_tokens == 200

    def test_sparse_ids_are_not_invented(self):
        transcript = _make_transcript(
            ("one", "three", "ten"),
            src_ids=("SRC000001", "SRC000003", "SRC000010"),
        )
        plan = _plan(transcript, weights=(10, 10, 10), target=100, hard_max=200)
        owned = [src for window in plan.windows for src in window.owned_src_refs]
        assert owned == ["SRC000001", "SRC000003", "SRC000010"]
        assert "SRC000002" not in owned
        assert plan.windows[0].first_owned_src_ref == "SRC000001"
        assert plan.windows[0].last_owned_src_ref == "SRC000010"

    def test_natural_order_is_authoritative_not_lexical(self):
        transcript = _make_transcript(
            ("later-id-first", "earlier-id-second"),
            src_ids=("SRC000010", "SRC000002"),
        )
        plan = _plan(transcript, weights=(10, 10), target=100, hard_max=200)
        owned = [src for window in plan.windows for src in window.owned_src_refs]
        assert owned == ["SRC000010", "SRC000002"]
        assert owned != sorted(owned)

    def test_duplicate_src_fails_without_dedupe(self):
        transcript = _make_transcript(
            ("a", "b"), src_ids=("SRC000001", "SRC000001")
        )
        with pytest.raises(SourceAnalysisWindowPlanError, match="unicité"):
            _plan(transcript, weights=(10, 10))

    def test_tiny_tail_fixture_rebalances(self):
        weights = (100, 100, 100, 5)
        greedy = _naive_greedy_cuts(weights, 100)
        assert greedy[-1] - greedy[-2] == 1
        transcript = _make_transcript(tuple(f"s{i}" for i in range(4)))
        plan = _plan(transcript, weights=weights, target=100, hard_max=200)
        last = plan.windows[-1]
        assert last.owned_src_count > 1
        assert last.estimated_input_tokens >= 15
        assert last.estimated_input_tokens <= 200
        owned = [src for window in plan.windows for src in window.owned_src_refs]
        assert owned == list(transcript.src_ids())

    def test_tiny_tail_merge_helper(self):
        merged = apply_tiny_tail(
            [0, 2, 3, 4], (40, 40, 40, 1), min_content=10, hard_content=100
        )
        assert merged[-1] == 4
        assert len(merged) == 3

    def test_multi_window_generalizes(self):
        texts = tuple(f"seg{i}" for i in range(12))
        weights = tuple([30] * 12)
        transcript = _make_transcript(texts)
        plan = _plan(transcript, weights=weights, target=80, hard_max=200)
        assert plan.window_count >= 4
        owned = [src for window in plan.windows for src in window.owned_src_refs]
        assert owned == list(transcript.src_ids())
        assert all(window.estimated_input_tokens <= 200 for window in plan.windows)
        assert all(not window.context_src_refs for window in plan.windows)
        ids = [window.window_id for window in plan.windows]
        assert ids == [format_window_id(i) for i in range(1, len(ids) + 1)]

    def test_balanced_cuts_complete_and_left_tiebreak(self):
        cuts = balanced_cuts((10, 10, 10, 10, 10, 10), 3)
        assert cuts[0] == 0
        assert cuts[-1] == 6
        assert all(later > earlier for earlier, later in zip(cuts, cuts[1:]))

    def test_coverage_order_and_context_empty(self):
        transcript = _make_transcript(tuple(f"s{i}" for i in range(6)))
        plan = _plan(transcript, weights=(20, 20, 20, 20, 20, 20), target=50, hard_max=200)
        owned = [src for window in plan.windows for src in window.owned_src_refs]
        assert owned == list(transcript.src_ids())
        assert plan.context_src_count == 0
        assert plan.strategy == "hybrid"

    def test_determinism_and_serialization(self):
        transcript = _make_transcript(("a", "b", "c", "d"))
        first = _plan(transcript, weights=(25, 25, 25, 25), target=50, hard_max=200)
        second = _plan(transcript, weights=(25, 25, 25, 25), target=50, hard_max=200)
        assert first.plan_sha256() == second.plan_sha256()
        assert first.canonical_text() == second.canonical_text()
        encoded = first.canonical_text().lower()
        assert "generated_at" not in encoded
        assert "updated_at" not in encoded
        assert "uuid" not in encoded
        assert [window.input_hash for window in first.windows] == [
            window.input_hash for window in second.windows
        ]

    def test_source_text_mutation_changes_relevant_hash(self):
        transcript = _make_transcript(("alpha", "beta", "gamma", "delta"))
        weights = (20, 20, 20, 20)
        original = _plan(transcript, weights=weights, target=50, hard_max=200)
        mutated = _replace_text(transcript, "SRC000001", "ALPHA-CHANGED")
        changed = _plan(mutated, weights=weights, target=50, hard_max=200)
        assert original.windows[0].owned_src_refs == changed.windows[0].owned_src_refs
        assert (
            original.windows[0].owned_content_sha256
            != changed.windows[0].owned_content_sha256
        )
        assert original.windows[0].input_hash != changed.windows[0].input_hash
        unaffected = [
            (left.input_hash, right.input_hash)
            for left, right in zip(original.windows[1:], changed.windows[1:])
            if left.owned_src_refs == right.owned_src_refs
            and "SRC000001" not in left.owned_src_refs
        ]
        assert unaffected
        assert all(left == right for left, right in unaffected)

    def test_window_input_signature_is_not_window_id(self):
        transcript = _make_transcript(("a", "b"))
        plan = _plan(transcript, weights=(10, 10), target=100, hard_max=200)
        window = plan.windows[0]
        signature = window.input_signature(clean_transcript_sha256="b" * 64)
        assert isinstance(signature, WindowInputSignature)
        assert signature.window_id == "WIN001"
        assert signature.digest() != "WIN001"
        assert signature.window_input_hash == window.input_hash

    def test_materialization_distinguishes_owned(self):
        transcript = _make_transcript(("one", "two"))
        plan = _plan(transcript, weights=(10, 10), target=100, hard_max=200)
        content = materialize_window_content(transcript, plan.windows[0])
        assert [item.ownership for item in content.owned] == ["OWNED", "OWNED"]
        assert content.context == ()
        assert [item.src_id for item in content.owned] == ["SRC000001", "SRC000002"]


class TestContracts:
    def test_window_prompt_contract_is_not_prompt_1_3(self):
        contract = WindowAnalysisPromptContract()
        assert contract.version == WINDOW_PROMPT_VERSION == "window-analysis-1.0"
        assert contract.distinct_from_prompt_1_3 is True
        assert contract.implemented is False

    def test_intermediate_record_id(self):
        assert format_intermediate_record_id("WIN001", 1) == "WIN001:R0001"
        assert format_intermediate_record_id("WIN012", 42) == "WIN012:R0042"

    def test_drop_record_forbidden(self):
        skeleton = ConsolidationContractSkeleton()
        assert skeleton.drop_records_v1 is False
        assert "DROP_RECORD" not in skeleton.operations
        with pytest.raises(SourceAnalysisWindowPlanError, match="interdite"):
            assert_allowed_consolidation_operation("DROP_RECORD")
        assert assert_allowed_consolidation_operation("KEEP_RECORD") == "KEEP_RECORD"


class TestDerivedProvenance:
    def test_planner_accepts_derived_clean(self, analysis_env):
        clean_path, provenance = _sparse_env(analysis_env)
        transcript = load_transcript_input(
            clean_path,
            project_name=analysis_env.project_name,
            mode=TranscriptInputMode.DERIVED,
            provenance_path=provenance,
            original_transcript_path=analysis_env.transcript_path,
        )
        plan = plan_windows_v2(
            transcript,
            config=WindowPlannerConfig(
                target_input_tokens=80,
                hard_max_input_tokens=200,
            ),
            overhead=0,
            remeasure=False,
        )
        owned = [src for window in plan.windows for src in window.owned_src_refs]
        assert owned == list(transcript.src_ids())
        assert "SRC000006" not in owned
        assert "SRC000008" not in owned


class TestHistoricalCoexistence:
    def test_old_plan_windows_still_present_and_forces_min_two(self):
        transcript = _make_transcript(("a", "b", "c"))
        windows = plan_windows(
            transcript,
            estimated_tokens=10,
            budget_tokens=1000,
            overlap_segments=1,
        )
        assert len(windows) >= 2

    def test_prompt_1_3_unchanged(self):
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"

    def test_generation_c_unchanged(self):
        hashes = generation_c_hashes()
        assert hashes["raw_matches_historical"] is True
        assert hashes["anthropic_matches_historical"] is True


class TestCliAndPublication:
    def test_cli_writes_audit_only(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = run_window_planner_implementation(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert result.outcome in {"PASS", "PARTIAL"}
        assert result.deterministic is True
        assert result.protected_unchanged is True
        assert result.artifact["phase"] == PHASE
        assert result.artifact["planner"]["version"] == PLANNER_VERSION
        assert result.artifact["execution"]["provider_calls"] == 0
        assert not production_source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        assert not source_map_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).exists()
        assert implementation_artifact_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).is_file()
        assert report_path(
            analysis_env.project_name, sortie_dir=analysis_env.sortie
        ).is_file()
        encoded = json.dumps(result.artifact, ensure_ascii=False).lower()
        assert "generated_at" not in encoded
        again = run_window_planner_implementation(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert again.plan_sha256 == result.plan_sha256

    def test_cli_does_not_mark_success(self, analysis_env, no_ai_network):
        _sparse_env(analysis_env)
        result = run_window_planner_implementation(
            analysis_env.project_name,
            sortie_dir=analysis_env.sortie,
        )
        assert result.project_state_status != "SUCCESS"
        assert result.project_state_status != "completed"

    def test_cli_rejects_real_call(self):
        assert hybrid_cli(["demo", "--real-call"]) == 2


@pytest.mark.skipif(not REAL_CLEAN.is_file(), reason="real clean transcript absent")
class TestRealCleanPlannerV2:
    def test_real_corpus_plan(self, no_ai_network):
        from app.source_analysis_execution_strategy.windows import load_clean_transcript

        transcript = load_clean_transcript(REAL_PROJECT)
        assert transcript.transcript_id == "TR001"
        assert transcript.mode is TranscriptInputMode.DERIVED
        plan = plan_windows_v2(transcript)
        owned = [src for window in plan.windows for src in window.owned_src_refs]
        assert owned == list(transcript.src_ids())
        assert len(owned) == transcript.segment_count
        assert plan.context_src_count == 0
        assert plan.estimated_input_tokens_max <= HARD_MAX_INPUT_TOKENS
        assert all(
            window.estimated_input_tokens <= HARD_MAX_INPUT_TOKENS
            for window in plan.windows
        )
        again = plan_windows_v2(transcript)
        assert again.plan_sha256() == plan.plan_sha256()
        assert plan.window_count >= 1
        assert not source_map_path(REAL_PROJECT).exists()
