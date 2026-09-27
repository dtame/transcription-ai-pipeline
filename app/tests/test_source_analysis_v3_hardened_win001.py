"""Phase 3B.7.7A.21 — FakeAI / offline guards. 0 réseau réel."""

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
)
from app.source_analysis_local_v3.fixtures import v3_success_transport
from app.source_analysis_local_v3.prompt import (
    build_window_system_prompt_v13,
    build_window_system_prompt_v131,
)
from app.source_analysis_local_v3.schema import semantic_transport_v3_fingerprint
from app.source_analysis_local_v3.source_refs import classify_src_token
from app.source_analysis_v2_a15_forensics.constants import A15_SIGNATURE
from app.source_analysis_v3_a19_forensics.constants import A19_SIGNATURE
from app.source_analysis_v3_hardened_win001.constants import (
    AUTHORIZATION_SCOPE,
    EXPECTED_ANALYSIS_SIGNATURE,
    EXPECTED_FORENSIC_IDENTITY,
    EXPECTED_LOCAL_INPUT_ESTIMATE,
    EXPECTED_OWNED_SRC_COUNT,
    EXPECTED_SCHEMA_HASH,
    EXPECTED_WINDOW_INPUT_HASH,
    EXPECTED_WORD_COUNT,
    PHASE,
    WINDOW_ID,
)
from app.source_analysis_v3_hardened_win001.guard import (
    HardenedV3Win001Error,
    OneShotCallGuard,
    validate_authorization_scope,
    validate_provider,
    validate_target,
)
from app.source_analysis_v3_hardened_win001.handles import inspect_symbolic_refs
from app.source_analysis_v3_hardened_win001.payload import (
    assert_schema_identity,
    measure_schema,
)
from app.source_analysis_v3_hardened_win001.preflight import openai_dependency_status
from app.source_analysis_v3_hardened_win001.runner import run_hardened_v3_win001
from app.source_analysis_v3_hardened_win001.validate import interpret_hardened_response
from app.source_analysis_v3_hardened_win001.window import (
    load_candidate_win001,
    verify_win001_identity,
)
from app.source_analysis_v3_real_win001.constants import (
    AUTHORIZATION_SCOPE as A19_SCOPE,
)
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    AUTHORIZATION_SCOPE as A18_SCOPE,
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
                request_id="fake-a21",
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )


class TestGuards:
    def test_authorization_scope_exact(self):
        with pytest.raises(HardenedV3Win001Error):
            validate_authorization_scope(None)
        with pytest.raises(HardenedV3Win001Error):
            validate_authorization_scope("SMALL_V21_V3_SYMBOLIC_WIN001_ONLY")
        with pytest.raises(HardenedV3Win001Error):
            validate_authorization_scope(A19_SCOPE)
        with pytest.raises(HardenedV3Win001Error):
            validate_authorization_scope(A18_SCOPE)
        assert validate_authorization_scope(AUTHORIZATION_SCOPE) == AUTHORIZATION_SCOPE

    def test_wrong_scope_fails_before_network(self):
        result = run_hardened_v3_win001(
            "fixture",
            dry_run=True,
            authorization_scope="WRONG",
        )
        assert result.accepted is False
        assert result.blocked_precall is True
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0

    def test_win001_only_guard(self):
        for window_id in ("WIN002", "WIN003", "WIN007", "WIN996"):
            with pytest.raises(HardenedV3Win001Error):
                validate_target(window_id)
            result = run_hardened_v3_win001(
                "fixture",
                dry_run=True,
                authorization_scope=AUTHORIZATION_SCOPE,
                window_id=window_id,
            )
            assert result.accepted is False
            assert result.engine_generate_attempts == 0

    def test_provider_guard(self):
        with pytest.raises(HardenedV3Win001Error):
            validate_provider(provider="openai", model="claude-sonnet-5")
        with pytest.raises(HardenedV3Win001Error):
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

    def test_prompt_1_3_1_identity_and_1_3_immutability(self):
        v13 = build_window_system_prompt_v13("en")
        v131 = build_window_system_prompt_v131("en")
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V13 == "window-analysis-1.3"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V131 == "window-analysis-1.3.1"
        assert "empty only if no local IDEA exists" in v13
        assert "case-sensitive" not in v13.lower()
        assert "case-sensitive" in v131.lower()
        assert "zero padding" in v131.lower()
        assert "from its number" in v131.lower()
        assert "empty only if no local IDEA exists" not in v131

    def test_prompt_and_signature_identity(self):
        bundle = load_candidate_win001()
        identity = verify_win001_identity(bundle)
        assert identity["analysis_signature"] == EXPECTED_ANALYSIS_SIGNATURE
        assert identity["forensic_identity"] == EXPECTED_FORENSIC_IDENTITY
        assert identity["analysis_signature"] != A15_SIGNATURE
        assert identity["analysis_signature"] != A19_SIGNATURE
        assert identity["owned_src_count"] == EXPECTED_OWNED_SRC_COUNT
        assert identity["word_count"] == EXPECTED_WORD_COUNT
        assert identity["input_hash"] == EXPECTED_WINDOW_INPUT_HASH
        assert identity["context_src_count"] == 0
        assert identity["cache"] == "MISS"
        assert identity["local_input_estimate"] == EXPECTED_LOCAL_INPUT_ESTIMATE
        assert identity["prompt_version"] == "window-analysis-1.3.1"
        assert identity["same_a19_ownership"] is True

    def test_clean_identity(self):
        bundle = load_candidate_win001()
        identity = verify_win001_identity(bundle)
        assert identity["clean_sha256"] == identity["clean_file_sha256"]
        assert list(bundle["window"].owned_src_refs) == list(
            bundle["a19_window"].owned_src_refs
        )


class TestDryRunAndFakeExecute:
    def test_dry_run_zero_provider_and_retry_disabled(self, tmp_path):
        result = run_hardened_v3_win001(
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
        assert (
            tmp_path
            / "pastoral_retreat_v2_validation"
            / "audit"
            / "source_analysis_v3_hardened_win001_preflight.json"
        ).is_file()

    def test_fake_execute_one_generate_and_isolation(self, tmp_path):
        bundle = load_candidate_win001()
        owned = bundle["window"].owned_src_refs[0]
        engine = _fake_engine(owned)
        result = run_hardened_v3_win001(
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
        assert result.execution["win002_authorized"] is False
        assert result.execution["source_map"] == "NOT PUBLISHED"
        assert result.execution["production_default"] == "window-planner-v2.0"
        assert not (
            tmp_path / "pastoral_retreat_v2_validation" / "analysis" / "windows" / "WIN001"
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
        return load_candidate_win001()["window"]

    def _base(self):
        owned = self._window().owned_src_refs[0]
        return v3_success_transport(owned_src=owned)

    def test_strict_src_case_and_width(self):
        payload = self._base()
        payload["records"][0]["s"] = ["SRc000609"]
        result = interpret_hardened_response(payload, window=self._window())
        assert result["src_forensic"]["wrong_case_src"] >= 1
        assert result["src_forensic"]["src_success"] is False
        assert classify_src_token("SRc000609") == "wrong_case"
        payload2 = self._base()
        payload2["records"][0]["s"] = ["SRC609"]
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

    def test_no_case_normalization(self):
        payload = self._base()
        payload["records"][0]["s"] = ["SRc000609"]
        result = interpret_hardened_response(payload, window=self._window())
        tokens = [
            row["token"]
            for row in (result["src_audit"].get("wrong_case_refs") or [])
        ]
        assert "SRc000609" in tokens
        assert "SRC000609" not in tokens

    def test_example_optional_association_policy(self):
        payload = self._base()
        example = next(item for item in payload["records"] if item["k"] == "EXAMPLE")
        example["l"] = []
        result = interpret_hardened_response(payload, window=self._window())
        assert result["v3_decoder"] == "PASS"
        assert result["v3_validator"] == "PASS"
        empty_obs = [
            row
            for row in (result["inventory"].get("observations") or [])
            if row.get("code") == "example_empty_link_a19_era_rule_only"
        ]
        assert result["inventory"]["counts"]["example_empty_link_settled"] == 0
        assert empty_obs or result["example_policy"] == "B_OPTIONAL_ASSOCIATION_CANONICAL"


class TestHandleFailures:
    def _window(self):
        return load_candidate_win001()["window"]

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
        assert PHASE == "3B.7.7A.21"
        assert AUTHORIZATION_SCOPE == "SMALL_V21_V3_HARDENED_WIN001_ONLY"
        assert WINDOW_ID == "WIN001"
        assert PLANNER_VERSION == "window-planner-v2.0"
        assert not source_map_path("pastoral_retreat_v2_validation").is_file()

    def test_production_isolation(self):
        analyzer = Path(r"C:\TranscriptionAI\app\source_analysis\analyzer.py")
        text = analyzer.read_text(encoding="utf-8")
        assert "source_analysis_v3_hardened_win001" not in text
        main = Path(r"C:\TranscriptionAI\main.py")
        if main.is_file():
            assert "source_analysis_v3_hardened_win001" not in main.read_text(
                encoding="utf-8"
            )
