"""Structured-output schema — book-semantic-validation-transport-1.0.

Compatible with existing OpenAIEngine infrastructure:
response_format=json_object + local schema validation.
Do not invent unverified json_schema request features.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.book_semantic_gate_4b23.constants import (
    CLASSIFICATIONS,
    SEMANTIC_VALIDATION_TRANSPORT_VERSION,
    STRUCTURED_OUTPUT_MODE,
    VERDICT_FAIL,
    VERDICT_PASS,
    VERDICT_REVIEW,
)
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.file_utils import content_hash

_STRING = {"type": "string"}
_INT = {"type": "integer"}
_BOOL = {"type": "boolean"}
_ID_LIST = {"type": "array", "items": {"type": "string"}}
_VERDICTS = [VERDICT_PASS, VERDICT_REVIEW, VERDICT_FAIL]


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


def build_semantic_validation_schema() -> dict[str, Any]:
    claim = _object(
        {
            "i": {**_INT, "description": "Temporary claim index inside the paragraph."},
            "t": {**_STRING, "description": "Claim text copied from the paragraph."},
            "s": {**_INT, "description": "Inclusive start offset in paragraph text."},
            "e": {**_INT, "description": "Exclusive end offset in paragraph text."},
            "k": {
                "type": "string",
                "enum": list(CLASSIFICATIONS),
                "description": "Claim classification.",
            },
            "ev": {**_ID_LIST, "description": "Supporting evidence handles used."},
            "r": {
                "type": "array",
                "items": {"type": "string", "enum": list(REASON_CODES)},
                "description": "Reason codes. Empty when SUPPORTED or NON_SUBSTANTIVE.",
            },
            "x": {
                **_STRING,
                "description": "Brief evidence-grounded explanation. No hidden reasoning.",
            },
            "cf": {
                "type": "string",
                "enum": ["HIGH", "MEDIUM", "LOW"],
                "description": "Optional confidence.",
            },
        },
        required=["i", "t", "s", "e", "k", "ev", "r", "x"],
    )
    paragraph = _object(
        {
            "h": {**_STRING, "description": "Paragraph handle from the candidate."},
            "v": {
                "type": "string",
                "enum": list(CLASSIFICATIONS),
                "description": "Worst-class paragraph verdict.",
            },
            "c": {
                "type": "array",
                "items": {"$ref": "#/$defs/claim"},
                "description": "Claim decomposition covering the paragraph.",
            },
            "ev": {**_ID_LIST, "description": "Evidence handles used for this paragraph."},
            "r": {
                "type": "array",
                "items": {"type": "string", "enum": list(REASON_CODES)},
            },
        },
        required=["h", "v", "c", "ev", "r"],
    )
    counts = _object(
        {
            "supported": _INT,
            "questionable": _INT,
            "unsupported": _INT,
            "non_substantive": _INT,
        },
        required=["supported", "questionable", "unsupported", "non_substantive"],
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": SEMANTIC_VALIDATION_TRANSPORT_VERSION,
        "type": "object",
        "required": ["ch", "v", "pr", "sc", "uh", "rr"],
        "properties": {
            "ch": {**_STRING, "description": "Canonical chapter handle."},
            "v": {
                "type": "string",
                "enum": _VERDICTS,
                "description": "Chapter verdict after local acceptance policy.",
            },
            "pr": {
                "type": "array",
                "items": {"$ref": "#/$defs/paragraph"},
                "description": "One result per required paragraph.",
            },
            "sc": counts,
            "uh": {**_ID_LIST, "description": "Unknown paragraph or evidence handles."},
            "rr": {**_BOOL, "description": "True when human review is required."},
        },
        "$defs": {
            "claim": claim,
            "paragraph": paragraph,
        },
    }


def schema_identity(schema: Mapping[str, Any] | None = None) -> dict[str, Any]:
    raw = dict(schema or build_semantic_validation_schema())
    raw_text = json.dumps(raw, ensure_ascii=False, sort_keys=True)
    raw_bytes = raw_text.encode("utf-8")
    return {
        "transport_version": SEMANTIC_VALIDATION_TRANSPORT_VERSION,
        "raw_schema_sha256": content_hash(raw_text),
        "raw_schema_bytes": len(raw_bytes),
        "engine_mode": STRUCTURED_OUTPUT_MODE,
        "native_json_schema_response_format": False,
        "openai_engine_compatible": True,
        "temperature_in_schema": False,
        "thinking_in_schema": False,
        "additional_properties_closed": False,
        "note": (
            "OpenAIEngine currently sends response_format=json_object. "
            "This schema is the local contract and prompt identity, not an "
            "unverified native json_schema API feature."
        ),
    }


def canonical_schema_bytes() -> bytes:
    schema = build_semantic_validation_schema()
    return json.dumps(schema, ensure_ascii=False, sort_keys=True).encode("utf-8")


__all__ = [
    "build_semantic_validation_schema",
    "canonical_schema_bytes",
    "schema_identity",
]
