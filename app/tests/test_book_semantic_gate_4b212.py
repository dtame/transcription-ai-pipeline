"""Phase 4B.2.12 — offline Semantic Gate 2.0 contract consolidation. Network forbidden."""

from __future__ import annotations

import json

import pytest

from app.book_generation.pipeline import materialize_chapter
from app.book_generation.writer import production_book_absent
from app.book_semantic_gate_4b23.identity import verify_canonical_inputs
from app.book_semantic_gate_4b23.prompt import instruction_prompt, system_prompt
from app.book_semantic_gate_4b261.candidates import candidate_prompt_bundle
from app.book_semantic_gate_4b271.calibration import candidate_111_prompt_bundle
from app.book_semantic_gate_4b274.contract import candidate_112_prompt_bundle
from app.book_semantic_gate_4b275.contract import candidate_113_prompt_bundle
from app.book_semantic_gate_4b275.constants import (
    EXPECTED_PROMPT_111_SHA256,
    EXPECTED_PROMPT_112_SHA256,
    EXPECTED_PROMPT_113_SHA256,
    EXPECTED_PROMPT_11_SHA256,
    EXPECTED_PROMPT_INSTRUCTIONS_SHA256,
    EXPECTED_PROMPT_SYSTEM_SHA256,
)
from app.book_semantic_gate_4b29.contract import semantic_contract_20_candidate
from app.book_semantic_gate_4b29.coverage import validate_prepared_coverage
from app.book_semantic_gate_4b29.interface import BlockedRemoteTransport
from app.book_semantic_gate_4b29.validator import validate_response_20
from app.file_utils import content_hash
from app.book_semantic_gate_4b210.contract import semantic_contract_201_candidate
from app.book_semantic_gate_4b211.request import paragraph_context
from app.book_semantic_gate_4b211.review import LOCAL_UNITS
from app.book_semantic_gate_4b212.constants import (
    AUTHORIZATION_SCOPE,
    AUTHORIZED_TERRA_CALLS,
    EXPECTED_4B211_RAW_TEXT_SHA256,
    EXPECTED_CLEAN_TRANSCRIPT,
    EXPECTED_EDITORIAL_PLAN,
    EXPECTED_SOURCE_MAP,
    FALLBACKS,
    FIXTURE_KIND,
    HISTORICAL_4B211_STATUS,
    HISTORICAL_H01_STATUS,
    HISTORICAL_H02_STATUS,
    HISTORICAL_H11_STATUS,
    PHASE,
    PROJECT_NAME,
    PROMPT_VERSION_20_ACTIVATED,
    PROMPT_VERSION_20_CANDIDATE,
    PROMPT_VERSION_201_ACTIVATED,
    PROMPT_VERSION_201_CANDIDATE,
    PROMPT_VERSION_202_ACTIVATED,
    PROMPT_VERSION_202_CANDIDATE,
    REAL_TERRA_CANARY_AUTHORIZED,
    REMOTE_STRICT_SCHEMA_COMPATIBILITY,
    RETRIES,
    SELECTED_CASE_HANDLE,
    SEMANTIC_GATE_20_ENABLED,
    SEMANTIC_GATE_202_ENABLED,
    TERRA_EXECUTION_AUTHORIZED,
    TRANSPORT_VERSION_20_ACTIVATED,
)
from app.book_semantic_gate_4b212.contract import semantic_contract_202_candidate
from app.book_semantic_gate_4b212.fakeai import run_negative_fakeai_tests
from app.book_semantic_gate_4b212.forensics import (
    load_historical_raw,
    real_response_forensics,
    schema_mismatch_analysis,
)
from app.book_semantic_gate_4b212.guard import (
    BookSemanticGate212Error,
    assert_offline_only,
    validate_authorization_scope,
)
from app.book_semantic_gate_4b212.policy import apply_acceptance_policy_202
from app.book_semantic_gate_4b212.replay import (
    historical_replay_201,
    historical_semantic_observations,
    synthetic_202_fixture_replay,
)
from app.book_semantic_gate_4b212.runner import run_phase
from app.book_semantic_gate_4b212.safety import provider_safety
from app.book_semantic_gate_4b212.schema_feasibility import strict_schema_feasibility
from app.book_semantic_gate_4b212.validator import validate_response_202


@pytest.fixture(autouse=True)
def _no_network(no_ai_network, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("PROVIDER NETWORK FORBIDDEN")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.Client.send", forbidden)
    return None


class TestPhaseGuards:
    def test_offline_and_historical_statuses(self):
        assert_offline_only()
        assert PHASE == "4B.2.12"
        assert AUTHORIZED_TERRA_CALLS == 0
        assert TERRA_EXECUTION_AUTHORIZED is False
        assert REAL_TERRA_CANARY_AUTHORIZED is False
        assert PROMPT_VERSION_20_ACTIVATED is False
        assert PROMPT_VERSION_201_ACTIVATED is False
        assert PROMPT_VERSION_202_ACTIVATED is False
        assert TRANSPORT_VERSION_20_ACTIVATED is False
        assert SEMANTIC_GATE_20_ENABLED is False
        assert SEMANTIC_GATE_202_ENABLED is False
        assert HISTORICAL_H01_STATUS == "PARTIAL"
        assert HISTORICAL_H02_STATUS == "PARTIAL"
        assert HISTORICAL_H11_STATUS == "PARTIAL"
        assert HISTORICAL_4B211_STATUS == "PARTIAL"
        assert RETRIES == 0
        assert FALLBACKS == 0
        assert PROMPT_VERSION_202_CANDIDATE == "book-semantic-validator-2.0.2-candidate"
        assert PROMPT_VERSION_202_CANDIDATE != PROMPT_VERSION_20_CANDIDATE
        assert PROMPT_VERSION_202_CANDIDATE != PROMPT_VERSION_201_CANDIDATE

    def test_execute_real_rejected_by_cli(self):
        from app.book_semantic_gate_4b212.__main__ import main

        assert main(["--execute-real"]) == 2

    def test_wrong_scope_rejected(self):
        with pytest.raises(BookSemanticGate212Error):
            validate_authorization_scope("wrong")
        result = run_phase(
            authorization_scope=None,
            write_artifacts=False,
            run_tests=False,
        )
        assert result.mode == "REJECTED"


class TestCanonicalAndHistoricalPreservation:
    def test_canonical_artifacts_match_expected(self):
        identities = verify_canonical_inputs()
        assert identities["source_map"]["sha256"] == EXPECTED_SOURCE_MAP
        assert identities["editorial_plan"]["sha256"] == EXPECTED_EDITORIAL_PLAN
        assert identities["clean_transcript"]["sha256"] == EXPECTED_CLEAN_TRANSCRIPT
        assert production_book_absent(PROJECT_NAME)

    def test_historical_contracts_unmodified(self):
        assert content_hash(system_prompt()) == EXPECTED_PROMPT_SYSTEM_SHA256
        assert content_hash(instruction_prompt()) == EXPECTED_PROMPT_INSTRUCTIONS_SHA256
        assert candidate_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_11_SHA256
        assert candidate_111_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_111_SHA256
        assert candidate_112_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_112_SHA256
        assert candidate_113_prompt_bundle()["prompt_sha256"] == EXPECTED_PROMPT_113_SHA256
        frozen_20 = semantic_contract_20_candidate()
        frozen_201 = semantic_contract_201_candidate()
        consolidated = semantic_contract_202_candidate()
        assert frozen_20["candidate_version"] == PROMPT_VERSION_20_CANDIDATE
        assert frozen_201["candidate_version"] == PROMPT_VERSION_201_CANDIDATE
        assert frozen_201["predecessor_2_0_sha256"] == frozen_20["candidate_sha256"]
        assert consolidated["predecessor_2_0_sha256"] == frozen_20["candidate_sha256"]
        assert consolidated["predecessor_2_0_1_sha256"] == frozen_201["candidate_sha256"]
        assert consolidated["candidate_sha256"] != frozen_20["candidate_sha256"]
        assert consolidated["candidate_sha256"] != frozen_201["candidate_sha256"]
        assert consolidated["does_not_overwrite_2_0_candidate"] is True
        assert consolidated["does_not_overwrite_2_0_1_candidate"] is True

    def test_historical_raw_response_unmodified(self):
        saved = load_historical_raw()
        assert content_hash(str(saved.get("text") or "")) == EXPECTED_4B211_RAW_TEXT_SHA256
        assert saved.get("repaired") is False
        assert saved.get("manually_edited") is False
        assert saved.get("parsed", {}).get("pr", [{}])[0].get("v") == "PASS"
        sc = saved.get("parsed", {}).get("sc") or {}
        assert "SUPPORTED" in sc
        assert "supported" not in sc

    def test_historical_labels_unmodified(self):
        assert [item["human_verdict"] for item in LOCAL_UNITS] == ["SUPPORTED"] * 5
        assert LOCAL_UNITS[1]["unit_id"] == "u01"
        assert LOCAL_UNITS[1]["human_verdict"] == "SUPPORTED"


class TestForensicsAndContract:
    def test_anomalies_are_explained_without_repair(self):
        forensics = real_response_forensics()
        mismatch = schema_mismatch_analysis()
        assert forensics["text_sha256_match"] is True
        assert forensics["semantic_elements_correct"]["all_k_supported"] is True
        assert forensics["semantic_elements_correct"]["target_paraphrase_supported"] is True
        assert mismatch["anomaly_a"]["validator_imposes_undocumented_case"] is True
        assert mismatch["anomaly_b"]["instructions_mix_semantic_and_operational"] is True
        assert mismatch["historical_contract_ok"] is False
        assert "PASS" in str(mismatch["anomaly_b"]["received"])

    def test_contract_202_excludes_operational_fields(self):
        consolidated = semantic_contract_202_candidate()
        prompt = consolidated["system_candidate"] + "\n" + consolidated["instructions_candidate"]
        assert consolidated["overfit_tokens_absent_from_candidate"] is True
        assert "human_label" not in prompt.lower()
        assert "Do not require the same words" in prompt
        assert "Do not emit PASS, BLOCK, REVIEW" in prompt or "Do not emit PASS" in prompt
        assert consolidated["operational_decision_excluded_from_model"] is True
        assert "v" not in consolidated["model_emits"]
        assert "sc" not in consolidated["model_emits"]
        example = consolidated["example_json"]
        assert "v" not in example
        assert "sc" not in example
        assert example["pr"][0]["u"][0]["k"] == "SUPPORTED"
        assert "h01" not in prompt.lower()
        assert SELECTED_CASE_HANDLE not in json.dumps(example)


class TestValidatorStrictness:
    def _prepared(self):
        context = paragraph_context()
        return dict(context.get("prepared") or {}), list(context.get("allowed_handles") or [])

    def test_historical_201_still_fails_201_validator(self):
        saved = load_historical_raw()
        prepared, allowed = self._prepared()
        validation = validate_response_20(
            saved.get("parsed"),
            prepared,
            allowed_evidence=allowed,
            expected_chapter="CH016",
        )
        assert validation["ok"] is False
        errors = " ".join(validation.get("errors") or [])
        assert "sc:unexpected_fields" in errors
        assert "pr[0].v:invalid" in errors

    def test_does_not_convert_pass_or_lowercase(self):
        prepared, allowed = self._prepared()
        units = [
            {
                "id": str(unit.get("unit_id") or ""),
                "k": "SUPPORTED",
                "ev": [allowed[0]],
                "r": [],
            }
            for unit in (prepared.get("units") or [])
        ]
        units[0]["k"] = "PASS"
        payload = {"ch": "CH016", "pr": [{"h": "h01", "u": units}]}
        validation = validate_response_202(payload, prepared, allowed_evidence=allowed, expected_chapter="CH016")
        assert validation["ok"] is False
        blob = " ".join(validation.get("errors") or [])
        assert "operational_value_in_semantic_field:PASS" in blob
        assert validation["does_not_convert_pass_to_supported"] is True
        units[0]["k"] = "supported"
        payload = {"ch": "CH016", "pr": [{"h": "h01", "u": units}]}
        lowered = validate_response_202(payload, prepared, allowed_evidence=allowed, expected_chapter="CH016")
        assert lowered["ok"] is False
        assert "invalid_case" in " ".join(lowered.get("errors") or [])

    def test_synthetic_fixture_is_accepted_and_marked(self):
        replay = synthetic_202_fixture_replay()
        assert replay["fixture_kind"] == FIXTURE_KIND
        assert replay["not_a_terra_response"] is True
        assert replay["pass"] is True
        assert replay["acceptance_policy"] == "PASS"
        assert "v" not in replay["fixture"]["payload"]
        assert "sc" not in replay["fixture"]["payload"]


class TestReplayAndPolicy:
    def test_historical_replay_remains_fail_and_block(self):
        replay = historical_replay_201()
        assert replay["contract_validation"] == "FAIL"
        assert replay["acceptance_policy"] == "BLOCK"
        assert replay["pass"] is True
        assert replay["historical_4b211_status_unchanged"] == "PARTIAL"

    def test_semantic_observations_do_not_declare_historical_pass(self):
        observations = historical_semantic_observations()
        assert observations["all_five_supported"] is True
        assert observations["target_recognized"] is True
        assert observations["historical_canary_not_declared_pass"] is True
        assert observations["historical_4b211_status"] == "PARTIAL"
        assert observations["no_false_rejection_observed"] is True

    def test_fakeai_negatives_and_policy(self):
        result = run_negative_fakeai_tests()
        assert result["passed"] is True
        assert result["not_terra"] is True
        by_name = {row["scenario"]: row for row in result["scenarios"]}
        assert by_name["invented_causality"]["decision"] == "BLOCK"
        assert by_name["legitimate_paraphrase"]["decision"] == "PASS"
        assert by_name["questionable"]["decision"] == "REVIEW"
        assert by_name["operational_value_in_semantic_field"]["decision"] == "BLOCK"
        assert by_name["unknown_reason_code"]["decision"] == "BLOCK"
        assert by_name["missing_unit"]["decision"] == "BLOCK"
        assert all(item["blocked"] for item in result["no_silent_normalization"])

    def test_review_does_not_accept_cache(self):
        prepared, allowed = TestValidatorStrictness()._prepared()
        coverage = validate_prepared_coverage(prepared)
        first = str((prepared.get("units") or [{}])[0].get("unit_id") or "u00")
        rows = []
        for unit in prepared.get("units") or []:
            uid = str(unit.get("unit_id") or "")
            if uid == first:
                rows.append(
                    {
                        "id": uid,
                        "k": "QUESTIONABLE",
                        "ev": [allowed[0]],
                        "r": ["OTHER"],
                        "n": "Needs review.",
                    }
                )
            else:
                rows.append({"id": uid, "k": "SUPPORTED", "ev": [allowed[0]], "r": []})
        payload = {"ch": "CH016", "pr": [{"h": "h01", "u": rows}]}
        validation = validate_response_202(payload, prepared, allowed_evidence=allowed, expected_chapter="CH016")
        policy = apply_acceptance_policy_202(prepared, coverage, validation)
        assert validation["ok"] is True
        assert policy["decision"] == "REVIEW"
        assert policy["production_cache_acceptance"] is False
        assert policy["publication_authorized"] is False


class TestSchemaFeasibilityAndSafety:
    def test_strict_schema_is_unverified_and_inactive(self):
        feasibility = strict_schema_feasibility()
        assert feasibility["REMOTE_COMPATIBILITY"] == REMOTE_STRICT_SCHEMA_COMPATIBILITY == "UNVERIFIED"
        assert feasibility["activated"] is False
        assert feasibility["transport_impact"]["keep_existing_transport"] is True
        assert feasibility["provider_calls"] == 0

    def test_provider_safety_blocks_remote(self):
        safety = provider_safety()
        assert safety["ok"] is True
        assert safety["imports_network"] == []
        assert safety["invokes_provider"] == []
        with pytest.raises(Exception):
            BlockedRemoteTransport(provider="openai", model="gpt-5.6-terra")
        assert materialize_chapter.__module__ == "app.book_generation.pipeline"
        assert "book_semantic_gate_4b212" not in (
            __import__("pathlib").Path("app/book_generation/pipeline.py").read_text(
                encoding="utf-8"
            )
        )


class TestPipelineUnchanged:
    def test_book_json_unpublished(self):
        assert production_book_absent(PROJECT_NAME)
        assert AUTHORIZATION_SCOPE.endswith("ONLY")
