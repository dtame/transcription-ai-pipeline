"""Phase 3B.7.7A.47 — FakeAI / offline forensics. 0 réseau. 0 publication."""

from __future__ import annotations

import copy

import pytest

from app.source_analysis.models import (
    forbidden_editorial_fields,
    scan_editorial_structure,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_a47_contract_forensics.constants import (
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
    A45_STATUS_PRESERVED,
    A46_INTENT_LENGTH,
    A46_RAW_RESPONSE_HASH,
    A46_STATUS_PRESERVED,
    CAN_A46_SAVED_RESPONSE_BE_VALIDATED_UNDER_CORRECTED_CONTRACT_WITHOUT_REPAIR,
    FROZEN_PROMPT_VERSION,
    FROZEN_TRANSPORT_VERSION,
    HISTORICAL_INTENT_LIMIT,
    INTENT_CONTRACT_ROOT_CAUSE,
    INTENT_SEMANTIC_VERDICT,
    NEXT_PROMPT_VERSION,
    NEXT_SCHEMA_HASH,
    PHASE,
    PHASE_3B_STATUS,
    PROJECT_NAME,
    READY_FOR_A46_OFFLINE_REVALIDATION,
    READY_FOR_NEW_PROVIDER_CANARY,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    SCHEMA_HASH,
    SELECTED_INTENT_LIMIT,
    TEXT_LIMITS,
)
from app.source_analysis_v31_global_a47_contract_forensics.contract import (
    contract_matrix,
    corrected_text_limits,
    historical_text_limits,
    schema_has_max_length,
)
from app.source_analysis_v31_global_a47_contract_forensics.evidence import (
    a46_intent_text,
    derived_a46_transport,
    verify_a46_identity,
)
from app.source_analysis_v31_global_a47_contract_forensics.intent_review import review_a46_intent
from app.source_analysis_v31_global_a47_contract_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_a47_contract_forensics.prompt_v301 import (
    SYSTEM_PROMPT as SYSTEM_PROMPT_V301,
    prompt_v301_bundle,
)
from app.source_analysis_v31_global_a47_contract_forensics.replay import (
    replay_a46_counterfactual,
    replay_a46_frozen,
)
from app.source_analysis_v31_global_a47_contract_forensics.scanner import classify_a46_editorial
from app.source_analysis_v31_global_reuse_output.prompt_v30 import (
    SYSTEM_PROMPT as SYSTEM_PROMPT_V30,
    prompt_v30_bundle,
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
    def test_a34_through_a46_remain_immutable(self):
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
        assert PHASE == "3B.7.7A.47"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert not source_map_path(PROJECT_NAME).is_file()

    def test_frozen_prompt_schema_transport_unmutated(self):
        prompt = prompt_v30_bundle()
        measured = measure_global_schema_v30()
        schema = build_global_consolidation_schema_v30()
        assert prompt["prompt_version"] == FROZEN_PROMPT_VERSION == "global-consolidation-3.0"
        assert "- intent <= 240" in SYSTEM_PROMPT_V30
        assert HISTORICAL_INTENT_LIMIT == 240
        assert TEXT_LIMITS["intent"] == SELECTED_INTENT_LIMIT == 320
        assert measured["hash"] == SCHEMA_HASH == NEXT_SCHEMA_HASH
        assert FROZEN_TRANSPORT_VERSION == "global-consolidation-transport-3.0"
        assert schema_has_max_length(schema) is False
        assert prompt["previous_prompt_mutated"] is False


class TestA46Identity:
    def test_raw_response_hash_and_fail_status(self):
        identity = verify_a46_identity()
        assert identity["ok"] is True
        assert identity["raw_response_hash"] == A46_RAW_RESPONSE_HASH
        assert identity["recomputed_raw_text_hash"] == A46_RAW_RESPONSE_HASH
        assert identity["a46_historical_status"] == "FAIL"
        assert identity["immutable"] is True
        assert identity["repaired"] is False
        intent = a46_intent_text()
        assert len(intent) == A46_INTENT_LENGTH == 290
        original = intent
        _ = original[:240]
        assert a46_intent_text() == original


class TestIntentContract:
    def test_matrix_locates_240(self):
        matrix = contract_matrix()
        assert "prompt 3.0 instruction (frozen historical)" in matrix["where_240_exists"]
        assert "transport 3.0 JSON schema" in matrix["where_240_does_not_exist"]
        assert matrix["root_cause"] == INTENT_CONTRACT_ROOT_CAUSE
        assert matrix["selected_limit"] == SELECTED_INTENT_LIMIT == 320

    def test_historical_240_rejects_290_selected_320_accepts(self):
        intent = a46_intent_text()
        historical = _validate(_tiny(intent), limits=historical_text_limits())
        assert historical["ok"] is False
        assert any("gm.in exceeds 240" in err for err in historical["errors"])
        selected = _validate(_tiny(intent), limits=corrected_text_limits())
        assert selected["ok"] is True
        live = _validate(_tiny(intent))
        assert live["ok"] is True

    def test_exactly_at_limit_and_limit_plus_one(self):
        limits = corrected_text_limits()
        at = _validate(_tiny("a" * SELECTED_INTENT_LIMIT), limits=limits)
        over = _validate(_tiny("a" * (SELECTED_INTENT_LIMIT + 1)), limits=limits)
        assert at["ok"] is True
        assert over["ok"] is False
        assert any("gm.in exceeds 320" in err for err in over["errors"])

    def test_prompt_3_0_1_is_successor_not_mutation(self):
        frozen = prompt_v30_bundle()
        nxt = prompt_v301_bundle()
        assert nxt["prompt_version"] == NEXT_PROMPT_VERSION == "global-consolidation-3.0.1"
        assert nxt["previous_prompt_mutated"] is False
        assert nxt["activated_production"] == "FUTURE_ONLY"
        assert nxt["previous_prompt_hash"] == frozen["combined_sha256"]
        assert f"intent <= {SELECTED_INTENT_LIMIT}" in SYSTEM_PROMPT_V301
        assert "- intent <= 240" in SYSTEM_PROMPT_V30
        assert nxt["combined_sha256"] != frozen["combined_sha256"]

    def test_intent_semantic_verdict(self):
        review = review_a46_intent(a46_intent_text())
        assert review["verdict"] == INTENT_SEMANTIC_VERDICT
        assert review["modified"] is False
        assert review["truncation_forbidden"] is True
        assert review["fits_selected"] is True


class TestStructuralScanner:
    def test_lexical_chapter_in_idea_text_allowed(self):
        payload = {"i": [{"h": "I1", "v": "The chapter cites Romans.", "m": ["L1"]}]}
        scan = scan_editorial_structure(payload)
        assert scan["ok"] is True
        assert forbidden_editorial_fields(payload) == ()

    def test_lexical_section_and_book_allowed(self):
        payload = {
            "ideas": [
                {"summary": "In this section of scripture the book of Hebrews speaks."},
            ],
            "references": [{"raw_reference": "The conclusion of the cited passage..."}],
        }
        assert scan_editorial_structure(payload)["ok"] is True

    def test_real_chapter_structure_rejected(self):
        payload = {"chapters": [{"title": "One", "body": "no"}]}
        scan = scan_editorial_structure(payload)
        assert scan["ok"] is False
        assert "chapters" in scan["keys"]

    def test_real_section_and_editorial_plan_rejected(self):
        assert scan_editorial_structure({"sections": []})["ok"] is False
        assert scan_editorial_structure({"editorial_plan": {"steps": []}})["ok"] is False
        assert scan_editorial_structure({"book_title": "My Book"})["ok"] is False

    def test_nested_forbidden_structure_rejected(self):
        payload = {"gm": {"th": "x"}, "meta": {"outline": {"chapters": [{"title": "x"}]}}}
        scan = scan_editorial_structure(payload)
        assert scan["ok"] is False
        assert "chapters" in scan["keys"]
        assert "outline" in scan["keys"]

    def test_a46_editorial_is_lexical_false_positive(self):
        transport = derived_a46_transport()
        from app.source_analysis_v31_global_a47_contract_forensics.evidence import (
            read_a46_candidate,
        )

        classified = classify_a46_editorial(transport, read_a46_candidate())
        assert classified["classification"] == "FALSE_POSITIVE_LEXICAL_SCAN"
        assert classified["a46_actual_forbidden_editorial_structure"] == "NO"
        assert classified["lexical_chapter_false_positive"] is True
        assert classified["lexical_hit_count"] > 0


class TestA46Replay:
    def test_frozen_still_fails_validator_counterfactual_passes(self):
        frozen = replay_a46_frozen()
        assert frozen["historical_status"] == "FAIL"
        assert frozen["global_validator"] == "FAIL"
        assert frozen["canonical_reconstruction"] == "PASS"
        assert frozen["canonical_validation"] == "PASS"
        assert frozen["idea_accountability"] == "286 / 286"
        assert frozen["keep_count"] == 286
        assert frozen["merge_equivalent_count"] == 0
        assert frozen["drop_count"] == 0
        assert frozen["raw_unchanged"] is True
        counter = replay_a46_counterfactual()
        assert counter["historical_a46_status"] == "FAIL"
        assert counter["global_validator"] == "PASS"
        assert counter["canonical_reconstruction"] == "PASS"
        assert counter["canonical_validation"] == "PASS"
        assert counter["counterfactual"] == "PASS"
        assert counter["truncated"] is False
        assert counter["rewritten"] is False
        assert counter["published"] is False
        assert counter["semantic_status"] == "PASS"
        assert (
            CAN_A46_SAVED_RESPONSE_BE_VALIDATED_UNDER_CORRECTED_CONTRACT_WITHOUT_REPAIR
            == "YES"
        )
        assert READY_FOR_A46_OFFLINE_REVALIDATION == "YES"
        assert READY_FOR_NEW_PROVIDER_CANARY == "NO"
        raw = derived_a46_transport()
        again = derived_a46_transport()
        assert raw == again
        mutated = copy.deepcopy(raw)
        mutated["gm"]["in"] = mutated["gm"]["in"][:240]
        assert mutated != raw
