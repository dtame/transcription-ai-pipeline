"""
Schéma JSON du transport provider — editorial-plan-transport-1.0.

Distinct du contrat EditorialPlan canonique. Les IDs CH/SEC, stats,
provenance et coverage complète sont reconstruits localement.

Contraintes Anthropic déjà apprises (Phase 3B) :
pas de minLength, pas de minItems hors {0,1}, pas de maxItems,
pas de minimum/maximum, pas de schéma récursif, pas de $ref externe.
additionalProperties reste absent du canonique ; l'adaptateur Anthropic
ferme la copie provider.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.editorial_planning.constants import (
    DEFERRAL_REASONS,
    EDITORIAL_ACTIONS,
    EDITORIAL_PLAN_TRANSPORT_VERSION,
    EXCLUSION_REASONS,
)
from app.file_utils import content_hash

_ID_LIST = {"type": "array", "items": {"type": "string"}}
_STRING = {"type": "string"}


def _object(
    properties: dict[str, Any],
    required: list[str] | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        node["required"] = list(required)
    if description:
        node["description"] = description
    return node


def build_editorial_plan_transport_schema() -> dict[str, Any]:
    action = _object(
        {
            "k": {
                "type": "string",
                "enum": list(EDITORIAL_ACTIONS),
                "description": "Editorial action kind.",
            },
            "n": {"type": "string", "description": "Short organizational note."},
        },
        required=["k"],
    )
    coverage_row = _object(
        {
            "id": {"type": "string", "description": "Canonical IDEA id."},
            "why": {
                "type": "string",
                "description": "Closed reason vocabulary.",
            },
            "n": {"type": "string", "description": "Short note."},
        },
        required=["id", "why"],
    )
    section = _object(
        {
            "h": {"type": "string", "description": "Temporary section handle."},
            "t": {"type": "string", "description": "Working title."},
            "p": {"type": "string", "description": "Purpose, not manuscript prose."},
            "i": {**_ID_LIST, "description": "IDEA ids. At least one after validation."},
            "x": {**_ID_LIST, "description": "EXAMPLE ids."},
            "ref": {**_ID_LIST, "description": "REFERENCE ids."},
            "u": {**_ID_LIST, "description": "UNCERTAINTY ids."},
            "rep": {**_ID_LIST, "description": "REPETITION ids."},
            "top": {**_ID_LIST, "description": "TOPIC ids."},
            "act": {
                "type": "array",
                "items": {"$ref": "#/$defs/action"},
            },
        },
        required=["t", "p", "i"],
    )
    chapter = _object(
        {
            "h": {"type": "string", "description": "Temporary chapter handle."},
            "t": {"type": "string", "description": "Working title."},
            "p": {"type": "string", "description": "Purpose."},
            "sum": {"type": "string", "description": "Short coverage summary."},
            "top": {**_ID_LIST, "description": "TOPIC ids."},
            "act": {
                "type": "array",
                "items": {"$ref": "#/$defs/action"},
            },
            "sections": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/$defs/section"},
            },
        },
        required=["t", "p", "sections"],
    )
    title = _object(
        {
            "t": {"type": "string", "description": "Editorial title candidate."},
            "why": {"type": "string", "description": "Why this candidate."},
        },
        required=["t"],
    )
    concept = _object(
        {
            "promise": _STRING,
            "subject": _STRING,
            "journey": _STRING,
            "progression": {
                "type": "string",
                "description": "Reader progression if supported by content.",
            },
        },
        required=["promise", "subject", "journey", "progression"],
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": EDITORIAL_PLAN_TRANSPORT_VERSION,
        "type": "object",
        "required": [
            "concept",
            "titles",
            "pick",
            "angle",
            "reader",
            "strategy",
            "chapters",
            "deferred",
            "excluded",
        ],
        "properties": {
            "concept": concept,
            "titles": {"type": "array", "minItems": 1, "items": title},
            "pick": {
                "type": "integer",
                "description": "Index into titles for the working title.",
            },
            "subtitle": _STRING,
            "angle": _STRING,
            "reader": _STRING,
            "strategy": _STRING,
            "chapters": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/$defs/chapter"},
            },
            "deferred": {
                "type": "array",
                "items": coverage_row,
                "description": f"IDEAs deferred. why in {list(DEFERRAL_REASONS)}.",
            },
            "excluded": {
                "type": "array",
                "items": coverage_row,
                "description": f"IDEAs excluded. why in {list(EXCLUSION_REASONS)}.",
            },
        },
        "$defs": {
            "action": action,
            "section": section,
            "chapter": chapter,
        },
    }


def schema_identity(schema: Mapping[str, Any] | None = None) -> dict[str, Any]:
    raw = dict(schema or build_editorial_plan_transport_schema())
    raw_text = json.dumps(raw, ensure_ascii=False, sort_keys=True)
    raw_bytes = raw_text.encode("utf-8")
    adapted = prepare_anthropic_json_schema(raw)
    adapted_text = json.dumps(adapted, ensure_ascii=False, sort_keys=True)
    adapted_bytes = adapted_text.encode("utf-8")
    audit = audit_unsupported_features(adapted)
    incompat = sum(len(v) for v in audit.values())
    return {
        "transport_version": EDITORIAL_PLAN_TRANSPORT_VERSION,
        "raw_schema_sha256": content_hash(raw_text),
        "adapted_schema_sha256": content_hash(adapted_text),
        "raw_schema_bytes": len(raw_bytes),
        "adapted_schema_bytes": len(adapted_bytes),
        "anthropic_known_incompatibilities": incompat,
        "anthropic_audit": {key: list(value) for key, value in audit.items()},
        "additional_properties_false_on_adapted": _all_objects_closed(adapted),
    }


def _all_objects_closed(node: Any) -> bool:
    if isinstance(node, dict):
        if node.get("type") == "object" and node.get("additionalProperties") is not False:
            return False
        return all(_all_objects_closed(value) for value in node.values())
    if isinstance(node, list):
        return all(_all_objects_closed(item) for item in node)
    return True


def canonical_schema_bytes() -> bytes:
    schema = build_editorial_plan_transport_schema()
    return json.dumps(schema, ensure_ascii=False, sort_keys=True).encode("utf-8")


def adapted_schema_bytes() -> bytes:
    adapted = prepare_anthropic_json_schema(build_editorial_plan_transport_schema())
    return json.dumps(adapted, ensure_ascii=False, sort_keys=True).encode("utf-8")
