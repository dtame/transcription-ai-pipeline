"""Build compact Semantic Gate 2.0 requests. Offsets stay local. No human labels."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from app.book_semantic_gate_4b29.constants import (
    OFFSET_CONVENTION,
    PHASE,
    PROMPT_VERSION_20_CANDIDATE,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b29.contract import semantic_contract_20_candidate
from app.file_utils import content_hash

_LABEL_KEYS = frozenset(
    {
        "expected_class",
        "accepted_classes",
        "role",
        "human_label",
        "human_label_authority",
        "expected_reason_codes",
        "notes",
        "case_id",
    }
)


def _strip_labels(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        return {
            key: _strip_labels(value)
            for key, value in payload.items()
            if str(key) not in _LABEL_KEYS
        }
    if isinstance(payload, list):
        return [_strip_labels(item) for item in payload]
    return payload


def build_model_request(
    prepared: Mapping[str, Any],
    *,
    chapter_handle: str,
    evidence_records: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compact model-facing request. Offsets and labels remain local."""
    units = []
    for unit in prepared.get("units") or []:
        units.append(
            {
                "id": str(unit.get("unit_id") or ""),
                "t": str(unit.get("text") or ""),
            }
        )
    paragraph = {
        "h": str(prepared.get("paragraph_id") or ""),
        "t": str(prepared.get("paragraph") or ""),
        "ev": list(prepared.get("evidence_handles") or []),
        "u": units,
    }
    if evidence_records:
        paragraph["evidence"] = [
            {
                "id": str(item.get("id") or item.get("handle") or ""),
                "text": str(item.get("text") or item.get("sum") or ""),
            }
            for item in evidence_records
            if str(item.get("id") or item.get("handle") or "").strip()
        ]
    model_input = {
        "ch": str(chapter_handle or "").strip(),
        "contract": PROMPT_VERSION_20_CANDIDATE,
        "transport": TRANSPORT_VERSION_20_CANDIDATE,
        "offset_convention": OFFSET_CONVENTION,
        "pr": [paragraph],
    }
    model_input = _strip_labels(model_input)
    contract = semantic_contract_20_candidate()
    user = (
        contract["instructions_candidate"]
        + "\n\nSEMANTIC_GATE_INPUT_JSON\n"
        + json.dumps(model_input, ensure_ascii=False, sort_keys=True)
    )
    messages = [
        {"role": "system", "content": contract["system_candidate"]},
        {"role": "user", "content": user},
    ]
    local_offsets = [
        {
            "unit_id": str(unit.get("unit_id") or ""),
            "start_offset": int(unit.get("start_offset") or 0),
            "end_offset": int(unit.get("end_offset") or 0),
            "boundary_type": str(unit.get("boundary_type") or ""),
            "boundary_ambiguity": bool(unit.get("boundary_ambiguity")),
        }
        for unit in prepared.get("units") or []
    ]
    serialized = json.dumps(model_input, ensure_ascii=False, sort_keys=True)
    return {
        "phase": PHASE,
        "model_input": model_input,
        "messages": messages,
        "local_offsets": local_offsets,
        "offset_convention": OFFSET_CONVENTION,
        "human_labels_included": False,
        "model_asked_to_emit_offsets": False,
        "paragraph_copied_once": True,
        "request_sha256": content_hash(serialized),
        "not_a_terra_request": True,
        "secrets_included": False,
    }


__all__ = ["build_model_request"]
