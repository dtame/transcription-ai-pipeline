"""Phase 3B.7.7A.22 — FakeAI / offline guards. 0 réseau réel."""

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
from app.source_analysis_v3_hardened_win001.constants import (
    AUTHORIZATION_SCOPE as A21_SCOPE,
    EXPECTED_ANALYSIS_SIGNATURE as A21_SIGNATURE,
)
from app.source_analysis_v3_real_win001.constants import AUTHORIZATION_SCOPE as A19_SCOPE
from app.source_analysis_v3_second_window.constants import (
    AUTHORIZATION_SCOPE,
    CANDIDATE_WINDOW_IDS,
    EXPECTED_SCHEMA_HASH,
    EXPECTED_WIN004_FIRST_OWNED_SRC,
    EXPECTED_WIN004_INPUT_HASH,
    EXPECTED_WIN004_LAST_OWNED_SRC,
    EXPECTED_WIN004_OWNED_SRC_COUNT,
    EXPECTED_WIN004_WORD_COUNT,
    PHASE,
    PREFERRED_WINDOW_ID,
)
from app.source_analysis_v3_second_window.guard import (
    OneShotCallGuard,
    SecondWindowError,
    validate_authorization_scope,
    validate_provider,
    validate_target,
)
from app.source_analysis_v3_second_window.handles import inspect_symbolic_refs
from app.source_analysis_v3_second_window.payload import (
    assert_schema_identity,
    measure_schema,
)
from app.source_analysis_v3_second_window.preflight import openai_dependency_status
from app.source_analysis_v3_second_window.runner import run_second_window_canary
from app.source_analysis_v3_second_window.selection import select_representative_window
from app.source_analysis_v3_second_window.validate import interpret_hardened_response
from app.source_analysis_v3_second_window.window import (
    load_selected_window,
    verify_selected_identity,
)
from app.source_analysis_v3_symbolic_grammar_canary.constants import (
    AUTHORIZATION_SCOPE as A18_SCOPE,
)
from app.source_analysis_execution_strategy.windows import load_clean_transcript


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
                request_id="fake-a22",
            )
        ],
        retry_policy=no_delay_policy(max_attempts=1),
    )


class TestGuards:
    def test_authorization_scope_exact(self):
        with pytest.raises(SecondWindowError):
            validate_authorization_scope(None)
        with pytest.raises(SecondWindowError):
            validate_authorization_scope("SMALL_V21_V3_HARDENED_WIN001_ONLY")
        with pytest.raises(SecondWindowError):
            validate_authorization_scope(A19_SCOPE)
        with pytest.raises(SecondWindowError):
            validate_authorization_scope(A18_SCOPE)
        with pytest.raises(SecondWindowError):
            validate_authorization_scope(A21_SCOPE)
        assert validate_authorization_scope(AUTHORIZATION_SCOPE) == AUTHORIZATION_SCOPE

    def test_wrong_scope_fails_before_network(self):
        result = run_second_window_canary(
            "fixture",
            dry_run=True,
            authorization_scope="WRONG",
        )
        assert result.accepted is False
        assert result.blocked_precall is True
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0

    def test_win001_rejected(self):
        with pytest.raises(SecondWindowError):
            validate_target("WIN001", PREFERRED_WINDOW_ID)
        result = run_second_window_canary(
            "pastoral_retreat_v2_validation",
            dry_run=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            window_id="WIN001",
        )
        assert result.accepted is False
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0

    def test_other_windows_rejected_when_win004_selected(self):
        for window_id in ("WIN002", "WIN003", "WIN005", "WIN006", "WIN007", "WIN996"):
            with pytest.raises(SecondWindowError):
                validate_target(window_id, PREFERRED_WINDOW_ID)
            result = run_second_window_canary(
                "pastoral_retreat_v2_validation",
                dry_run=True,
                authorization_scope=AUTHORIZATION_SCOPE,
                window_id=window_id,
            )
            assert result.accepted is False
            assert result.engine_generate_attempts == 0

    def test_selected_target_binding(self):
        assert validate_target(PREFERRED_WINDOW_ID, PREFERRED_WINDOW_ID) == PREFERRED_WINDOW_ID
        assert validate_target(None, PREFERRED_WINDOW_ID) == PREFERRED_WINDOW_ID

    def test_provider_guard(self):
        with pytest.raises(SecondWindowError):
            validate_provider(provider="openai", model="claude-sonnet-5")
        with pytest.raises(SecondWindowError):
            validate_provider(provider="anthropic", model="claude-opus-4")
        validate_provider(provider="anthropic", model="claude-sonnet-5")


class TestSelection:
    def test_representative_selection_prefers_win004(self):
        transcript = load_clean_transcript("pastoral_retreat_v2_validation")
        first = select_representative_window(transcript)
        second = select_representative_window(transcript)
        assert first["selected_window_id"] == PREFERRED_WINDOW_ID
        assert second["selected_window_id"] == PREFERRED_WINDOW_ID
        assert first["selected"]["src_range"] == second["selected"]["src_range"]
        assert first["win004_used"] is True
        assert first["provider_quality_guess_used"] is False
        ids = {row["window_id"] for row in first["candidate_windows"]}
        assert ids == set(CANDIDATE_WINDOW_IDS)
        assert "WIN001" not in ids


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
        assert "case-sensitive" in v131.lower()
        assert "zero padding" in v131.lower()
        assert "from its number" in v131.lower()
        assert "empty only if no local IDEA exists" not in v131

    def test_source_ownership_and_signature_isolation(self):
        bundle = load_selected_window()
        identity = verify_selected_identity(bundle)
        assert identity["window_id"] == PREFERRED_WINDOW_ID
        assert identity["first_owned_src_ref"] == EXPECTED_WIN004_FIRST_OWNED_SRC
        assert identity["last_owned_src_ref"] == EXPECTED_WIN004_LAST_OWNED_SRC
        assert identity["owned_src_count"] == EXPECTED_WIN004_OWNED_SRC_COUNT
        assert identity["word_count"] == EXPECTED_WIN004_WORD_COUNT
        assert identity["input_hash"] == EXPECTED_WIN004_INPUT_HASH
        assert identity["context_src_count"] == 0
        assert identity["cache"] == "MISS"
        assert identity["local_input_estimate"] <= 35000
        assert identity["prompt_version"] == "window-analysis-1.3.1"
        assert identity["analysis_signature"] != A21_SIGNATURE
        assert identity["differs_from_a21_signature"] is True
        assert identity["differs_from_a21_ownership"] is True


class TestDryRunAndFakeExecute:
    def test_dry_run_zero_provider_and_retry_disabled(self, tmp_path):
        result = run_second_window_canary(
            "pastoral_retreat_v2_validation",
            dry_run=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            window_id=PREFERRED_WINDOW_ID,
            artifact_sortie_dir=tmp_path,
            write_artifacts=True,
            tests="offline",
        )
        assert result.accepted is True
        assert result.mode == "DRY_RUN"
        assert result.engine_generate_attempts == 0
        assert result.anthropic_post_attempts == 0
        assert result.preflight["selected_target"] == PREFERRED_WINDOW_ID
        assert result.preflight["thinking_mode"] == "disabled"
        assert result.preflight["effort"] is None
        assert result.preflight["budget_tokens"] is None
        assert result.preflight["task_budget"] is None
        assert result.preflight["retry"]["auto_retry"] is False
        assert result.preflight["retry"]["max_attempts"] == 1
        assert result.preflight["timeouts"]["read_timeout_seconds"] == 1800.0
        assert result.preflight["timeouts"]["connect_timeout_seconds"] == 30.0
        assert result.preflight["dry_run_twice"]["deterministic"] is True
        assert result.preflight["analysis_signature"] != A21_SIGNATURE
        assert (
            tmp_path
            / "pastoral_retreat_v2_validation"
            / "audit"
            / "source_analysis_v3_second_window_preflight.json"
        ).is_file()
        assert (
            tmp_path
            / "pastoral_retreat_v2_validation"
            / "audit"
            / "source_analysis_v3_second_window_selection.json"
        ).is_file()

    def test_fake_execute_one_generate_and_isolation(self, tmp_path):
        bundle = load_selected_window()
        owned = bundle["window"].owned_src_refs[0]
        engine = _fake_engine(owned)
        result = run_second_window_canary(
            "pastoral_retreat_v2_validation",
            dry_run=False,
            execute_real=True,
            authorization_scope=AUTHORIZATION_SCOPE,
            window_id=PREFERRED_WINDOW_ID,
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
        assert result.execution["handle_gate"]["numeric_link_regression"] == "NO"
        assert result.execution["authorized_target"] == PREFERRED_WINDOW_ID
        assert result.execution["win001_authorized"] is False
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
        return load_selected_window()["window"]

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
        payload3 = self._base()
        payload3["records"][0]["s"] = ["SRC000001"]
        out = interpret_hardened_response(payload3, window=self._window())
        assert out["src_forensic"]["out_of_window_src"] >= 1 or out["src_forensic"]["unknown_src"] >= 1

    def test_example_optional_association_policy(self):
        payload = self._base()
        example = next(item for item in payload["records"] if item["k"] == "EXAMPLE")
        example["l"] = []
        result = interpret_hardened_response(payload, window=self._window())
        assert result["v3_decoder"] == "PASS"
        assert result["v3_validator"] == "PASS"
        assert result["example_policy"] == "B_OPTIONAL_ASSOCIATION_CANONICAL"


class TestHandleFailures:
    def _window(self):
        return load_selected_window()["window"]

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
        assert PHASE == "3B.7.7A.22"
        assert AUTHORIZATION_SCOPE == "SMALL_V21_V3_SECOND_WINDOW_CANARY_ONLY"
        assert PREFERRED_WINDOW_ID == "WIN004"
        assert PLANNER_VERSION == "window-planner-v2.0"
        assert not source_map_path("pastoral_retreat_v2_validation").is_file()

    def test_production_isolation(self):
        analyzer = Path(r"C:\TranscriptionAI\app\source_analysis\analyzer.py")
        text = analyzer.read_text(encoding="utf-8")
        assert "source_analysis_v3_second_window" not in text
        main = Path(r"C:\TranscriptionAI\main.py")
        if main.is_file():
            assert "source_analysis_v3_second_window" not in main.read_text(
                encoding="utf-8"
            )
