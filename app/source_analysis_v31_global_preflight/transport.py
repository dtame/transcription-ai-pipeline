"""Schéma provider compact global-consolidation-transport-1.0. Pas d'envoi Anthropic."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.file_utils import content_hash
from app.source_analysis_local_v2.schema import measure_schema_pair
from app.source_analysis_v31_global_preflight.constants import (
    GLOBAL_TRANSPORT_VERSION,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)

ROOT_FIELDS = ("gm", "n", "r", "d")
GM_FIELDS = ("th", "in", "ic", "au", "ac", "vo")
NODE_FIELDS = ("h", "k", "v", "s", "m")
REL_FIELDS = ("t", "a", "b", "s")
DISP_FIELDS = ("i", "o", "g", "w")


def build_global_consolidation_schema() -> dict[str, Any]:
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
                        "o": {"type": "string"},
                        "g": {"type": "string"},
                        "w": {"type": "string"},
                    },
                },
            },
        },
    }


def global_schema_fingerprint(schema: Mapping[str, Any] | None = None) -> str:
    payload = build_global_consolidation_schema() if schema is None else schema
    return content_hash(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))


def measure_global_schema() -> dict[str, Any]:
    schema = build_global_consolidation_schema()
    measured = measure_schema_pair(schema)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "transport_version": GLOBAL_TRANSPORT_VERSION,
        "is_source_map": False,
        "purpose": "provider transport; canonical SourceMap is reconstructed offline",
        "raw_bytes": measured.get("raw_bytes"),
        "adapted_bytes": measured.get("adapted_bytes"),
        "hash": global_schema_fingerprint(schema),
        "raw": measured.get("raw"),
        "adapted": measured.get("adapted"),
        "grammar_canary_required": True,
        "grammar_canary_run": False,
        "sent_to_anthropic": False,
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
            "d.o": "KEEP|MERGE_EQUIVALENT|LINK_RELATED|OTHER|DROP",
            "d.g": "global handle or empty",
            "d.w": "reason / note",
        },
        "canonical_ids": "assigned by deterministic reconstruction, never by provider",
        "schema": schema,
    }


__all__ = [
    "DISP_FIELDS",
    "GM_FIELDS",
    "NODE_FIELDS",
    "REL_FIELDS",
    "ROOT_FIELDS",
    "build_global_consolidation_schema",
    "global_schema_fingerprint",
    "measure_global_schema",
]
