"""Schéma provider global-consolidation-transport-1.1. Pas d'envoi Anthropic."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.ai.providers._anthropic_schema import audit_unsupported_features
from app.file_utils import content_hash
from app.source_analysis_local_v2.schema import measure_schema_pair
from app.source_analysis_v31_global_preflight.transport import (
    DISP_FIELDS,
    GM_FIELDS,
    NODE_FIELDS,
    REL_FIELDS,
    ROOT_FIELDS,
    build_global_consolidation_schema,
)

NEXT_TRANSPORT_VERSION = "global-consolidation-transport-1.1"
REPRESENTATION_OPS = (
    "KEEP",
    "MERGE_EQUIVALENT",
    "DROP",
    "OTHER",
)
REASON_CODES = (
    "none",
    "exact_duplicate",
    "transport_artifact",
    "non_substantive_fragment",
)
DROP_REASON_CODES = (
    "exact_duplicate",
    "transport_artifact",
    "non_substantive_fragment",
)
NON_DROP_REASON_CODE = "none"
RETIRED_OPS = ("LINK_RELATED",)
UNSUPPORTED_SCHEMA_KEYWORDS = (
    "if",
    "then",
    "else",
    "dependentRequired",
    "dependentSchemas",
    "oneOf",
    "anyOf",
    "allOf",
    "$ref",
)


def build_global_consolidation_schema_v11() -> dict[str, Any]:
    string_items = {"type": "array", "items": {"type": "string"}}
    return {
        "type": "object",
        "required": list(ROOT_FIELDS),
        "properties": {
            "gm": {
                "type": "object",
                "required": list(GM_FIELDS),
                "properties": {
                    "th": {"type": "string"},
                    "in": {"type": "string"},
                    "ic": {"type": "string"},
                    "au": {"type": "string"},
                    "ac": {"type": "string"},
                    "vo": {"type": "string"},
                },
            },
            "n": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": list(NODE_FIELDS),
                    "properties": {
                        "h": {"type": "string"},
                        "k": {"type": "string"},
                        "v": {"type": "string"},
                        "s": string_items,
                        "m": string_items,
                    },
                },
            },
            "r": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": list(REL_FIELDS),
                    "properties": {
                        "t": {"type": "string"},
                        "a": {"type": "string"},
                        "b": {"type": "string"},
                        "s": string_items,
                    },
                },
            },
            "d": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": list(DISP_FIELDS),
                    "properties": {
                        "i": {"type": "string"},
                        "o": {
                            "type": "string",
                            "enum": list(REPRESENTATION_OPS),
                        },
                        "g": {"type": "string"},
                        "w": {
                            "type": "string",
                            "enum": list(REASON_CODES),
                        },
                    },
                },
            },
        },
    }


def schema_contains_unsupported_constructs(schema: Mapping[str, Any]) -> list[str]:
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key in UNSUPPORTED_SCHEMA_KEYWORDS:
                if key in node:
                    found.append(key)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return sorted(set(found))


def global_schema_v11_fingerprint(schema: Mapping[str, Any] | None = None) -> str:
    payload = build_global_consolidation_schema_v11() if schema is None else schema
    return content_hash(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))


def measure_global_schema_v11() -> dict[str, Any]:
    schema = build_global_consolidation_schema_v11()
    measured = measure_schema_pair(schema)
    adapted = measured.get("adapted") or {}
    v10 = build_global_consolidation_schema()
    v10_measured = measure_schema_pair(v10)
    raw = int(measured.get("raw_bytes") or 0)
    adapted_bytes = int(measured.get("adapted_bytes") or 0)
    raw_v10 = int(v10_measured.get("raw_bytes") or 0)
    adapted_v10 = int(v10_measured.get("adapted_bytes") or 0)
    unsupported_constructs = schema_contains_unsupported_constructs(schema)
    adapted_unsupported = audit_unsupported_features(
        measured.get("adapted") and schema or schema
    )
    from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema

    adapted_schema = prepare_anthropic_json_schema(schema)
    adapted_audit = audit_unsupported_features(adapted_schema)
    return {
        "transport_version": NEXT_TRANSPORT_VERSION,
        "previous_transport_version": "global-consolidation-transport-1.0",
        "is_source_map": False,
        "purpose": "provider transport; canonical SourceMap is reconstructed offline",
        "raw_bytes": raw,
        "adapted_bytes": adapted_bytes,
        "hash": global_schema_v11_fingerprint(schema),
        "raw": measured.get("raw"),
        "adapted": adapted,
        "v10_raw_bytes": raw_v10,
        "v10_adapted_bytes": adapted_v10,
        "raw_delta_bytes": raw - raw_v10,
        "adapted_delta_bytes": adapted_bytes - adapted_v10,
        "raw_delta_percent": round(100.0 * (raw - raw_v10) / raw_v10, 2) if raw_v10 else None,
        "adapted_delta_percent": (
            round(100.0 * (adapted_bytes - adapted_v10) / adapted_v10, 2)
            if adapted_v10
            else None
        ),
        "grammar_canary_required": True,
        "grammar_canary_run": False,
        "a35_grammar_acceptance_does_not_prove_v11": True,
        "sent_to_anthropic": False,
        "conditional_schema_used": False,
        "unsupported_constructs": unsupported_constructs,
        "adapted_unsupported": adapted_audit,
        "field_meanings": {
            "gm.th": "global theme",
            "gm.in": "author intent",
            "gm.ic": "intent confidence",
            "gm.au": "target audience",
            "gm.ac": "audience confidence",
            "gm.vo": "author voice profile",
            "n.h": "provider-local symbolic handle (T1/I1/E1/F1/U1/P1)",
            "n.k": "TOPIC|IDEA|EXAMPLE|REFERENCE|UNCERTAINTY|REPETITION",
            "n.v": "text",
            "n.s": "canonical SRC refs",
            "n.m": "importance and optional flags; IDEA kind stays empty",
            "r.t": "relation type",
            "r.a": "left handle",
            "r.b": "right handle",
            "r.s": "supporting SRC",
            "d.i": "local input id",
            "d.o": "KEEP|MERGE_EQUIVALENT|DROP|OTHER (representation only)",
            "d.g": "global handle or empty",
            "d.w": "machine reason_code: none|exact_duplicate|transport_artifact|non_substantive_fragment",
        },
        "representation_ops": list(REPRESENTATION_OPS),
        "reason_codes": list(REASON_CODES),
        "retired_ops": list(RETIRED_OPS),
        "canonical_ids": "assigned by deterministic reconstruction, never by provider",
        "schema": schema,
        "adapted_schema": adapted_schema,
    }


__all__ = [
    "DROP_REASON_CODES",
    "NEXT_TRANSPORT_VERSION",
    "NON_DROP_REASON_CODE",
    "REASON_CODES",
    "REPRESENTATION_OPS",
    "RETIRED_OPS",
    "UNSUPPORTED_SCHEMA_KEYWORDS",
    "build_global_consolidation_schema_v11",
    "global_schema_v11_fingerprint",
    "measure_global_schema_v11",
    "schema_contains_unsupported_constructs",
]
