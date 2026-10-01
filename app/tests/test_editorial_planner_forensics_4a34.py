"""Phase 4A.3.4 — offline silent-omission forensics. 0 réseau réel."""

from __future__ import annotations

import json

import pytest

from app.editorial_planner_forensics_4a34.constants import (
    A3_CANDIDATE_SHA256,
    A33_CANDIDATE_SHA256,
    A33_REQUEST_SHA256,
    ADAPTED_SCHEMA_SHA256,
    AUTHORIZATION_SCOPE,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SOURCE_MAP_SHA256,
    HISTORICAL_PROMPT,
    MAX_ANTHROPIC_POST,
    MAX_ENGINE_GENERATE,
    MAX_OUTPUT_TOKENS,
    PUBLICATION_AUTHORIZED,
    RAW_SCHEMA_BYTES,
    REAL_PROVIDER_CALLS,
    SUCCESSOR_PROMPT,
    TRANSPORT_VERSION,
)
from app.editorial_planner_forensics_4a34.coverage_stress import run_coverage_stress
from app.editorial_planner_forensics_4a34.guard import (
    assert_no_book_generator,
    assert_offline_package,
    assert_phase3b_untouched,
)
from app.editorial_planner_forensics_4a34.identity import (
    compare_historical_prompt,
    compare_schema,
    file_sha256,
)
from app.editorial_planner_forensics_4a34.paths import (
    a3_candidate_path,
    a33_candidate_path,
    a33_raw_path,
    production_editorial_plan_path,
    production_source_map_path,
    repo_root,
)
from app.editorial_planner_forensics_4a34.payload import (
    build_production_payload,
    build_production_request,
)
from app.editorial_planner_forensics_4a34.runner import run_preflight
from app.editorial_planner_language_policy_4a32.language import load_language_provenance
from app.editorial_planning.constants import PUBLICATION_AUTHORIZED as PLANNER_PUBLICATION
from app.editorial_planning.guard import assert_offline_package as planner_offline
from app.editorial_planning.language_policy import SUCCESSOR_PROMPT_VERSION
from app.editorial_planning.pipeline import load_published_source_map
from app.editorial_planning.prompt import prompt_bundle as prompt_10
from app.editorial_planning.prompt_v101 import prompt_bundle as prompt_101
from app.editorial_planning.prompt_v102 import prompt_bundle as prompt_102
from app.editorial_planning.schema import (
    build_editorial_plan_transport_schema,
    schema_identity,
)
from app.editorial_planning.writer import editorial_plan_path
from app.file_utils import content_hash


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOfflineGuards:
    def test_offline_and_phase3b_untouched(self):
        assert_offline_package()
        assert_phase3b_untouched()
        assert_no_book_generator()
        planner_offline()
        assert PUBLICATION_AUTHORIZED is False
        assert PLANNER_PUBLICATION is False
        assert REAL_PROVIDER_CALLS == 0
        assert MAX_ENGINE_GENERATE == 0
        assert MAX_ANTHROPIC_POST == 0
        assert HISTORICAL_PROMPT == "editorial-planner-1.0"
        assert SUCCESSOR_PROMPT_VERSION == "editorial-planner-1.0.1"
        assert SUCCESSOR_PROMPT == "editorial-planner-1.0.2"
        assert TRANSPORT_VERSION == "editorial-plan-transport-1.0"
        assert MAX_OUTPUT_TOKENS == 65536


class TestContracts:
    def test_schema_identity_unchanged(self):
        schema = compare_schema()
        live = schema_identity()
        assert schema["identity"] == "MATCH"
        assert schema["schema_changed"] == "NO"
        assert live["raw_schema_bytes"] == RAW_SCHEMA_BYTES == 3661
        assert live["adapted_schema_bytes"] == 3909
        assert live["adapted_schema_sha256"] == ADAPTED_SCHEMA_SHA256
        assert schema["new_grammar_canary_required"] == "NO"
        encoded = json.dumps(
            build_editorial_plan_transport_schema(), ensure_ascii=False
        )
        assert "IDEA001" not in encoded

    def test_historical_prompts_unchanged(self):
        prompt = compare_historical_prompt()
        assert prompt["identity"] == "MATCH"
        assert prompt["historical_prompt_mutated"] == "NO"
        v10 = prompt_10()
        v101 = prompt_101("en")
        v102 = prompt_102("en")
        assert v10["version"] == "editorial-planner-1.0"
        assert v101["version"] == "editorial-planner-1.0.1"
        assert v102["version"] == "editorial-planner-1.0.2"
        assert v10["prompt_sha256"] != v101["prompt_sha256"]
        assert v101["prompt_sha256"] != v102["prompt_sha256"]
        assert "COMPLETUDE EXHAUSTIVE DES IDEA" in v102["system"]
        assert "IDEA007" not in v102["system"]
        assert "IDEA008" not in v102["instructions"]
        assert "LANGUE DE SORTIE OBLIGATOIRE" in v102["system"]

    def test_historical_artifacts_unchanged(self):
        candidate = a33_candidate_path(root=repo_root())
        a3 = a3_candidate_path(root=repo_root())
        raw = a33_raw_path(root=repo_root())
        source = production_source_map_path(root=repo_root())
        if not candidate.is_file():
            pytest.skip("A.3.3 candidate absent")
        assert file_sha256(candidate) == A33_CANDIDATE_SHA256
        assert file_sha256(a3) == A3_CANDIDATE_SHA256
        assert file_sha256(source) == EXPECTED_SOURCE_MAP_SHA256
        assert raw.is_file()
        assert "IDEA007" not in json.loads(raw.read_text(encoding="utf-8")).get(
            "text", ""
        )
        assert not production_editorial_plan_path(root=repo_root()).is_file()


class TestRequestAndCoverage:
    def test_current_project_resolves_to_en(self):
        source_map, *_rest = load_published_source_map("pastoral_retreat_v2_validation")
        provenance = load_language_provenance(source_map)
        assert provenance["canonical_document_language"] == "en"

    def test_future_request_deterministic_and_differs_from_a33(self):
        source_map, *_rest = load_published_source_map("pastoral_retreat_v2_validation")
        first = build_production_payload(
            source_map, canonical_document_language="en"
        )
        second = build_production_payload(
            source_map, canonical_document_language="en"
        )
        assert first == second
        assert first["model"] == "claude-opus-5"
        assert first["max_tokens"] == 65536
        assert "thinking" not in first
        request = build_production_request(
            source_map, canonical_document_language="en"
        )
        assert request.thinking_mode == "provider_default"
        assert request.metadata["prompt_version"] == "editorial-planner-1.0.2"
        assert request.metadata["expected_idea_count"] == 286
        blob = json.dumps(first, ensure_ascii=False)
        assert "x-api-key" not in blob
        assert "sk-ant-" not in blob
        assert "EXPECTED_IDEA_COUNT\n286\n" in request.prompt
        assert "CANONICAL_DOCUMENT_LANGUAGE\nen\n" in request.prompt
        assert "IDEA007" in request.prompt
        assert "IDEA008" in request.prompt
        encoded = json.dumps(first, ensure_ascii=False, separators=(",", ":"))
        digest = content_hash(encoded)
        assert digest != A33_REQUEST_SHA256

    def test_fakeai_coverage_stress_on_production_source_map(self):
        source_map, *_rest = load_published_source_map("pastoral_retreat_v2_validation")
        result = run_coverage_stress(source_map)
        assert result["idea_count"] == EXPECTED_IDEA_COUNT
        assert result["status"] == "PASS"
        by_name = {row["scenario"]: row for row in result["scenarios"]}
        assert by_name["286_assigned"]["validation_status"] != "FAIL"
        assert by_name["285_assigned_1_deferred"]["validation_status"] != "FAIL"
        assert by_name["285_assigned_1_excluded"]["validation_status"] != "FAIL"
        assert by_name["284_assigned_2_omitted"]["validation_status"] == "FAIL"
        assert by_name["duplicate_disposition"]["validation_status"] == "FAIL"
        assert by_name["unknown_idea"]["validation_status"] == "FAIL"
        assert by_name["reuse_plus_primary"]["validation_status"] != "FAIL"
        assert by_name["shuffled_complete_coverage"]["validation_status"] != "FAIL"
        assert "IDEA007" in by_name["284_assigned_2_omitted"]["empty_disposition_ids"]
        assert "IDEA008" in by_name["284_assigned_2_omitted"]["empty_disposition_ids"]


class TestCli:
    def test_cli_rejects_execute_real(self):
        from app.editorial_planner_forensics_4a34.__main__ import main

        assert main(["--execute-real"]) == 2
        assert main(["--authorization-scope", "wrong", "--dry-run"]) == 2


class TestPreflightRun:
    def test_run_writes_audits_without_publication_or_provider(self, tmp_path):
        bundle = run_preflight(
            tests="offline 4A.3.4 unit",
            test_delta={"new_failure_count": 0},
            write_artifacts=True,
            root=tmp_path,
        )
        header = bundle["header"]
        assert header["real_provider_calls"] == 0
        assert header["engine_generate_called"] is False
        assert header["anthropic_post_called"] is False
        assert header["editorial_plan_json"] == "NOT PUBLISHED"
        assert header["a33_historical_status"] == "FAIL"
        assert header["idea007_present_in_request"] == "YES"
        assert header["idea008_present_in_request"] == "YES"
        assert header["request_input_defect"] == "NO"
        assert header["output_cap_failure"] == "NO"
        assert header["transport_defect"] == "NO"
        assert header["schema_defect"] == "NO"
        assert header["validator_defect"] == "NO"
        assert header["prompt_coverage_weakness"] == "YES"
        assert header["provider_compliance_failure"] == "YES"
        assert header["primary_root_cause"] == "PROVIDER_COMPLIANCE_FAILURE"
        assert header["successor_prompt"] == "editorial-planner-1.0.2"
        assert header["schema_changed"] == "NO"
        assert header["new_grammar_canary_required"] == "NO"
        assert header["new_synthetic_contract_canary_required"] == "NO"
        assert header["future_canonical_language"] == "en"
        assert header["future_max_output"] == 65536
        assert header["future_request_determinism"] == "PASS"
        assert header["future_idea_input_coverage"] == f"{EXPECTED_IDEA_COUNT} / 286"
        assert header["context_safety"] == "PASS"
        assert header["fakeai_coverage_stress"] == "PASS"
        assert header["ready_for_editorial_plan_publication"] == "NO"
        assert header["result"] == "PASS"
        assert header["ready_for_one_final_controlled_editorial_planner_canary"] == "YES"
        assert header["future_exact_request_sha256"] != A33_REQUEST_SHA256
        assert not editorial_plan_path(
            "pastoral_retreat_v2_validation", sortie_dir=tmp_path
        ).is_file()
        audit_dir = tmp_path / "audit" / "editorial_planner_omission_forensics_4a34"
        assert (audit_dir / "editorial_planner_4a34_omission_forensics.json").is_file()
        assert (audit_dir / "editorial_planner_4a34_IDEA007_forensics.json").is_file()
        assert (audit_dir / "editorial_planner_4a34_IDEA008_forensics.json").is_file()
        assert (audit_dir / "editorial_planner_post_4a34_readiness.json").is_file()
        assert AUTHORIZATION_SCOPE.endswith("OFFLINE_SILENT_OMISSION_FORENSICS_ONLY")
        assert bundle["a33_candidate"]["sha256"] == A33_CANDIDATE_SHA256
        assert bundle["coverage"]["idea_count"] == 286
        assert bundle["coverage_stress"]["status"] == "PASS"
