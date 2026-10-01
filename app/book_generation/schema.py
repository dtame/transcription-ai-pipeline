"""
Structured-output schema — book-generation-transport-1.0.

One generation unit (chapter, or section fallback). Compact enough for
repeated chapter calls. Anthropic constraints already learned:
no minLength, no minItems except {0,1}, no maxItems, no minimum/maximum,
no recursive schema, no external $ref.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.ai.providers._anthropic_schema import (
    audit_unsupported_features,
    prepare_anthropic_json_schema,
)
from app.book_generation.constants import (
    BOOK_GENERATION_TRANSPORT_VERSION,
    TRANSPORT_KINDS,
)
from app.file_utils import content_hash

_STRING = {"type": "string"}
_ID_LIST = {"type": "array", "items": {"type": "string"}}


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


def build_book_generation_transport_schema() -> dict[str, Any]:
    paragraph = _object(
        {
            "h": {"type": "string", "description": "Temporary paragraph handle."},
            "k": {
                "type": "string",
                "enum": list(TRANSPORT_KINDS),
                "description": "sub=substantive, con=connective.",
            },
            "t": {"type": "string", "description": "Paragraph text."},
            "e": {
                **_ID_LIST,
                "description": "Supplied evidence handles only.",
            },
            "u": {
                **_ID_LIST,
                "description": "Optional UNC handles when uncertainty is preserved.",
            },
        },
        required=["k", "t"],
    )
    section = _object(
        {
            "sid": {
                "type": "string",
                "description": "Canonical section ID from the supplied plan.",
            },
            "paras": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/$defs/paragraph"},
            },
        },
        required=["sid", "paras"],
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": BOOK_GENERATION_TRANSPORT_VERSION,
        "type": "object",
        "required": ["sections"],
        "properties": {
            "sections": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/$defs/section"},
            },
        },
        "$defs": {
            "paragraph": paragraph,
            "section": section,
        },
    }


def schema_identity(schema: Mapping[str, Any] | None = None) -> dict[str, Any]:
    raw = dict(schema or build_book_generation_transport_schema())
    raw_text = json.dumps(raw, ensure_ascii=False, sort_keys=True)
    raw_bytes = raw_text.encode("utf-8")
    adapted = prepare_anthropic_json_schema(raw)
    adapted_text = json.dumps(adapted, ensure_ascii=False, sort_keys=True)
    adapted_bytes = adapted_text.encode("utf-8")
    audit = audit_unsupported_features(adapted)
    incompat = sum(len(v) for v in audit.values())
    return {
        "transport_version": BOOK_GENERATION_TRANSPORT_VERSION,
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
    schema = build_book_generation_transport_schema()
    return json.dumps(schema, ensure_ascii=False, sort_keys=True).encode("utf-8")


def adapted_schema_bytes() -> bytes:
    adapted = prepare_anthropic_json_schema(build_book_generation_transport_schema())
    return json.dumps(adapted, ensure_ascii=False, sort_keys=True).encode("utf-8")
