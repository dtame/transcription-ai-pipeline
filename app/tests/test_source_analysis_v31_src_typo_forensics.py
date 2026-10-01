"""Phase 3B.7.7A.32 — WIN007 SRC typo forensics. 0 provider. 0 promotion."""

from __future__ import annotations

import hashlib

import pytest

from app.source_analysis.writer import source_map_path
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v3.schema import (
    measure_v31_local_lite_schema_pair,
    semantic_transport_v3_fingerprint,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis_v31_src_typo_forensics.classify import (
    analyze_transformation,
    levenshtein,
    srec_transformation,
)
from app.source_analysis_v31_src_typo_forensics.constants import (
    A18_PROOF_STILL_APPLIES,
    A19_CANONICAL,
    A19_MALFORMED,
    A31_STATUS_UNCHANGED,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_CANONICAL,
    EXPECTED_RAW_SCHEMA_BYTES,
    EXPECTED_SCHEMA_HASH,
    MALFORMED_TOKEN,
    OPTION_B_IMPLEMENTED,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    WIN007_PROMOTION_AUTHORIZED,
    WIN007_RAW_SHA256,
    WIN007_REQUEST_ID,
    WIN007_RETRY_AUTHORIZED,
)
from app.source_analysis_v31_src_typo_forensics.evidence import (
    read_win007_raw_bytes,
    win007_raw_path,
)
from app.source_analysis_v31_src_typo_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_src_typo_forensics.policy import (
    evaluate_prefix_digit_rule,
    option_b_full_token_ed1,
    required_rejection_cases,
)
from app.source_analysis_v31_src_typo_forensics.replay import (
    derived_single_correction,
    replay_win007_offline,
)
from app.source_analysis_v31_src_typo_forensics.counterfactual import (
    replay_derived_correction,
)


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


class TestOffline:
    def test_package_offline_and_unwired(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_WINDOW_CALLS == 0
        assert WIN007_RETRY_AUTHORIZED is False
        assert WIN007_PROMOTION_AUTHORIZED is False
        assert OPTION_B_IMPLEMENTED is False
        assert A31_STATUS_UNCHANGED == "FAIL"
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert PRODUCTION_PLANNER_VERSION == PLANNER_VERSION == "window-planner-v2.0"
        assert not source_map_path(PROJECT_NAME).is_file()


class TestEditDistanceAndHistoryForm:
    def test_srec007337_transformation(self):
        analysis = srec_transformation()
        assert analysis["from"] == EXPECTED_CANONICAL
        assert analysis["to"] == MALFORMED_TOKEN
        assert analysis["edit_distance_case_sensitive"] == 2
        assert analysis["edit_distance_case_insensitive"] == 1
        assert analysis["numeric_payload_preserved"] is True
        assert analysis["prefix_corruption"] is True
        assert analysis["option_b_full_token_ed1"] is False
        assert analysis["production_corrected"] is False

    def test_src000609_historical_form(self):
        analysis = analyze_transformation(A19_MALFORMED, A19_CANONICAL)
        assert A19_MALFORMED == "SRc000609"
        assert A19_CANONICAL == "SRC000609"
        assert analysis["edit_distance_case_sensitive"] == 1
        assert analysis["numeric_payload_preserved"] is True
        assert analysis["prefix_from"] == "SRC"
        assert analysis["prefix_to"] == "SRc"

    def test_levenshtein_numeric_preservation(self):
        assert levenshtein(MALFORMED_TOKEN, EXPECTED_CANONICAL) == 2
        assert MALFORMED_TOKEN[-6:] == EXPECTED_CANONICAL[-6:] == "007337"


class TestCanonicalizationPolicyEvaluator:
    def test_unique_candidate_refined_rule(self):
        owned = {EXPECTED_CANONICAL, "SRC007207", "SRC008415"}
        result = evaluate_prefix_digit_rule(
            MALFORMED_TOKEN,
            owned=owned,
            semantic_compatible=True,
            intended_class="EXACT_INTENDED_SOURCE",
        )
        assert result["accept"] is True
        assert result["candidate"] == EXPECTED_CANONICAL
        assert result["numeric_preserved"] is True

    def test_option_b_as_written_rejects_srec_accepts_src(self):
        owned = {EXPECTED_CANONICAL, A19_CANONICAL}
        srec = option_b_full_token_ed1(MALFORMED_TOKEN, owned=owned)
        src = option_b_full_token_ed1(A19_MALFORMED, owned=owned)
        assert srec["covers_srec007337"] is False
        assert srec["accept"] is False
        assert src["covers_src000609"] is True
        assert src["accept"] is True

    def test_ambiguous_and_required_rejections(self):
        owned = {EXPECTED_CANONICAL, "SRC007207", "SRC007338", "SRC008415"}
        rows = required_rejection_cases(owned)
        names = {row["name"] for row in rows}
        assert "out_of_window" in names
        assert "numeric_payload_change" in names
        assert "already_valid_wrong_reference" in names
        assert "empty_source_token" in names
        assert "non_src_like" in names
        assert "semantic_mismatch" in names
        assert all(row["rejected"] for row in rows)

    def test_already_valid_src_preservation(self):
        owned = {EXPECTED_CANONICAL, "SRC007338"}
        result = evaluate_prefix_digit_rule("SRC007338", owned=owned)
        assert result["accept"] is False
        assert result["reason"] == "already_valid_untouched"
        assert result["must_not_rewrite_valid_src"] is True

    def test_numeric_mutation_rejection(self):
        owned = {EXPECTED_CANONICAL}
        result = evaluate_prefix_digit_rule(
            "SRec007338",
            owned=owned,
            semantic_compatible=True,
            intended_class="EXACT_INTENDED_SOURCE",
        )
        assert result["accept"] is False
        assert "out_of_window_or_unknown" in result["reason"]

    def test_out_of_window_rejection(self):
        owned = {EXPECTED_CANONICAL}
        result = evaluate_prefix_digit_rule("SRec000001", owned=owned)
        assert result["accept"] is False


class TestWin007Replay:
    def test_reproduces_exact_failure(self):
        replay = replay_win007_offline(PROJECT_NAME)
        assert replay["request_id"] == WIN007_REQUEST_ID
        assert replay["request_id_match"] is True
        assert replay["reproduced"] is True
        assert replay["observed_token"] == MALFORMED_TOKEN
        assert replay["structured_parse"] == "PASS"
        assert replay["v31_decoder"] == "FAIL"
        assert replay["response_repaired"] is False
        assert replay["normalized"] is False
        inventory = replay["src_inventory"]
        assert inventory["srec007337_is_only_root"] is True
        assert inventory["malformed_occurrences"] == 1
        raw = read_win007_raw_bytes(PROJECT_NAME)
        assert hashlib.sha256(raw).hexdigest() == WIN007_RAW_SHA256

    def test_counterfactual_single_correction_and_no_raw_mutation(self):
        replay = replay_win007_offline(PROJECT_NAME)
        before = win007_raw_path(PROJECT_NAME).read_bytes()
        derived = derived_single_correction(replay["payload"])
        assert derived["records"][13]["s"][1] == EXPECTED_CANONICAL
        assert replay["payload"]["records"][13]["s"][1] == MALFORMED_TOKEN
        counter = replay_derived_correction(replay)
        after = win007_raw_path(PROJECT_NAME).read_bytes()
        assert after == before
        assert counter["original_raw_unchanged"] is True
        assert counter["original_payload_token_still_srec"] is True
        assert counter["technical"] == "PASS"
        assert counter["other_technical_failures_after_correction"] == []
        assert counter["promoted"] is False
        assert WIN007_PROMOTION_AUTHORIZED is False


class TestSchemaUnchanged:
    def test_a18_grammar_identity(self):
        pair = measure_v31_local_lite_schema_pair()
        assert pair["raw_bytes"] == EXPECTED_RAW_SCHEMA_BYTES == 588
        assert pair["adapted_bytes"] == EXPECTED_ADAPTED_SCHEMA_BYTES == 650
        assert semantic_transport_v31_local_lite_fingerprint() == EXPECTED_SCHEMA_HASH
        assert semantic_transport_v3_fingerprint() == EXPECTED_SCHEMA_HASH
        assert A18_PROOF_STILL_APPLIES is True
