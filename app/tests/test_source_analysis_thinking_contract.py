"""Phase 3B.7.7A.12 — FakeAI / offline. 0 réseau. 0 WIN001 réel."""

from __future__ import annotations

import pytest

from app.ai.errors import AIConfigurationError
from app.ai.providers.anthropic_engine import AnthropicEngine
from app.source_analysis.ultra_compact_schema import SEMANTIC_TRANSPORT_VERSION
from app.source_analysis.window_fixtures import make_transcript, window_for
from app.source_analysis.window_granularity import POLICY_VERSION
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    build_window_system_prompt,
    window_prompt_sha256,
)
from app.source_analysis.window_signature import (
    WindowSignatureInputs,
    build_window_analysis_signature,
)
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.e2e import run_direct_e2e
from app.source_analysis_local_v2.pipeline import analyze_window_v2, build_v2_window_request
from app.source_analysis_local_v2.prompt import build_window_system_prompt_v12
from app.source_analysis_local_v2.schema import compare_v1_v2_schemas
from app.source_analysis_local_v2.subdivision import child_cache_identity
from app.source_analysis_local_v2.synthetic import measure_v2_worst_case
from app.source_analysis_local_v2.thinking import audit_thinking_capability
from app.source_analysis_output_ceiling_review.constants import PROMPT_10_SHA, PROMPT_11_SHA
from app.source_analysis_thinking_contract.canary import (
    GrammarCanaryAuthorizationError,
    grammar_canary_readiness,
    run_grammar_canary,
    run_semantic_win001_canary,
)
from app.source_analysis_thinking_contract.constants import (
    MAX_OUTPUT_TOKENS_FROZEN,
    NEW_WIN001_CALLS,
    PHASE,
    REAL_PROVIDER_CALL_AUTHORIZED,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SELECTED_CONTRACT,
    SELECTED_THINKING_MODE,
    TARGET_JSON_LOCAL_TOKENS,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
)
from app.source_analysis_thinking_contract.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
    package_imports_network_clients,
    package_invokes_provider,
)
from app.source_analysis_thinking_contract.payload import build_named_payload
from app.source_analysis_thinking_contract.signature import (
    same_window_thinking_signatures,
    v2_forensic_identity,
)
from app.source_analysis_thinking_contract.v2_config import V2_THINKING_MODE
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis.canonical_vocabulary import (
    GENERATION_C_ANTHROPIC_SHA256_3B43,
    GENERATION_C_RAW_SHA256_3B43,
)
from app.source_analysis_local_v2.fixtures import v2_success_transport
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy


def _engine(payload):
    return FakeAIEngine(
        script=[FakeReply(text="{}", parsed=payload, finish_reason="stop")],
        retry_policy=no_delay_policy(),
    )


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
        assert NEW_WIN001_CALLS == 0
        assert REAL_WINDOW_CALLS == 0
        assert REAL_PROVIDER_CALL_AUTHORIZED is False
        assert PHASE == "3B.7.7A.12"


class TestHistoricalFreeze:
    def test_prompt_1_1_and_1_0_byte_identical(self):
        sha11 = window_prompt_sha256(
            build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION)
        )
        sha10 = window_prompt_sha256(
            build_window_system_prompt("en", version=WINDOW_ANALYSIS_PROMPT_VERSION_V10)
        )
        assert sha11 == PROMPT_11_SHA
        assert sha10 == PROMPT_10_SHA

    def test_prompt_1_2_unchanged(self):
        first = build_window_system_prompt_v12("en")
        second = build_window_system_prompt_v12("en")
        assert first == second
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V12 == "window-analysis-1.2"
        assert "planificateur éditorial" in first

    def test_transport_v2_unchanged(self):
        comparison = compare_v1_v2_schemas()
        assert comparison["v2_generic"]["raw_bytes"] == 559
        assert comparison["v2_generic"]["adapted_bytes"] == 621
        assert SEMANTIC_TRANSPORT_VERSION == "semantic-transport-v1"

    def test_generation_c_unchanged(self):
        hashes = generation_c_hashes()
        assert hashes["raw_sha256"] == GENERATION_C_RAW_SHA256_3B43
        assert hashes["anthropic_sha256"] == GENERATION_C_ANTHROPIC_SHA256_3B43

    def test_granularity_and_planner_unchanged(self):
        assert POLICY_VERSION == "window-granularity-1.0"
        assert PLANNER_VERSION == "window-planner-v2.0"

    def test_a11_historical_thinking_audit_still_unverified_for_default(self):
        audit = audit_thinking_capability()
        assert audit["THINKING_CAP_CONTROL"] == "UNVERIFIED"
        assert audit["implemented_guessed_parameter"] is False
        assert audit["current_payload_thinking_config"]["explicit_thinking_field_sent"] is False

    def test_historical_signature_regression(self):
        base = dict(
            window_input_hash="h1",
            window_id="WIN001",
            transcript_id="TR001",
            transcript_sha256="t" * 64,
            planner_version=PLANNER_VERSION,
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION,
            prompt_sha256="p" * 64,
            transport_version=SEMANTIC_TRANSPORT_VERSION,
            response_schema_sha256="s" * 64,
            provider="anthropic",
            model="claude-sonnet-5",
            temperature=None,
            max_output_tokens=32000,
            output_language="en",
            context_safety_ratio=0.7,
        )
        historical = WindowSignatureInputs(**base)
        assert "thinking_mode" not in historical.to_dict()
        assert "effort" not in historical.to_dict()
        same = WindowSignatureInputs(**base, thinking_mode=None, effort=None)
        assert build_window_analysis_signature(historical) == (
            build_window_analysis_signature(same)
        )
        disabled = WindowSignatureInputs(**base, thinking_mode="disabled")
        assert build_window_analysis_signature(disabled) != (
            build_window_analysis_signature(historical)
        )


class TestSyntheticWorstCase:
    def test_still_within_12000(self):
        measured = measure_v2_worst_case()
        assert measured["local_tokens"] <= TARGET_JSON_LOCAL_TOKENS
        assert measured["within_json_target"] is True
        assert MAX_OUTPUT_TOKENS_FROZEN == 32000


class TestSignatureCacheForensics:
    def test_signature_and_forensic_separation(self):
        transcript = make_transcript(("same WIN001 content",), content_sha256="c" * 64)
        window = window_for(transcript)
        system = build_window_system_prompt_v12("en")
        user = "user"
        identities = same_window_thinking_signatures(
            window,
            transcript,
            system_prompt=system,
            user_prompt=user,
            response_schema_sha256="s" * 64,
            provider="anthropic",
            model="claude-sonnet-5",
            temperature=None,
            max_output_tokens=32000,
            context_safety_ratio=0.7,
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V12,
        )
        assert identities["all_distinct"] is True
        sigs = identities["signatures"]
        assert sigs["THINKING_DISABLED"] != sigs["ADAPTIVE_LOW"]
        assert sigs["ADAPTIVE_LOW"] != sigs["ADAPTIVE_MEDIUM"]
        assert sigs["ADAPTIVE_MEDIUM"] != sigs["provider_default"]
        assert sigs["ADAPTIVE_HIGH"] != sigs["provider_default"]
        forensics = identities["forensics"]
        assert len(set(forensics.values())) == len(forensics)

    def test_cache_identity_includes_thinking(self):
        disabled = child_cache_identity(
            parent_id="WIN001",
            child_id="WIN001.A",
            owned_src_refs=("SRC000001",),
            owned_content_sha256="a" * 64,
            thinking_mode="disabled",
            effort=None,
        )
        low = child_cache_identity(
            parent_id="WIN001",
            child_id="WIN001.A",
            owned_src_refs=("SRC000001",),
            owned_content_sha256="a" * 64,
            thinking_mode="adaptive",
            effort="low",
        )
        medium = child_cache_identity(
            parent_id="WIN001",
            child_id="WIN001.A",
            owned_src_refs=("SRC000001",),
            owned_content_sha256="a" * 64,
            thinking_mode="adaptive",
            effort="medium",
        )
        default = child_cache_identity(
            parent_id="WIN001",
            child_id="WIN001.A",
            owned_src_refs=("SRC000001",),
            owned_content_sha256="a" * 64,
            thinking_mode="provider_default",
            effort=None,
        )
        assert len({disabled, low, medium, default}) == 4
        forensic_a = v2_forensic_identity(
            content_sha256="a" * 64, thinking_mode="disabled", effort=None
        )
        forensic_b = v2_forensic_identity(
            content_sha256="a" * 64, thinking_mode="adaptive", effort="low"
        )
        assert forensic_a != forensic_b


class TestSelectedContractFakeAIE2E:
    def test_v2_request_uses_selected_contract(self):
        transcript = make_transcript(("hello",))
        window = window_for(transcript)
        request = build_v2_window_request(window, transcript)
        assert request.thinking_mode == SELECTED_THINKING_MODE == V2_THINKING_MODE
        assert request.effort is None
        assert request.metadata["thinking_contract"] == SELECTED_CONTRACT
        assert request.max_output_tokens == 32000

    def test_selected_contract_e2e(self, tmp_path):
        result = run_direct_e2e(tmp_path)
        assert result.no_drop is True
        transcript = make_transcript(("e2e selected",))
        window = window_for(transcript)
        transport = v2_success_transport(owned_src=window.owned_src_refs[0])
        outcome = analyze_window_v2(window, transcript, _engine(transport))
        assert outcome.ready is True
        assert outcome.request is not None
        assert outcome.request.thinking_mode == "disabled"
        assert outcome.result is not None

    def test_adaptive_low_and_medium_payload_only(self):
        low = build_named_payload("ADAPTIVE_LOW")
        medium = build_named_payload("ADAPTIVE_MEDIUM")
        assert low["thinking"]["type"] == "adaptive"
        assert low["effort"] == "low"
        assert medium["effort"] == "medium"


class TestGrammarCanaryBlocked:
    def test_prepared_not_executed(self):
        ready = grammar_canary_readiness()
        assert ready["v2_grammar_canary_ready"] is True
        assert ready["v2_grammar_canary_executed"] is False
        assert ready["semantic_win001_ready"] is False
        with pytest.raises(GrammarCanaryAuthorizationError):
            run_grammar_canary(execute_real=True)
        with pytest.raises(GrammarCanaryAuthorizationError):
            run_semantic_win001_canary()


class TestBudgetTokensNeverSent:
    def test_http_attempts_zero(self):
        from app.source_analysis_thinking_contract.payload import build_v2_payload_request

        engine = AnthropicEngine(model="claude-sonnet-5", api_key="cle-de-test")
        request = build_v2_payload_request(thinking_budget_tokens=8000)
        with pytest.raises(AIConfigurationError):
            engine.build_payload(request, "claude-sonnet-5")
