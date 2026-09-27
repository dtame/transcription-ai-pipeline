"""
consolidation-transport-v1 — schéma provider MINIMAL.

Le provider ne renvoie PAS le SourceMap canonique.
Aucune enum, aucun pattern, aucun minItems : le decoder local est strict.
Leçon Generation C : garder le schéma radicalement compact.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.file_utils import content_hash
from app.source_analysis.consolidation_models import CONSOLIDATION_TRANSPORT_VERSION
from app.source_analysis.schema_complexity import analyze_schema_complexity

CONSOLIDATION_SCHEMA_VERSION = "1.0"

CONSOLIDATION_ROOT_FIELDS = ("gm", "ops")
CONSOLIDATION_GM_FIELDS = ("th", "in", "au", "vo", "te", "ie", "ae", "ve")
CONSOLIDATION_OP_FIELDS = ("o", "r", "m", "v", "t", "a", "b", "c")


def build_consolidation_response_schema() -> dict:
    """
    Schéma JSON du transport de consolidation.

    Reconstruit à chaque appel. 1 objet racine + 1 objet gm + 1 array ops.
    """
    string_items = {"type": "array", "items": {"type": "string"}}
    return {
        "type": "object",
        "required": list(CONSOLIDATION_ROOT_FIELDS),
        "properties": {
            "gm": {
                "type": "object",
                "required": list(CONSOLIDATION_GM_FIELDS),
                "properties": {
                    "th": {"type": "string"},
                    "in": {"type": "string"},
                    "au": {"type": "string"},
                    "vo": {"type": "string"},
                    "te": dict(string_items),
                    "ie": dict(string_items),
                    "ae": dict(string_items),
                    "ve": dict(string_items),
                },
            },
            "ops": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["o"],
                    "properties": {
                        "o": {"type": "string"},
                        "r": {"type": "string"},
                        "m": {"type": "array", "items": {"type": "string"}},
                        "v": {"type": "string"},
                        "t": {"type": "string"},
                        "a": {"type": "string"},
                        "b": {"type": "string"},
                        "c": {"type": "string"},
                    },
                },
            },
        },
    }


def consolidation_schema_fingerprint(schema: Mapping[str, Any] | None = None) -> str:
    payload = build_consolidation_response_schema() if schema is None else schema
    return content_hash(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))


def consolidation_schema_metrics(schema: Mapping[str, Any] | None = None) -> dict[str, int]:
    payload = build_consolidation_response_schema() if schema is None else schema
    return analyze_schema_complexity(payload)


def looks_like_consolidation_transport(payload: Mapping[str, Any] | None) -> bool:
    if not isinstance(payload, Mapping):
        return False
    return "gm" in payload and "ops" in payload


__all__ = [
    "CONSOLIDATION_GM_FIELDS",
    "CONSOLIDATION_OP_FIELDS",
    "CONSOLIDATION_ROOT_FIELDS",
    "CONSOLIDATION_SCHEMA_VERSION",
    "CONSOLIDATION_TRANSPORT_VERSION",
    "build_consolidation_response_schema",
    "consolidation_schema_fingerprint",
    "consolidation_schema_metrics",
    "looks_like_consolidation_transport",
]
