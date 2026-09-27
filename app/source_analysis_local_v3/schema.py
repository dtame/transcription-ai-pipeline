"""
semantic-transport-v3 — contrat local versionné.

Ne mute pas semantic-transport-v1 / v2.
Ajoute h (owner handle) et change l en tableau de handles symboliques.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.file_utils import content_hash
from app.source_analysis_local_v2.schema import measure_schema_pair
from app.source_analysis_local_v3.constants import (
    SEMANTIC_TRANSPORT_VERSION_V3,
    SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
)

V3_ROOT_FIELDS = (
    "theme",
    "intent",
    "ic",
    "aud",
    "ac",
    "records",
)
V3_RECORD_FIELDS = ("k", "v", "s", "h", "l", "m")


def build_semantic_transport_v3_schema() -> dict:
    """
    Schéma raw v3. Aucune enum, aucun maxItems, aucun pattern.

    h = owner handle (chaîne ; vide pour les kinds sans owner).
    l = handles symboliques cibles (chaînes). Pas d'index numériques.
    La grammaire Tn/In est validée en Python, pas par le schéma provider.
    """
    return {
        "type": "object",
        "required": list(V3_ROOT_FIELDS),
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
                    "required": list(V3_RECORD_FIELDS),
                    "properties": {
                        "k": {"type": "string"},
                        "v": {"type": "string"},
                        "s": {"type": "array", "items": {"type": "string"}},
                        "h": {"type": "string"},
                        "l": {"type": "array", "items": {"type": "string"}},
                        "m": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    }


def semantic_transport_v3_fingerprint(schema: Mapping[str, Any] | None = None) -> str:
    payload = build_semantic_transport_v3_schema() if schema is None else schema
    return content_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def measure_v3_schema_pair() -> dict[str, Any]:
    schema = build_semantic_transport_v3_schema()
    measured = measure_schema_pair(schema)
    measured["transport_version"] = SEMANTIC_TRANSPORT_VERSION_V3
    measured["server_grammar_acceptance"] = "UNVERIFIED"
    measured["a13_does_not_verify_v3"] = True
    return measured


def build_semantic_transport_v31_local_lite_schema() -> dict:
    """
    Même forme JSON que v3. Le contrat sémantique change ; le schéma fil ne change pas.
    """
    return build_semantic_transport_v3_schema()


def semantic_transport_v31_local_lite_fingerprint(
    schema: Mapping[str, Any] | None = None,
) -> str:
    payload = (
        build_semantic_transport_v31_local_lite_schema() if schema is None else schema
    )
    return semantic_transport_v3_fingerprint(payload)


def measure_v31_local_lite_schema_pair() -> dict[str, Any]:
    schema = build_semantic_transport_v31_local_lite_schema()
    measured = measure_schema_pair(schema)
    v3 = measure_v3_schema_pair()
    measured["transport_version"] = SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE
    measured["wire_shape_identical_to_v3"] = (
        measured.get("raw_bytes") == v3.get("raw_bytes")
        and measured.get("adapted_bytes") == v3.get("adapted_bytes")
        and semantic_transport_v31_local_lite_fingerprint(schema)
        == semantic_transport_v3_fingerprint()
    )
    measured["server_grammar_acceptance"] = v3.get("server_grammar_acceptance")
    measured["a13_does_not_verify_v3"] = True
    return measured


__all__ = [
    "V3_RECORD_FIELDS",
    "V3_ROOT_FIELDS",
    "build_semantic_transport_v3_schema",
    "build_semantic_transport_v31_local_lite_schema",
    "measure_v3_schema_pair",
    "measure_v31_local_lite_schema_pair",
    "semantic_transport_v3_fingerprint",
    "semantic_transport_v31_local_lite_fingerprint",
]
