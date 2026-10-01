"""Phase 4A.2 — offline exact production preflight. 0 réseau réel."""

from __future__ import annotations

import json

import pytest

from app.editorial_planner_canary_4a1.constants import CANARY_MAX_OUTPUT_TOKENS
from app.editorial_planner_preflight_4a2.constants import (
    ADAPTED_SCHEMA_SHA256,
    AUTHORIZATION_SCOPE,
    EXPECTED_IDEA_COUNT,
    FUTURE_RETRIES,
    MAX_ANTHROPIC_POST,
    MAX_ENGINE_GENERATE,
    MODEL,
    OLD_PROPOSED_MAX_OUTPUT,
    PHASE_4A_HARD_OUTPUT_TOKENS,
    PUBLICATION_AUTHORIZED,
    RAW_SCHEMA_BYTES,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    THINKING_MODE,
)
from app.editorial_planner_preflight_4a2.guard import (
    assert_no_book_generator,
    assert_offline_package,
    assert_phase3b_untouched,
)
from app.editorial_planner_preflight_4a2.identity import (
    compare_prompt,
    compare_schema,
    source_map_identity_audit,
)
from app.editorial_planner_preflight_4a2.payload import (
    build_production_payload,
    build_production_request,
)
from app.editorial_planner_preflight_4a2.runner import run_preflight
from app.editorial_planner_preflight_4a2.scenarios import (
    all_assigned_transport,
    disposition_row_cost,
)
from app.editorial_planning.constants import PUBLICATION_AUTHORIZED as PLANNER_PUBLICATION
from app.editorial_planning.guard import assert_offline_package as planner_offline
from app.editorial_planning.pipeline import load_published_source_map
from app.editorial_planning.writer import editorial_plan_path


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestFrozenContracts:
    def test_offline_and_phase3b_untouched(self):
        assert_offline_package()
        assert_phase3b_untouched()
        assert_no_book_generator()
        planner_offline()
        assert PUBLICATION_AUTHORIZED is False
        assert PLANNER_PUBLICATION is False
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert MAX_ENGINE_GENERATE == 0
        assert MAX_ANTHROPIC_POST == 0
        assert FUTURE_RETRIES == 0
        assert OLD_PROPOSED_MAX_OUTPUT == 16384
        assert PHASE_4A_HARD_OUTPUT_TOKENS == 21644
        assert CANARY_MAX_OUTPUT_TOKENS == 4096

    def test_schema_and_prompt_match_phase4a1(self):
        schema = compare_schema()
        prompt = compare_prompt()
        assert schema["identity"] == "MATCH"
        assert prompt["identity"] == "MATCH"
        assert schema["live"]["raw_schema_bytes"] == RAW_SCHEMA_BYTES == 3661
        assert schema["live"]["adapted_schema_bytes"] == 3909
        assert schema["live"]["adapted_schema_sha256"] == ADAPTED_SCHEMA_SHA256

    def test_source_map_identity(self):
        identity = source_map_identity_audit()
        assert identity["blocked_precall"] is False
        assert identity["hash_match"] is True
        assert identity["bytes_match"] is True
        assert identity["chars_match"] is True
        assert identity["inventory"]["ideas"] == EXPECTED_IDEA_COUNT
        assert identity["canonical_source_map_validation"] == "PASS"
        assert identity["source_map_not_modified"] is True


class TestExactRequest:
    def test_production_request_is_deterministic_and_offline(self):
        source_map, *_rest = load_published_source_map("pastoral_retreat_v2_validation")
        first = build_production_payload(source_map, max_output_tokens=32000)
        second = build_production_payload(source_map, max_output_tokens=32000)
        assert first == second
        assert first["model"] == MODEL
        assert first["max_tokens"] == 32000
        assert "thinking" not in first
        request = build_production_request(source_map, max_output_tokens=32000)
        assert request.thinking_mode == THINKING_MODE
        assert request.effort is None
        assert request.thinking_budget_tokens is None
        blob = json.dumps(first, ensure_ascii=False)
        assert "x-api-key" not in blob
        assert "sk-ant-" not in blob
        assert "WIN001" not in request.prompt
        assert "processed/chunk" not in request.prompt.split("SOURCEMAP_DIGEST_JSON", 1)[-1]
        assert "IDEA286" in request.prompt or "IDEA" in request.prompt

    def test_cli_rejects_execute_real(self):
        from app.editorial_planner_preflight_4a2.__main__ import main

        assert main(["--execute-real"]) == 2
        assert main(["--authorization-scope", "wrong", "--dry-run"]) == 2


class TestDispositionAndFakeAI:
    def test_assigned_is_id_only(self):
        cost = disposition_row_cost()
        assert cost["assigned_reason_required"] is False
        assert cost["deferred_reason_required"] is True
        assert cost["assigned_id_chars"] < cost["deferred_min_chars"]

    def test_all_assigned_covers_286(self):
        source_map, *_rest = load_published_source_map("pastoral_retreat_v2_validation")
        transport = all_assigned_transport(source_map)
        assigned = [
            idea_id
            for chapter in transport["chapters"]
            for section in chapter["sections"]
            for idea_id in section["i"]
        ]
        assert transport["deferred"] == []
        assert transport["excluded"] == []
        assert set(assigned) == {idea.idea_id for idea in source_map.ideas}
        assert len(source_map.ideas) == 286


class TestPreflightRun:
    def test_run_writes_audits_without_publication_or_provider(self, tmp_path):
        bundle = run_preflight(
            tests="offline 4A.2 unit",
            test_delta={"new_failure_count": 0},
            write_artifacts=True,
            root=tmp_path,
        )
        header = bundle["header"]
        assert header["real_provider_calls"] == 0
        assert header["engine_generate_called"] is False
        assert header["anthropic_post_called"] is False
        assert header["editorial_plan_json"] == "NOT PUBLISHED"
        assert header["request_determinism"] == "PASS"
        assert header["schema_identity"] == "MATCH"
        assert header["unknown_input_refs"] == 0
        assert header["idea_input_coverage"] == "286 / 286"
        assert header["fakeai_full_scale_stress"] == "PASS"
        assert header["source_map_mutated"] == "NO"
        assert header["thinking_mode"] == "provider_default"
        assert header["result"] in {"PASS", "FAIL", "BLOCKED"}
        if header["transport_change_required"] == "NO" and header["output_safety"] == "PASS":
            assert header["ready_for_one_real_editorial_planner_canary"] == "YES"
            assert header["new_grammar_canary_required"] == "NO"
        assert header["ready_for_editorial_plan_publication"] == "NO"
        assert bundle["cache"]["a1_cache_cannot_collide"] is True
        assert bundle["stress"]["all_assigned_286"] is True
        assert not editorial_plan_path(
            "pastoral_retreat_v2_validation", sortie_dir=tmp_path
        ).is_file()
        audit_dir = tmp_path / "audit" / "editorial_planner_preflight_4a2"
        assert (audit_dir / "editorial_planner_4a2_exact_request_identity.json").is_file()
        assert (audit_dir / "editorial_planner_post_4a2_readiness.json").is_file()
        assert AUTHORIZATION_SCOPE.endswith("OFFLINE_PRODUCTION_PREFLIGHT_ONLY")
