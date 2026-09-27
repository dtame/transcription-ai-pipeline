"""Phase 3B.7.7A.16 — FakeAI / offline. 0 réseau. 0 WIN001 retry."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.source_analysis.ultra_compact_schema import SEMANTIC_TRANSPORT_VERSION
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.constants import (
    SEMANTIC_TRANSPORT_VERSION_V2,
    WINDOW_ANALYSIS_PROMPT_VERSION_V121,
)
from app.source_analysis_local_v2.links import ALLOWED_TARGET_KINDS
from app.source_analysis_local_v2.schema import build_semantic_transport_v2_schema
from app.source_analysis_v2_a15_forensics.constants import (
    A15_INVALID_LINKS,
    A15_RECORDS,
    ADAPTIVE_LOW_JUSTIFIED,
    FUTURE_REAL_CALL_AUTHORIZED,
    MODE,
    NEW_PROMPT_VERSION,
    NEW_TRANSPORT_VERSION,
    PHASE,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_CHANGED,
    SELECTED_LINK_ARCHITECTURE,
    WIN001_RETRY_AUTHORIZED,
)
from app.source_analysis_v2_a15_forensics.evidence import (
    protected_historical_hashes,
    read_a15_raw_bytes,
)
from app.source_analysis_v2_a15_forensics.link_forensics import build_link_forensics
from app.source_analysis_v2_a15_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v2_a15_forensics.prompt_audit import audit_effective_1_2_1_request
from app.source_analysis_v2_a15_forensics.replay import replay_a15_offline
from app.source_analysis_v2_a15_forensics.runner import build_bundle
from app.source_analysis_v2_real_win001.paths import candidate_cache_dir
from app.source_analysis_v2_a15_forensics.constants import A15_SIGNATURE
from app.source_analysis.writer import source_map_path


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOfflineGuards:
    def test_package_is_offline(self):
        assert_offline_package()
        assert_analyzer_not_wired()

    def test_no_provider_or_retry_constants(self):
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_WINDOW_CALLS == 0
        assert WIN001_RETRY_AUTHORIZED is False
        assert FUTURE_REAL_CALL_AUTHORIZED is False
        assert PHASE == "3B.7.7A.16"
        assert MODE == "OFFLINE_A15_INVALID_LINK_FORENSICS_AND_SEMANTIC_REVIEW"


class TestA15Replay:
    def test_exact_replay_parse_decoder_validator(self):
        replay = replay_a15_offline()
        assert replay["structured_parse"] == "PASS"
        assert replay["v2_decoder"] == "FAIL"
        assert replay["v2_validator"] == "FAIL"
        assert replay["record_count"] == A15_RECORDS
        assert replay["link_metrics"]["invalid_targets"] == A15_INVALID_LINKS
        assert replay["reproduced"] is True
        assert replay["response_repaired"] is False
        assert replay["cached"] is False

    def test_raw_bytes_immutable(self):
        raw = read_a15_raw_bytes()
        again = read_a15_raw_bytes()
        assert raw == again
        assert len(raw) == 21328


class TestInvalidLinks:
    def test_exact_invalid_link_count_and_records(self):
        replay = replay_a15_offline()
        forensics = build_link_forensics(replay["transport"])
        assert forensics["invalid_link_count"] == 7
        assert forensics["invalid_record_count"] == 5
        assert forensics["invalid_record_indexes"] == [57, 58, 75, 76, 77]
        assert forensics["self_links"] == 0
        assert forensics["out_of_range_links"] == 0
        table = forensics["invalid_table"]
        assert len(table) == 7
        assert table[0]["record_index"] == 57
        assert table[0]["target_index"] == 1
        assert table[0]["target_kind"] == "TOPIC"
        assert table[1]["target_index"] == 2
        assert table[2]["record_index"] == 58
        assert table[2]["target_index"] == 10
        assert table[3]["target_index"] == 11
        assert table[4]["record_index"] == 75
        assert table[4]["target_index"] == 3
        assert table[5]["record_index"] == 76
        assert table[5]["target_index"] == 4
        assert table[6]["record_index"] == 77
        assert table[6]["target_index"] == 5

    def test_per_kind_compliance(self):
        replay = replay_a15_offline()
        forensics = build_link_forensics(replay["transport"])
        idea = forensics["per_kind_compliance"]["IDEA"]
        rel = forensics["per_kind_compliance"]["RELATION"]
        ex = forensics["per_kind_compliance"]["EXAMPLE"]
        assert idea["valid_links"] == idea["total_links"]
        assert idea["pct"] == 100.0
        assert rel["valid_links"] == 32
        assert rel["total_links"] == 36
        assert rel["pct"] == 88.89
        assert ex["valid_links"] == 2
        assert ex["total_links"] == 5
        assert ex["pct"] == 40.0
        assert forensics["valid_link_analysis"]["idea_understood_topic_targets"] is True

    def test_global_index_vs_per_kind_ordinal(self):
        replay = replay_a15_offline()
        forensics = build_link_forensics(replay["transport"])
        hyp = forensics["hypotheses"]
        assert hyp["global_index"]["valid_relation_uses_global_idea_indexes"] is True
        assert hyp["per_kind_ordinal"]["any_invalid_matches_idea_ordinal_target"] is False
        assert hyp["per_kind_ordinal"]["valid_relation_uses_idea_ordinals"] is False
        assert hyp["conceptual_topic_targets"]["example_76_matches_topic_4_grandmother_and_shares_src"] is True
        assert forensics["arithmetic_vs_semantic"]["invalid_links_are_arithmetic_mistakes"] is False
        assert forensics["arithmetic_vs_semantic"]["model_used_global_indexes_correctly_elsewhere"] is True


class TestPromptAndSchema:
    def test_prompt_1_2_1_compliance_and_conflict(self):
        audit = audit_effective_1_2_1_request()
        assert audit["historical_1_2_1_mutated"] is False
        assert audit["compliance"]["zero_based_target_explicit"] is True
        assert audit["compliance"]["per_kind_target_rules_explicit"] is True
        assert audit["compliance"]["self_link_prohibition_explicit"] is True
        assert audit["compliance"]["relation_rule_correct"] is True
        assert audit["compliance"]["relation_json_example_present"] is False
        assert audit["compliance"]["example_json_example_present"] is True
        assert audit["conflicts"]["old_v1_phrase_present"] is False
        assert audit["conflicts"]["conflicting_passages"] == []
        assert audit["position"]["repeated"] is True
        assert audit["ambiguity_remaining"] is True
        assert audit["schema_audit"]["can_enforce_relation_to_idea"] is False
        assert audit["schema_audit"]["schema_enlarged"] is False

    def test_historical_prompt_and_transport_immutable(self):
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V121 == "window-analysis-1.2.1"
        assert SEMANTIC_TRANSPORT_VERSION_V2 == "semantic-transport-v2"
        assert WINDOW_ANALYSIS_PROMPT_VERSION != WINDOW_ANALYSIS_PROMPT_VERSION_V121
        assert SEMANTIC_TRANSPORT_VERSION != SEMANTIC_TRANSPORT_VERSION_V2
        schema = build_semantic_transport_v2_schema()
        assert schema["properties"]["records"]["items"]["properties"]["l"]["items"]["type"] == "integer"
        assert "enum" not in schema["properties"]["records"]["items"]["properties"]["k"]


class TestIsolationAndDecision:
    def test_no_repair_no_cache_source_map_production(self):
        before = protected_historical_hashes()
        bundle = build_bundle(tests="unit")
        after = protected_historical_hashes()
        assert before == after
        assert bundle["replay"]["response_repaired"] is False
        assert not candidate_cache_dir(PROJECT_NAME, A15_SIGNATURE).exists()
        assert not source_map_path(PROJECT_NAME).is_file()
        assert PRODUCTION_PLANNER_VERSION == PLANNER_VERSION == "window-planner-v2.0"
        assert SCHEMA_CHANGED is False
        assert NEW_PROMPT_VERSION is None
        assert NEW_TRANSPORT_VERSION is None
        assert SELECTED_LINK_ARCHITECTURE == "LOCAL_SYMBOLIC_HANDLES"
        assert ADAPTIVE_LOW_JUSTIFIED is False
        assert ALLOWED_TARGET_KINDS["RELATION"] == frozenset({"IDEA"})
        assert ALLOWED_TARGET_KINDS["EXAMPLE"] == frozenset({"IDEA"})
        assert "TOPIC" not in ALLOWED_TARGET_KINDS["RELATION"]

    def test_coverage_bands_and_gaps(self):
        bundle = build_bundle(tests="unit")
        coverage = bundle["coverage"]
        assert len(coverage["bands"]) == 10
        assert coverage["semantic_src_coverage_pct"] == 19.92
        assert coverage["no_false_100_percent_requirement"] is True
        assert coverage["largest_gaps"]
        assert coverage["output_completeness"]["appears_complete_across_window"] is True
        semantic = bundle["semantic"]
        assert semantic["status"] == "FORENSIC_SEMANTIC_REVIEW_OF_INVALID_TRANSPORT"
        assert semantic["validated_result"] is False
        assert semantic["records_reviewed"] == 92
        assert semantic["grounding_counts"]["UNSUPPORTED"] == 0
        assert semantic["adaptive_low_justified"] is False
        assert semantic["major_idea_coverage"]["never_consume_as_canonical"] is True
        assert bundle["header"]["result"] in {"PASS", "PARTIAL"}
        analyzer = Path(r"C:\TranscriptionAI\app\source_analysis\analyzer.py")
        assert "source_analysis_v2_a15_forensics" not in analyzer.read_text(encoding="utf-8")
