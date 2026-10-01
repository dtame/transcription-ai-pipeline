"""Schéma provider global-consolidation-transport-3.0. Pas d'envoi Anthropic."""

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
    schema_contains_unsupported_constructs,
)
from app.source_analysis_v31_global_output_architecture.constants import (
    DROP_REASONS_V20,
)
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    build_global_consolidation_schema_v20,
)
from app.source_analysis_v31_global_preflight.transport import GM_FIELDS

ROOT_FIELDS = ("gm", "t", "i", "x", "f", "u", "drop")
TOPIC_FIELDS = ("h", "v", "m")
IDEA_REQUIRED_FIELDS = ("h", "m", "p")
IDEA_OPTIONAL_FIELDS = ("v",)
EXAMPLE_FIELDS = ("h", "l", "g")
REF_FIELDS = ("h", "l")
UNC_FIELDS = ("h", "l")
DROP_FIELDS = ("i", "w")
NEXT_TRANSPORT_VERSION = "global-consolidation-transport-3.0"
PREVIOUS_TRANSPORT_VERSION = "global-consolidation-transport-2.0"


def build_global_consolidation_schema_v30() -> dict[str, Any]:
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
                    "required": list(IDEA_REQUIRED_FIELDS),
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


def global_schema_v30_fingerprint(schema: Mapping[str, Any] | None = None) -> str:
    payload = build_global_consolidation_schema_v30() if schema is None else schema
    return content_hash(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))


def measure_global_schema_v30() -> dict[str, Any]:
    schema = build_global_consolidation_schema_v30()
    measured = measure_schema_pair(schema)
    adapted_schema = prepare_anthropic_json_schema(schema)
    v20 = build_global_consolidation_schema_v20()
    v20_measured = measure_schema_pair(v20)
    raw = int(measured.get("raw_bytes") or 0)
    adapted_bytes = int(measured.get("adapted_bytes") or 0)
    raw_v20 = int(v20_measured.get("raw_bytes") or 0)
    adapted_v20 = int(v20_measured.get("adapted_bytes") or 0)
    return {
        "transport_version": NEXT_TRANSPORT_VERSION,
        "previous_transport_version": PREVIOUS_TRANSPORT_VERSION,
        "is_source_map": False,
        "purpose": (
            "compact provider transport 3.0; hard single-member REUSE; "
            "synthesized v only on multi-member merges; derived SRC; "
            "canonical SourceMap reconstructed offline"
        ),
        "raw_bytes": raw,
        "adapted_bytes": adapted_bytes,
        "hash": global_schema_v30_fingerprint(schema),
        "v20_raw_bytes": raw_v20,
        "v20_adapted_bytes": adapted_v20,
        "raw_delta_bytes": raw - raw_v20,
        "adapted_delta_bytes": adapted_bytes - adapted_v20,
        "grammar_canary_required": True,
        "grammar_canary_run": False,
        "sent_to_anthropic": False,
        "unsupported_constructs": schema_contains_unsupported_constructs(schema),
        "adapted_unsupported": audit_unsupported_features(adapted_schema),
        "conditional_schema_used": False,
        "v_optional_uniform_wire": True,
        "reuse_vs_synthesize": "derived from membership cardinality and field presence",
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
            "i.v": "synthesized proposition; FORBIDDEN on single-member REUSE",
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
            "single-member idea proposition text",
            "explicit reuse/synthesize mode string",
        ],
        "canonical_ids": "assigned by deterministic reconstruction, never by provider",
        "schema": schema,
        "adapted_schema": adapted_schema,
        "unsupported_schema_keywords": list(UNSUPPORTED_SCHEMA_KEYWORDS),
    }


__all__ = [
    "DROP_FIELDS",
    "EXAMPLE_FIELDS",
    "IDEA_OPTIONAL_FIELDS",
    "IDEA_REQUIRED_FIELDS",
    "NEXT_TRANSPORT_VERSION",
    "PREVIOUS_TRANSPORT_VERSION",
    "REF_FIELDS",
    "ROOT_FIELDS",
    "TOPIC_FIELDS",
    "UNC_FIELDS",
    "build_global_consolidation_schema_v30",
    "global_schema_v30_fingerprint",
    "measure_global_schema_v30",
]
