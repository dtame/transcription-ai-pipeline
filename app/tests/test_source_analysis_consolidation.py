"""
Phase 3B.7.4 — Consolidation transport + decoder + validator.

Aucun réseau. Aucun engine.generate() vers un fournisseur réel.
Aucun source_map de production. Aucun Attempt #3.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ai.errors import AIError, AITimeoutError
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.ai.settings import resolve_stage_settings
from app.source_analysis.canonical_vocabulary import (
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
)
from app.source_analysis.consolidation_analyzer import (
    ConsolidationAnalysisHooks,
    build_consolidation_ai_request,
    consolidate,
    consolidate_from_orchestration,
)
from app.source_analysis.consolidation_fixtures import (
    cross_window_relation_transport,
    drop_transport,
    duplicate_disposition_transport,
    duplicate_merge_member_transport,
    editorial_leak_transport,
    example_cross_window_transport,
    fake_engine,
    forward_ref_transport,
    global_metadata_transport,
    global_repetition_transport,
    incompatible_merge_transport,
    invalid_metadata_evidence_transport,
    invalid_relation_type_transport,
    invalid_repetition_type_transport,
    keep_two_window_transport,
    make_orchestration,
    merge_topics_transport,
    multiple_merge_membership_transport,
    non_merge_transport,
    ready_results_three,
    ready_results_two,
    singleton_merge_transport,
    unaccounted_transport,
    unknown_record_transport,
    unsupported_synthesis_transport,
)
from app.source_analysis.consolidation_input import (
    build_consolidation_input,
    build_consolidation_input_from_plan,
)
from app.source_analysis.consolidation_models import (
    CONSOLIDATION_MAX_OUTPUT_TOKENS,
    CONSOLIDATION_OUTPUT_LANGUAGE,
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    CONSOLIDATION_TARGET_MODEL,
    CONSOLIDATION_TARGET_PROVIDER,
    CONSOLIDATION_TRANSPORT_VERSION,
    STAGE_CONSOLIDATION,
)
from app.source_analysis.consolidation_prompt import (
    CONSOLIDATION_PROMPT_ROLE,
    build_consolidation_system_prompt,
    build_consolidation_user_prompt,
)
from app.source_analysis.consolidation_schema import (
    build_consolidation_response_schema,
    consolidation_schema_metrics,
)
from app.source_analysis.consolidation_signature import (
    build_consolidation_signature,
    signature_inputs_for,
)
from app.source_analysis.consolidation_writer import (
    leftover_partial,
    result_path,
    transport_path,
)
from app.source_analysis.errors import (
    ConsolidationContextExceeded,
    ConsolidationError,
    ConsolidationInputError,
    ConsolidationResultValidationError,
    ConsolidationTransportValidationError,
    ConsolidationTransportWriteError,
    SourceMapEditorialLeakError,
    WindowsIncompleteError,
)
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.window_models import STAGE_WINDOW
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_consolidation.cli import main as consolidation_cli
from app.source_analysis_consolidation.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_consolidation.runner import (
    run_consolidation_pipeline,
    run_real_preflight,
)
from app.source_analysis_hybrid.offline import assert_analyzer_not_wired as assert_hybrid_not_wired
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis_window_pipeline.offline import (
    assert_analyzer_not_wired as assert_window_not_wired,
)

REAL_PROJECT = "pastoral_retreat_v2_validation"
REAL_CLEAN = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
    r"\transcripts\clean\transcript_data.json"
)


def _input_two():
    _transcript, plan, results = ready_results_two()
    orch = make_orchestration(plan, results)
    return plan, results, orch, build_consolidation_input(orch, plan=plan)


def _input_three():
    _transcript, plan, results = ready_results_three()
    orch = make_orchestration(plan, results)
    return plan, results, orch, build_consolidation_input(orch, plan=plan)


def _run(tmp_path, transport, consolidation_input, **kwargs):
    root = tmp_path / "consolidation"
    engine = fake_engine(transport)
    result = consolidate(
        consolidation_input,
        engine,
        consolidation_root=root,
        **kwargs,
    )
    return result, root, engine


class TestConsolidationInputBuilder:
    def test_requires_all_windows_ready(self):
        _transcript, plan, results = ready_results_three()
        orch = make_orchestration(plan, results[:2], all_ready=False)
        with pytest.raises(WindowsIncompleteError):
            build_consolidation_input(orch, plan=plan)

    def test_from_plan_rejects_two_of_three(self):
        _transcript, plan, results = ready_results_three()
        with pytest.raises(WindowsIncompleteError):
            build_consolidation_input_from_plan(plan, results[:2])

    def test_restores_shuffled_plan_order(self):
        _transcript, plan, results = ready_results_three()
        shuffled = (results[2], results[0], results[1])
        built = build_consolidation_input_from_plan(plan, shuffled)
        assert [window.window_id for window in built.windows] == [
            "WIN001",
            "WIN002",
            "WIN003",
        ]

    def test_rejects_duplicate_window_in_shuffled(self):
        _transcript, plan, results = ready_results_three()
        with pytest.raises(ConsolidationInputError):
            build_consolidation_input_from_plan(
                plan, (results[0], results[0], results[1])
            )

    def test_no_full_transcript(self):
        _plan, _results, _orch, built = _input_two()
        payload = built.to_dict()
        text = str(payload)
        assert payload["contains_full_transcript"] is False
        assert "Faith during trials changes the crossing." not in text
        assert "transcript_data" not in text

    def test_intermediate_ids_unique(self):
        _plan, _results, _orch, built = _input_three()
        ids = [record.record_id for record in built.all_records()]
        assert len(ids) == len(set(ids))
        assert "WIN001:R0001" in ids
        assert "WIN002:R0001" in ids

    def test_real_src_preserved(self):
        _plan, _results, _orch, built = _input_two()
        topic = built.record_by_id()["WIN001:R0001"]
        assert topic.source_refs == ("SRC000001",)

    def test_no_numeric_range_assumption(self):
        _plan, _results, _orch, built = _input_two()
        payload = built.to_dict()
        assert "SRC000003" not in str(payload.get("windows"))

    def test_hash_deterministic(self):
        _plan, results, orch, built = _input_two()
        again = build_consolidation_input(orch, plan=_plan)
        assert built.input_hash == again.input_hash
        assert built.to_dict() == again.to_dict()

    def test_hash_changes_when_record_changes(self):
        plan, results, _orch, built = _input_two()
        mutated = results[0]
        records = list(mutated.records)
        first = records[0]
        records[0] = type(first)(
            record_id=first.record_id,
            transport_index=first.transport_index,
            kind=first.kind,
            value="Changed topic",
            source_refs=first.source_refs,
            links=first.links,
            link_record_ids=first.link_record_ids,
            metadata=first.metadata,
        )
        from app.source_analysis.consolidation_fixtures import make_window_result

        changed = make_window_result(plan.windows[0], tuple(records), signature="9" * 64)
        other = build_consolidation_input_from_plan(plan, (changed, results[1]))
        assert other.input_hash != built.input_hash

    def test_context_guard(self):
        _plan, _results, orch, _built = _input_two()
        with pytest.raises(ConsolidationContextExceeded):
            build_consolidation_input(orch, plan=_plan, safe_budget=1)

    def test_no_truncation_on_overflow(self):
        _plan, _results, orch, _built = _input_two()
        try:
            build_consolidation_input(orch, plan=_plan, safe_budget=1)
        except ConsolidationContextExceeded as exc:
            assert exc.safe_input_budget == 1
            assert exc.estimated_tokens > 1


class TestPromptAndSchema:
    def test_prompt_role_and_forbids(self):
        system = build_consolidation_system_prompt("en")
        assert CONSOLIDATION_PROMPT_ROLE in system
        assert "DROP" in system
        assert "chapitre" in system.lower() or "chapter" in system.lower()
        assert "SourceMap" in system or "SOURCEMAP" in system.upper() or "sourcemap" in system.lower()

    def test_prompt_versions_isolated(self):
        assert CONSOLIDATION_PROMPT_VERSION != SOURCE_ANALYZER_PROMPT_VERSION
        assert CONSOLIDATION_PROMPT_VERSION != WINDOW_ANALYSIS_PROMPT_VERSION
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V10 == "window-analysis-1.0"
        assert WINDOW_ANALYSIS_PROMPT_VERSION == "window-analysis-1.1"

    def test_user_prompt_has_no_full_transcript(self):
        _plan, _results, _orch, built = _input_two()
        user = build_consolidation_user_prompt(built)
        assert "Faith during trials changes the crossing." not in user
        assert "WIN001:R0001" in user

    def test_schema_is_compact(self):
        schema = build_consolidation_response_schema()
        metrics = consolidation_schema_metrics(schema)
        assert metrics["enum_count"] == 0
        assert metrics["arrays_of_objects"] == 1
        assert metrics["constraints"] == 0
        assert metrics["serialized_json_bytes"] < 2000


class TestAIRequestAndSignature:
    def test_request_is_structured(self):
        _plan, _results, _orch, built = _input_two()
        bundle = build_consolidation_ai_request(built)
        assert bundle.request.wants_structured_output
        assert bundle.request.stage == STAGE_CONSOLIDATION
        assert bundle.request.max_output_tokens == CONSOLIDATION_MAX_OUTPUT_TOKENS
        assert bundle.request.metadata["output_language"] == CONSOLIDATION_OUTPUT_LANGUAGE

    def test_signature_changes_with_window_order(self):
        _plan, _results, _orch, built = _input_two()
        input_a = built
        from app.source_analysis.consolidation_models import ConsolidationInput

        reversed_input = ConsolidationInput(
            schema_version=input_a.schema_version,
            contract=input_a.contract,
            transcript_id=input_a.transcript_id,
            planner_version=input_a.planner_version,
            strategy=input_a.strategy,
            prompt_version=input_a.prompt_version,
            transport_version=input_a.transport_version,
            windows=tuple(reversed(input_a.windows)),
            input_hash=input_a.input_hash,
            estimated_tokens=input_a.estimated_tokens,
            token_estimate_method=input_a.token_estimate_method,
        )
        a = signature_inputs_for(
            input_a,
            prompt_sha256="p",
            response_schema_sha256="s",
            provider="fake",
            model="fake-model",
            temperature=None,
            max_output_tokens=16000,
            context_safety_ratio=0.7,
        )
        b = signature_inputs_for(
            reversed_input,
            prompt_sha256="p",
            response_schema_sha256="s",
            provider="fake",
            model="fake-model",
            temperature=None,
            max_output_tokens=16000,
            context_safety_ratio=0.7,
        )
        assert a.window_result_hashes != b.window_result_hashes
        assert build_consolidation_signature(a) != build_consolidation_signature(b)

    def test_signature_changes_with_settings(self):
        _plan, _results, _orch, built = _input_two()
        base = signature_inputs_for(
            built,
            prompt_sha256="p",
            response_schema_sha256="s",
            provider="fake",
            model="fake-model",
            temperature=None,
            max_output_tokens=16000,
            context_safety_ratio=0.7,
        )
        changed = signature_inputs_for(
            built,
            prompt_sha256="p",
            response_schema_sha256="s",
            provider="anthropic",
            model="claude-sonnet-5",
            temperature=0.2,
            max_output_tokens=8000,
            context_safety_ratio=0.7,
        )
        assert build_consolidation_signature(base) != build_consolidation_signature(
            changed
        )


class TestFakeAISuccess:
    def test_keep_fixture(self, tmp_path, no_ai_network):
        _plan, _results, _orch, built = _input_two()
        result, root, engine = _run(tmp_path, keep_two_window_transport(), built)
        assert engine.call_count == 1
        assert transport_path("fixture", root=root).is_file()
        assert result_path("fixture", root=root).is_file()
        assert result.to_dict()["canonical_sourcemap"] is False
        assert all(node.operation == "KEEP_RECORD" for node in result.nodes)

    def test_merge_fixture(self, tmp_path, no_ai_network):
        _plan, _results, _orch, built = _input_two()
        result, _root, _engine = _run(tmp_path, merge_topics_transport(), built)
        merge = next(node for node in result.nodes if node.operation == "MERGE_RECORDS")
        assert merge.member_ids == ("WIN001:R0001", "WIN002:R0001")
        assert merge.value == "Faith during trials and adversity"
        assert merge.source_refs == ("SRC000001", "SRC000002")
        assert merge.source_refs_are_local_union is True

    def test_non_merge_does_not_force_equivalence(self, tmp_path, no_ai_network):
        _plan, _results, _orch, built = _input_two()
        result, _root, _engine = _run(tmp_path, non_merge_transport(), built)
        topics = [node for node in result.nodes if node.kind == "TOPIC"]
        assert len(topics) == 2
        assert all(node.operation == "KEEP_RECORD" for node in topics)

    def test_cross_window_relation(self, tmp_path, no_ai_network):
        _plan, _results, _orch, built = _input_three()
        result, _root, _engine = _run(
            tmp_path, cross_window_relation_transport(), built
        )
        assert result.relations[0].relation_type == "supports"
        assert result.relations[0].left_ref == "WIN001:R0002"
        assert result.relations[0].right_ref == "WIN003:R0001"

    def test_example_illustrates_idea(self, tmp_path, no_ai_network):
        _plan, _results, _orch, built = _input_two()
        result, _root, _engine = _run(
            tmp_path, example_cross_window_transport(), built
        )
        assert result.relations[0].relation_type == "illustrates"

    def test_global_repetition(self, tmp_path, no_ai_network):
        _plan, _results, _orch, built = _input_three()
        result, _root, _engine = _run(tmp_path, global_repetition_transport(), built)
        assert result.repetitions[0].character == "rhetorical"

    def test_global_metadata_grounded(self, tmp_path, no_ai_network):
        _plan, _results, _orch, built = _input_three()
        result, _root, _engine = _run(tmp_path, global_metadata_transport(), built)
        meta = result.global_metadata
        assert meta.theme_evidence
        assert meta.intent_evidence
        assert meta.audience_evidence
        assert meta.voice_evidence


class TestInvalidFixtures:
    @pytest.mark.parametrize(
        "factory",
        [
            unknown_record_transport,
            incompatible_merge_transport,
            singleton_merge_transport,
            duplicate_disposition_transport,
            unaccounted_transport,
            drop_transport,
            invalid_relation_type_transport,
            invalid_repetition_type_transport,
            invalid_metadata_evidence_transport,
            unsupported_synthesis_transport,
            editorial_leak_transport,
            forward_ref_transport,
            duplicate_merge_member_transport,
            multiple_merge_membership_transport,
        ],
    )
    def test_invalid_fail_closed(self, tmp_path, no_ai_network, factory):
        three = factory in {
            cross_window_relation_transport,
            global_repetition_transport,
            global_metadata_transport,
        }
        _plan, _results, _orch, built = _input_three() if three else _input_two()
        root = tmp_path / "consolidation"
        with pytest.raises(
            (
                ConsolidationTransportValidationError,
                ConsolidationResultValidationError,
                SourceMapEditorialLeakError,
            )
        ):
            consolidate(
                built,
                fake_engine(factory()),
                consolidation_root=root,
            )
        assert transport_path("fixture", root=root).is_file()
        assert not result_path("fixture", root=root).exists()


class TestTransportFirstAndFailures:
    def test_transport_first_order(self, tmp_path, no_ai_network):
        _plan, _results, _orch, built = _input_two()
        order: list[str] = []
        _run(
            tmp_path,
            keep_two_window_transport(),
            built,
            hooks=ConsolidationAnalysisHooks(
                after_generate=lambda _r: order.append("generate"),
                after_transport_write=lambda _p: order.append("transport"),
                before_decode=lambda _p: order.append("decode"),
                after_validate=lambda _r: order.append("validate"),
            ),
        )
        assert order == ["generate", "transport", "decode", "validate"]

    def test_write_failure_stops_before_decode(
        self, tmp_path, no_ai_network, monkeypatch
    ):
        _plan, _results, _orch, built = _input_two()
        decoded = {"called": False}

        def boom(*_args, **_kwargs):
            raise ConsolidationTransportWriteError("disk full")

        def decode_should_not_run(*_args, **_kwargs):
            decoded["called"] = True
            raise AssertionError("decoder must not run")

        monkeypatch.setattr(
            "app.source_analysis.consolidation_analyzer.write_consolidation_transport",
            boom,
        )
        monkeypatch.setattr(
            "app.source_analysis.consolidation_analyzer.decode_consolidation_transport",
            decode_should_not_run,
        )
        with pytest.raises(ConsolidationTransportWriteError):
            consolidate(
                built,
                fake_engine(keep_two_window_transport()),
                consolidation_root=tmp_path / "consolidation",
            )
        assert decoded["called"] is False
        assert not result_path(
            "fixture", root=tmp_path / "consolidation"
        ).exists()

    def test_post_transport_invalid_keeps_transport(self, tmp_path, no_ai_network):
        _plan, _results, _orch, built = _input_two()
        root = tmp_path / "consolidation"
        with pytest.raises(
            (
                ConsolidationTransportValidationError,
                SourceMapEditorialLeakError,
            )
        ):
            consolidate(
                built,
                fake_engine(drop_transport()),
                consolidation_root=root,
            )
        assert transport_path("fixture", root=root).is_file()
        assert not result_path("fixture", root=root).exists()

    def test_provider_error_no_transport(self, tmp_path, no_ai_network):
        _plan, _results, _orch, built = _input_two()
        root = tmp_path / "consolidation"
        engine = FakeAIEngine(
            script=[AITimeoutError("offline timeout")],
            retry_policy=no_delay_policy(max_attempts=1),
        )
        with pytest.raises(AIError):
            consolidate(built, engine, consolidation_root=root)
        assert engine.call_count == 1
        assert not transport_path("fixture", root=root).exists()
        assert not result_path("fixture", root=root).exists()

    def test_invalid_input_makes_zero_calls(self, tmp_path, no_ai_network):
        _transcript, plan, results = ready_results_three()
        orch = make_orchestration(plan, results[:2], all_ready=False)
        engine = fake_engine(keep_two_window_transport())
        with pytest.raises(WindowsIncompleteError):
            consolidate_from_orchestration(
                orch,
                engine,
                plan=plan,
                consolidation_root=tmp_path / "consolidation",
            )
        assert engine.call_count == 0

    def test_engine_required(self, tmp_path):
        _plan, _results, _orch, built = _input_two()
        with pytest.raises(ConsolidationError, match="injecté"):
            consolidate(
                built,
                None,
                consolidation_root=tmp_path / "consolidation",
            )

    def test_byte_identical_results(self, tmp_path, no_ai_network):
        _plan, _results, _orch, built = _input_two()
        a = tmp_path / "a"
        b = tmp_path / "b"
        r1 = consolidate(
            built, fake_engine(keep_two_window_transport()), consolidation_root=a
        )
        r2 = consolidate(
            built, fake_engine(keep_two_window_transport()), consolidation_root=b
        )
        assert transport_path("fixture", root=a).read_bytes() == transport_path(
            "fixture", root=b
        ).read_bytes()
        assert result_path("fixture", root=a).read_bytes() == result_path(
            "fixture", root=b
        ).read_bytes()
        assert r1.consolidation_signature == r2.consolidation_signature
        assert b"timestamp" not in result_path("fixture", root=a).read_bytes()


class TestStageIsolation:
    def test_editorial_stages_unchanged(self):
        source = resolve_stage_settings("source_analysis")
        assert source.provider == "anthropic"
        assert source.model == "claude-sonnet-5"
        assert source.max_output_tokens is None
        editorial = resolve_stage_settings("editorial_planning")
        assert editorial.provider == "anthropic"
        assert editorial.model == "claude-opus-5"
        book = resolve_stage_settings("book_generation")
        assert book.provider == "anthropic"
        validation = resolve_stage_settings("book_validation")
        assert validation.provider == "openai"
        window = resolve_stage_settings(STAGE_WINDOW)
        assert window.max_output_tokens == 32000
        consolidation = resolve_stage_settings(STAGE_CONSOLIDATION)
        assert consolidation.provider == CONSOLIDATION_TARGET_PROVIDER
        assert consolidation.model == CONSOLIDATION_TARGET_MODEL
        assert consolidation.max_output_tokens == CONSOLIDATION_MAX_OUTPUT_TOKENS
        assert consolidation.connect_timeout_seconds == 30
        assert consolidation.read_timeout_seconds == 1800


class TestIntegrity:
    def test_prompt_1_3_unchanged(self):
        assert SOURCE_ANALYZER_PROMPT_VERSION == "1.3"

    def test_window_prompt_unchanged(self):
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V10 == "window-analysis-1.0"
        assert WINDOW_ANALYSIS_PROMPT_VERSION == "window-analysis-1.1"

    def test_generation_c_unchanged(self):
        hashes = generation_c_hashes()
        assert hashes["raw_sha256"] == GENERATION_C_RAW_SHA256_3B43
        assert hashes["anthropic_sha256"] == GENERATION_C_ANTHROPIC_SHA256_3B43
        assert hashes["raw_matches_historical"] is True
        assert hashes["anthropic_matches_historical"] is True

    def test_analyzer_not_wired(self):
        assert_hybrid_not_wired()
        assert_window_not_wired()
        assert_analyzer_not_wired()
        assert_offline_package()

    def test_transport_version(self):
        assert CONSOLIDATION_TRANSPORT_VERSION == "consolidation-transport-v1"
        assert CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS == 80000


class TestCli:
    def test_rejects_real_call(self):
        assert consolidation_cli(["demo", "--real-call"]) == 2


@pytest.mark.skipif(not REAL_CLEAN.is_file(), reason="real clean transcript absent")
class TestRealPreflight:
    def test_preflight_zero_calls(self, no_ai_network):
        from app.source_analysis_execution_strategy.windows import load_clean_transcript

        transcript = load_clean_transcript(REAL_PROJECT)
        plan = plan_windows_v2(transcript)
        assert plan.window_count == 3
        preflight = run_real_preflight(REAL_PROJECT)
        assert preflight["windows"] == 3
        assert preflight["ready"] == 0
        assert preflight["all_windows_ready"] is False
        assert preflight["consolidation_input_created"] is False
        assert preflight["AI_calls"] == 0
        assert not source_map_path(REAL_PROJECT).exists()
        assert Path(
            r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
            r"\analysis\consolidation"
        ).exists() is False

    def test_runner_writes_audit_only(self, no_ai_network):
        result = run_consolidation_pipeline(REAL_PROJECT)
        assert result.outcome in {"PASS", "PARTIAL"}
        assert result.deterministic is True
        assert result.protected_unchanged is True
        assert result.artifact["execution"]["anthropic_calls"] == 0
        assert result.artifact["execution"]["source_map_published"] is False
        assert not source_map_path(REAL_PROJECT).exists()
        assert result.project_state_status not in {"SUCCESS", "completed"}
        again = run_consolidation_pipeline(REAL_PROJECT)
        assert again.artifact_sha256 == result.artifact_sha256
        assert result.artifact["schema_metrics"]["SERVER_GRAMMAR_VERIFIED"] == "NO"
