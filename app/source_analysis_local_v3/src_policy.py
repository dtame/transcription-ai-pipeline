"""Politiques SRC versionnées. 1.0 strict immuable. 1.1 canonicalisation étroite.

Ce n'est PAS une réparation sémantique. Le décodeur reste fail-closed sur
les identifiants qu'il reçoit. La canonicalisation n'opère que sur une
copie dérivée, après parse structuré, avant le décodage strict.
"""

from __future__ import annotations

from typing import Any

from app.source_analysis_local_v3.constants import (
    CURRENT_SRC_REFERENCE_POLICY_VERSION,
    HISTORICAL_SRC_REFERENCE_POLICY_VERSION,
    SRC_REFERENCE_POLICY_VERSION_10_STRICT,
    SRC_REFERENCE_POLICY_VERSION_11_NARROW_CANONICALIZATION,
)
from app.source_analysis_local_v3.source_refs import SRC_PREFIX, SRC_WIDTH

# Closed prefix set. Not unrestricted fuzzy matching.
# "src"  = case-only corruption of the canonical 3-letter prefix (SRc, Src, …).
# "srec" = observed 4-letter insertion form (SRec, SREC, …).
ELIGIBLE_MALFORMED_PREFIX_CASEFOLD = frozenset({"src", "srec"})
CORRECTION_REASON = "MALFORMED_SRC_PREFIX_EXACT_NUMERIC_PAYLOAD"

PIPELINE_POSITION = (
    "after raw structured parse / before strict derived SRC validation "
    "and decoding that require canonical identifiers"
)

SIGNATURE_DECISION = "REUSE_EXISTING_WINDOW_SIGNATURE_DISTINCT_CANDIDATE_PROVENANCE"


def src_reference_policy() -> dict[str, Any]:
    return {
        "current_policy_version": CURRENT_SRC_REFERENCE_POLICY_VERSION,
        "historical_strict_policy_version": HISTORICAL_SRC_REFERENCE_POLICY_VERSION,
        "strict_policy_version": SRC_REFERENCE_POLICY_VERSION_10_STRICT,
        "narrow_canonicalization_policy_version": (
            SRC_REFERENCE_POLICY_VERSION_11_NARROW_CANONICALIZATION
        ),
        "canonical_format": f"{SRC_PREFIX}" + ("[0-9]" * SRC_WIDTH),
        "canonical_example": "SRC007337",
        "eligible_malformed_prefix_casefold": sorted(ELIGIBLE_MALFORMED_PREFIX_CASEFOLD),
        "correction_reason": CORRECTION_REASON,
        "pipeline_position": PIPELINE_POSITION,
        "semantic_repair": False,
        "already_valid_src_never_rewritten": True,
        "generic_strip_to_digits": False,
        "fail_closed": True,
        "signature": {
            "src_policy_in_window_signature_inputs": False,
            "src_policy_in_candidate_provenance": True,
            "src_policy_in_validator_policy_version": True,
            "src_policy_in_cache_identity": True,
            "decision": SIGNATURE_DECISION,
        },
    }


__all__ = [
    "CORRECTION_REASON",
    "CURRENT_SRC_REFERENCE_POLICY_VERSION",
    "ELIGIBLE_MALFORMED_PREFIX_CASEFOLD",
    "HISTORICAL_SRC_REFERENCE_POLICY_VERSION",
    "PIPELINE_POSITION",
    "SIGNATURE_DECISION",
    "SRC_REFERENCE_POLICY_VERSION_10_STRICT",
    "SRC_REFERENCE_POLICY_VERSION_11_NARROW_CANONICALIZATION",
    "src_reference_policy",
]
