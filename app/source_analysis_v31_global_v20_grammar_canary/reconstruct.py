"""Reconstruction canonique A.40 — transport 2.0 + inventaire synthétique. 0 provider."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.source_analysis.models import AnalysisProvenance
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.validator import ensure_valid_source_map, validate_source_map
from app.source_analysis_v31_global_output_architecture.membership import derived_src_union
from app.source_analysis_v31_global_output_architecture.reconstruct import (
    compact_to_source_map_payload,
)
from app.source_analysis_v31_global_preflight.validator import assign_canonical_ids
from app.source_analysis_v31_global_v20_grammar_canary.constants import (
    IDEA_KIND_POLICY,
    MODEL,
    PHASE,
    PROMPT_VERSION,
    PROVIDER,
    SCHEMA_VERSION,
    TRANSPORT_VERSION,
)


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if isinstance(item, str) and item]


def reconstruct_source_map_v20(
    transport: Mapping[str, Any],
    inventory: Mapping[str, Any],
    transcript: TranscriptInput,
    *,
    signature: str,
) -> dict[str, Any]:
    local_src = inventory.get("src_by_input") or {}
    nodes = []
    for idea in _as_list(transport.get("i")):
        if isinstance(idea, Mapping):
            nodes.append(
                {
                    "h": idea.get("h"),
                    "k": "IDEA",
                    "s": derived_src_union(_strings(idea.get("m")), local_src),
                }
            )
    for topic in _as_list(transport.get("t")):
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
    payload = compact_to_source_map_payload(transport, inventory)
    provenance = AnalysisProvenance(
        prompt_version=PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        provider=PROVIDER,
        model=MODEL,
        strategy="global-consolidation-v20-grammar-canary-a40",
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
            "empty_relations_valid": False,
            "transport_version": TRANSPORT_VERSION,
            "phase": PHASE,
            "source_map_published": False,
        }
    empty_kind = all(idea.kind == "" for idea in source_map.ideas)
    empty_relations = all(not idea.relations for idea in source_map.ideas)
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
    return {
        "ok": not validation_errors and ensure_ok and empty_kind,
        "source_map": source_map,
        "payload": serialized,
        "canonical_json": json.dumps(serialized, ensure_ascii=False, sort_keys=True),
        "assigned_provider_to_canonical": assigned_ids,
        "idea_kind_policy": IDEA_KIND_POLICY,
        "all_idea_kinds_empty": empty_kind,
        "empty_relations_valid": empty_relations and ensure_ok and not validation_errors,
        "validate_source_map": "PASS" if not validation_errors else "FAIL",
        "ensure_valid_source_map": "PASS" if ensure_ok else "FAIL",
        "errors": validation_errors,
        "ensure_error": ensure_error,
        "transport_version": TRANSPORT_VERSION,
        "prompt_version": PROMPT_VERSION,
        "phase": PHASE,
        "source_map_published": False,
        "relations_present": any(idea.relations for idea in source_map.ideas),
        "repetitions_present": bool(source_map.repetitions),
    }


__all__ = ["reconstruct_source_map_v20"]
