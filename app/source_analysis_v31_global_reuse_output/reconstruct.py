"""Reconstruction déterministe transport 3.0 : REUSE hérite du local, SYNTHESIZE use v."""

from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from app.source_analysis.models import AnalysisProvenance
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.validator import ensure_valid_source_map, validate_source_map
from app.source_analysis_v31_global_output_architecture.reconstruct import (
    compact_to_source_map_payload,
)
from app.source_analysis_v31_global_preflight.validator import assign_canonical_ids
from app.source_analysis_v31_global_reuse_output.constants import (
    IDEA_KIND_POLICY,
    MODEL,
    NEXT_PROMPT_VERSION,
    NEXT_TRANSPORT_VERSION,
    PHASE,
    PROVIDER,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_global_reuse_output.validate import derived_src_union


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if isinstance(item, str) and item]


def _local_record(inventory: Mapping[str, Any], input_id: str) -> Mapping[str, Any]:
    records = inventory.get("records") or inventory.get("by_id") or {}
    row = records.get(input_id) if isinstance(records, Mapping) else None
    return row if isinstance(row, Mapping) else {}


def local_idea_text(inventory: Mapping[str, Any], input_id: str) -> str:
    row = _local_record(inventory, input_id)
    return str(row.get("value") or row.get("v") or "")


def expand_reused_idea_text(
    transport: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Injecte le texte local pour REUSE. Ne paraphrase pas."""
    expanded = copy.deepcopy(dict(transport))
    ideas = []
    for idea in _as_list(expanded.get("i")):
        if not isinstance(idea, Mapping):
            continue
        row = dict(idea)
        members = _strings(row.get("m"))
        if len(members) == 1 and not str(row.get("v") or "").strip():
            row["v"] = local_idea_text(inventory, members[0])
            row["reuse"] = True
        else:
            row["reuse"] = False
        ideas.append(row)
    expanded["i"] = ideas
    return expanded


def reconstruct_source_map_v30(
    transport: Mapping[str, Any],
    inventory: Mapping[str, Any],
    transcript: TranscriptInput,
    *,
    signature: str,
) -> dict[str, Any]:
    local_src = inventory.get("src_by_input") or {}
    expanded = expand_reused_idea_text(transport, inventory)
    nodes = []
    for idea in _as_list(expanded.get("i")):
        if isinstance(idea, Mapping):
            nodes.append(
                {
                    "h": idea.get("h"),
                    "k": "IDEA",
                    "s": derived_src_union(_strings(idea.get("m")), local_src),
                }
            )
    for topic in _as_list(expanded.get("t")):
        if isinstance(topic, Mapping):
            nodes.append(
                {
                    "h": topic.get("h"),
                    "k": "TOPIC",
                    "s": derived_src_union(_strings(topic.get("m")), local_src),
                }
            )
    assigned = assign_canonical_ids(nodes)
    assigned_ids = {
        str(item.get("h") or ""): str(item.get("canonical_id") or "")
        for item in assigned
    }
    wire_for_payload = copy.deepcopy(expanded)
    for idea in _as_list(wire_for_payload.get("i")):
        if isinstance(idea, dict):
            idea.pop("reuse", None)
    payload = compact_to_source_map_payload(wire_for_payload, inventory)
    provenance = AnalysisProvenance(
        prompt_version=NEXT_PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        provider=PROVIDER,
        model=MODEL,
        strategy="global-consolidation-reuse-output-a43",
        signature=signature,
    )
    try:
        source_map = normalize_source_map(payload, transcript, provenance=provenance)
    except Exception as exc:  # noqa: BLE001 — no repair
        return {
            "ok": False,
            "source_map": None,
            "payload": payload,
            "canonical_json": "",
            "assigned_provider_to_canonical": assigned_ids,
            "errors": [str(exc)],
            "validate_source_map": "FAIL",
            "ensure_valid_source_map": "FAIL",
            "transport_version": NEXT_TRANSPORT_VERSION,
            "phase": PHASE,
            "source_map_published": False,
        }
    empty_kind = all(idea.kind == "" for idea in source_map.ideas)
    serialized = source_map.to_dict()
    validation_errors = list(validate_source_map(source_map, transcript))
    ensure_ok = False
    ensure_error = None
    try:
        ensure_valid_source_map(source_map, transcript)
        ensure_ok = True
    except Exception as exc:  # noqa: BLE001
        ensure_error = str(exc)
        validation_errors.append(str(exc))
    reuse_exact = []
    for idea in _as_list(expanded.get("i")):
        if not isinstance(idea, Mapping) or not idea.get("reuse"):
            continue
        members = _strings(idea.get("m"))
        expected = local_idea_text(inventory, members[0]) if members else ""
        reuse_exact.append(str(idea.get("v") or "") == expected)
    return {
        "ok": not validation_errors and ensure_ok and empty_kind,
        "source_map": source_map,
        "payload": serialized,
        "canonical_json": json.dumps(serialized, ensure_ascii=False, sort_keys=True),
        "assigned_provider_to_canonical": assigned_ids,
        "idea_kind_policy": IDEA_KIND_POLICY,
        "all_idea_kinds_empty": empty_kind,
        "reuse_text_exact": all(reuse_exact) if reuse_exact else True,
        "reused_ideas": sum(
            1
            for idea in _as_list(expanded.get("i"))
            if isinstance(idea, Mapping) and idea.get("reuse")
        ),
        "validate_source_map": "PASS" if not validation_errors else "FAIL",
        "ensure_valid_source_map": "PASS" if ensure_ok else "FAIL",
        "errors": validation_errors,
        "ensure_error": ensure_error,
        "transport_version": NEXT_TRANSPORT_VERSION,
        "prompt_version": NEXT_PROMPT_VERSION,
        "phase": PHASE,
        "source_map_published": False,
        "relations_present": any(idea.relations for idea in source_map.ideas),
        "repetitions_present": bool(source_map.repetitions),
    }


__all__ = [
    "expand_reused_idea_text",
    "local_idea_text",
    "reconstruct_source_map_v30",
]
