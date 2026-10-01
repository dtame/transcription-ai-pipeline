"""Phase 4A.3.2 — offline language policy + 1.0.1 preflight. 0 réseau réel."""

from __future__ import annotations

import json

import pytest

from app.editorial_planner_language_policy_4a32.constants import (
    A3_CANDIDATE_SHA256,
    A3_REQUEST_SHA256,
    ADAPTED_SCHEMA_SHA256,
    AUTHORIZATION_SCOPE,
    EXPECTED_IDEA_COUNT,
    EXPECTED_SOURCE_MAP_SHA256,
    HISTORICAL_PROMPT,
    MAX_ANTHROPIC_POST,
    MAX_ENGINE_GENERATE,
    MAX_OUTPUT_TOKENS,
    NEW_PROMPT,
    PUBLICATION_AUTHORIZED,
    RAW_SCHEMA_BYTES,
    REAL_PROVIDER_CALLS,
    TRANSPORT_VERSION,
)
from app.editorial_planner_language_policy_4a32.guard import (
    assert_no_book_generator,
    assert_offline_package,
    assert_phase3b_untouched,
)
from app.editorial_planner_language_policy_4a32.identity import (
    compare_historical_prompt,
    compare_schema,
    file_sha256,
)
from app.editorial_planner_language_policy_4a32.language import load_language_provenance
from app.editorial_planner_language_policy_4a32.paths import (
    a3_candidate_path,
    production_editorial_plan_path,
    production_source_map_path,
    repo_root,
)
from app.editorial_planner_language_policy_4a32.payload import (
    build_production_payload,
    build_production_request,
)
from app.editorial_planner_language_policy_4a32.runner import run_preflight
from app.editorial_planner_preflight_4a2.coverage import input_coverage_audit
from app.editorial_planning.constants import PUBLICATION_AUTHORIZED as PLANNER_PUBLICATION
from app.editorial_planning.guard import assert_offline_package as planner_offline
from app.editorial_planning.pipeline import load_published_source_map
from app.editorial_planning.schema import schema_identity
from app.editorial_planning.writer import editorial_plan_path


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
        assert NEW_PROMPT == "editorial-planner-1.0.1"
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

    def test_historical_prompt_unchanged(self):
        prompt = compare_historical_prompt()
        assert prompt["identity"] == "MATCH"
        assert prompt["historical_prompt_mutated"] == "NO"

    def test_historical_candidate_and_source_map_unchanged(self):
        candidate = a3_candidate_path(root=repo_root())
        source = production_source_map_path(root=repo_root())
        if not candidate.is_file():
            pytest.skip("A.3 candidate absent")
        assert file_sha256(candidate) == A3_CANDIDATE_SHA256
        assert file_sha256(source) == EXPECTED_SOURCE_MAP_SHA256
        assert not production_editorial_plan_path(root=repo_root()).is_file()


class TestProductionLanguageAndRequest:
    def test_current_project_resolves_to_en(self):
        source_map, *_rest = load_published_source_map("pastoral_retreat_v2_validation")
        provenance = load_language_provenance(source_map)
        assert provenance["canonical_document_language"] == "en"
        assert provenance["source_map_primary_language"] == "en"
        assert provenance["blocked"] is False

    def test_request_is_deterministic_differs_from_a3_and_offline(self):
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
        assert request.effort is None
        blob = json.dumps(first, ensure_ascii=False)
        assert "x-api-key" not in blob
        assert "sk-ant-" not in blob
        assert "CANONICAL_DOCUMENT_LANGUAGE\nen\n" in request.prompt
        assert "code « en »" in (request.system_prompt or "")
        encoded = json.dumps(first, ensure_ascii=False, separators=(",", ":"))
        from app.file_utils import content_hash

        digest = content_hash(encoded)
        assert digest != A3_REQUEST_SHA256
        assert "IDEA286" in request.prompt or "IDEA" in request.prompt
        assert "WIN001" not in request.prompt.split("SOURCEMAP_DIGEST_JSON", 1)[-1]

    def test_production_input_covers_all_286_ideas(self):
        source_map, *_rest = load_published_source_map("pastoral_retreat_v2_validation")
        coverage = input_coverage_audit(source_map)
        assert coverage["idea_input_coverage"] == f"{EXPECTED_IDEA_COUNT} / 286"
        assert coverage["idea_count"] == 286
        assert coverage["unknown_input_refs"] == 0
        assert coverage["pass"] is True


class TestCli:
    def test_cli_rejects_execute_real(self):
        from app.editorial_planner_language_policy_4a32.__main__ import main

        assert main(["--execute-real"]) == 2
        assert main(["--authorization-scope", "wrong", "--dry-run"]) == 2


class TestPreflightRun:
    def test_run_writes_audits_without_publication_or_provider(self, tmp_path):
        bundle = run_preflight(
            tests="offline 4A.3.2 unit",
            test_delta={"new_failure_count": 0},
            write_artifacts=True,
            root=tmp_path,
        )
        header = bundle["header"]
        assert header["real_provider_calls"] == 0
        assert header["engine_generate_called"] is False
        assert header["anthropic_post_called"] is False
        assert header["editorial_plan_json"] == "NOT PUBLISHED"
        assert header["canonical_document_language"] == "en"
        assert header["historical_prompt_mutated"] == "NO"
        assert header["schema_changed"] == "NO"
        assert header["new_grammar_canary_required"] == "NO"
        assert header["request_changed"] == "YES"
        assert header["request_determinism"] == "PASS"
        assert header["unknown_refs"] == 0
        assert header["idea_input_coverage"] == f"{EXPECTED_IDEA_COUNT} / 286"
        assert header["max_output"] == 65536
        assert header["context_safety"] == "PASS"
        assert header["ready_for_editorial_plan_publication"] == "NO"
        assert header["result"] == "PASS"
        assert header["ready_for_one_real_english_editorial_planner_canary"] == "YES"
        assert header["new_exact_request_sha256"] != A3_REQUEST_SHA256
        assert not editorial_plan_path(
            "pastoral_retreat_v2_validation", sortie_dir=tmp_path
        ).is_file()
        audit_dir = tmp_path / "audit" / "editorial_planner_language_policy_4a32"
        assert (audit_dir / "editorial_planner_4a32_exact_request_identity.json").is_file()
        assert (audit_dir / "editorial_planner_post_4a32_readiness.json").is_file()
        assert AUTHORIZATION_SCOPE.endswith("OFFLINE_LANGUAGE_POLICY_PREFLIGHT_ONLY")
        assert bundle["candidate"]["sha256"] == A3_CANDIDATE_SHA256
        assert bundle["coverage"]["idea_count"] == 286
