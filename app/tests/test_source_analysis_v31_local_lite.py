"""Phase 3B.7.7A.26 — local-lite. FakeAI / offline. 0 réseau."""

from __future__ import annotations

import dataclasses

import pytest

from app.source_analysis.errors import (
    HybridReconstructionError,
    WindowTransportValidationError,
)
from app.source_analysis.hybrid_reconstructor import _idea_raw_local_lite
from app.source_analysis.models import IDEA_KINDS, AnalysisProvenance, Idea
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.schema import build_response_schema
from app.source_analysis.transcript_input import (
    load_transcript_input,
    transcript_data_file,
)
from app.source_analysis.validator import validate_source_map
from app.source_analysis.window_fixtures import make_transcript, window_for
from app.source_analysis.window_models import WindowIntermediateRecord
from app.source_analysis.window_prompt import KNOWN_WINDOW_PROMPT_VERSIONS
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.tests.source_analysis_fixtures import (  # noqa: F401 — fixture pytest
    analysis_env,
    fake_analysis_payload,
)
from app.source_analysis_local_v3.compatibility import (
    normalize_v3_transport_to_local_lite,
)
from app.source_analysis_local_v3.constants import (
    SEMANTIC_TRANSPORT_VERSION_V3,
    SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
    WINDOW_ANALYSIS_PROMPT_VERSION_V132,
    WINDOW_ANALYSIS_PROMPT_VERSION_V140,
)
from app.source_analysis_local_v3.decoder import (
    decode_transport,
    decode_v3_transport,
    decode_v31_local_lite_transport,
)
from app.source_analysis_local_v3.fixtures import (
    v3_success_transport,
    v31_a22_pattern_transports,
    v31_example_empty_link_transport,
    v31_i44_proposition_illustration,
    v31_success_transport,
)
from app.source_analysis_local_v3.handles import is_idea_handle
from app.source_analysis_local_v3.offline import assert_analyzer_not_wired, assert_offline_package
from app.source_analysis_local_v3.pipeline import analyze_window_v31
from app.source_analysis_local_v3.prompt import (
    build_window_system_prompt_v13,
    build_window_system_prompt_v131,
    build_window_system_prompt_v132,
    build_window_system_prompt_v140,
    window_prompt_v131_sha256,
    window_prompt_v132_sha256,
    window_prompt_v140_sha256,
)
from app.source_analysis_local_v3.resolver import resolve_v3_handles
from app.source_analysis_local_v3.schema import (
    measure_v31_local_lite_schema_pair,
    semantic_transport_v3_fingerprint,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis_v3_hardened_win001.constants import EXPECTED_PROMPT_SHA256 as A21_PROMPT
from app.source_analysis_v3_hardened_win004.constants import EXPECTED_PROMPT_SHA256 as A24_PROMPT
from app.source_analysis_v3_symbolic_grammar_canary.constants import A17_SCHEMA_FINGERPRINT
from app.source_analysis_v31_local_lite.constants import (
    FUTURE_REAL_CALL_AUTHORIZED,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
)
from app.source_analysis.consolidation_models import ConsolidationNode
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy


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


def _window(owned="SRC000001"):
    transcript = make_transcript(
        ["Faith window teaches how a trial is crossed."],
        src_ids=(owned,),
        transcript_id="TR-V31",
        content_sha256="e" * 64,
    )
    return transcript, window_for(transcript, owned=(owned,), window_id="WIN001")


def _engine(payload):
    return FakeAIEngine(
        script=[FakeReply(text="{}", parsed=payload, finish_reason="stop")],
        retry_policy=no_delay_policy(),
    )


class TestIdentityAndIsolation:
    def test_versions_and_production_isolation(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_WINDOW_CALLS == 0
        assert FUTURE_REAL_CALL_AUTHORIZED is False
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V13 == "window-analysis-1.3"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V131 == "window-analysis-1.3.1"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V132 == "window-analysis-1.3.2"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V140 == "window-analysis-1.4.0"
        assert SEMANTIC_TRANSPORT_VERSION_V3 == "semantic-transport-v3"
        assert SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE == "semantic-transport-v3.1-local-lite"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V140 not in KNOWN_WINDOW_PROMPT_VERSIONS
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V132 not in KNOWN_WINDOW_PROMPT_VERSIONS
        assert PLANNER_VERSION == "window-planner-v2.0"


class TestPrompt140:
    def test_prompt_identity_and_historical_immutability(self):
        v13 = build_window_system_prompt_v13("en")
        v131 = build_window_system_prompt_v131("en")
        v132 = build_window_system_prompt_v132("en")
        v140 = build_window_system_prompt_v140("en")
        assert window_prompt_v131_sha256(v131) != window_prompt_v140_sha256(v140)
        assert window_prompt_v132_sha256(v132) != window_prompt_v140_sha256(v140)
        assert A21_PROMPT
        assert A24_PROMPT
        assert "idea.kind" in v13
        assert "idea.kind" in v132
        assert "idea.kind" not in v140
        assert "m=[importance]" in v140
        assert "Do not classify the IDEA" in v140
        assert "claim, explanation, principle" in v140
        assert "Fine-grained IDEA subtype classification is not a local task" in v140
        assert '"m":["central"]' in v140
        assert '"m":["claim","central"]' not in v140
        assert "never use example" not in v140.lower() or "Do not classify" in v140
        assert v140 != v132 != v131 != v13
        assert window_prompt_v140_sha256(v140) != A24_PROMPT
        assert "Copy every SRC identifier EXACTLY" in v140


class TestSchemaAndTransport:
    def test_v31_schema_identical_to_v3(self):
        measured = measure_v31_local_lite_schema_pair()
        assert measured["raw_bytes"] == 588
        assert measured["adapted_bytes"] == 650
        assert measured["wire_shape_identical_to_v3"] is True
        assert semantic_transport_v31_local_lite_fingerprint() == A17_SCHEMA_FINGERPRINT
        assert semantic_transport_v31_local_lite_fingerprint() == semantic_transport_v3_fingerprint()


class TestVersionAwareDecoder:
    def test_valid_local_lite_and_historical_v3(self):
        lite = decode_v31_local_lite_transport(
            v31_success_transport(), allowed_source_refs={"SRC000001"}
        )
        idea = next(row for row in lite["records"] if row["k"] == "IDEA")
        assert idea["m"] == ["central"] or idea["m"][0] in {"central", "supporting", "minor"}
        decode_v3_transport(v3_success_transport(), allowed_source_refs={"SRC000001"})
        decode_transport(
            v3_success_transport(),
            transport_version=SEMANTIC_TRANSPORT_VERSION_V3,
            allowed_source_refs={"SRC000001"},
        )
        decode_transport(
            v31_success_transport(),
            transport_version=SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
            allowed_source_refs={"SRC000001"},
        )
        with pytest.raises(WindowTransportValidationError, match="inconnue"):
            decode_transport(
                v31_success_transport(),
                transport_version="guess-from-payload",
                allowed_source_refs={"SRC000001"},
            )

    def test_old_subtype_and_example_leakage_rejected(self):
        claim = v31_success_transport()
        claim["records"][1]["m"] = ["claim", "primary"]
        with pytest.raises(WindowTransportValidationError, match="importance"):
            decode_v31_local_lite_transport(claim, allowed_source_refs={"SRC000001"})
        leak = v31_success_transport()
        leak["records"][1]["m"] = ["example", "supporting"]
        with pytest.raises(WindowTransportValidationError):
            decode_v31_local_lite_transport(leak, allowed_source_refs={"SRC000001"})
        with pytest.raises(WindowTransportValidationError):
            decode_v31_local_lite_transport(
                v3_success_transport(), allowed_source_refs={"SRC000001"}
            )

    def test_empty_and_unknown_importance_rejected(self):
        empty = v31_success_transport()
        empty["records"][1]["m"] = []
        with pytest.raises(WindowTransportValidationError, match="importance"):
            decode_v31_local_lite_transport(empty, allowed_source_refs={"SRC000001"})
        unknown = v31_success_transport()
        unknown["records"][1]["m"] = ["primary"]
        with pytest.raises(WindowTransportValidationError, match="importance invalide"):
            decode_v31_local_lite_transport(unknown, allowed_source_refs={"SRC000001"})

    def test_strict_src_and_handles(self):
        typo = v31_success_transport()
        typo["records"][0]["s"] = ["SRc000609"]
        with pytest.raises(WindowTransportValidationError, match="SRc000609"):
            decode_v31_local_lite_transport(typo, allowed_source_refs={"SRC000001"})
        wrong = v31_success_transport()
        wrong["records"][1]["l"] = ["I2"]
        decoded = decode_v31_local_lite_transport(
            wrong, allowed_source_refs={"SRC000001"}
        )
        with pytest.raises(WindowTransportValidationError, match="ne peut cibler"):
            resolve_v3_handles(decoded)
        numeric = v31_success_transport()
        numeric["records"][3]["l"] = [0, 1]
        with pytest.raises(WindowTransportValidationError):
            decode_v31_local_lite_transport(numeric, allowed_source_refs={"SRC000001"})
        empty_link = decode_v31_local_lite_transport(
            v31_example_empty_link_transport(), allowed_source_refs={"SRC000001"}
        )
        example = next(row for row in empty_link["records"] if row["k"] == "EXAMPLE")
        assert example["l"] == []
        assert is_idea_handle("I1") is True

    def test_i44_and_a22_patterns(self):
        decoded = decode_v31_local_lite_transport(
            v31_i44_proposition_illustration(), allowed_source_refs={"SRC000001"}
        )
        idea = next(row for row in decoded["records"] if row["k"] == "IDEA")
        example = next(row for row in decoded["records"] if row["k"] == "EXAMPLE")
        assert idea["m"] == ["central"]
        assert "example" not in idea["m"]
        assert "leader" in example["v"].lower() or "shirt" in example["v"].lower()
        for payload in v31_a22_pattern_transports():
            item = decode_v31_local_lite_transport(
                payload, allowed_source_refs={"SRC000001"}
            )
            ideas = [row for row in item["records"] if row["k"] == "IDEA"]
            assert ideas[0]["m"] == ["central"]


class TestReconstructorRegression:
    def test_importance_cannot_become_kind(self):
        node = ConsolidationNode(
            node_id="C0001",
            operation="KEEP_RECORD",
            kind="IDEA",
            value="",
            member_ids=("WIN001:R0001",),
            source_refs=("SRC000001",),
            source_refs_are_local_union=True,
        )
        member = WindowIntermediateRecord(
            record_id="WIN001:R0001",
            transport_index=1,
            kind="IDEA",
            value="Faith changes the crossing.",
            source_refs=("SRC000001",),
            links=(),
            link_record_ids=(),
            metadata=("central",),
        )
        raw = _idea_raw_local_lite(node, (member,), {}, {}, ("SRC000001",))
        assert raw["importance"] == "central"
        assert raw["kind"] == ""
        assert raw["kind"] != "central"
        primary = WindowIntermediateRecord(
            record_id="WIN001:R0001",
            transport_index=1,
            kind="IDEA",
            value="Faith changes the crossing.",
            source_refs=("SRC000001",),
            links=(),
            link_record_ids=(),
            metadata=("primary",),
        )
        with pytest.raises(HybridReconstructionError, match="importance"):
            _idea_raw_local_lite(node, (primary,), {}, {}, ("SRC000001",))
        leaked = WindowIntermediateRecord(
            record_id="WIN001:R0001",
            transport_index=1,
            kind="IDEA",
            value="Faith changes the crossing.",
            source_refs=("SRC000001",),
            links=(),
            link_record_ids=(),
            metadata=("claim", "central"),
        )
        with pytest.raises(HybridReconstructionError, match="local-lite"):
            _idea_raw_local_lite(node, (leaked,), {}, {}, ("SRC000001",))


class TestFakeAIAndCompatibility:
    def test_fakeai_win001_and_v3_normalization(self):
        transcript, window = _window()
        outcome = analyze_window_v31(
            window, transcript, _engine(v31_success_transport())
        )
        assert outcome.ready is True
        assert outcome.result is not None
        assert outcome.result.transport_version == SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE
        assert outcome.result.prompt_version == WINDOW_ANALYSIS_PROMPT_VERSION_V140
        normalized, provenance = normalize_v3_transport_to_local_lite(
            v3_success_transport(),
            source_transport_version=SEMANTIC_TRANSPORT_VERSION_V3,
        )
        idea = next(row for row in normalized["records"] if row["k"] == "IDEA")
        assert idea["m"] == ["central"]
        assert provenance["invented_semantics"] is False
        decode_v31_local_lite_transport(normalized, allowed_source_refs={"SRC000001"})


class TestCanonicalOptionalKind:
    """Absence de sous-type : validateur Python oui ; schéma LLM production inchangé."""

    def test_empty_kind_accepted_importance_cannot_become_kind(self, analysis_env):
        transcript = load_transcript_input(
            transcript_data_file(analysis_env.transcripts_dir),
            project_name=analysis_env.project_name,
        )
        source_map = normalize_source_map(
            fake_analysis_payload(), transcript, provenance=_PROVENANCE
        )
        absent = dataclasses.replace(
            source_map,
            ideas=(
                dataclasses.replace(source_map.ideas[0], kind=""),
                *source_map.ideas[1:],
            ),
        )
        assert absent.ideas[0].kind == ""
        assert absent.ideas[0].to_dict()["kind"] == ""
        assert validate_source_map(absent, transcript) == []
        leaked = dataclasses.replace(
            source_map,
            ideas=(
                dataclasses.replace(source_map.ideas[0], kind="central"),
                *source_map.ideas[1:],
            ),
        )
        errors = validate_source_map(leaked, transcript)
        assert any("kind invalide" in error for error in errors)
        serialized = Idea(
            idea_id="IDEA001",
            summary="Faith changes the crossing.",
            kind="",
            importance="central",
            source_refs=("SRC000001",),
        ).to_dict()
        assert "kind" in serialized
        assert serialized["kind"] == ""

    def test_production_llm_schema_kind_enum_unchanged(self):
        idea = build_response_schema()["properties"]["ideas"]["items"]
        assert idea["properties"]["kind"]["enum"] == list(IDEA_KINDS)
        assert "" not in idea["properties"]["kind"]["enum"]
        assert "kind" in idea["required"]
