"""Politique SRC 1.1 — canonicalisation étroite d'identifiants. Pas de réparation sémantique."""

from __future__ import annotations

from typing import Any

from app.source_analysis_local_v3.src_policy import (
    CORRECTION_REASON,
    ELIGIBLE_MALFORMED_PREFIX_CASEFOLD,
    PIPELINE_POSITION,
    src_reference_policy,
)
from app.source_analysis_v31_src_canonicalization.constants import (
    A19_CANONICAL,
    A19_MALFORMED,
    CORRECTION_REASON_CODE,
    EXPECTED_CANONICAL,
    MALFORMED_TOKEN,
    MODE,
    NUMERIC_PAYLOAD,
    PHASE,
    PIPELINE_PLACEMENT,
    SCHEMA_VERSION,
    SIGNATURE_DECISION,
    SIGNATURE_INCLUDES_SRC_POLICY,
    SRC_POLICY_NEW,
    SRC_POLICY_OLD,
)


def build_policy() -> dict[str, Any]:
    live = src_reference_policy()
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "feature": "IDENTIFIER_CANONICALIZATION",
        "not": "semantic_repair",
        "old_policy_version": SRC_POLICY_OLD,
        "new_policy_version": SRC_POLICY_NEW,
        "canonical_format": "SRC + six decimal digits",
        "canonical_example": EXPECTED_CANONICAL,
        "already_valid_src_never_rewritten": True,
        "eligible_only_if_not_already_canonical": True,
        "required_digit_payload_width": 6,
        "numeric_preservation": {
            "change_digit": False,
            "insert_digit": False,
            "delete_digit": False,
            "reorder_digits": False,
            "pad": False,
            "truncate": False,
        },
        "prefix_rule": {
            "type": "closed_casefold_set",
            "eligible_malformed_prefix_casefold": sorted(
                ELIGIBLE_MALFORMED_PREFIX_CASEFOLD
            ),
            "unrestricted_fuzzy_matching": False,
            "generic_strip_to_digits": False,
            "historical_forms_admitted": [A19_MALFORMED, MALFORMED_TOKEN],
            "arbitrary_prefixes_rejected": [
                "ABC007337",
                "foo007337",
                "source007337",
                "007337",
                "XRC007337",
            ],
            "rationale": (
                "Closed set {src, srec} admits the demonstrated provider "
                "literal-copy class (SRc case-only; SRec insertion+case) "
                "and rejects arbitrary alphabetic prefixes."
            ),
        },
        "gates": {
            "ownership": "canonical candidate must be in the current window owned SRC set",
            "existence": "canonical candidate must exist in exact CLEAN transcript data",
            "unique_candidate": "exactly one candidate or reject",
            "fail_closed": True,
        },
        "correction_reason": CORRECTION_REASON_CODE,
        "raw_token_preserved_as": "raw_source_ref",
        "canonical_token_preserved_as": "canonical_source_ref",
        "semantic_auto_approval": False,
        "pipeline_position": PIPELINE_PLACEMENT,
        "decoder_remains_strict": True,
        "strict_raw_validity_distinct_from_derived": True,
        "historical_strict_policy_preserved": True,
        "a19_offline_regression_token": A19_MALFORMED,
        "a19_offline_regression_canonical": A19_CANONICAL,
        "a19_historical_status_rewritten": False,
        "win007_authorized_mapping": {
            "raw": MALFORMED_TOKEN,
            "canonical": EXPECTED_CANONICAL,
            "numeric_payload": NUMERIC_PAYLOAD,
        },
        "signature": {
            "src_policy_in_window_signature_inputs": SIGNATURE_INCLUDES_SRC_POLICY,
            "decision": SIGNATURE_DECISION,
            "reason": (
                "WindowSignatureInputs hashes window input, prompt, transport, "
                "schema, provider, model, thinking — not SRC identifier policy. "
                "A.33 reuses the A.31 WIN007 analysis signature and records the "
                "SRC policy version in candidate provenance and cache identity."
            ),
        },
        "live_policy": live,
        "correction_reason_constant": CORRECTION_REASON,
        "pipeline_position_constant": PIPELINE_POSITION,
    }


__all__ = ["build_policy"]
