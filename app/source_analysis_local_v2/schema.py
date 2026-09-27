"""
semantic-transport-v2 — contrat local versionné.

Même forme records[] que Generation C (grammar compactness).
Ce n'est PAS un alias de semantic-transport-v1 : le schéma est reconstruit
ici, le decoder/validator ferment les kinds locaux, v1 reste intact.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.file_utils import content_hash
from app.source_analysis.schema_complexity import analyze_schema_complexity
from app.source_analysis.ultra_compact_schema import build_ultra_compact_response_schema
from app.source_analysis_local_v2.constants import (
    DEFERRED_KINDS,
    LOCAL_KINDS,
    SEMANTIC_TRANSPORT_VERSION_V2,
)

V2_ROOT_FIELDS = (
    "theme",
    "intent",
    "ic",
    "aud",
    "ac",
    "records",
)
V2_RECORD_FIELDS = ("k", "v", "s", "l", "m")


def build_semantic_transport_v2_schema() -> dict:
    """
    Schéma raw v2. Aucune enum, aucun maxItems, aucun pattern.

    Forme identique à Generation C pour ne pas augmenter la grammaire.
    Les kinds autorisés sont validés localement, pas par le schéma provider.
    """
    return {
        "type": "object",
        "required": list(V2_ROOT_FIELDS),
        "properties": {
            "theme": {"type": "string"},
            "intent": {"type": "string"},
            "ic": {"type": "string"},
            "aud": {"type": "string"},
            "ac": {"type": "string"},
            "records": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": list(V2_RECORD_FIELDS),
                    "properties": {
                        "k": {"type": "string"},
                        "v": {"type": "string"},
                        "s": {"type": "array", "items": {"type": "string"}},
                        "l": {"type": "array", "items": {"type": "integer"}},
                        "m": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    }


def build_semantic_transport_v2_fixed_slot_schema() -> dict:
    """Variante hors production — comparaison de complexité uniquement."""
    item = {
        "type": "object",
        "required": ["v", "s", "l", "m"],
        "properties": {
            "v": {"type": "string"},
            "s": {"type": "array", "items": {"type": "string"}},
            "l": {"type": "array", "items": {"type": "integer"}},
            "m": {"type": "array", "items": {"type": "string"}},
        },
    }
    return {
        "type": "object",
        "required": ["theme", "intent", "ic", "aud", "ac", *tuple(k.lower() for k in LOCAL_KINDS)],
        "properties": {
            "theme": {"type": "string"},
            "intent": {"type": "string"},
            "ic": {"type": "string"},
            "aud": {"type": "string"},
            "ac": {"type": "string"},
            **{kind.lower(): {"type": "array", "items": item} for kind in LOCAL_KINDS},
        },
    }


def semantic_transport_v2_fingerprint(schema: Mapping[str, Any] | None = None) -> str:
    payload = build_semantic_transport_v2_schema() if schema is None else schema
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def measure_schema_pair(schema: Mapping[str, Any]) -> dict[str, Any]:
    adapted = prepare_anthropic_json_schema(schema)
    raw_metrics = analyze_schema_complexity(schema)
    adapted_metrics = analyze_schema_complexity(adapted)
    unsupported = audit_unsupported_features(adapted)
    return {
        "raw": raw_metrics,
        "adapted": adapted_metrics,
        "adapted_unsupported": unsupported,
        "raw_bytes": raw_metrics["serialized_json_bytes"],
        "adapted_bytes": adapted_metrics["serialized_json_bytes"],
        "maxItems_in_raw": raw_metrics.get("constraints", 0) and "maxItems" in json.dumps(schema),
        "maxItems_in_adapted": bool(unsupported.get("maxItems")),
        "provider_cardinality_enforced": False,
        "server_grammar_acceptance": "UNVERIFIED",
    }


def compare_v1_v2_schemas() -> dict[str, Any]:
    v1 = build_ultra_compact_response_schema()
    v2 = build_semantic_transport_v2_schema()
    slots = build_semantic_transport_v2_fixed_slot_schema()
    v1_m = measure_schema_pair(v1)
    v2_m = measure_schema_pair(v2)
    slots_m = measure_schema_pair(slots)
    return {
        "transport_version": SEMANTIC_TRANSPORT_VERSION_V2,
        "not_an_alias_of_v1": True,
        "v1_is_generation_c": True,
        "shape": "generic_records",
        "local_kinds": list(LOCAL_KINDS),
        "deferred_kinds_absent_from_decoder": list(DEFERRED_KINDS),
        "v1": v1_m,
        "v2_generic": v2_m,
        "v2_fixed_slots": slots_m,
        "v2_vs_v1_raw_bytes_delta": v2_m["raw_bytes"] - v1_m["raw_bytes"],
        "v2_vs_v1_adapted_bytes_delta": v2_m["adapted_bytes"] - v1_m["adapted_bytes"],
        "fixed_slots_vs_generic_adapted_delta": (
            slots_m["adapted_bytes"] - v2_m["adapted_bytes"]
        ),
        "selected_shape": "generic_records",
        "selected_reason": (
            "Same ultra-compact records[] shape as Generation C. "
            "Lower grammar complexity than fixed slots. Compatible with "
            "existing decoder/normalizer architecture. No maxItems."
        ),
        "grammar_risk": "UNVERIFIED",
        "future_grammar_canary_recommended": v2_m["raw_bytes"] != v1_m["raw_bytes"]
        or True,
    }


def transport_design_facts() -> dict[str, Any]:
    comparison = compare_v1_v2_schemas()
    return {
        "version": SEMANTIC_TRANSPORT_VERSION_V2,
        "historical_v1_unchanged": True,
        "comparison": comparison,
    }


__all__ = [
    "V2_RECORD_FIELDS",
    "V2_ROOT_FIELDS",
    "build_semantic_transport_v2_fixed_slot_schema",
    "build_semantic_transport_v2_schema",
    "compare_v1_v2_schemas",
    "measure_schema_pair",
    "semantic_transport_v2_fingerprint",
    "transport_design_facts",
]
