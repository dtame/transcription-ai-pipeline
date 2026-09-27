"""
Phase 3B.7.5 — Hybrid canonical reconstruction + end-to-end FakeAI.

Aucun réseau. Aucun engine.generate() vers un fournisseur réel.
Aucun source_map de production. Phase 3B reste INCOMPLETE.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ai.errors import AITimeoutError
from app.ai.providers.fake import FakeAIEngine
from app.ai.retry import no_delay_policy
from app.ai.settings import resolve_stage_settings
from app.source_analysis.canonical_vocabulary import (
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
)
from app.source_analysis.consolidation_decoder import decode_consolidation_transport
from app.source_analysis.consolidation_fixtures import (
    default_provider_metadata,
    make_window_result,
)
from app.source_analysis.consolidation_input import build_consolidation_input_from_plan
from app.source_analysis.consolidation_models import STAGE_CONSOLIDATION
from app.source_analysis.consolidation_validator import validate_consolidation_result
from app.source_analysis.errors import (
    HybridPreconditionError,
    HybridReconstructionError,
)
from app.source_analysis.hybrid_e2e_fixtures import (
    CONSOLIDATION_AUDIENCE,
    CONSOLIDATION_INTENT,
    CONSOLIDATION_THEME,
    CONSOLIDATION_VOICE,
    MERGED_IDEA_VALUE,
    MERGED_TOPIC_VALUE,
    e2e_engine,
    intermediate,
    make_e2e_transcript,
    plan_e2e_windows,
    sparse_transcript,
    test_planner_config as make_test_planner_config,
    two_window_sparse_plan,
)
from app.source_analysis.hybrid_reconstructor import (
    HybridCanonicalReconstructor,
    reconstruct_source_map,
    reconstruction_allowed,
    union_source_refs_in_source_order,
)
from app.source_analysis.hybrid_service import (
    assert_fake_engine,
    preflight_hybrid_reconstruction,
    run_hybrid_source_analysis,
)
from app.source_analysis.hybrid_signature import HYBRID_STRATEGY
from app.source_analysis.models import SOURCE_MAP_SCHEMA_VERSION
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.validator import validate_source_map
from app.source_analysis.window_fixtures import window_for, window_plan_from_inputs
from app.source_analysis.window_models import STAGE_WINDOW
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis.writer import render_source_map, source_map_path
from app.source_analysis_hybrid.config import WindowPlannerConfig
from app.source_analysis_hybrid.constants import (
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_TRANSPORT_VERSION,
    HARD_MAX_INPUT_TOKENS,
    OVERLAP_POLICY,
    PLANNER_VERSION,
    TARGET_INPUT_TOKENS,
    WINDOW_TRANSPORT_VERSION,
)
from app.source_analysis_hybrid.offline import (
    assert_analyzer_not_wired as assert_hybrid_planner_not_wired,
)
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_hybrid_reconstruction.cli import main as hybrid_cli
from app.source_analysis_hybrid_reconstruction.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_hybrid_reconstruction.runner import (
    run_hybrid_reconstruction_pipeline,
    run_real_preflight,
)
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis_window_orchestration.offline import (
    assert_analyzer_not_wired as assert_window_orch_not_wired,
)
from app.source_analysis_window_pipeline.offline import (
    assert_analyzer_not_wired as assert_window_not_wired,
)
from app.source_analysis_consolidation.offline import (
    assert_analyzer_not_wired as assert_consolidation_not_wired,
)

REAL_PROJECT = "pastoral_retreat_v2_validation"
REAL_CLEAN = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
    r"\transcripts\clean\transcript_data.json"
)


def _reconstruct(transcript, plan, results, transport):
    built = build_consolidation_input_from_plan(plan, results)
    decoded = decode_consolidation_transport(
        transport,
        built,
        signature="e" * 64,
        provider_metadata=default_provider_metadata(),
    )
    validate_consolidation_result(decoded, built)
    return reconstruct_source_map(
        transcript,
        plan,
        results,
        decoded,
        consolidation_input=built,
    )


def _gm(theme_ev, intent_ev, audience_ev, voice_ev):
    return {
        "th": "Theme from consolidation",
        "in": "Intent from consolidation",
        "au": "Audience from consolidation",
        "vo": "Voice from consolidation",
        "te": theme_ev,
        "ie": intent_ev,
        "ae": audience_ev,
        "ve": voice_ev,
    }


def _two_window_keep_setup():
    transcript = make_e2e_transcript(
        texts=("Alpha source one.", "Beta source two."),
        src_ids=("SRC000001", "SRC000002"),
        transcript_id="TR-UNIT",
        content_sha256="1" * 64,
    )
    windows = (
        window_for(transcript, owned=("SRC000001",), window_id="WIN001"),
        window_for(transcript, owned=("SRC000002",), window_id="WIN002"),
    )
    plan = window_plan_from_inputs(transcript, windows)
    results = (
        make_window_result(
            windows[0],
            (
                intermediate(
                    "WIN001:R0001",
                    "TOPIC",
                    "Alpha topic",
                    ("SRC000001",),
                    metadata=("Alpha summary.",),
                ),
                intermediate(
                    "WIN001:R0002",
                    "IDEA",
                    "Alpha idea unique",
                    ("SRC000001",),
                    index=1,
                    link_ids=("WIN001:R0001",),
                    metadata=("claim", "central"),
                ),
                intermediate(
                    "WIN001:R0003",
                    "IDEA",
                    "The night is long but not empty.",
                    ("SRC000001",),
                    index=2,
                    link_ids=("WIN001:R0001",),
                    metadata=("observation", "minor"),
                ),
                intermediate("WIN001:R0004", "INTENT_KIND", "enseigner", (), index=3),
                intermediate("WIN001:R0005", "AUDIENCE_KIND", "croyants", (), index=4),
                intermediate(
                    "WIN001:R0006",
                    "VOICE",
                    "didactic",
                    (),
                    index=5,
                    metadata=("tone",),
                ),
            ),
            signature="1" * 64,
        ),
        make_window_result(
            windows[1],
            (
                intermediate(
                    "WIN002:R0001",
                    "TOPIC",
                    "Beta topic",
                    ("SRC000002",),
                    metadata=("Beta summary.",),
                ),
                intermediate(
                    "WIN002:R0002",
                    "IDEA",
                    "Beta idea unique",
                    ("SRC000002",),
                    index=1,
                    link_ids=("WIN002:R0001",),
                    metadata=("explanation", "supporting"),
                ),
                intermediate(
                    "WIN002:R0003",
                    "IDEA",
                    "The night remains long yet inhabited.",
                    ("SRC000002",),
                    index=2,
                    link_ids=("WIN002:R0001",),
                    metadata=("observation", "minor"),
                ),
                intermediate("WIN002:R0004", "INTENT_KIND", "encourager", (), index=3),
                intermediate("WIN002:R0005", "AUDIENCE_KIND", "pasteurs", (), index=4),
                intermediate(
                    "WIN002:R0006",
                    "VOICE",
                    "oral",
                    (),
                    index=5,
                    metadata=("register",),
                ),
            ),
            signature="2" * 64,
            theme="Window two disagrees",
            intent="Window two intent disagrees",
            audience="Window two audience disagrees",
        ),
    )
    return transcript, plan, results


class TestPreconditions:
    def test_all_windows_ready_required(self):
        transcript, plan, results = _two_window_keep_setup()
        with pytest.raises(HybridPreconditionError):
            reconstruct_source_map(
                transcript,
                plan,
                results[:1],
                default_provider_metadata(),  # type: ignore[arg-type]
            )

    def test_reconstruction_allowed_false_when_not_ready(self):
        assert reconstruction_allowed(
            all_windows_ready=False, consolidation_available=False
        ) is False

    def test_wrong_transcript(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        other = make_e2e_transcript(transcript_id="TR-OTHER", content_sha256="2" * 64)
        with pytest.raises(HybridPreconditionError):
            reconstruct_source_map(
                other,
                plan,
                run.orchestration.get_ready_results_in_plan_order(),
                run.consolidation_result,
            )

    def test_wrong_plan(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        other_plan = window_plan_from_inputs(
            transcript,
            (
                window_for(
                    transcript,
                    owned=plan.windows[0].owned_src_refs[:2],
                    window_id="WIN001",
                ),
                plan.windows[1],
                plan.windows[2],
            ),
        )
        with pytest.raises((HybridPreconditionError, HybridReconstructionError)):
            reconstruct_source_map(
                transcript,
                other_plan,
                run.orchestration.get_ready_results_in_plan_order(),
                run.consolidation_result,
            )

    def test_stale_consolidation(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        results = run.orchestration.get_ready_results_in_plan_order()
        stale = make_window_result(
            plan.windows[0],
            results[0].records[:-1],
            signature=results[0].window_analysis_signature,
            theme=results[0].candidates.theme,
            intent=results[0].candidates.intent,
            audience=results[0].candidates.audience,
        )
        with pytest.raises(HybridPreconditionError):
            reconstruct_source_map(
                transcript,
                plan,
                (stale, results[1], results[2]),
                run.consolidation_result,
            )


class TestKeepMerge:
    def test_keep_preserves_semantic_content_and_src(self):
        transcript, plan, results = _two_window_keep_setup()
        transport = {
            "gm": _gm(
                ["WIN001:R0001"],
                ["WIN001:R0004"],
                ["WIN001:R0005"],
                ["WIN001:R0006", "WIN002:R0006"],
            ),
            "ops": [
                {"o": "KEEP", "r": "WIN001:R0001"},
                {"o": "KEEP", "r": "WIN001:R0002"},
                {"o": "KEEP", "r": "WIN001:R0003"},
                {"o": "KEEP", "r": "WIN002:R0001"},
                {"o": "KEEP", "r": "WIN002:R0002"},
                {"o": "KEEP", "r": "WIN002:R0003"},
                {"o": "KEEP", "r": "WIN002:R0004"},
                {"o": "KEEP", "r": "WIN002:R0005"},
            ],
        }
        source_map = _reconstruct(transcript, plan, results, transport)
        labels = [topic.label for topic in source_map.topics]
        assert "Alpha topic" in labels
        assert "Beta topic" in labels
        alpha = next(topic for topic in source_map.topics if topic.label == "Alpha topic")
        assert alpha.source_refs == ("SRC000001",)
        assert alpha.summary == "Alpha summary."

    def test_explicit_merge_one_record_union_src(self):
        transcript, plan, results = _two_window_keep_setup()
        transport = {
            "gm": _gm(
                ["WIN001:R0001"],
                ["WIN001:R0004"],
                ["WIN001:R0005"],
                ["WIN001:R0006", "WIN002:R0006"],
            ),
            "ops": [
                {
                    "o": "MERGE",
                    "m": ["WIN001:R0001", "WIN002:R0001"],
                    "v": "Merged topic text",
                },
                {"o": "KEEP", "r": "WIN001:R0002"},
                {"o": "KEEP", "r": "WIN001:R0003"},
                {"o": "KEEP", "r": "WIN002:R0002"},
                {"o": "KEEP", "r": "WIN002:R0003"},
                {"o": "KEEP", "r": "WIN002:R0004"},
                {"o": "KEEP", "r": "WIN002:R0005"},
            ],
        }
        source_map = _reconstruct(transcript, plan, results, transport)
        assert len(source_map.topics) == 1
        assert source_map.topics[0].label == "Merged topic text"
        assert source_map.topics[0].source_refs == ("SRC000001", "SRC000002")

    def test_no_local_semantic_dedupe(self):
        transcript, plan, results = _two_window_keep_setup()
        transport = {
            "gm": _gm(
                ["WIN001:R0001"],
                ["WIN001:R0004"],
                ["WIN001:R0005"],
                ["WIN001:R0006", "WIN002:R0006"],
            ),
            "ops": [
                {"o": "KEEP", "r": "WIN001:R0001"},
                {"o": "KEEP", "r": "WIN001:R0002"},
                {"o": "KEEP", "r": "WIN001:R0003"},
                {"o": "KEEP", "r": "WIN002:R0001"},
                {"o": "KEEP", "r": "WIN002:R0002"},
                {"o": "KEEP", "r": "WIN002:R0003"},
                {"o": "KEEP", "r": "WIN002:R0004"},
                {"o": "KEEP", "r": "WIN002:R0005"},
            ],
        }
        source_map = _reconstruct(transcript, plan, results, transport)
        nights = [idea.summary for idea in source_map.ideas if "night" in idea.summary]
        assert len(nights) == 2


class TestSourceUnion:
    def test_sparse_src_no_range_expansion(self):
        transcript = sparse_transcript()
        plan = two_window_sparse_plan(transcript)
        results = (
            make_window_result(
                plan.windows[0],
                (
                    intermediate(
                        "WIN001:R0001",
                        "TOPIC",
                        "A",
                        ("SRC000001",),
                        metadata=("A.",),
                    ),
                    intermediate(
                        "WIN001:R0002",
                        "IDEA",
                        "Idea A",
                        ("SRC000001",),
                        index=1,
                        link_ids=("WIN001:R0001",),
                        metadata=("claim", "central"),
                    ),
                    intermediate("WIN001:R0003", "INTENT_KIND", "enseigner", (), index=2),
                    intermediate("WIN001:R0004", "AUDIENCE_KIND", "croyants", (), index=3),
                    intermediate(
                        "WIN001:R0005",
                        "VOICE",
                        "didactic",
                        (),
                        index=4,
                        metadata=("tone",),
                    ),
                ),
                signature="1" * 64,
            ),
            make_window_result(
                plan.windows[1],
                (
                    intermediate(
                        "WIN002:R0001",
                        "TOPIC",
                        "B",
                        ("SRC000003", "SRC000010"),
                        metadata=("B.",),
                    ),
                    intermediate(
                        "WIN002:R0002",
                        "IDEA",
                        "Idea B",
                        ("SRC000003",),
                        index=1,
                        link_ids=("WIN002:R0001",),
                        metadata=("claim", "central"),
                    ),
                    intermediate("WIN002:R0003", "INTENT_KIND", "enseigner", (), index=2),
                    intermediate("WIN002:R0004", "AUDIENCE_KIND", "croyants", (), index=3),
                    intermediate(
                        "WIN002:R0005",
                        "VOICE",
                        "oral",
                        (),
                        index=4,
                        metadata=("register",),
                    ),
                ),
                signature="2" * 64,
            ),
        )
        transport = {
            "gm": _gm(
                ["WIN001:R0001"],
                ["WIN001:R0003"],
                ["WIN001:R0004"],
                ["WIN001:R0005", "WIN002:R0005"],
            ),
            "ops": [
                {
                    "o": "MERGE",
                    "m": ["WIN001:R0001", "WIN002:R0001"],
                    "v": "Sparse merged",
                },
                {"o": "KEEP", "r": "WIN001:R0002"},
                {"o": "KEEP", "r": "WIN002:R0002"},
                {"o": "KEEP", "r": "WIN002:R0003"},
                {"o": "KEEP", "r": "WIN002:R0004"},
            ],
        }
        source_map = _reconstruct(transcript, plan, results, transport)
        assert source_map.topics[0].source_refs == (
            "SRC000001",
            "SRC000003",
            "SRC000010",
        )
        assert "SRC000002" not in source_map.topics[0].source_refs

    def test_union_helper_source_order_and_dedupe(self):
        transcript = sparse_transcript()
        refs = union_source_refs_in_source_order(
            [("SRC000010", "SRC000001"), ("SRC000001", "SRC000003")],
            transcript.src_index(),
        )
        assert refs == ("SRC000001", "SRC000003", "SRC000010")


class TestCanonicalIdsAndOrder:
    def test_first_source_appearance_ignores_transport_order(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        sm = run.source_map
        assert sm.topics[0].label == MERGED_TOPIC_VALUE
        assert sm.topics[0].source_refs[0] == "SRC000001"
        assert sm.topics[1].label == "Walking through the valley"

    def test_no_intermediate_ids(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        for ids in run.source_map.declared_ids().values():
            for identifier in ids:
                assert not identifier.startswith("WIN")
                assert ":" not in identifier
                assert not (
                    identifier.startswith("C") and identifier[1:].isdigit()
                )


class TestInternalRefsAndCollections:
    def test_internal_refs_rewritten(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        sm = run.source_map
        idea_ids = {idea.idea_id for idea in sm.ideas}
        topic_ids = {topic.topic_id for topic in sm.topics}
        for idea in sm.ideas:
            assert set(idea.topic_refs) <= topic_ids
            for relation in idea.relations:
                assert relation.to_idea in idea_ids
        for example in sm.examples:
            assert set(example.supports_idea_refs) <= idea_ids
        for repetition in sm.repetitions:
            assert set(repetition.idea_refs) <= idea_ids

    def test_cross_window_relation_and_example(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        sm = run.source_map
        faith = next(idea for idea in sm.ideas if idea.summary == MERGED_IDEA_VALUE)
        walk = next(
            idea for idea in sm.ideas if idea.summary == "Keep walking through the valley."
        )
        assert any(
            relation.relation == "supports" and relation.to_idea == walk.idea_id
            for relation in faith.relations
        )
        assert sm.examples[0].supports_idea_refs == (faith.idea_id,)
        prayer = next(
            idea
            for idea in sm.ideas
            if idea.summary == "Prayer is not optional in the valley."
        )
        assert any(
            relation.relation == "supports" and relation.to_idea == faith.idea_id
            for relation in prayer.relations
        )

    def test_reference_and_uncertainty_preserved(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        sm = run.source_map
        assert sm.references[0].raw_reference == "Paul says somewhere"
        assert sm.references[0].kind == "biblical"
        assert sm.uncertainties[0].kind == "incomplete_reference"
        assert "located" in sm.uncertainties[0].description

    def test_repetition_canonical(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        rep = run.source_map.repetitions[0]
        assert rep.character == "rhetorical"
        assert len(rep.idea_refs) == 2
        assert rep.source_refs == ("SRC000001", "SRC000007")

    def test_idea_kind_and_importance_preserved(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        faith = next(
            idea for idea in run.source_map.ideas if idea.summary == MERGED_IDEA_VALUE
        )
        assert faith.kind == "claim"
        assert faith.importance == "central"

    def test_dangling_rel_incompatible_endpoints_fail(self):
        transcript, plan, results = _two_window_keep_setup()
        transport = {
            "gm": _gm(
                ["WIN001:R0001"],
                ["WIN001:R0004"],
                ["WIN001:R0005"],
                ["WIN001:R0006", "WIN002:R0006"],
            ),
            "ops": [
                {"o": "KEEP", "r": "WIN001:R0001"},
                {"o": "KEEP", "r": "WIN001:R0002"},
                {"o": "KEEP", "r": "WIN001:R0003"},
                {"o": "KEEP", "r": "WIN002:R0001"},
                {"o": "KEEP", "r": "WIN002:R0002"},
                {"o": "KEEP", "r": "WIN002:R0003"},
                {"o": "KEEP", "r": "WIN002:R0004"},
                {"o": "KEEP", "r": "WIN002:R0005"},
                {
                    "o": "REL",
                    "t": "supports",
                    "a": "WIN001:R0001",
                    "b": "WIN001:R0002",
                },
            ],
        }
        with pytest.raises(HybridReconstructionError):
            _reconstruct(transcript, plan, results, transport)

    def test_invalid_idea_kind_fail_closed(self):
        transcript, plan, results = _two_window_keep_setup()
        broken = list(results[0].records)
        broken[1] = intermediate(
            "WIN001:R0002",
            "IDEA",
            "Alpha idea unique",
            ("SRC000001",),
            index=1,
            link_ids=("WIN001:R0001",),
            metadata=("hypothesis", "central"),
        )
        stale_results = (
            make_window_result(
                plan.windows[0],
                tuple(broken),
                signature="1" * 64,
            ),
            results[1],
        )
        transport = {
            "gm": _gm(
                ["WIN001:R0001"],
                ["WIN001:R0004"],
                ["WIN001:R0005"],
                ["WIN001:R0006", "WIN002:R0006"],
            ),
            "ops": [
                {"o": "KEEP", "r": "WIN001:R0001"},
                {"o": "KEEP", "r": "WIN001:R0002"},
                {"o": "KEEP", "r": "WIN001:R0003"},
                {"o": "KEEP", "r": "WIN002:R0001"},
                {"o": "KEEP", "r": "WIN002:R0002"},
                {"o": "KEEP", "r": "WIN002:R0003"},
                {"o": "KEEP", "r": "WIN002:R0004"},
                {"o": "KEEP", "r": "WIN002:R0005"},
            ],
        }
        with pytest.raises(HybridReconstructionError):
            _reconstruct(transcript, plan, stale_results, transport)


class TestGlobalMetadata:
    def test_follows_consolidation_not_window_vote(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        sm = run.source_map
        assert sm.source_analysis.main_theme == CONSOLIDATION_THEME
        assert sm.source_analysis.author_intent.summary == CONSOLIDATION_INTENT
        assert sm.source_analysis.target_audience.summary == CONSOLIDATION_AUDIENCE
        assert CONSOLIDATION_VOICE in sm.author_voice_profile.distinctive_traits
        results = run.orchestration.get_ready_results_in_plan_order()
        window_themes = {result.candidates.theme for result in results}
        assert sm.source_analysis.main_theme not in window_themes
        assert sm.author_voice_profile.tone == ("didactic",)
        assert sm.analysis.strategy == HYBRID_STRATEGY


class TestEndToEnd:
    def test_full_path_fake_ai(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        assert plan.planner_version == PLANNER_VERSION
        assert plan.window_count >= 3
        engine = e2e_engine(plan)
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            engine,
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        assert run.all_windows_ready is True
        assert run.window_fake_calls == 3
        assert run.consolidation_fake_calls == 1
        assert run.real_provider_calls == 0
        assert validate_source_map(run.source_map, transcript) == []
        reconstructor = HybridCanonicalReconstructor()
        assert reconstructor.version
        assert not hasattr(reconstructor, "engine")

    def test_warm_cache_zero_window_calls(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        engine = e2e_engine(plan)
        first = run_hybrid_source_analysis(
            transcript,
            plan,
            engine,
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c1",
        )
        second = run_hybrid_source_analysis(
            transcript,
            plan,
            engine,
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c2",
        )
        assert first.window_fake_calls == 3
        assert second.window_fake_calls == 0
        assert second.consolidation_fake_calls == 1

    def test_determinism(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        a = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "a" / "w",
            consolidation_root=tmp_path / "a" / "c",
        )
        b = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "b" / "w",
            consolidation_root=tmp_path / "b" / "c",
        )
        assert render_source_map(a.source_map.to_dict()) == render_source_map(
            b.source_map.to_dict()
        )
        assert b"timestamp" not in render_source_map(a.source_map.to_dict()).encode(
            "utf-8"
        )

    def test_coverage_coherent_not_forced_100(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        stats = run.source_map.stats
        assert stats.topic_count == len(run.source_map.topics)
        assert stats.idea_count == len(run.source_map.ideas)
        assert stats.source_segment_count == transcript.segment_count
        assert 0 < stats.source_coverage_ratio <= 1.0

    def test_schema_and_transcript_metadata(self, tmp_path, no_ai_network):
        transcript, plan = plan_e2e_windows()
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=tmp_path / "w",
            consolidation_root=tmp_path / "c",
        )
        sm = run.source_map
        assert sm.schema_version == SOURCE_MAP_SCHEMA_VERSION
        assert sm.transcript_id == transcript.transcript_id
        assert sm.project_name == transcript.project_name
        assert sm.primary_language == transcript.primary_language

    def test_signature_changes_when_consolidation_changes(self, tmp_path, no_ai_network):
        transcript, plan, results = _two_window_keep_setup()
        keep = {
            "gm": _gm(
                ["WIN001:R0001"],
                ["WIN001:R0004"],
                ["WIN001:R0005"],
                ["WIN001:R0006", "WIN002:R0006"],
            ),
            "ops": [
                {"o": "KEEP", "r": "WIN001:R0001"},
                {"o": "KEEP", "r": "WIN001:R0002"},
                {"o": "KEEP", "r": "WIN001:R0003"},
                {"o": "KEEP", "r": "WIN002:R0001"},
                {"o": "KEEP", "r": "WIN002:R0002"},
                {"o": "KEEP", "r": "WIN002:R0003"},
                {"o": "KEEP", "r": "WIN002:R0004"},
                {"o": "KEEP", "r": "WIN002:R0005"},
            ],
        }
        merged = {
            "gm": keep["gm"],
            "ops": [
                {
                    "o": "MERGE",
                    "m": ["WIN001:R0001", "WIN002:R0001"],
                    "v": "Merged topic text",
                },
                {"o": "KEEP", "r": "WIN001:R0002"},
                {"o": "KEEP", "r": "WIN001:R0003"},
                {"o": "KEEP", "r": "WIN002:R0002"},
                {"o": "KEEP", "r": "WIN002:R0003"},
                {"o": "KEEP", "r": "WIN002:R0004"},
                {"o": "KEEP", "r": "WIN002:R0005"},
            ],
        }
        a = _reconstruct(transcript, plan, results, keep)
        b = _reconstruct(transcript, plan, results, merged)
        assert a.analysis.signature != b.analysis.signature

    def test_rejects_non_fake_engine(self, tmp_path):
        transcript, plan = plan_e2e_windows()
        with pytest.raises(HybridReconstructionError):
            assert_fake_engine(object())
        with pytest.raises(HybridReconstructionError):
            run_hybrid_source_analysis(
                transcript,
                plan,
                None,
                windows_root=tmp_path / "w",
                consolidation_root=tmp_path / "c",
            )


class TestIntegrity:
    def test_production_planner_policy_unchanged(self):
        config = WindowPlannerConfig()
        assert config.version == PLANNER_VERSION
        assert config.target_input_tokens == TARGET_INPUT_TOKENS == 50000
        assert config.hard_max_input_tokens == HARD_MAX_INPUT_TOKENS == 60000
        assert config.overlap_policy == OVERLAP_POLICY
        test_cfg = make_test_planner_config()
        assert test_cfg.target_input_tokens != TARGET_INPUT_TOKENS

    def test_prompt_and_transport_versions(self):
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V10 == "window-analysis-1.0"
        assert WINDOW_ANALYSIS_PROMPT_VERSION == "window-analysis-1.1"
        assert WINDOW_TRANSPORT_VERSION == "semantic-transport-v1"
        assert CONSOLIDATION_PROMPT_VERSION == "consolidation-1.0"
        assert CONSOLIDATION_TRANSPORT_VERSION == "consolidation-transport-v1"

    def test_generation_c_unchanged(self):
        hashes = generation_c_hashes()
        assert hashes["raw_sha256"] == GENERATION_C_RAW_SHA256_3B43
        assert hashes["anthropic_sha256"] == GENERATION_C_ANTHROPIC_SHA256_3B43
        assert hashes["raw_matches_historical"] is True

    def test_analyzer_not_wired(self):
        assert_hybrid_planner_not_wired()
        assert_window_not_wired()
        assert_window_orch_not_wired()
        assert_consolidation_not_wired()
        assert_analyzer_not_wired()
        assert_offline_package()

    def test_stage_isolation(self):
        source = resolve_stage_settings("source_analysis")
        assert source.provider == "anthropic"
        window = resolve_stage_settings(STAGE_WINDOW)
        assert window.max_output_tokens == 32000
        consolidation = resolve_stage_settings(STAGE_CONSOLIDATION)
        assert consolidation.provider == "anthropic"


class TestCli:
    def test_rejects_real_call(self):
        assert hybrid_cli(["demo", "--real-call"]) == 2


@pytest.mark.skipif(not REAL_CLEAN.is_file(), reason="real clean transcript absent")
class TestRealPreflight:
    def test_preflight_zero_calls(self, no_ai_network):
        from app.source_analysis_execution_strategy.windows import load_clean_transcript

        transcript = load_clean_transcript(REAL_PROJECT)
        plan = plan_windows_v2(transcript)
        assert plan.window_count == 3
        engine = FakeAIEngine(
            script=[AITimeoutError("preflight must not call")],
            retry_policy=no_delay_policy(max_attempts=1),
        )
        run = preflight_hybrid_reconstruction(
            transcript,
            plan,
            engine,
            windows_root=Path("unused-preflight"),
        )
        preflight = run_real_preflight(REAL_PROJECT)
        assert preflight["transcript_id"] == "TR001"
        assert preflight["windows"] == 3
        assert preflight["ready"] == 0
        assert preflight["all_windows_ready"] is False
        assert preflight["consolidation_available"] is False
        assert preflight["canonical_reconstruction_allowed"] is False
        assert preflight["AI_calls"] == 0
        assert run.window_fake_calls == 0
        assert not source_map_path(REAL_PROJECT).exists()

    def test_runner_writes_audit_only(self, no_ai_network):
        result = run_hybrid_reconstruction_pipeline(REAL_PROJECT)
        assert result.outcome in {"PASS", "PARTIAL"}
        assert result.deterministic is True
        assert result.protected_unchanged is True
        assert result.artifact["execution"]["anthropic_calls"] == 0
        assert result.artifact["execution"]["source_map_published"] is False
        assert not source_map_path(REAL_PROJECT).exists()
        assert result.project_state_status not in {"SUCCESS", "completed"}
        again = run_hybrid_reconstruction_pipeline(REAL_PROJECT)
        assert again.artifact_sha256 == result.artifact_sha256
