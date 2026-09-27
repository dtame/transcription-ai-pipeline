"""Prépare, sans exécuter, le canary grammar v3. 0 POST."""

from __future__ import annotations

from typing import Any

from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.source_analysis_local_v3.schema import (
    build_semantic_transport_v3_schema,
    measure_v3_schema_pair,
)
from app.source_analysis_v2_grammar_canary.constants import (
    EXPECTED_ADAPTED_SCHEMA_BYTES as V2_ADAPTED,
)
from app.source_analysis_v2_grammar_canary.constants import (
    EXPECTED_RAW_SCHEMA_BYTES as V2_RAW,
)
from app.source_analysis_v3_symbolic_handles.constants import (
    CANARY_EXECUTED,
    CANARY_MAX_OUTPUT_TOKENS,
    CANARY_SRC_IDS,
    CANARY_TEXTS,
    CANARY_TRANSCRIPT_ID,
    CANARY_WINDOW_ID,
    MODE,
    MODEL,
    PHASE,
    SCHEMA_VERSION,
    SEMANTIC_TRANSPORT_VERSION_V2,
    SEMANTIC_TRANSPORT_VERSION_V3,
    THINKING_MODE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
)


def build_grammar_canary_readiness() -> dict[str, Any]:
    schema = build_semantic_transport_v3_schema()
    measured = measure_v3_schema_pair()
    adapted = prepare_anthropic_json_schema(schema)
    unsupported = audit_unsupported_features(adapted)
    materially_different = (
        measured["raw_bytes"] != V2_RAW or measured["adapted_bytes"] != V2_ADAPTED
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "prepared": True,
        "executed": CANARY_EXECUTED,
        "authorized_now": False,
        "materially_different_from_v2": materially_different,
        "a13_verifies": SEMANTIC_TRANSPORT_VERSION_V2,
        "a13_does_not_verify_v3": True,
        "server_grammar_verified": False,
        "future_canary": {
            "window_id": CANARY_WINDOW_ID,
            "transcript_id": CANARY_TRANSCRIPT_ID,
            "src_ids": list(CANARY_SRC_IDS),
            "texts": list(CANARY_TEXTS),
            "pastoral": False,
            "win001": False,
            "model": MODEL,
            "thinking": THINKING_MODE,
            "effort": None,
            "max_output_tokens": CANARY_MAX_OUTPUT_TOKENS,
            "max_attempts": 1,
            "retry": False,
            "transport": SEMANTIC_TRANSPORT_VERSION_V3,
            "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V13,
            "mandatory_stop": True,
        },
        "schema": {
            "raw_bytes": measured["raw_bytes"],
            "adapted_bytes": measured["adapted_bytes"],
            "v2_raw_bytes": V2_RAW,
            "v2_adapted_bytes": V2_ADAPTED,
            "additionalProperties_false": True,
            "unsupported": unsupported,
            "pattern_in_schema": False,
            "enum_in_schema": False,
            "maxItems_in_schema": False,
        },
        "next_phase_if_pass": "3B.7.7A.18 — do not execute now",
    }


__all__ = ["build_grammar_canary_readiness"]
