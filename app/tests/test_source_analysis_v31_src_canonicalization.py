"""Phase 3B.7.7A.33 — canonicalisation SRC étroite + replay WIN007. 0 provider."""

from __future__ import annotations

import copy
import hashlib

import pytest

from app.source_analysis.errors import WindowTransportValidationError
from app.source_analysis.writer import source_map_path
from app.source_analysis.window_granularity import POLICY_VERSION as V10_POLICY
from app.source_analysis_hybrid.constants import PLANNER_VERSION
from app.source_analysis_local_v2.constants import GRANULARITY_POLICY_VERSION
from app.source_analysis_local_v2.granularity import (
    EXAMPLE_V_TEXT_HARD_LIMIT,
    TEXT_HARD_LIMITS,
    THEME_TEXT_HARD_LIMIT,
)
from app.source_analysis_local_v3.decoder import decode_v31_local_lite_transport
from app.source_analysis_local_v3.schema import (
    measure_v31_local_lite_schema_pair,
    semantic_transport_v3_fingerprint,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis_local_v3.source_refs import collect_v3_source_refs, is_canonical_src
from app.source_analysis_local_v3.src_canonicalization import (
    apply_src_reference_policy,
    canonicalize_src_token,
    classify_malformed_token,
)
from app.source_analysis_local_v3.src_policy import (
    CORRECTION_REASON,
    ELIGIBLE_MALFORMED_PREFIX_CASEFOLD,
    src_reference_policy,
)
from app.source_analysis_v3_a19_forensics.constants import (
    A19_MALFORMED_SRC,
    A19_STATUS_UNCHANGED,
)
from app.source_analysis_v31_src_canonicalization.constants import (
    A18_PROOF_STILL_APPLIES,
    A19_CANONICAL,
    A19_MALFORMED,
    A31_HISTORICAL_STATUS,
    A32_STATUS,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_CANONICAL,
    EXPECTED_RAW_SCHEMA_BYTES,
    EXPECTED_SCHEMA_HASH,
    MALFORMED_TOKEN,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SRC_POLICY_NEW,
    SRC_POLICY_OLD,
    WIN007_NEW_PROVIDER_CALL,
    WIN007_RAW_SHA256,
    WIN007_REQUEST_ID,
)
from app.source_analysis_v31_src_canonicalization.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_src_canonicalization.replay import replay_strict_and_canonical
from app.source_analysis_v31_src_typo_forensics.constants import OPTION_B_IMPLEMENTED
from app.source_analysis_v31_src_typo_forensics.evidence import (
    read_win007_raw_bytes,
    win007_raw_path,
)
from app.source_analysis_v31_src_typo_forensics.replay import replay_win007_offline


@pytest.fixture(autouse=True)
def _no_network(no_ai_network):
    return None


OWNED = {EXPECTED_CANONICAL, "SRC007207", "SRC007338", "SRC000609"}
EXISTING = set(OWNED) | {"SRC008415"}


def _payload_with(token: str) -> dict:
    return {
        "theme": "t",
        "intent": "i",
        "ic": "ic",
        "aud": "a",
        "ac": "ac",
        "records": [{"k": "IDEA", "h": "I1", "v": "claim", "s": [token], "l": [], "m": ["primary"]}],
    }


class TestOffline:
    def test_package_offline_and_unwired(self):
        assert_offline_package()
        assert_analyzer_not_wired()
        assert REAL_PROVIDER_CALLS_THIS_PHASE == 0
        assert REAL_WINDOW_CALLS == 0
        assert WIN007_NEW_PROVIDER_CALL is False
        assert A31_HISTORICAL_STATUS == "FAIL"
        assert A32_STATUS == "PASS"
        assert OPTION_B_IMPLEMENTED is False
        assert PHASE_3B_STATUS == "INCOMPLETE"
        assert PRODUCTION_PLANNER_VERSION == PLANNER_VERSION == "window-planner-v2.0"
        assert not source_map_path(PROJECT_NAME).is_file()


class TestCanonicalizer:
    def test_canonical_src_unchanged(self):
        decision = canonicalize_src_token(
            EXPECTED_CANONICAL, owned=OWNED, existing=EXISTING
        )
        assert decision["action"] == "unchanged"
        assert decision["rewritten"] is False
        assert decision["canonical_source_ref"] == EXPECTED_CANONICAL
        assert is_canonical_src(EXPECTED_CANONICAL) is True

    def test_src000609_eligible(self):
        decision = canonicalize_src_token(
            A19_MALFORMED, owned=OWNED, existing=EXISTING
        )
        assert A19_MALFORMED == "SRc000609"
        assert classify_malformed_token(A19_MALFORMED)["eligible"] is True
        assert decision["action"] == "canonicalized"
        assert decision["canonical_source_ref"] == A19_CANONICAL
        assert decision["reason"] == CORRECTION_REASON
        assert decision["raw_source_ref"] == A19_MALFORMED

    def test_srec007337_eligible(self):
        decision = canonicalize_src_token(
            MALFORMED_TOKEN, owned=OWNED, existing=EXISTING
        )
        assert decision["action"] == "canonicalized"
        assert decision["canonical_source_ref"] == EXPECTED_CANONICAL
        assert decision["digits"] == "007337"
        assert decision["reason"] == CORRECTION_REASON

    def test_arbitrary_prefix_rejected(self):
        for token in ("ABC007337", "foo007337", "source007337", "007337", "XRC007337"):
            decision = canonicalize_src_token(token, owned=OWNED, existing=EXISTING)
            assert decision["action"] == "rejected", token
            assert decision["rewritten"] is False

    def test_wrong_digit_count_rejected(self):
        for token in ("SRec07337", "SRec0007337"):
            decision = canonicalize_src_token(token, owned=OWNED, existing=EXISTING)
            assert decision["action"] == "rejected"
            assert classify_malformed_token(token)["reason"] == "DIGIT_PAYLOAD_NOT_SIX"

    def test_out_of_window_rejected(self):
        decision = canonicalize_src_token(
            "SRec000001", owned=OWNED, existing=EXISTING | {"SRC000001"}
        )
        assert decision["action"] == "rejected"
        assert decision["reason"] == "OUT_OF_WINDOW"

    def test_unknown_canonical_src_rejected(self):
        owned = {EXPECTED_CANONICAL}
        existing = {EXPECTED_CANONICAL}
        decision = canonicalize_src_token(
            "SRec007338", owned=owned, existing=existing
        )
        assert decision["action"] == "rejected"
        assert decision["reason"] in {"OUT_OF_WINDOW", "UNKNOWN_SRC"}

    def test_valid_src_never_rewritten(self):
        payload = _payload_with("SRC007338")
        original = copy.deepcopy(payload)
        result = apply_src_reference_policy(
            payload, owned=OWNED, existing=EXISTING
        )
        assert payload == original
        assert result["derived"]["records"][0]["s"][0] == "SRC007338"
        assert result["audit"]["canonicalized_src_count"] == 0

    def test_numeric_mutation_not_redirected_to_intended(self):
        decision = canonicalize_src_token(
            "SRec007338", owned=OWNED, existing=EXISTING
        )
        assert decision["canonical_source_ref"] != EXPECTED_CANONICAL
        if decision["action"] == "canonicalized":
            assert decision["canonical_source_ref"] == "SRC007338"

    def test_raw_object_unchanged(self):
        payload = _payload_with(MALFORMED_TOKEN)
        marker = id(payload)
        token_before = payload["records"][0]["s"][0]
        result = apply_src_reference_policy(
            payload, owned=OWNED, existing=EXISTING
        )
        assert id(payload) == marker
        assert payload["records"][0]["s"][0] == token_before == MALFORMED_TOKEN
        assert result["derived"]["records"][0]["s"][0] == EXPECTED_CANONICAL
        assert result["audit"]["raw_object_is_derived"] is False

    def test_provenance_emitted(self):
        payload = _payload_with(MALFORMED_TOKEN)
        result = apply_src_reference_policy(
            payload, owned=OWNED, existing=EXISTING
        )
        audit = result["audit"]
        assert audit["canonicalized_src_count"] == 1
        assert audit["raw_malformed_src_count"] == 1
        assert audit["rejected_malformed_src_count"] == 0
        row = audit["corrections"][0]
        assert row["raw_source_ref"] == MALFORMED_TOKEN
        assert row["canonical_source_ref"] == EXPECTED_CANONICAL
        assert row["reason"] == CORRECTION_REASON

    def test_ambiguous_or_invalid_fail_closed(self):
        empty = canonicalize_src_token("", owned=OWNED, existing=EXISTING)
        assert empty["action"] == "rejected"
        banana = canonicalize_src_token("banana", owned=OWNED, existing=EXISTING)
        assert banana["action"] == "rejected"
        none = canonicalize_src_token(None, owned=OWNED, existing=EXISTING)
        assert none["action"] == "rejected"

    def test_strict_policy_does_not_rewrite(self):
        payload = _payload_with(MALFORMED_TOKEN)
        result = apply_src_reference_policy(
            payload,
            owned=OWNED,
            existing=EXISTING,
            policy_version=SRC_POLICY_OLD,
        )
        assert result["derived"]["records"][0]["s"][0] == MALFORMED_TOKEN
        assert result["audit"]["canonicalized_src_count"] == 0
        assert result["audit"]["rejected_malformed_src_count"] == 1
        assert result["audit"]["strict_raw_validity"] == "FAIL"

    def test_prefix_set_is_closed(self):
        assert ELIGIBLE_MALFORMED_PREFIX_CASEFOLD == frozenset({"src", "srec"})
        policy = src_reference_policy()
        assert policy["generic_strip_to_digits"] is False
        assert policy["already_valid_src_never_rewritten"] is True

    def test_decoder_remains_strict_on_raw_malformed(self):
        errors: list[str] = []
        refs = collect_v3_source_refs(
            [MALFORMED_TOKEN], "records[13]", errors, {EXPECTED_CANONICAL}
        )
        assert refs == []
        assert any(MALFORMED_TOKEN in err for err in errors)
        with pytest.raises(WindowTransportValidationError, match=MALFORMED_TOKEN):
            decode_v31_local_lite_transport(
                _payload_with(MALFORMED_TOKEN),
                allowed_source_refs={EXPECTED_CANONICAL},
            )


class TestWin007Replay:
    def test_strict_policy_still_fails(self):
        replay = replay_win007_offline(PROJECT_NAME)
        assert replay["request_id"] == WIN007_REQUEST_ID
        assert replay["reproduced"] is True
        assert replay["observed_token"] == MALFORMED_TOKEN
        assert replay["v31_decoder"] == "FAIL"
        assert replay["src_inventory"]["malformed_occurrences"] == 1
        assert replay["src_inventory"]["total_src_occurrences"] == 290
        assert replay["src_inventory"]["exact_valid_occurrences"] == 289

    def test_new_policy_passes_with_exactly_one_correction(self):
        before = win007_raw_path(PROJECT_NAME).read_bytes()
        replay = replay_strict_and_canonical(PROJECT_NAME)
        after = win007_raw_path(PROJECT_NAME).read_bytes()
        assert after == before
        assert hashlib.sha256(after).hexdigest() == WIN007_RAW_SHA256
        assert replay["raw_response_mutated"] is False
        assert replay["original_payload_token_still_srec"] is True
        assert replay["strict_reproduced"] is True
        assert replay["raw_token"] == MALFORMED_TOKEN
        assert replay["canonical_token"] == EXPECTED_CANONICAL
        assert replay["canonicalized_src"] == 1
        assert replay["rejected_malformed_src"] == 0
        assert replay["exactly_one_canonicalization"] is True
        assert replay["decoder"] == "PASS"
        assert replay["handle_registry"] == "PASS"
        assert replay["handle_resolution"] == "PASS"
        assert replay["local_validator"] == "PASS"
        assert replay["length_policy"] == "PASS"
        assert replay["canonical_reconstruction"] == "PASS"
        assert replay["strict_raw_validity"] == "FAIL"
        assert replay["derived_canonical_validity"] == "PASS"
        assert replay["provider_calls"] == 0
        assert replay["example_max"] == 211
        assert replay["example_max"] <= 225

    def test_identity_matches_saved_request(self):
        replay = replay_strict_and_canonical(PROJECT_NAME)
        assert replay["identity"]["request_id"] == WIN007_REQUEST_ID
        assert replay["identity"]["same_paid_response"] is True


class TestHistorical:
    def test_a31_failure_reproducible(self):
        replay = replay_win007_offline(PROJECT_NAME)
        assert A31_HISTORICAL_STATUS == "FAIL"
        assert replay["reproduced"] is True
        raw = read_win007_raw_bytes(PROJECT_NAME)
        assert hashlib.sha256(raw).hexdigest() == WIN007_RAW_SHA256

    def test_a19_historical_status_unchanged(self):
        assert A19_STATUS_UNCHANGED == "FAIL"
        assert A19_MALFORMED_SRC == "SRc000609"
        assert A19_MALFORMED == A19_MALFORMED_SRC

    def test_a30_kind_specific_length_policy_unchanged(self):
        assert THEME_TEXT_HARD_LIMIT == 225
        assert EXAMPLE_V_TEXT_HARD_LIMIT == 225
        assert TEXT_HARD_LIMITS["EXAMPLE.v"] == 225
        assert TEXT_HARD_LIMITS["theme"] == 225
        assert GRANULARITY_POLICY_VERSION == "window-granularity-1.1-minimal"
        assert V10_POLICY == "window-granularity-1.0"


class TestSchemaUnchanged:
    def test_a18_grammar_identity(self):
        pair = measure_v31_local_lite_schema_pair()
        assert pair["raw_bytes"] == EXPECTED_RAW_SCHEMA_BYTES == 588
        assert pair["adapted_bytes"] == EXPECTED_ADAPTED_SCHEMA_BYTES == 650
        assert semantic_transport_v31_local_lite_fingerprint() == EXPECTED_SCHEMA_HASH
        assert semantic_transport_v3_fingerprint() == EXPECTED_SCHEMA_HASH
        assert A18_PROOF_STILL_APPLIES is True
        assert SRC_POLICY_OLD == "src-reference-policy-1.0-strict"
        assert SRC_POLICY_NEW == "src-reference-policy-1.1-narrow-canonicalization"
