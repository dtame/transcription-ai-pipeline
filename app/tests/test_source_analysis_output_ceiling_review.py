"""Phase 3B.7.7A.10 — revue offline. 0 réseau. 0 WIN001."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.source_analysis.publication_isolation import inspect_analysis_directory
from app.source_analysis.writer import source_map_path
from app.source_analysis_output_ceiling_review.constants import (
    CALL_C_THINKING_TOKENS,
    NEW_WIN001_CALLS,
    PHASE,
    PRIMARY_ROOT_CAUSE,
    PROJECT_NAME,
    REAL_PROVIDER_CALL_AUTHORIZED_NEXT,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SELECTED_ARCHITECTURE,
    SMALL_SIGNATURE,
)
from app.source_analysis_output_ceiling_review.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
    package_imports_network_clients,
    package_invokes_provider,
)
from app.source_analysis_output_ceiling_review.raw_analyzer import (
    analyze_structured_raw_text,
)
from app.source_analysis_output_ceiling_review.raw_parser import extract_root_prefix
from app.source_analysis_output_ceiling_review.runner import build_bundle

REAL_PROJECT = Path(
    r"C:\TranscriptionAI\sortie\pastoral_retreat_v2_validation"
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
        assert REAL_PROVIDER_CALL_AUTHORIZED_NEXT is False
        assert PHASE == "3B.7.7A.10"


class TestRawAnalyzer:
    def test_prefix_parser_does_not_repair(self):
        text = '{"theme":"t","records":[{"k":"IDEA","v":"one","s":[],"l":[],"m":[]},{"k":"REP'
        prefix = extract_root_prefix(text)
        assert prefix["records_array_reached"] is True
        assert prefix["records_array_closed"] is False
        assert len(prefix["complete_records"]) == 1
        assert prefix["incomplete_record_present"] is True
        metrics = analyze_structured_raw_text(text)
        assert metrics["json_valid"] is False
        assert metrics["treated_as_transport"] is False
        assert metrics["complete_record_count"] == 1
        assert metrics["incomplete_record_count"] == 1

    def test_analyzer_is_deterministic(self):
        text = '{"theme":"t","intent":"i","ic":"high","aud":"a","ac":"low","records":[{"k":"TOPIC","v":"x","s":["SRC000001"],"l":[],"m":[]}]}'
        first = analyze_structured_raw_text(text)
        second = analyze_structured_raw_text(text)
        assert first == second


class TestBundleOffline:
    def test_real_project_review_does_not_publish(self):
        bundle = build_bundle(PROJECT_NAME)
        assert bundle["forensics"]["provider_called"] is False
        assert bundle["forensics"]["repairs_json"] is False
        assert bundle["forensics"]["writes_source_map"] is False
        assert not source_map_path(PROJECT_NAME).exists()
        assert (
            bundle["forensics"]["output_composition"]["provider_thinking_tokens"]
            == CALL_C_THINKING_TOKENS
        )
        prefix = bundle["forensics"]["structured_prefix"]
        assert prefix["complete_record_count"] == 108
        assert prefix["metrics"]["kind_counts"]["IDEA"] == 53
        assert prefix["metrics"]["kind_counts"]["RELATION"] == 18
        assert prefix["exceeded_total_hard_ceiling"] is False
        assert bundle["decision"]["selected_architecture"] == SELECTED_ARCHITECTURE
        assert bundle["decision"]["root_cause"]["primary"] == PRIMARY_ROOT_CAUSE
        assert bundle["decision"]["real_provider_call_authorized_next"] is False
        assert bundle["integrity"]["forensic_bytes_preserved"]["http_raw_unchanged"]
        assert bundle["result"] in {"PASS", "PARTIAL"}

    def test_real_analysis_tree_is_forensic_only(self):
        report = inspect_analysis_directory(REAL_PROJECT / "analysis")
        assert report["ok"] is True
        assert report["published_canonical_present"] is False
        assert report["semantic_artifact_present"] is False
        assert SMALL_SIGNATURE in str(
            next((REAL_PROJECT / "analysis" / "provider_forensics").rglob("*.bin"))
        )
