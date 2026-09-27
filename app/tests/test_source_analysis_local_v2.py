"""Phase 3B.7.7A.11 — FakeAI / offline. 0 réseau. 0 WIN001 réel."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ai.errors import AIError
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.errors import (
    WindowGranularityLimitExceeded,
    WindowSemanticCapacityExceeded,
    WindowTransportValidationError,
)
from app.source_analysis.ultra_compact_schema import (
    SEMANTIC_TRANSPORT_VERSION,
    build_ultra_compact_response_schema,
)
from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_prompt import (
    KNOWN_WINDOW_PROMPT_VERSIONS,
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    build_window_system_prompt,
    window_prompt_sha256,
)
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.constants import (
    DEFERRED_KINDS,
    GRANULARITY_POLICY_VERSION,
    HARD_CEILINGS,
    LOCAL_KINDS,
    NEW_WIN001_CALLS,
    PHASE,
    REAL_PROVIDER_CALL_AUTHORIZED_NEXT,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SEMANTIC_TRANSPORT_VERSION_V2,
    SOURCE_REFS_HARD_MAX,
    TARGET_JSON_LOCAL_TOKENS,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
)
from app.source_analysis_local_v2.decoder import decode_v2_transport
from app.source_analysis_local_v2.e2e import run_direct_e2e, run_hierarchical_e2e
from app.source_analysis_local_v2.fixtures import (
    multi_src_window,
    v2_capacity_transport,
    v2_deferred_kind_transport,
    v2_invalid_kind_transport,
    v2_over_limit_transport,
    v2_source_ref_overflow_transport,
    v2_success_transport,
    v2_truncated_json,
    v2_value_overflow_transport,
)
from app.source_analysis_local_v2.forensics_replay import replay_call_c_against_v2
from app.source_analysis_local_v2.granularity import validate_v2_transport_granularity
from app.source_analysis_local_v2.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
    package_imports_network_clients,
    package_invokes_provider,
)
from app.source_analysis_local_v2.pipeline import analyze_window_v2
from app.source_analysis_local_v2.prompt import build_window_system_prompt_v12
from app.source_analysis_local_v2.schema import (
    build_semantic_transport_v2_schema,
    compare_v1_v2_schemas,
)
from app.source_analysis_local_v2.subdivision import (
    LocalV2SubdivisionError,
    LocalV2SubdivisionNotTriggered,
    child_cache_identity,
    plan_subdivision,
)
from app.source_analysis_local_v2.synthetic import measure_v2_worst_case
from app.source_analysis_local_v2.thinking import audit_thinking_capability
from app.source_analysis_local_v2.validator import validate_v2_transport
from app.source_analysis_output_ceiling_review.constants import PROMPT_10_SHA, PROMPT_11_SHA
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis.canonical_vocabulary import (
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
)
from app.source_analysis.window_fixtures import make_transcript, window_for


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _engine(payload):
    if isinstance(payload, BaseException):
        return FakeAIEngine(script=[payload], retry_policy=no_delay_policy())
    if isinstance(payload, str):
        return FakeAIEngine(
            script=[FakeReply(text=payload, parsed=None)],
            retry_policy=no_delay_policy(),
        )
    return FakeAIEngine(
        script=[FakeReply(text="{}", parsed=payload, finish_reason="stop")],
        retry_policy=no_delay_policy(),
    )


class TestOfflineGuards:
    def test_package_has_no_network_imports(self):
        assert package_imports_network_clients() == []
        assert_offline_package()
        assert_analyzer_not_wired()

    def test_phase_authorizes_zero_calls(self):
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert NEW_WIN001_CALLS == 0
        assert REAL_PROVIDER_CALL_AUTHORIZED_NEXT is False
        assert PHASE == "3B.7.7A.11"


class TestHistoricalFreeze:
    def test_prompt_1_1_byte_identical(self):
        sha = window_prompt_sha256(
            build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION)
        )
        assert sha == PROMPT_11_SHA
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V12 not in KNOWN_WINDOW_PROMPT_VERSIONS

    def test_prompt_1_0_byte_identical(self):
        sha = window_prompt_sha256(
            build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION_V10)
        )
        assert sha == PROMPT_10_SHA

    def test_generation_c_unchanged(self):
        hashes = generation_c_hashes()
        assert hashes["raw_sha256"] == GENERATION_C_RAW_SHA256_3B43
        assert hashes["anthropic_sha256"] == GENERATION_C_ANTHROPIC_SHA256_3B43
        assert SEMANTIC_TRANSPORT_VERSION == "semantic-transport-v1"
        assert build_ultra_compact_response_schema() != "alias"

    def test_granularity_1_0_unchanged(self):
        assert POLICY_VERSION == "window-granularity-1.0"
        assert GRANULARITY_POLICY_VERSION == "window-granularity-1.1-minimal"

    def test_production_planner_unchanged(self):
        assert PLANNER_VERSION == "window-planner-v2.0"


class TestPrompt12:
    def test_versioned_and_local(self):
        text = build_window_system_prompt_v12("en")
        assert "EXTRACTION SÉMANTIQUE LOCALE" in text
        assert "LOCAL SEMANTIC EXTRACTOR" in text
        assert "planificateur éditorial" in text
        assert "générateur de livre" in text
        for kind in LOCAL_KINDS:
            assert kind in text
        for kind in DEFERRED_KINDS:
            assert kind in text


class TestTransportV2Schema:
    def test_not_an_alias(self):
        v2 = build_semantic_transport_v2_schema()
        v1 = build_ultra_compact_response_schema()
        assert v2 == v1
        assert SEMANTIC_TRANSPORT_VERSION_V2 != SEMANTIC_TRANSPORT_VERSION
        comparison = compare_v1_v2_schemas()
        assert comparison["not_an_alias_of_v1"] is True
        assert comparison["selected_shape"] == "generic_records"
        assert comparison["v2_generic"]["maxItems_in_adapted"] is False
        assert comparison["grammar_risk"] == "UNVERIFIED"


class TestDecoderValidator:
    def test_success_single_window(self):
        transcript, window = multi_src_window()
        owned = window.owned_src_refs[0]
        transport = v2_success_transport(owned_src=owned)
        decoded = decode_v2_transport(transport, allowed_source_refs=set(window.owned_src_refs))
        validate_v2_transport(decoded, window)
        outcome = analyze_window_v2(window, transcript, _engine(transport))
        assert outcome.ready is True
        assert outcome.result is not None
        assert outcome.capacity_signaled is False
        assert {r.kind for r in outcome.result.records}.isdisjoint(DEFERRED_KINDS)

    def test_max_policy_within_target(self):
        measured = measure_v2_worst_case()
        assert measured["within_json_target"] is True
        assert measured["local_tokens"] <= TARGET_JSON_LOCAL_TOKENS
        decoded = decode_v2_transport(
            __import__(
                "app.source_analysis_local_v2.synthetic", fromlist=["build_max_policy_v2_transport"]
            ).build_max_policy_v2_transport(),
            allowed_source_refs=None,
        )
        assert decoded["records"]

    def test_over_limit(self):
        transcript, window = multi_src_window()
        transport = v2_over_limit_transport(owned_src=window.owned_src_refs[0])
        outcome = analyze_window_v2(window, transcript, _engine(transport))
        assert outcome.ready is False
        assert outcome.transport is not None
        assert outcome.result is None
        assert outcome.retried is False

    def test_value_length_overflow(self):
        transcript, window = multi_src_window()
        transport = v2_value_overflow_transport(owned_src=window.owned_src_refs[0])
        with pytest.raises(WindowGranularityLimitExceeded):
            validate_v2_transport_granularity(transport)

    def test_source_ref_overflow(self):
        texts = tuple(f"unit {i}" for i in range(1, 60))
        src = tuple(f"SRC{i:06d}" for i in range(1, 60))
        transcript = make_transcript(texts, src_ids=src, content_sha256="c" * 64)
        window = window_for(transcript, owned=src)
        transport = v2_success_transport(owned_src=src[0])
        transport["records"][1]["s"] = list(src[: SOURCE_REFS_HARD_MAX + 1])
        with pytest.raises(WindowGranularityLimitExceeded):
            validate_v2_transport_granularity(transport)

    def test_invalid_kind(self):
        with pytest.raises(WindowTransportValidationError):
            decode_v2_transport(
                v2_invalid_kind_transport(), allowed_source_refs={"SRC000001"}
            )

    def test_deferred_kind(self):
        with pytest.raises(WindowTransportValidationError):
            decode_v2_transport(
                v2_deferred_kind_transport(kind="VOICE"),
                allowed_source_refs={"SRC000001"},
            )
        with pytest.raises(WindowTransportValidationError):
            decode_v2_transport(
                v2_deferred_kind_transport(kind="REPETITION"),
                allowed_source_refs={"SRC000001"},
            )


class TestCapacitySubdivision:
    def test_capacity_signal_plans_offline(self):
        transcript, window = multi_src_window()
        transport = v2_capacity_transport(owned_src=window.owned_src_refs[0])
        outcome = analyze_window_v2(window, transcript, _engine(transport))
        assert outcome.ready is False
        assert outcome.capacity_signaled is True
        assert outcome.subdivision_plan is not None
        assert outcome.subdivided_executed is False
        assert outcome.retried is False
        plan = outcome.subdivision_plan
        owned = list(window.owned_src_refs)
        child_refs = [ref for child in plan.children for ref in child.owned_src_refs]
        assert child_refs == owned
        assert len(child_refs) == len(set(child_refs))

    def test_subdivision_determinism(self):
        transcript, window = multi_src_window()
        transport = v2_capacity_transport(owned_src=window.owned_src_refs[0])
        first = plan_subdivision(
            window, transcript, transport, trigger_validated=True, parse_ok=True, provider_ok=True
        )
        second = plan_subdivision(
            window, transcript, transport, trigger_validated=True, parse_ok=True, provider_ok=True
        )
        assert first.to_dict() == second.to_dict()

    def test_subdivision_depth_failure(self):
        transcript, window = multi_src_window()
        transport = v2_capacity_transport(owned_src=window.owned_src_refs[0])
        with pytest.raises(LocalV2SubdivisionError):
            plan_subdivision(
                window,
                transcript,
                transport,
                parent_depth=2,
                trigger_validated=True,
                parse_ok=True,
                provider_ok=True,
            )

    def test_minimum_unit_fail_closed(self):
        transcript = make_transcript(("one unit",), src_ids=("SRC000001",), content_sha256="d" * 64)
        window = window_for(transcript, owned=("SRC000001",))
        transport = v2_capacity_transport(owned_src="SRC000001")
        with pytest.raises(LocalV2SubdivisionError):
            plan_subdivision(
                window, transcript, transport, trigger_validated=True, parse_ok=True, provider_ok=True
            )

    def test_child_cache_identity_stable(self):
        first = child_cache_identity(
            parent_id="WIN001",
            child_id="WIN001.A",
            owned_src_refs=("SRC000001",),
            owned_content_sha256="a" * 64,
        )
        second = child_cache_identity(
            parent_id="WIN001",
            child_id="WIN001.A",
            owned_src_refs=("SRC000001",),
            owned_content_sha256="a" * 64,
        )
        assert first == second

    def test_no_subdivision_on_parse_failure(self):
        transcript, window = multi_src_window()
        outcome = analyze_window_v2(window, transcript, _engine(v2_truncated_json()))
        assert outcome.ready is False
        assert outcome.parse_ok is False
        assert outcome.subdivision_plan is None

    def test_no_subdivision_on_provider_failure(self):
        transcript, window = multi_src_window()
        outcome = analyze_window_v2(window, transcript, _engine(AIError("provider down")))
        assert outcome.ready is False
        assert outcome.provider_ok is False
        assert outcome.subdivision_plan is None

    def test_plan_api_rejects_parse_failure(self):
        transcript, window = multi_src_window()
        with pytest.raises(LocalV2SubdivisionNotTriggered):
            plan_subdivision(
                window,
                transcript,
                v2_success_transport(owned_src=window.owned_src_refs[0]),
                trigger_validated=True,
                parse_ok=False,
                provider_ok=True,
            )


class TestFakeAIE2E:
    def test_direct_and_deferred_recovery(self, tmp_path):
        result = run_direct_e2e(tmp_path)
        assert result.deferred_local_kinds_absent is True
        assert result.source_map.repetitions
        assert result.source_map.source_analysis.author_intent.kinds
        assert result.source_map.source_analysis.target_audience.kinds
        assert result.source_map.author_voice_profile.tone
        assert result.no_drop is True
        for idea in result.source_map.ideas:
            assert idea.source_refs

    def test_hierarchical(self, tmp_path):
        result = run_hierarchical_e2e(tmp_path)
        assert result.route == "REGIONAL_THEN_GLOBAL"
        assert result.regional_groups
        assert result.source_map.repetitions
        assert result.deferred_local_kinds_absent is True


class TestCallCReplay:
    def test_truncated_remains_invalid(self):
        replay = replay_call_c_against_v2()
        assert replay["became_valid_v2_result"] is False
        assert replay["repaired"] is False
        assert replay["subdivision_triggered"] is False
        assert replay["v2_decode_ok"] is False


class TestThinkingAudit:
    def test_unverified_no_guessed_param(self):
        audit = audit_thinking_capability()
        assert audit["THINKING_CAP_CONTROL"] == "UNVERIFIED"
        assert audit["verified_locally"] == "NO"
        assert audit["implemented_guessed_parameter"] is False
        assert audit["current_payload_thinking_config"]["explicit_thinking_field_sent"] is False
        assert audit["thinking_mode_observed"]["explicitly_requested_by_app"] is False


class TestSchemaMetricsIsolation:
    def test_schema_size_metrics_and_per_kind_ceilings(self):
        comparison = compare_v1_v2_schemas()
        assert comparison["v2_generic"]["raw_bytes"] > 0
        assert comparison["v2_generic"]["adapted_bytes"] > 0
        assert comparison["v1"]["raw_bytes"] > 0
        assert HARD_CEILINGS["IDEA"] <= 64
        assert HARD_CEILINGS["RELATION"] <= 36
        measured = measure_v2_worst_case()
        for kind in LOCAL_KINDS:
            assert measured["kind_counts"].get(kind, 0) <= HARD_CEILINGS[kind]

    def test_isolation_and_no_source_map(self):
        from app.source_analysis.writer import source_map_path
        from app.source_analysis_local_v2.facts import inspect_isolation
        from app.source_analysis_local_v2.constants import PROJECT_NAME

        assert not source_map_path(PROJECT_NAME).is_file()
        report = inspect_isolation()
        assert report["unauthorized_semantic_artifacts_forbidden"] is True
