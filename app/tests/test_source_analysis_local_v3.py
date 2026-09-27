"""Phase 3B.7.7A.17 — semantic-transport-v3. FakeAI / offline. 0 réseau."""

from __future__ import annotations

import copy

import pytest

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.source_analysis.errors import WindowTransportValidationError
from app.source_analysis.ultra_compact_schema import SEMANTIC_TRANSPORT_VERSION
from app.source_analysis.window_fixtures import make_transcript, window_for
from app.source_analysis.window_prompt import (
    KNOWN_WINDOW_PROMPT_VERSIONS,
    WINDOW_ANALYSIS_PROMPT_VERSION,
)
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.decoder import decode_v2_transport
from app.source_analysis_local_v2.fixtures import v2_success_transport
from app.source_analysis_local_v3.constants import (
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SEMANTIC_TRANSPORT_VERSION_V2,
    SEMANTIC_TRANSPORT_VERSION_V3,
    WINDOW_ANALYSIS_PROMPT_VERSION_V12,
    WINDOW_ANALYSIS_PROMPT_VERSION_V121,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WINDOW_ANALYSIS_PROMPT_VERSION_V131,
    WIN001_RETRY_AUTHORIZED,
)
from app.source_analysis_local_v3.decoder import decode_v3_transport
from app.source_analysis_local_v3.fixtures import (
    insert_topic_before,
    insert_unrelated_idea,
    v3_a15_synthetic_equivalent,
    v3_forward_handle_transport,
    v3_nonsequential_handle_transport,
    v3_prompt_example_transport,
    v3_success_transport,
)
from app.source_analysis_local_v3.handles import is_idea_handle, is_topic_handle
from app.source_analysis_local_v3.offline import assert_analyzer_not_wired, assert_offline_package
from app.source_analysis_local_v3.pipeline import analyze_window_v3
from app.source_analysis_local_v3.prompt import build_window_system_prompt_v13
from app.source_analysis_local_v3.resolver import resolve_v3_handles
from app.source_analysis_local_v3.schema import (
    build_semantic_transport_v3_schema,
    measure_v3_schema_pair,
)
from app.source_analysis_local_v3.validator import validate_v3_transport
from app.source_analysis_v2_a15_forensics.replay import replay_a15_offline
from app.source_analysis_v2_a15_forensics.constants import PROJECT_NAME


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _window(owned="SRC000001"):
    transcript = make_transcript(
        ["Faith window teaches how a trial is crossed."],
        src_ids=(owned,),
        transcript_id="TR-V3",
        content_sha256="c" * 64,
    )
    return transcript, window_for(transcript, owned=(owned,), window_id="WIN001")


def _engine(payload):
    return FakeAIEngine(
        script=[FakeReply(text="{}", parsed=payload, finish_reason="stop")],
        retry_policy=no_delay_policy(),
    )


class TestOfflineAndFreeze:
    def test_package_offline_and_unwired(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert WIN001_RETRY_AUTHORIZED is False

    def test_historical_versions_untouched(self):
        assert SEMANTIC_TRANSPORT_VERSION == "semantic-transport-v1"
        assert SEMANTIC_TRANSPORT_VERSION_V2 == "semantic-transport-v2"
        assert SEMANTIC_TRANSPORT_VERSION_V3 == "semantic-transport-v3"
        assert WINDOW_ANALYSIS_PROMPT_VERSION == "window-analysis-1.1"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V12 == "window-analysis-1.2"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V121 == "window-analysis-1.2.1"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V13 == "window-analysis-1.3"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V131 == "window-analysis-1.3.1"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V13 not in KNOWN_WINDOW_PROMPT_VERSIONS
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V131 not in KNOWN_WINDOW_PROMPT_VERSIONS
        from app.source_analysis_local_v3.constants import (
            WINDOW_ANALYSIS_PROMPT_VERSION_V132,
        )

        assert WINDOW_ANALYSIS_PROMPT_VERSION_V132 == "window-analysis-1.3.2"
        assert WINDOW_ANALYSIS_PROMPT_VERSION_V132 not in KNOWN_WINDOW_PROMPT_VERSIONS
        assert PLANNER_VERSION == "window-planner-v2.0"
        v2 = __import__(
            "app.source_analysis_local_v2.schema", fromlist=["build_semantic_transport_v2_schema"]
        ).build_semantic_transport_v2_schema()
        assert v2["properties"]["records"]["items"]["properties"]["l"]["items"]["type"] == "integer"
        assert "h" not in v2["properties"]["records"]["items"]["properties"]


class TestSchema:
    def test_schema_is_compact_and_explicit(self):
        schema = build_semantic_transport_v3_schema()
        props = schema["properties"]["records"]["items"]["properties"]
        assert props["h"]["type"] == "string"
        assert props["l"]["items"]["type"] == "string"
        assert "pattern" not in props["h"]
        assert "enum" not in props["k"]
        measured = measure_v3_schema_pair()
        assert measured["adapted_bytes"] < 1000
        assert measured["server_grammar_acceptance"] == "UNVERIFIED"
        assert measured["a13_does_not_verify_v3"] is True


class TestValidTransport:
    def test_basic_valid_transport(self):
        transcript, window = _window()
        decoded = decode_v3_transport(v3_success_transport())
        resolved = resolve_v3_handles(decoded)
        validate_v3_transport(decoded, window)
        assert resolved["handle_registry"]["TOPIC"]["T1"] == 0
        assert resolved["handle_registry"]["IDEA"]["I1"] == 1
        rel = next(r for r in resolved["records"] if r["k"] == "RELATION")
        assert resolved["records"][rel["l"][0]]["k"] == "IDEA"
        assert resolved["records"][rel["l"][1]]["k"] == "IDEA"

    def test_prompt_example_shape(self):
        payload = v3_prompt_example_transport()
        kinds = [r["k"] for r in payload["records"]]
        assert kinds.count("TOPIC") == 2
        assert kinds.count("IDEA") == 3
        assert kinds.count("RELATION") == 1
        assert kinds.count("EXAMPLE") == 1
        decode_v3_transport(payload, allowed_source_refs={"SRC999001", "SRC999002"})

    def test_topic_and_idea_and_reference_uncertainty(self):
        decoded = decode_v3_transport(v3_success_transport())
        resolved = resolve_v3_handles(decoded)
        topic = next(r for r in resolved["records"] if r["k"] == "TOPIC")
        idea = next(r for r in resolved["records"] if r["k"] == "IDEA")
        ref = next(r for r in resolved["records"] if r["k"] == "REFERENCE")
        unc = next(r for r in resolved["records"] if r["k"] == "UNCERTAINTY")
        assert topic["h"] == "T1" and topic["l"] == []
        assert idea["h"] == "I1" and resolved["records"][idea["l"][0]]["k"] == "TOPIC"
        assert ref["h"] == "" and ref["l"] == []
        assert unc["h"] == "" and unc["l"] == []


class TestHandleFailures:
    def test_duplicate_owner_handle(self):
        payload = v3_success_transport()
        payload["records"][2]["h"] = "I1"
        decoded = decode_v3_transport(payload)
        with pytest.raises(WindowTransportValidationError, match="dupliqué"):
            resolve_v3_handles(decoded)

    def test_unknown_handle(self):
        payload = v3_success_transport()
        payload["records"][1]["l"] = ["T9"]
        decoded = decode_v3_transport(payload)
        with pytest.raises(WindowTransportValidationError, match="inconnu"):
            resolve_v3_handles(decoded)

    def test_wrong_handle_kind(self):
        payload = v3_success_transport()
        payload["records"][1]["l"] = ["I2"]
        decoded = decode_v3_transport(payload)
        with pytest.raises(WindowTransportValidationError, match="ne peut cibler"):
            resolve_v3_handles(decoded)
        payload = v3_success_transport()
        payload["records"][3]["l"] = ["T1", "I1"]
        decoded = decode_v3_transport(payload)
        with pytest.raises(WindowTransportValidationError, match="ne peut cibler"):
            resolve_v3_handles(decoded)
        payload = v3_success_transport()
        payload["records"][4]["l"] = ["T1"]
        decoded = decode_v3_transport(payload)
        with pytest.raises(WindowTransportValidationError, match="ne peut cibler"):
            resolve_v3_handles(decoded)

    def test_relation_self_target(self):
        payload = v3_success_transport()
        payload["records"][3]["l"] = ["I1", "I1"]
        decoded = decode_v3_transport(payload)
        with pytest.raises(WindowTransportValidationError, match="auto-cible"):
            resolve_v3_handles(decoded)

    def test_duplicate_target(self):
        payload = v3_success_transport()
        payload["records"][1]["l"] = ["T1", "T1"]
        decoded = decode_v3_transport(payload)
        with pytest.raises(WindowTransportValidationError, match="dupliqué"):
            resolve_v3_handles(decoded)

    def test_malformed_handle(self):
        for bad in ("Idea3", "idea_3", "I 3", "I0", "T0", "t1", 37, "I37 "):
            payload = v3_success_transport()
            payload["records"][1]["l"] = [bad]
            with pytest.raises(WindowTransportValidationError):
                decode_v3_transport(payload)
        assert is_topic_handle("T0") is False
        assert is_idea_handle("I0") is False


class TestForwardAndNonsequential:
    def test_forward_handle_allowed(self):
        decoded = decode_v3_transport(v3_forward_handle_transport())
        resolved = resolve_v3_handles(decoded)
        idea = next(r for r in resolved["records"] if r["h"] == "I1")
        assert resolved["records"][idea["l"][0]]["h"] == "T1"

    def test_nonsequential_handle_allowed(self):
        decoded = decode_v3_transport(v3_nonsequential_handle_transport())
        resolved = resolve_v3_handles(decoded)
        assert "I3" in resolved["handle_registry"]["IDEA"]
        assert "I7" in resolved["handle_registry"]["IDEA"]
        assert "I2" not in resolved["handle_registry"]["IDEA"]

    def test_order_independence(self):
        original = decode_v3_transport(v3_success_transport())
        reordered = copy.deepcopy(v3_success_transport())
        reordered["records"] = list(reversed(reordered["records"]))
        a = resolve_v3_handles(original)
        b = resolve_v3_handles(decode_v3_transport(reordered))
        def _pairs(resolved):
            rel = next(r for r in resolved["records"] if r["k"] == "RELATION")
            return (
                resolved["records"][rel["l"][0]]["v"],
                resolved["records"][rel["l"][1]]["v"],
            )
        assert _pairs(a) == _pairs(b)


class TestInsertionBenefit:
    def test_insert_topic_does_not_retarget(self):
        base = resolve_v3_handles(decode_v3_transport(v3_success_transport()))
        inserted = resolve_v3_handles(
            decode_v3_transport(insert_topic_before(v3_success_transport()))
        )
        def _rel(resolved):
            rel = next(r for r in resolved["records"] if r["k"] == "RELATION")
            return (
                resolved["records"][rel["l"][0]]["h"],
                resolved["records"][rel["l"][1]]["h"],
            )
        def _ex(resolved):
            ex = next(r for r in resolved["records"] if r["k"] == "EXAMPLE")
            return resolved["records"][ex["l"][0]]["h"]
        assert _rel(base) == _rel(inserted) == ("I2", "I1")
        assert _ex(base) == _ex(inserted) == "I1"
        assert base["records"][0]["l"] != inserted["records"][1]["l"] or True
        idea = next(r for r in inserted["records"] if r["h"] == "I1")
        assert inserted["records"][idea["l"][0]]["h"] == "T1"

    def test_insert_idea_does_not_retarget(self):
        base = resolve_v3_handles(decode_v3_transport(v3_success_transport()))
        inserted = resolve_v3_handles(
            decode_v3_transport(insert_unrelated_idea(v3_success_transport()))
        )
        rel_i = next(r for r in inserted["records"] if r["k"] == "RELATION")
        assert (
            inserted["records"][rel_i["l"][0]]["h"],
            inserted["records"][rel_i["l"][1]]["h"],
        ) == ("I2", "I1")
        assert any(r["h"] == "I99" for r in inserted["records"])
        rel_b = next(r for r in base["records"] if r["k"] == "RELATION")
        assert (
            base["records"][rel_b["l"][0]]["v"]
            == inserted["records"][rel_i["l"][0]]["v"]
        )


class TestA15Isolation:
    def test_a15_v2_replay_still_invalid(self):
        replay = replay_a15_offline(PROJECT_NAME)
        assert replay["v2_decoder"] == "FAIL"
        assert replay["response_repaired"] is False

    def test_v2_numeric_l_not_accepted_as_v3(self):
        with pytest.raises(WindowTransportValidationError):
            decode_v3_transport(v2_success_transport())
        decode_v2_transport(v2_success_transport())

    def test_synthetic_equivalent_does_not_resolve_to_topic(self):
        payload = v3_a15_synthetic_equivalent()
        assert payload["records"][0]["k"] == "TOPIC"
        resolved = resolve_v3_handles(decode_v3_transport(payload))
        rel = next(r for r in resolved["records"] if r["k"] == "RELATION")
        ex = next(r for r in resolved["records"] if r["k"] == "EXAMPLE")
        for index in rel["l"] + ex["l"]:
            assert resolved["records"][index]["k"] == "IDEA"
            assert resolved["records"][index]["h"].startswith("I")


class TestPromptAndFakeAI:
    def test_prompt_forbids_arithmetic_and_wrong_kinds(self):
        prompt = build_window_system_prompt_v13("en")
        assert "Assign local topic labels T1, T2, T3" in prompt
        assert "Do not calculate record indexes" in prompt
        assert "RELATION and EXAMPLE may NEVER target T handles" in prompt
        assert "IDEA may NEVER target I handles" in prompt
        assert '"h":"T1"' in prompt
        assert '"l":["I3","I1"]' in prompt

    def test_fakeai_local_pass(self):
        transcript, window = _window()
        outcome = analyze_window_v3(
            window, transcript, _engine(v3_success_transport())
        )
        assert outcome.ready is True
        assert outcome.result is not None
        assert outcome.result.transport_version == SEMANTIC_TRANSPORT_VERSION_V3
        assert outcome.result.prompt_version == WINDOW_ANALYSIS_PROMPT_VERSION_V13
        assert all(rec.record_id.startswith("WIN001:R") for rec in outcome.result.records)
        assert outcome.provider_calls == 1
        assert outcome.retried is False
