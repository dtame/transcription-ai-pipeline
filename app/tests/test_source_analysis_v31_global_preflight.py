"""Phase 3B.7.7A.34 — preflight consolidation globale offline. 0 provider."""

from __future__ import annotations

import copy

import pytest

from app.source_analysis.models import format_idea_id, format_topic_id
from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_v31_global_preflight.constants import (
    A28_STATUS_PRESERVED,
    A30_STATUS_PRESERVED,
    A31_STATUS_PRESERVED,
    A32_STATUS_PRESERVED,
    A33_STATUS_PRESERVED,
    CONSOLIDATION_AUTHORIZED,
    FROZEN_GRANULARITY,
    FROZEN_PLANNER,
    FROZEN_PROMPT,
    FROZEN_SRC_POLICY,
    FROZEN_TRANSPORT,
    GRAMMAR_CANARY_AUTHORIZED,
    IDEA_DISPOSITION_COVERAGE_REQUIRED,
    MODEL,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_CONSOLIDATION_CALLS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    WIN007_CANONICAL_SRC,
    WIN007_RAW_SRC,
    WIN007_REQUEST_ID,
)
from app.source_analysis_v31_global_preflight.loaders import load_all_ready_candidates
from app.source_analysis_v31_global_preflight.normalize import (
    build_normalized_input,
    make_input_id,
)
from app.source_analysis_v31_global_preflight.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_preflight.runner import build_bundle
from app.source_analysis_v31_global_preflight.validator import (
    assign_canonical_ids,
    validate_global_transport,
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _synthetic_input_ids() -> tuple[list[str], set[str], set[str]]:
    idea_ids = ["W001:I1", "W002:I1"]
    allowed_ids = set(idea_ids) | {"W001:T1", "W002:T1"}
    allowed_src = {"SRC000001", "SRC001202", "SRC000010"}
    return idea_ids, allowed_ids, allowed_src


def _valid_transport() -> dict:
    return {
        "gm": {
            "th": "pastoral formation",
            "in": "form pastors",
            "ic": "high",
            "au": "pastors",
            "ac": "medium",
            "vo": "oral teaching, pastoral",
        },
        "n": [
            {
                "h": "T1",
                "k": "TOPIC",
                "v": "pastoral formation",
                "s": ["SRC000001"],
                "m": [],
            },
            {
                "h": "I1",
                "k": "IDEA",
                "v": "Pastors must be formed.",
                "s": ["SRC000001", "SRC001202"],
                "m": ["central"],
            },
        ],
        "r": [
            {
                "t": "supports",
                "a": "I1",
                "b": "T1",
                "s": ["SRC000001"],
            }
        ],
        "d": [
            {"i": "W001:I1", "o": "MERGE_EQUIVALENT", "g": "I1", "w": "same proposition"},
            {"i": "W002:I1", "o": "MERGE_EQUIVALENT", "g": "I1", "w": "same proposition"},
        ],
    }


class TestOffline:
    def test_package_offline_and_unwired(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_WINDOW_CALLS == 0
        assert REAL_CONSOLIDATION_CALLS == 0
        assert CONSOLIDATION_AUTHORIZED is False
        assert GRAMMAR_CANARY_AUTHORIZED is False
        assert A28_STATUS_PRESERVED == "FAIL"
        assert A30_STATUS_PRESERVED == "PASS"
        assert A31_STATUS_PRESERVED == "FAIL"
        assert A32_STATUS_PRESERVED == "PASS"
        assert A33_STATUS_PRESERVED == "PASS"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert PRODUCTION_PLANNER_VERSION == PLANNER_VERSION == "window-planner-v2.0"
        assert FROZEN_PLANNER == "window-planner-v2.1-small"
        assert FROZEN_PROMPT == "window-analysis-1.4.0"
        assert FROZEN_TRANSPORT == "semantic-transport-v3.1-local-lite"
        assert FROZEN_GRANULARITY == "window-granularity-1.2-kind-specific"
        assert FROZEN_SRC_POLICY == "src-reference-policy-1.1-narrow-canonicalization"
        assert MODEL == "claude-sonnet-5"
        assert not source_map_path(PROJECT_NAME).is_file()


class TestReadyLoadAndNormalize:
    def test_loads_all_seven_ready_candidates(self):
        loaded = load_all_ready_candidates(PROJECT_NAME)
        assert loaded["missing"] == []
        assert loaded["ready_count"] == 7
        assert loaded["all_ready"] is True
        for window_id in (
            "WIN001",
            "WIN002",
            "WIN003",
            "WIN004",
            "WIN005",
            "WIN006",
            "WIN007",
        ):
            assert loaded["windows"][window_id]["present"] is True
            assert loaded["windows"][window_id]["payload"]["records"]

    def test_mixed_v3_v31_normalization(self):
        normalized = build_normalized_input(PROJECT_NAME)
        win001 = normalized["windows"]["WIN001"]
        win002 = normalized["windows"]["WIN002"]
        assert win001["source_transport_version"] == "semantic-transport-v3"
        assert win002["source_transport_version"] == "semantic-transport-v3.1-local-lite"
        assert win001["invented_semantics"] is False
        assert win001["text_rewritten"] is False
        assert win001["ideas_merged"] is False
        ideas = [item for item in win001["records"] if item["kind"] == "IDEA"]
        assert ideas
        assert all(item["idea_kind"] == "" for item in ideas)
        assert all(item["importance"] for item in ideas)
        assert win001["dropped_local_idea_subtypes"]

    def test_win003_provenance(self):
        normalized = build_normalized_input(PROJECT_NAME)
        provenance = normalized["win003_provenance"]
        assert provenance.get("original_provider_phase") == "A.28"
        assert provenance.get("revalidation_phase") == "A.30"
        assert provenance.get("provider_call_during_a30") is False

    def test_win007_src_provenance(self):
        normalized = build_normalized_input(PROJECT_NAME)
        hits = [
            item
            for item in normalized["windows"]["WIN007"]["records"]
            if item.get("src_provenance")
        ]
        assert hits
        row = hits[0]
        assert WIN007_CANONICAL_SRC in row["source_refs"]
        assert WIN007_RAW_SRC not in row["source_refs"]
        assert row["src_provenance"]["raw_provider_src"] == WIN007_RAW_SRC
        assert row["src_provenance"]["canonical_src"] == WIN007_CANONICAL_SRC
        assert row["src_provenance"]["policy"] == FROZEN_SRC_POLICY
        assert normalized["win007_request_id"] == WIN007_REQUEST_ID

    def test_deterministic_normalized_ids(self):
        first = build_normalized_input(PROJECT_NAME)
        second = build_normalized_input(PROJECT_NAME)
        assert first["compact_sha256"] == second["compact_sha256"]
        ids = [item["input_id"] for item in first["all_records"]]
        assert ids == [item["input_id"] for item in second["all_records"]]
        assert len(ids) == len(set(ids))
        assert make_input_id("WIN003", 17, "IDEA", "I17") == "W003:I17"
        idea_ids = first["idea_input_ids"]
        assert all(item.startswith("W") and ":" in item for item in idea_ids)
        assert all(item.split(":", 1)[1].startswith("I") for item in idea_ids)


class TestValidator:
    def test_one_hundred_percent_idea_disposition_required(self):
        idea_ids, allowed_ids, allowed_src = _synthetic_input_ids()
        payload = _valid_transport()
        result = validate_global_transport(
            payload,
            idea_input_ids=idea_ids,
            allowed_input_ids=allowed_ids,
            allowed_source_refs=allowed_src,
        )
        assert result["ok"] is True
        assert result["idea_disposition_coverage"] == 100.0
        assert IDEA_DISPOSITION_COVERAGE_REQUIRED == 100

    def test_unknown_local_handles_rejected(self):
        idea_ids, allowed_ids, allowed_src = _synthetic_input_ids()
        payload = _valid_transport()
        payload["d"].append({"i": "W009:I99", "o": "KEEP", "g": "I1", "w": ""})
        result = validate_global_transport(
            payload,
            idea_input_ids=idea_ids,
            allowed_input_ids=allowed_ids,
            allowed_source_refs=allowed_src,
        )
        assert result["ok"] is False
        assert any("unknown local handle" in err for err in result["errors"])

    def test_unknown_src_rejected(self):
        idea_ids, allowed_ids, allowed_src = _synthetic_input_ids()
        payload = _valid_transport()
        payload["n"][1]["s"] = ["SRC000001", "SRC009999"]
        result = validate_global_transport(
            payload,
            idea_input_ids=idea_ids,
            allowed_input_ids=allowed_ids,
            allowed_source_refs=allowed_src,
        )
        assert result["ok"] is False
        assert any("unknown SRC" in err for err in result["errors"])

    def test_silent_drop_rejected(self):
        idea_ids, allowed_ids, allowed_src = _synthetic_input_ids()
        payload = _valid_transport()
        payload["d"] = payload["d"][:1]
        result = validate_global_transport(
            payload,
            idea_input_ids=idea_ids,
            allowed_input_ids=allowed_ids,
            allowed_source_refs=allowed_src,
        )
        assert result["ok"] is False
        assert any("silent drop" in err for err in result["errors"])

    def test_merge_provenance_requires_src_union(self):
        idea_ids, allowed_ids, allowed_src = _synthetic_input_ids()
        payload = _valid_transport()
        payload["n"][1]["s"] = []
        result = validate_global_transport(
            payload,
            idea_input_ids=idea_ids,
            allowed_input_ids=allowed_ids,
            allowed_source_refs=allowed_src,
        )
        assert result["ok"] is False
        assert any("SRC" in err or "merge" in err for err in result["errors"])

    def test_global_traceability_requires_src_on_ideas(self):
        idea_ids, allowed_ids, allowed_src = _synthetic_input_ids()
        payload = _valid_transport()
        payload["n"].append(
            {"h": "I2", "k": "IDEA", "v": "ungrounded", "s": [], "m": ["minor"]}
        )
        result = validate_global_transport(
            payload,
            idea_input_ids=idea_ids,
            allowed_input_ids=allowed_ids,
            allowed_source_refs=allowed_src,
        )
        assert result["ok"] is False
        assert any("missing SRC" in err for err in result["errors"])

    def test_deterministic_canonical_ordering(self):
        nodes = [
            {"h": "I2", "k": "IDEA", "v": "later", "s": ["SRC000010"], "m": ["minor"]},
            {"h": "I1", "k": "IDEA", "v": "earlier", "s": ["SRC000001"], "m": ["central"]},
            {"h": "T1", "k": "TOPIC", "v": "theme", "s": ["SRC000001"], "m": []},
        ]
        assigned = assign_canonical_ids(nodes)
        ideas = [item for item in assigned if item["k"] == "IDEA"]
        topics = [item for item in assigned if item["k"] == "TOPIC"]
        assert ideas[0]["h"] == "I1"
        assert ideas[0]["canonical_id"] == format_idea_id(1)
        assert ideas[1]["h"] == "I2"
        assert ideas[1]["canonical_id"] == format_idea_id(2)
        assert topics[0]["canonical_id"] == format_topic_id(1)

    def test_forbidden_not_important_drop(self):
        idea_ids, allowed_ids, allowed_src = _synthetic_input_ids()
        payload = _valid_transport()
        payload["d"][1] = {
            "i": "W002:I1",
            "o": "DROP",
            "g": "",
            "w": "not_important",
        }
        result = validate_global_transport(
            payload,
            idea_input_ids=idea_ids,
            allowed_input_ids=allowed_ids,
            allowed_source_refs=allowed_src,
        )
        assert result["ok"] is False


class TestBundle:
    def test_build_bundle_offline_pass_shape(self):
        original = source_map_path(PROJECT_NAME)
        before = original.is_file()
        bundle = build_bundle(tests="offline A.34 unit")
        assert bundle["header"]["real_provider_calls"] == 0
        assert bundle["header"]["real_consolidation_calls"] == 0
        assert bundle["header"]["source_map"] == "NOT PUBLISHED"
        assert bundle["header"]["global_consolidation"] == "NOT EXECUTED"
        assert bundle["gates"]["provider_calls_zero"] is True
        assert original.is_file() is before
        assert copy.deepcopy(bundle["header"]["historical"]) == {
            "A.28": "FAIL",
            "A.30": "PASS",
            "A.31": "FAIL",
            "A.32": "PASS",
            "A.33": "PASS",
        }
