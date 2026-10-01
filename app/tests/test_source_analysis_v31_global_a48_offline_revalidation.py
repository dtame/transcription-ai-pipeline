"""Phase 3B.7.7A.48 — FakeAI / offline revalidation. 0 réseau. 0 publication."""

from __future__ import annotations

import copy

import pytest

from app.source_analysis.models import (
    forbidden_editorial_fields,
    scan_editorial_structure,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_a47_contract_forensics.evidence import (
    a46_intent_text,
    derived_a46_transport,
)
from app.source_analysis_v31_global_a47_contract_forensics.replay import replay_a46_frozen
from app.source_analysis_v31_global_a48_offline_revalidation.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    A39_STATUS_PRESERVED,
    A40_STATUS_PRESERVED,
    A41_STATUS_PRESERVED,
    A42_STATUS_PRESERVED,
    A43_STATUS_PRESERVED,
    A44_STATUS_PRESERVED,
    A45_REQUEST_HASH,
    A45_STATUS_PRESERVED,
    A46_INTENT_LENGTH,
    A46_RAW_RESPONSE_HASH,
    A46_STATUS_PRESERVED,
    A47_STATUS_PRESERVED,
    FUTURE_PROMPT,
    GLOBAL_INTENT_MAX_CHARS,
    HISTORICAL_INTENT_LIMIT,
    HISTORICAL_PROMPT,
    NEW_GRAMMAR_CANARY_REQUIRED,
    NEW_PROVIDER_CANARY_REQUIRED_FOR_A46,
    PHASE,
    PHASE_3B_STATUS,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_HASH,
    SOURCE_MAP_PUBLICATION_AUTHORIZED,
    TEXT_LIMITS,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_a48_offline_revalidation.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_a48_offline_revalidation.replay import (
    replay_a46_under_corrected_contract,
)
from app.source_analysis_v31_global_reuse_output.prompt_v30 import (
    SYSTEM_PROMPT as SYSTEM_PROMPT_V30,
    prompt_v30_bundle,
)
from app.source_analysis_v31_global_reuse_output.prompt_v301 import (
    SYSTEM_PROMPT as SYSTEM_PROMPT_V301,
    prompt_v301_bundle,
)
from app.source_analysis_v31_global_reuse_output.transport_v30 import (
    build_global_consolidation_schema_v30,
    measure_global_schema_v30,
)
from app.source_analysis_v31_global_reuse_output.validate import validate_global_transport_v30


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


def _gm(intent: str) -> dict:
    return {
        "th": "theme",
        "in": intent,
        "ic": "high",
        "au": "audience",
        "ac": "medium",
        "vo": "voice",
    }


def _tiny(intent: str) -> dict:
    return {
        "gm": _gm(intent),
        "t": [],
        "i": [{"h": "I1", "m": ["L1"], "p": "central"}],
        "x": [],
        "f": [],
        "u": [],
        "drop": [],
    }


def _validate(payload: dict, *, limits: dict | None = None):
    return validate_global_transport_v30(
        payload,
        idea_input_ids=["L1"],
        allowed_input_ids={"L1"},
        text_limits=limits,
    )


class TestHistoricalFreeze:
    def test_a34_through_a47_remain_immutable(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert A34_STATUS_PRESERVED == "PASS"
        assert A35_STATUS_PRESERVED == "FAIL"
        assert A36_STATUS_PRESERVED == "PASS"
        assert A37_STATUS_PRESERVED == "PASS"
        assert A38_STATUS_PRESERVED == "FAIL"
        assert A39_STATUS_PRESERVED == "PASS"
        assert A40_STATUS_PRESERVED == "FAIL"
        assert A41_STATUS_PRESERVED == "PASS"
        assert A42_STATUS_PRESERVED == "PASS"
        assert A43_STATUS_PRESERVED == "PASS"
        assert A44_STATUS_PRESERVED == "PASS"
        assert A45_STATUS_PRESERVED == "PASS"
        assert A46_STATUS_PRESERVED == "FAIL"
        assert A47_STATUS_PRESERVED == "PASS"
        assert PHASE == "3B.7.7A.48"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert SOURCE_MAP_PUBLICATION_AUTHORIZED is False
        assert not source_map_path(PROJECT_NAME).is_file()

    def test_historical_a46_report_still_fail(self):
        frozen = replay_a46_frozen()
        assert frozen["historical_status"] == "FAIL"
        assert frozen["global_validator"] == "FAIL"
        assert frozen["raw_unchanged"] is True


class TestIntentLimit:
    def test_live_limit_is_only_320(self):
        assert GLOBAL_INTENT_MAX_CHARS == 320
        assert TEXT_LIMITS["intent"] == 320
        assert HISTORICAL_INTENT_LIMIT == 240
        assert TEXT_LIMITS["intent"] != HISTORICAL_INTENT_LIMIT
        assert 240 not in {TEXT_LIMITS["intent"], GLOBAL_INTENT_MAX_CHARS}
        assert 290 not in {TEXT_LIMITS["intent"], GLOBAL_INTENT_MAX_CHARS}

    def test_319_320_pass_321_fail(self):
        at_319 = _validate(_tiny("a" * 319))
        at_320 = _validate(_tiny("a" * 320))
        at_321 = _validate(_tiny("a" * 321))
        assert at_319["ok"] is True
        assert at_320["ok"] is True
        assert at_321["ok"] is False
        assert any("gm.in exceeds 320" in err for err in at_321["errors"])

    def test_a46_intent_290_passes_live_validator(self):
        intent = a46_intent_text()
        assert len(intent) == A46_INTENT_LENGTH == 290
        assert _validate(_tiny(intent))["ok"] is True

    def test_generic_not_pastoral_specific(self):
        payload = _tiny("Teach a compact source-supported global intent.")
        assert _validate(payload)["ok"] is True


class TestPromptVersioning:
    def test_prompt_3_0_frozen_and_3_0_1_successor(self):
        frozen = prompt_v30_bundle()
        nxt = prompt_v301_bundle()
        measured = measure_global_schema_v30()
        schema = build_global_consolidation_schema_v30()
        assert frozen["prompt_version"] == HISTORICAL_PROMPT == "global-consolidation-3.0"
        assert nxt["prompt_version"] == FUTURE_PROMPT == "global-consolidation-3.0.1"
        assert "- intent <= 240" in SYSTEM_PROMPT_V30
        assert "- intent <= 320" in SYSTEM_PROMPT_V301
        assert "- intent <= 240" not in SYSTEM_PROMPT_V301
        assert nxt["previous_prompt_mutated"] is False
        assert nxt["sent_to_provider"] is False
        assert nxt["combined_sha256"] != frozen["combined_sha256"]
        assert measured["hash"] == SCHEMA_HASH
        assert TRANSPORT_VERSION == "global-consolidation-transport-3.0"
        assert nxt["transport_version"] == TRANSPORT_VERSION
        assert "maxLength" not in str(schema.get("properties", {}).get("gm", {}))
        assert A45_REQUEST_HASH.startswith("fbffc38c")
        assert nxt["do_not_reuse_historical_a45_request_hash"] is True
        assert NEW_GRAMMAR_CANARY_REQUIRED == "NO"
        assert NEW_PROVIDER_CANARY_REQUIRED_FOR_A46 == "NO"


class TestStructuralScanner:
    def test_lexical_words_in_ordinary_text_pass(self):
        payload = {
            "ideas": [
                {
                    "summary": (
                        "Genesis chapter 5, later in chapter 17, the book of Hebrews, "
                        "this section of scripture, part of the introduction and conclusion."
                    )
                }
            ]
        }
        scan = scan_editorial_structure(payload)
        assert scan["ok"] is True
        assert forbidden_editorial_fields(payload) == ()

    def test_forbidden_structures_fail(self):
        cases = (
            {"chapters": [{"title": "One"}]},
            {"chapter_title": "One"},
            {"sections": [{"title": "A"}]},
            {"book_parts": [{"title": "I"}]},
            {"editorial_plan": {"steps": []}},
            {"book_title": "My Book"},
            {"table_of_contents": []},
            {"toc": []},
            {"gm": {"th": "x"}, "meta": {"outline": {"chapters": [{"title": "x"}]}}},
        )
        for payload in cases:
            scan = scan_editorial_structure(payload)
            assert scan["ok"] is False, payload


class TestA46Replay:
    def test_corrected_offline_pipeline_passes(self):
        replay = replay_a46_under_corrected_contract()
        identity = replay["identity"]
        assert identity["ok"] is True
        assert identity["raw_response_hash"] == A46_RAW_RESPONSE_HASH
        assert replay["historical_a46_status"] == "FAIL"
        assert replay["raw_unchanged"] is True
        assert replay["structured_parse"] == "PASS"
        assert replay["decoder"] == "PASS"
        assert replay["handle_validation"] == "PASS"
        assert replay["idea_accountability"] == "286 / 286"
        assert replay["keep_count"] == 286
        assert replay["merge_equivalent_count"] == 0
        assert replay["drop_count"] == 0
        assert replay["SINGLE_MEMBER_WITH_V"] == 0
        assert replay["multi_member_global_ideas"] == 0
        assert replay["NON_IDEA_IN_MEMBERS"] == 0
        assert replay["NON_IDEA_IN_DROP"] == 0
        assert replay["unknown_handles"] == 0
        assert replay["duplicate_membership"] == 0
        assert replay["missing_ideas"] == 0
        assert replay["member_drop_overlap"] == 0
        assert float(replay["reuse_text_exact_equality"]) >= 100.0
        assert replay["reuse_text_audit"]["all_canonical_equals_local"] is True
        assert replay["derived_src"] == "PASS"
        assert replay["global_validator"] == "PASS"
        assert replay["canonical_reconstruction"] == "PASS"
        assert replay["canonical_validation"] == "PASS"
        assert replay["structural"]["status"] == "PASS"
        assert replay["editorial"]["a46_actual_forbidden_editorial_structure"] == "NO"
        assert replay["deterministic_replay"] == "PASS"
        assert replay["independent_replay"] == "PASS"
        assert replay["semantic"]["status"] == "PASS"
        assert replay["intent"]["unchanged"] is True
        assert replay["intent"]["length"] == 290
        assert replay["intent"]["review_status"] == "PASS"
        assert replay["published"] is False
        original = a46_intent_text()
        mutated = copy.deepcopy(derived_a46_transport())
        mutated["gm"]["in"] = mutated["gm"]["in"][:240]
        assert mutated["gm"]["in"] != original
        assert a46_intent_text() == original
        assert replay["candidate_payload"]["source_analysis"]["author_intent"]["summary"] == original

    def test_no_network_package(self):
        assert_offline_package()
        from app.source_analysis_v31_global_a48_offline_revalidation.offline import (
            package_imports_network_clients,
            package_invokes_provider,
        )

        assert package_imports_network_clients() == []
        assert package_invokes_provider() == []
