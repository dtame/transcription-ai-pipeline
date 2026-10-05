"""Build Semantic Gate 2.0.2 requests. Offsets stay local. No human labels."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.book_generation_integration_4b213.constants import (
    OFFSET_CONVENTION,
    PHASE,
    PROMPT_VERSION_202_CANDIDATE,
    TRANSPORT_VERSION_20_CANDIDATE,
)
from app.book_semantic_gate_4b212.contract import semantic_contract_202_candidate
from app.file_utils import content_hash


def build_semantic_request(
    prepared: Mapping[str, Any],
    *,
    chapter_id: str,
    section_id: str,
    generator_prompt_version: str,
    source_map_sha256: str,
    editorial_plan_sha256: str,
) -> dict[str, Any]:
    units = [
        {
            "id": str(unit.get("unit_id") or ""),
            "t": str(unit.get("text") or ""),
        }
        for unit in prepared.get("units") or []
    ]
    paragraph = {
        "h": str(prepared.get("paragraph_id") or ""),
        "t": str(prepared.get("paragraph") or ""),
        "ev": list(prepared.get("evidence_handles") or []),
        "u": units,
    }
    model_input = {
        "ch": str(chapter_id or "").strip(),
        "contract": PROMPT_VERSION_202_CANDIDATE,
        "transport": TRANSPORT_VERSION_20_CANDIDATE,
        "offset_convention": OFFSET_CONVENTION,
        "pr": [paragraph],
    }
    contract = semantic_contract_202_candidate()
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
        "local_prepared": dict(prepared),
        "chapter_id": chapter_id,
        "section_id": section_id,
        "generator_prompt_version": generator_prompt_version,
        "source_map_sha256": source_map_sha256,
        "editorial_plan_sha256": editorial_plan_sha256,
        "offset_convention": OFFSET_CONVENTION,
        "human_labels_included": False,
        "model_asked_to_emit_offsets": False,
        "request_sha256": content_hash(serialized),
        "not_a_terra_request": True,
        "secrets_included": False,
    }


__all__ = ["build_semantic_request"]
