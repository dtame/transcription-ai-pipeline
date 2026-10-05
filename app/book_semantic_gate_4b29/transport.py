"""Transport 2.0 candidate. Distinct from historical 1.0 / 1.1. No offsets from the model."""

from __future__ import annotations

import json
from typing import Any

from app.book_semantic_gate_4b23.constants import CLASSIFICATIONS
from app.book_semantic_gate_4b23.reasons import REASON_CODES
from app.book_semantic_gate_4b29.constants import (
    MODEL_VERDICTS,
    OFFSET_CONVENTION,
    PHASE,
    TRANSPORT_VERSION_11,
    TRANSPORT_VERSION_20_ACTIVATED,
    TRANSPORT_VERSION_20_CANDIDATE,
    TRANSPORT_VERSION_HISTORICAL,
)
from app.file_utils import content_hash

_STRING = {"type": "string"}
_INT = {"type": "integer"}
_BOOL = {"type": "boolean"}
_ID_LIST = {"type": "array", "items": {"type": "string"}}


def _object(
    properties: dict[str, Any],
    required: list[str] | None = None,
    additional: bool = False,
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": additional,
    }
    if required:
        node["required"] = list(required)
    return node


def build_transport_20_schema() -> dict[str, Any]:
    unit = _object(
        {
            "id": {**_STRING, "description": "Pre-established unit identifier."},
            "k": {
                "type": "string",
                "enum": list(CLASSIFICATIONS),
                "description": "Semantic verdict for the supplied unit.",
            },
            "ev": {**_ID_LIST, "description": "Evidence handles actually used."},
            "r": {
                "type": "array",
                "items": {"type": "string", "enum": list(REASON_CODES)},
                "description": "Closed reason catalog. Empty if SUPPORTED or NON_SUBSTANTIVE.",
            },
            "n": {
                **_STRING,
                "description": "Short reservation when QUESTIONABLE or UNSUPPORTED.",
            },
        },
        required=["id", "k", "ev", "r"],
    )
    paragraph = _object(
        {
            "h": {**_STRING, "description": "Paragraph handle."},
            "v": {
                "type": "string",
                "enum": list(CLASSIFICATIONS),
                "description": "Worst-class paragraph verdict.",
            },
            "u": {
                "type": "array",
                "items": {"$ref": "#/$defs/unit"},
                "description": "One row per supplied unit identifier.",
            },
        },
        required=["h", "v", "u"],
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
        "title": TRANSPORT_VERSION_20_CANDIDATE,
        "type": "object",
        "additionalProperties": False,
        "required": ["ch", "v", "pr", "sc", "uh", "rr"],
        "properties": {
            "ch": {**_STRING, "description": "Chapter handle."},
            "v": {
                "type": "string",
                "enum": list(MODEL_VERDICTS),
                "description": "Model global verdict. FAIL is mapped to BLOCK by local policy.",
            },
            "pr": {
                "type": "array",
                "items": {"$ref": "#/$defs/paragraph"},
            },
            "sc": {"$ref": "#/$defs/counts"},
            "uh": {**_ID_LIST, "description": "Unknown unit or paragraph handles."},
            "rr": {**_BOOL, "description": "Human review required."},
        },
        "$defs": {"unit": unit, "paragraph": paragraph, "counts": counts},
    }


def semantic_transport_20_candidate() -> dict[str, Any]:
    schema = build_transport_20_schema()
    return {
        "phase": PHASE,
        "transport_version": TRANSPORT_VERSION_20_CANDIDATE,
        "transport_activated": TRANSPORT_VERSION_20_ACTIVATED,
        "historical_1_0_unmodified": TRANSPORT_VERSION_HISTORICAL,
        "historical_1_1_unmodified": TRANSPORT_VERSION_11,
        "does_not_modify_historical_transport": True,
        "offset_convention": OFFSET_CONVENTION,
        "input_fields": [
            "ch",
            "contract",
            "transport",
            "offset_convention",
            "pr.h",
            "pr.t",
            "pr.ev",
            "pr.u.id",
            "pr.u.t",
        ],
        "output_fields": ["ch", "v", "pr.h", "pr.v", "pr.u.id", "pr.u.k", "pr.u.ev", "pr.u.r", "pr.u.n", "sc", "uh", "rr"],
        "unit_identifiers": "pre-established u00, u01, ...",
        "verdicts": list(CLASSIFICATIONS),
        "reason_codes": list(REASON_CODES),
        "evidence_handles": "subset of supplied canonical handles",
        "global_verdict": list(MODEL_VERDICTS),
        "errors": "reported by local validator, not repaired",
        "audit_metadata": "stored locally beside the raw response",
        "model_must_not_emit_offsets": True,
        "model_must_not_copy_unit_text": True,
        "compact": True,
        "schema": schema,
        "schema_sha256": content_hash(json.dumps(schema, ensure_ascii=False, sort_keys=True)),
        "secrets_included": False,
    }


__all__ = ["build_transport_20_schema", "semantic_transport_20_candidate"]
