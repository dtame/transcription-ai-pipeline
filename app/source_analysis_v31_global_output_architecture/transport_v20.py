"""Schéma provider global-consolidation-transport-2.0. Pas d'envoi Anthropic."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.file_utils import content_hash
from app.source_analysis.models import IMPORTANCE_LEVELS
from app.source_analysis_local_v2.schema import measure_schema_pair
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    UNSUPPORTED_SCHEMA_KEYWORDS,
    build_global_consolidation_schema_v11,
    schema_contains_unsupported_constructs,
)
from app.source_analysis_v31_global_output_architecture.constants import (
    DROP_REASONS_V20,
    NEXT_TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_preflight.transport import GM_FIELDS

ROOT_FIELDS = ("gm", "t", "i", "x", "f", "u", "drop")
TOPIC_FIELDS = ("h", "v", "m")
IDEA_FIELDS = ("h", "v", "m", "p")
EXAMPLE_FIELDS = ("h", "l", "g")
REF_FIELDS = ("h", "l")
UNC_FIELDS = ("h", "l")
DROP_FIELDS = ("i", "w")


def build_global_consolidation_schema_v20() -> dict[str, Any]:
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
            "t": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": list(TOPIC_FIELDS),
                    "properties": {
                        "h": {"type": "string"},
                        "v": {"type": "string"},
                        "m": string_items,
                    },
                },
            },
            "i": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": list(IDEA_FIELDS),
                    "properties": {
                        "h": {"type": "string"},
                        "v": {"type": "string"},
                        "m": string_items,
                        "p": {
                            "type": "string",
                            "enum": list(IMPORTANCE_LEVELS),
                        },
                    },
                },
            },
            "x": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": list(EXAMPLE_FIELDS),
                    "properties": {
                        "h": {"type": "string"},
                        "l": string_items,
                        "g": string_items,
                    },
                },
            },
            "f": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": list(REF_FIELDS),
                    "properties": {
                        "h": {"type": "string"},
                        "l": string_items,
                    },
                },
            },
            "u": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": list(UNC_FIELDS),
                    "properties": {
                        "h": {"type": "string"},
                        "l": string_items,
                    },
                },
            },
            "drop": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": list(DROP_FIELDS),
                    "properties": {
                        "i": {"type": "string"},
                        "w": {
                            "type": "string",
                            "enum": list(DROP_REASONS_V20),
                        },
                    },
                },
            },
        },
    }


def global_schema_v20_fingerprint(schema: Mapping[str, Any] | None = None) -> str:
    payload = build_global_consolidation_schema_v20() if schema is None else schema
    return content_hash(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))


def measure_global_schema_v20() -> dict[str, Any]:
    schema = build_global_consolidation_schema_v20()
    measured = measure_schema_pair(schema)
    adapted_schema = prepare_anthropic_json_schema(schema)
    v11 = build_global_consolidation_schema_v11()
    v11_measured = measure_schema_pair(v11)
    raw = int(measured.get("raw_bytes") or 0)
    adapted_bytes = int(measured.get("adapted_bytes") or 0)
    raw_v11 = int(v11_measured.get("raw_bytes") or 0)
    adapted_v11 = int(v11_measured.get("adapted_bytes") or 0)
    return {
        "transport_version": NEXT_TRANSPORT_VERSION,
        "previous_transport_version": "global-consolidation-transport-1.1",
        "is_source_map": False,
        "purpose": (
            "compact provider transport; inverse membership; derived SRC; "
            "canonical SourceMap reconstructed offline"
        ),
        "raw_bytes": raw,
        "adapted_bytes": adapted_bytes,
        "hash": global_schema_v20_fingerprint(schema),
        "v11_raw_bytes": raw_v11,
        "v11_adapted_bytes": adapted_v11,
        "raw_delta_bytes": raw - raw_v11,
        "adapted_delta_bytes": adapted_bytes - adapted_v11,
        "grammar_canary_required": True,
        "grammar_canary_run": False,
        "sent_to_anthropic": False,
        "unsupported_constructs": schema_contains_unsupported_constructs(schema),
        "adapted_unsupported": audit_unsupported_features(adapted_schema),
        "conditional_schema_used": False,
        "field_meanings": {
            "gm.th": "global theme",
            "gm.in": "author intent",
            "gm.ic": "intent confidence",
            "gm.au": "target audience",
            "gm.ac": "audience confidence",
            "gm.vo": "author voice profile",
            "t.h": "global topic handle T1…",
            "t.v": "concise topic label",
            "t.m": "local TOPIC input IDs (membership)",
            "i.h": "global idea handle I1…",
            "i.v": "concise global proposition",
            "i.m": "local IDEA input IDs (membership)",
            "i.p": "importance: central|supporting|minor",
            "x.h": "global example handle E1…",
            "x.l": "local EXAMPLE input IDs",
            "x.g": "supported global idea handles",
            "f.h": "global reference handle F1…",
            "f.l": "local REFERENCE input IDs",
            "u.h": "global uncertainty handle U1…",
            "u.l": "local UNCERTAINTY input IDs",
            "drop.i": "dropped local IDEA input ID",
            "drop.w": "transport_artifact|non_substantive_fragment",
        },
        "provider_does_not_emit": [
            "d[] disposition ledger",
            "r[] global relations",
            "SRC arrays",
            "example/reference/uncertainty prose",
            "OTHER",
            "exact_duplicate as DROP",
        ],
        "canonical_ids": "assigned by deterministic reconstruction, never by provider",
        "schema": schema,
        "adapted_schema": adapted_schema,
        "unsupported_schema_keywords": list(UNSUPPORTED_SCHEMA_KEYWORDS),
    }


__all__ = [
    "DROP_FIELDS",
    "EXAMPLE_FIELDS",
    "IDEA_FIELDS",
    "REF_FIELDS",
    "ROOT_FIELDS",
    "TOPIC_FIELDS",
    "UNC_FIELDS",
    "build_global_consolidation_schema_v20",
    "global_schema_v20_fingerprint",
    "measure_global_schema_v20",
]
