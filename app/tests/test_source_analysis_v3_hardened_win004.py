"""Phase 3B.7.7A.24 — FakeAI / offline guards. 0 réseau réel."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.ai.contracts import AIRequest
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.errors import MaxRealCallsExceededError
from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v3.constants import (
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
    WINDOW_ANALYSIS_PROMPT_VERSION_V132,
)
from app.source_analysis_local_v3.fixtures import v3_success_transport
from app.source_analysis_local_v3.prompt import (
    build_window_system_prompt_v13,
    build_window_system_prompt_v131,
    build_window_system_prompt_v132,
)
from app.source_analysis_local_v3.schema import semantic_transport_v3_fingerprint
from app.source_analysis_local_v3.source_refs import classify_src_token
from app.source_analysis_v3_a19_forensics.constants import A19_SIGNATURE
from app.source_analysis_v3_a22_forensics.constants import A22_SIGNATURE
from app.source_analysis_v3_hardened_win001.constants import (
    AUTHORIZATION_SCOPE as A21_SCOPE,
    EXPECTED_ANALYSIS_SIGNATURE as A21_SIGNATURE,
)
from app.source_analysis_v3_hardened_win004.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_ANALYSIS_SIGNATURE,
    EXPECTED_FORENSIC_IDENTITY,
    EXPECTED_LOCAL_INPUT_ESTIMATE,
    EXPECTED_OWNED_SRC_COUNT,
    EXPECTED_PROMPT_SHA256,
    EXPECTED_SCHEMA_HASH,
    EXPECTED_WINDOW_INPUT_HASH,
    EXPECTED_WORD_COUNT,
    PHASE,
    WINDOW_ID,
)
from app.source_analysis_v3_hardened_win004.guard import (
    HardenedV3Win004Error,
    OneShotCallGuard,
    validate_authorization_scope,
    validate_provider,
    validate_target,
)
from app.source_analysis_v3_hardened_win004.handles import inspect_symbolic_refs
from app.source_analysis_v3_hardened_win004.metadata import audit_all_metadata
from app.source_analysis_v3_hardened_win004.payload import (
    assert_schema_identity,
    measure_schema,
)
from app.source_analysis_v3_hardened_win004.preflight import openai_dependency_status
from app.source_analysis_v3_hardened_win004.runner import run_hardened_v3_win004
from app.source_analysis_v3_hardened_win004.validate import interpret_hardened_response
from app.source_analysis_v3_hardened_win004.window import (
    load_candidate_win004,
    verify_win004_identity,
)
from app.source_analysis_v3_second_window.constants import (
    AUTHORIZATION_SCOPE as A22_SCOPE,
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _fake_engine(owned_src: str, transport=None):
    payload = transport or v3_success_transport(owned_src=owned_src)
    return FakeAIEngine(
        script=[
            FakeReply(
                text=json.dumps(payload, ensure_ascii=False),
                parsed=payload,
                finish_reason="end_turn",
                input_tokens=48000,
                output_tokens=2100,
                thinking_tokens=0,
                request_id="fake-a24",
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )


class TestGuards:
    def test_authorization_scope_exact(self):
        with pytest.raises(HardenedV3Win004Error):
            validate_authorization_scope(None)
        with pytest.raises(HardenedV3Win004Error):
            validate_authorization_scope(A21_SCOPE)
        with pytest.raises(HardenedV3Win004Error):
            validate_authorization_scope(A22_SCOPE)
        with pytest.raises(HardenedV3Win004Error):
            validate_authorization_scope("SMALL_V21_V3_SYMBOLIC_WIN001_ONLY")
        assert validate_authorization_scope(AUTHORIZATION_SCOPE) == AUTHORIZATION_SCOPE

    def test_wrong_scope_fails_before_network(self):
        result = run_hardened_v3_win004(
            "fixture",
            dry_run=True,
            authorization_scope="WRONG",
        )
        assert result.accepted is False
        assert result.blocked_precall is True
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0

    def test_win004_only_guard(self):
        for window_id in ("WIN001", "WIN002", "WIN003", "WIN005", "WIN006", "WIN007"):
            with pytest.raises(HardenedV3Win004Error):
                validate_target(window_id)
            result = run_hardened_v3_win004(
                "fixture",
                dry_run=True,
                authorization_scope=AUTHORIZATION_SCOPE,
                window_id=window_id,
            )
            assert result.accepted is False
            assert result.engine_generate_attempts == 0

    def test_win001_rejection(self):
        with pytest.raises(HardenedV3Win004Error):
            validate_target("WIN001")

    def test_provider_guard(self):
        with pytest.raises(HardenedV3Win004Error):
            validate_provider(provider="openai", model="claude-sonnet-5")
        with pytest.raises(HardenedV3Win004Error):
            validate_provider(provider="anthropic", model="claude-opus-4")
        validate_provider(provider="anthropic", model="claude-sonnet-5")


class TestIdentityAndSchema:
    def test_openai_is_present(self):
        status = openai_dependency_status()
        assert status["intended_dependency"] is True
        assert status["present_in_active_venv"] is True
        assert status["production_semantics_changed"] is False

    def test_schema_identity(self):
        measured = measure_schema()
        assert measured["raw_bytes"] == 588
        assert measured["adapted_bytes"] == 650
        assert measured["raw_hash"] == EXPECTED_SCHEMA_HASH
        assert measured["raw_hash"] == semantic_transport_v3_fingerprint()
        assert_schema_identity(measured)

    def test_prompt_1_3_2_identity_and_historical_immutability(self):
        v13 = build_window_system_prompt_v13("en")
        v131 = build_window_system_prompt_v131("en")
        v132 = build_window_system_prompt_v132("en")
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V13 == "window-analysis-1.3"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V131 == "window-analysis-1.3.1"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V132 == "window-analysis-1.3.2"
        assert "Never use \"example\" as an IDEA kind" in v132
        assert "Never use \"example\" as an IDEA kind" not in v131
        assert "Never use \"example\" as an IDEA kind" not in v13
        assert "case-sensitive" in v131.lower()
        assert "case-sensitive" in v132.lower()
        assert "empty only if no local IDEA exists" in v13
        assert "empty only if no local IDEA exists" not in v131
        assert "empty only if no local IDEA exists" not in v132

    def test_prompt_and_signature_identity(self):
        bundle = load_candidate_win004()
        identity = verify_win004_identity(bundle)
        assert identity["analysis_signature"] == EXPECTED_ANALYSIS_SIGNATURE
        assert identity["forensic_identity"] == EXPECTED_FORENSIC_IDENTITY
        assert identity["analysis_signature"] != A21_SIGNATURE
        assert identity["analysis_signature"] != A19_SIGNATURE
        assert identity["analysis_signature"] != A22_SIGNATURE
        assert identity["owned_src_count"] == EXPECTED_OWNED_SRC_COUNT
        assert identity["word_count"] == EXPECTED_WORD_COUNT
        assert identity["input_hash"] == EXPECTED_WINDOW_INPUT_HASH
        assert identity["context_src_count"] == 0
        assert identity["cache"] == "MISS"
        assert identity["local_input_estimate"] == EXPECTED_LOCAL_INPUT_ESTIMATE
        assert identity["prompt_version"] == "window-analysis-1.3.2"
        assert identity["prompt_sha256"] == EXPECTED_PROMPT_SHA256
        assert identity["same_a22_ownership"] is True
        assert identity["same_a22_clean"] is True

    def test_clean_identity(self):
        bundle = load_candidate_win004()
        identity = verify_win004_identity(bundle)
        assert identity["clean_sha256"] == identity["clean_file_sha256"]
        assert list(bundle["window"].owned_src_refs) == list(
            bundle["a22_window"].owned_src_refs
        )
        assert bundle["window"].input_hash == bundle["a22_window"].input_hash


class TestDryRunAndFakeExecute:
    def test_dry_run_zero_provider_and_retry_disabled(self, tmp_path):
        result = run_hardened_v3_win004(
            "pastoral_retreat_v2_validation",
            dry_run=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            window_id=WINDOW_ID,
            artifact_sortie_dir=tmp_path,
            write_artifacts=True,
            tests="offline",
        )
        assert result.accepted is True
        assert result.mode == "DRY_RUN"
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0
        assert result.preflight["analysis_signature"] == EXPECTED_ANALYSIS_SIGNATURE
        assert result.preflight["thinking_mode"] == "disabled"
        assert result.preflight["effort"] is None
        assert result.preflight["budget_tokens"] is None
        assert result.preflight["task_budget"] is None
        assert result.preflight["retry"]["auto_retry"] is False
        assert result.preflight["retry"]["max_attempts"] == 1
        assert result.preflight["timeouts"]["read_timeout_seconds"] == 1800.0
        assert result.preflight["timeouts"]["connect_timeout_seconds"] == 30.0
        assert result.preflight["timeouts"]["historical_7200_used"] is False
        assert result.preflight["dry_run_twice"]["deterministic"] is True
        assert (
            result.preflight["dry_run_twice"]["first"]
            == result.preflight["dry_run_twice"]["second"]
        )
        assert result.preflight["prompt_version"] == "window-analysis-1.3.2"
        assert (
            tmp_path
            / "pastoral_retreat_v2_validation"
            / "audit"
            / "source_analysis_v3_hardened_win004_preflight.json"
        ).is_file()

    def test_fake_execute_one_generate_and_isolation(self, tmp_path):
        bundle = load_candidate_win004()
        owned = bundle["window"].owned_src_refs[0]
        engine = _fake_engine(owned)
        result = run_hardened_v3_win004(
            "pastoral_retreat_v2_validation",
            dry_run=False,
            execute_real=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            window_id=WINDOW_ID,
            engine=engine,
            allow_real_provider=False,
            artifact_sortie_dir=tmp_path,
            write_artifacts=True,
        )
        assert result.engine_generate_attempts == 1
        assert result.anthropic_post_attempts == 0
        assert result.execution["structured_parse"] == "PASS"
        assert result.execution["v3_decoder"] == "PASS"
        assert result.execution["handle_registry"] == "PASS"
        assert result.execution["handle_resolution"] == "PASS"
        assert result.execution["v3_validator"] == "PASS"
        assert result.execution["capacity_signal"] == "absent"
        assert result.execution["thinking_tokens"] == 0
        assert result.execution["src_forensic"]["src_success"] is True
        assert result.execution["src_forensic"]["malformed_src"] == 0
        assert result.execution["handle_gate"]["numeric_link_regression"] == "NO"
        assert result.execution["idea_kind_example"] == 0
        assert result.execution["other_windows_authorized"] is False
        assert result.execution["source_map"] == "NOT PUBLISHED"
        assert result.execution["production_default"] == "window-planner-v2.0"
        assert not (
            tmp_path / "pastoral_retreat_v2_validation" / "analysis" / "windows" / "WIN004"
        ).exists()
        assert not (
            tmp_path / "pastoral_retreat_v2_validation" / "analysis" / "source_map.json"
        ).exists()

    def test_one_attempt_guard(self):
        engine = FakeAIEngine(
            script=[FakeReply(text="{}", parsed={}, finish_reason="stop")] * 2,
            retry_policy=no_delay_policy(max_attempts=1),
        )
        guard = OneShotCallGuard(max_calls=1)
        request = AIRequest(prompt="x")
        guard.guarded_generate(engine, request)
        with pytest.raises(MaxRealCallsExceededError):
            guard.guarded_generate(engine, request)


class TestSrcContract:
    def _window(self):
        return load_candidate_win004()["window"]

    def _base(self):
        owned = self._window().owned_src_refs[0]
        return v3_success_transport(owned_src=owned)

    def test_strict_src_case_and_width(self):
        payload = self._base()
        payload["records"][0]["s"] = ["SRc003607"]
        result = interpret_hardened_response(payload, window=self._window())
        assert result["src_forensic"]["wrong_case_src"] >= 1
        assert result["src_forensic"]["src_success"] is False
        assert classify_src_token("SRc003607") == "wrong_case"
        payload2 = self._base()
        payload2["records"][0]["s"] = ["SRC3607"]
        result2 = interpret_hardened_response(payload2, window=self._window())
        assert result2["src_forensic"]["malformed_src"] >= 1

    def test_unknown_and_out_of_window_and_duplicate(self):
        payload = self._base()
        payload["records"][0]["s"] = ["SRC999999"]
        unknown = interpret_hardened_response(payload, window=self._window())
        assert unknown["src_forensic"]["unknown_src"] >= 1
        payload2 = self._base()
        owned = self._window().owned_src_refs[0]
        payload2["records"][0]["s"] = [owned, owned]
        dup = interpret_hardened_response(payload2, window=self._window())
        assert dup["src_forensic"]["duplicate_src"] >= 1

    def test_example_optional_association_policy(self):
        payload = self._base()
        example = next(item for item in payload["records"] if item["k"] == "EXAMPLE")
        example["l"] = []
        result = interpret_hardened_response(payload, window=self._window())
        assert result["v3_decoder"] == "PASS"
        assert result["v3_validator"] == "PASS"
        assert result["example_policy"] == "B_OPTIONAL_ASSOCIATION_CANONICAL"


class TestIdeaExampleContract:
    def _window(self):
        return load_candidate_win004()["window"]

    def _base(self):
        owned = self._window().owned_src_refs[0]
        return v3_success_transport(owned_src=owned)

    def test_idea_valid_vocabulary(self):
        payload = self._base()
        audit = audit_all_metadata(payload)
        assert audit["idea_kind_example"] == 0
        assert audit["metadata_vocabulary_pass"] is True
        result = interpret_hardened_response(payload, window=self._window())
        assert result["metadata"]["idea_kind_example"] == 0

    def test_idea_example_rejection(self):
        payload = self._base()
        payload["records"][1]["m"] = ["example", "supporting"]
        audit = audit_all_metadata(payload)
        assert audit["idea_kind_example"] == 1
        assert audit["metadata_vocabulary_pass"] is False
        result = interpret_hardened_response(payload, window=self._window())
        assert result["metadata"]["idea_kind_example"] == 1

    def test_example_example_acceptance(self):
        payload = self._base()
        example = next(item for item in payload["records"] if item["k"] == "EXAMPLE")
        example["m"] = ["example"]
        audit = audit_all_metadata(payload)
        assert audit["metadata_vocabulary_pass"] is True
        assert audit["other_metadata_violation_count"] == 0

    def test_idea_example_separation_fixture(self):
        payload = self._base()
        payload["records"][1]["v"] = "Coercive power can demand a shirt."
        payload["records"][1]["m"] = ["claim", "supporting"]
        example = next(item for item in payload["records"] if item["k"] == "EXAMPLE")
        example["v"] = "A tutor says I like that shirt."
        example["m"] = ["anecdote"]
        audit = audit_all_metadata(payload)
        assert audit["idea_kind_example"] == 0
        assert audit["metadata_vocabulary_pass"] is True


class TestHandleFailures:
    def _window(self):
        return load_candidate_win004()["window"]

    def _base(self):
        owned = self._window().owned_src_refs[0]
        return v3_success_transport(owned_src=owned)

    def test_unknown_handle_failure(self):
        payload = self._base()
        payload["records"][1]["l"] = ["T99"]
        result = interpret_hardened_response(payload, window=self._window())
        assert result["handles"]["counts"]["unknown"] >= 1 or result["handle_resolution"] == "FAIL"

    def test_wrong_kind_failure(self):
        payload = self._base()
        payload["records"][4]["l"] = ["T1"]
        metrics = inspect_symbolic_refs(payload)
        assert metrics["counts"]["wrong_kind"] >= 1
        result = interpret_hardened_response(payload, window=self._window())
        assert result["v3_validator"] == "FAIL" or result["handle_resolution"] == "FAIL"

    def test_duplicate_owner_failure(self):
        payload = self._base()
        payload["records"][0]["h"] = "T1"
        payload["records"].append(deepcopy(payload["records"][0]))
        metrics = inspect_symbolic_refs(payload)
        assert metrics["counts"]["duplicate_owners"] >= 1
        result = interpret_hardened_response(payload, window=self._window())
        assert result["handle_registry"] == "FAIL"

    def test_numeric_link_regression_rejection(self):
        payload = self._base()
        payload["records"][1]["l"] = [0]
        metrics = inspect_symbolic_refs(payload)
        assert metrics["numeric_link_regression"] == "YES"
        result = interpret_hardened_response(payload, window=self._window())
        assert result["v3_decoder"] == "FAIL" or result["handle_gate"]["numeric_link_regression"] == "YES"


class TestPhaseConstantsAndIsolation:
    def test_phase_and_scope(self):
        assert PHASE == "3B.7.7A.24"
        assert AUTHORIZATION_SCOPE == "SMALL_V21_V3_HARDENED_WIN004_ONLY"
        assert WINDOW_ID == "WIN004"
        assert PLANNER_VERSION == "window-planner-v2.0"
        assert not source_map_path("pastoral_retreat_v2_validation").is_file()

    def test_production_isolation(self):
        analyzer = Path(r"C:\TranscriptionAI\app\source_analysis\analyzer.py")
        text = analyzer.read_text(encoding="utf-8")
        assert "source_analysis_v3_hardened_win004" not in text
        main = Path(r"C:\TranscriptionAI\main.py")
        if main.is_file():
            assert "source_analysis_v3_hardened_win004" not in main.read_text(
                encoding="utf-8"
            )
