"""Mesure d'identité du schéma v3.1-local-lite. 0 provider."""

from __future__ import annotations

from typing import Any

from app.source_analysis_local_v3.schema import (
    measure_v31_local_lite_schema_pair,
    semantic_transport_v3_fingerprint,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis_v3_symbolic_grammar_canary.payload import measure_v3_schema_bytes
from app.source_analysis_v31_local_lite.constants import (
    A17_SCHEMA_FINGERPRINT,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    MODE,
    PHASE,
    SCHEMA_VERSION,
    TRANSPORT_VERSION,
)


def build_schema_identity() -> dict[str, Any]:
    v3 = measure_v3_schema_bytes()
    v31 = measure_v31_local_lite_schema_pair()
    raw_hash = semantic_transport_v31_local_lite_fingerprint()
    identical = (
        int(v31.get("raw_bytes") or 0) == EXPECTED_RAW_SCHEMA_BYTES
        and int(v31.get("adapted_bytes") or 0) == EXPECTED_ADAPTED_SCHEMA_BYTES
        and raw_hash == A17_SCHEMA_FINGERPRINT
        and raw_hash == semantic_transport_v3_fingerprint()
        and bool(v31.get("wire_shape_identical_to_v3"))
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "transport": TRANSPORT_VERSION,
        "raw_bytes": v31.get("raw_bytes"),
        "adapted_bytes": v31.get("adapted_bytes"),
        "schema_hash": raw_hash,
        "expected_raw_bytes": EXPECTED_RAW_SCHEMA_BYTES,
        "expected_adapted_bytes": EXPECTED_ADAPTED_SCHEMA_BYTES,
        "a17_hash": A17_SCHEMA_FINGERPRINT,
        "v3_raw_bytes": v3.get("raw_bytes"),
        "v3_adapted_bytes": v3.get("adapted_bytes"),
        "identical_to_a18": identical,
        "server_grammar_status": (
            "A18_PROOF_APPLICABLE" if identical else "UNVERIFIED"
        ),
        "grammar_canary_recommended": not identical,
        "wire_shape_unchanged": True,
        "semantic_contract_changed": True,
    }


__all__ = ["build_schema_identity"]
