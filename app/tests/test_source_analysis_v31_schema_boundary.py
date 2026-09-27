"""Phase 3B.7.7A.26.1 — frontière schema.py / kind canonique. Offline. 0 réseau."""

from __future__ import annotations

import dataclasses
import json

import pytest

from app.ai.errors import AIStructuredOutputError
from app.ai.structured import parse_structured_output
from app.source_analysis.errors import HybridReconstructionError, WindowTransportValidationError
from app.source_analysis.hybrid_reconstructor import _idea_raw_local_lite
from app.source_analysis.models import IDEA_KINDS, IMPORTANCE_LEVELS, Idea
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.schema import build_response_schema
from app.source_analysis.transcript_input import (
    load_transcript_input,
    transcript_data_file,
)
from app.source_analysis.validator import ensure_valid_source_map, validate_source_map
from app.source_analysis.consolidation_models import ConsolidationNode
from app.source_analysis.window_models import WindowIntermediateRecord
from app.source_analysis_local_v3.compatibility import normalize_v3_transport_to_local_lite
from app.source_analysis_local_v3.constants import (
    SEMANTIC_TRANSPORT_VERSION_V3,
    SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V140,
)
from app.source_analysis_local_v3.decoder import (
    decode_v3_transport,
    decode_v31_local_lite_transport,
)
from app.source_analysis_local_v3.e2e import run_direct_e2e_v31
from app.source_analysis_local_v3.fixtures import (
    seven_window_plan,
    v3_success_transport,
    v31_success_transport,
)
from app.source_analysis_local_v3.pipeline import build_v140_window_request
from app.source_analysis_local_v3.schema import (
    build_semantic_transport_v31_local_lite_schema,
)
from app.source_analysis_v31_schema_boundary.analysis import build_boundary_analysis
from app.source_analysis_v31_schema_boundary.constants import (
    A26_STATUS,
    BLOCKS_A27,
    GLOBAL_IDEA_SUBTYPE_STRATEGY,
    MISMATCH_CLASSIFICATION,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SELECTED_ARCHITECTURE,
)
from app.source_analysis_v31_schema_boundary.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
    assert_schema_py_untouched,
)
from app.source_analysis_v31_schema_boundary.probes import (
    probe_importance_never_becomes_kind,
    probe_schema_py_rejection,
)
from app.source_analysis.models import AnalysisProvenance
from app.tests.source_analysis_fixtures import (  # noqa: F401
    analysis_env,
    fake_analysis_payload,
)


_PROVENANCE = AnalysisProvenance(
    prompt_version="1.0",
    schema_version="1.0",
    provider="fake",
    model="fake-model",
    strategy="global",
    signature="sig",
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _node() -> ConsolidationNode:
    return ConsolidationNode(
        node_id="C0001",
        operation="KEEP_RECORD",
        kind="IDEA",
        value="",
        member_ids=("WIN001:R0001",),
        source_refs=("SRC000001",),
        source_refs_are_local_union=True,
    )


def _member(metadata: tuple[str, ...]) -> WindowIntermediateRecord:
    return WindowIntermediateRecord(
        record_id="WIN001:R0001",
        transport_index=1,
        kind="IDEA",
        value="Faith changes the crossing.",
        source_refs=("SRC000001",),
        links=(),
        link_record_ids=(),
        metadata=metadata,
    )


class TestIsolationAndA26:
    def test_offline_and_a26_preserved(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert_schema_py_untouched()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_WINDOW_CALLS == 0
        assert A26_STATUS == "PASS"
        assert SELECTED_ARCHITECTURE == "GLOBALIZE_IDEA_SUBTYPE"
        assert GLOBAL_IDEA_SUBTYPE_STRATEGY == "A_ABSENT_IF_OPTIONAL"
        assert MISMATCH_CLASSIFICATION == "EXPECTED_STAGE_SPECIFIC_SCHEMA"
        assert BLOCKS_A27 is False


class TestSchemaBoundary:
    def test_schema_py_is_generation_a_provider_grammar(self):
        analysis = build_boundary_analysis()
        role = analysis["schema_py_role"]
        consumers = analysis["consumers"]
        assert role["ideas_kind_required"] is True
        assert role["empty_string_in_enum"] is False
        assert role["ideas_kind_enum"] == list(IDEA_KINDS)
        assert consumers["which_airequest_uses_it_in_production"] == "NONE"
        assert consumers["used_for_local_window_extraction"] is False
        assert consumers["used_for_global_consolidation"] is False
        assert consumers["used_for_final_sourcemap_generation"] is False
        assert consumers["used_for_publication_validation"] is False
        assert consumers["reconstructed_local_lite_passes_through_it"] is False
        assert consumers["production_runtime"]["analyzer.py"]["uses_schema_py"] is False
        assert analysis["classification"]["mismatch_classification"] == (
            "EXPECTED_STAGE_SPECIFIC_SCHEMA"
        )

    def test_schema_py_rejects_empty_kind_accepts_valid(self):
        probe = probe_schema_py_rejection()
        assert probe["empty_kind_rejected_by_schema_py"] is True
        assert probe["valid_kind_accepted_by_schema_py"] is True

    def test_a27_request_cannot_hit_schema_py(self):
        transcript, plan = seven_window_plan()
        request = build_v140_window_request(plan.windows[0], transcript)
        assert request.response_schema == build_semantic_transport_v31_local_lite_schema()
        assert request.response_schema != build_response_schema()
        assert request.metadata["prompt_version"] == WINDOW_ANALYSIS_PROMPT_VERSION_V140
        assert request.metadata["transport_version"] == SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE


class TestCanonicalOptionalKind:
    def test_kind_absent_empty_valid_invalid(self, analysis_env):
        transcript = load_transcript_input(
            transcript_data_file(analysis_env.transcripts_dir),
            project_name=analysis_env.project_name,
        )
        source_map = normalize_source_map(
            fake_analysis_payload(), transcript, provenance=_PROVENANCE
        )
        absent = Idea.from_dict(
            {
                "idea_id": "IDEA001",
                "summary": "Faith changes the crossing.",
                "importance": "central",
                "source_refs": ["SRC000001"],
            }
        )
        assert absent.kind == ""
        empty = dataclasses.replace(source_map.ideas[0], kind="")
        empty_map = dataclasses.replace(source_map, ideas=(empty, *source_map.ideas[1:]))
        assert empty.to_dict()["kind"] == ""
        assert "kind" in empty.to_dict()
        assert validate_source_map(empty_map, transcript) == []
        for token in IDEA_KINDS:
            valid = dataclasses.replace(
                source_map,
                ideas=(
                    dataclasses.replace(source_map.ideas[0], kind=token),
                    *source_map.ideas[1:],
                ),
            )
            assert not any(
                "kind invalide" in error for error in validate_source_map(valid, transcript)
            )
        for token in ("central", "example", "not-a-kind"):
            leaked = dataclasses.replace(
                source_map,
                ideas=(
                    dataclasses.replace(source_map.ideas[0], kind=token),
                    *source_map.ideas[1:],
                ),
            )
            errors = validate_source_map(leaked, transcript)
            assert any("kind invalide" in error for error in errors)

    def test_empty_kind_serialization(self):
        serialized = Idea(
            idea_id="IDEA001",
            summary="Faith changes the crossing.",
            kind="",
            importance="central",
            source_refs=("SRC000001",),
        ).to_dict()
        assert serialized["kind"] == ""
        assert json.loads(json.dumps(serialized))["kind"] == ""


class TestImportanceNeverBecomesKind:
    def test_critical_no_contamination(self):
        probe = probe_importance_never_becomes_kind()
        assert probe["contamination"] is False
        assert probe["local_lite_reconstructor"]["kind"] == ""
        assert probe["local_lite_reconstructor"]["importance"] == "central"
        assert probe["historical_v3_reconstructor"]["kind"] == "claim"
        raw = _idea_raw_local_lite(_node(), (_member(("central",)),), {}, {}, ("SRC000001",))
        assert raw["kind"] == ""
        assert raw["importance"] == "central"
        assert raw["kind"] != "central"
        with pytest.raises(HybridReconstructionError):
            _idea_raw_local_lite(_node(), (_member(("claim",)),), {}, {}, ("SRC000001",))


class TestLocalLiteRoundtrip:
    def test_decode_normalize_reconstruct_validate_serialize_reload(self, tmp_path):
        decoded = decode_v31_local_lite_transport(
            v31_success_transport(), allowed_source_refs={"SRC000001"}
        )
        idea = next(row for row in decoded["records"] if row["k"] == "IDEA")
        assert len(idea["m"]) == 1
        assert idea["m"][0] in IMPORTANCE_LEVELS
        assert idea["m"][0] not in IDEA_KINDS
        direct = run_direct_e2e_v31(tmp_path / "roundtrip")
        source_map = direct.source_map
        transcript, _plan = seven_window_plan()
        assert source_map.ideas
        assert all(item.kind == "" for item in source_map.ideas)
        assert all(item.importance in IMPORTANCE_LEVELS for item in source_map.ideas)
        assert all(item.kind != item.importance for item in source_map.ideas)
        ensure_valid_source_map(source_map, transcript)
        serialized = source_map.to_dict()
        assert all(item["kind"] == "" for item in serialized["ideas"])
        from app.source_analysis.models import SourceMap

        reloaded = SourceMap.from_dict(serialized)
        ensure_valid_source_map(reloaded, transcript)
        assert all(item.kind == "" for item in reloaded.ideas)


class TestMixedVersion:
    def test_historical_v3_and_local_lite_common_path(self):
        decode_v3_transport(v3_success_transport(), allowed_source_refs={"SRC000001"})
        decode_v31_local_lite_transport(
            v31_success_transport(), allowed_source_refs={"SRC000001"}
        )
        with pytest.raises(WindowTransportValidationError):
            decode_v31_local_lite_transport(
                v3_success_transport(), allowed_source_refs={"SRC000001"}
            )
        normalized, provenance = normalize_v3_transport_to_local_lite(
            v3_success_transport(),
            source_transport_version=SEMANTIC_TRANSPORT_VERSION_V3,
        )
        assert provenance["invented_semantics"] is False
        idea = next(row for row in normalized["records"] if row["k"] == "IDEA")
        assert idea["m"][0] in IMPORTANCE_LEVELS
        assert "claim" not in idea["m"]
        decode_v31_local_lite_transport(normalized, allowed_source_refs={"SRC000001"})


class TestPublicationBoundary:
    def test_empty_kind_passes_implemented_gates_not_schema_py(self, analysis_env):
        transcript = load_transcript_input(
            transcript_data_file(analysis_env.transcripts_dir),
            project_name=analysis_env.project_name,
        )
        source_map = normalize_source_map(
            fake_analysis_payload(), transcript, provenance=_PROVENANCE
        )
        empty = dataclasses.replace(
            source_map,
            ideas=tuple(dataclasses.replace(idea, kind="") for idea in source_map.ideas),
        )
        ensure_valid_source_map(empty, transcript)
        payload = fake_analysis_payload()
        payload["ideas"][0]["kind"] = ""
        with pytest.raises(AIStructuredOutputError):
            parse_structured_output(
                json.dumps(payload, ensure_ascii=False),
                build_response_schema(),
            )
