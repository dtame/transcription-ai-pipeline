"""Reconstruction déterministe transport 2.0 + inventaire local → SourceMap."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.source_analysis.models import (
    EXAMPLE_KINDS,
    IMPORTANCE_LEVELS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    SEVERITY_LEVELS,
    UNCERTAINTY_KINDS,
    AnalysisProvenance,
    AuthorVoiceProfile,
)
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.validator import ensure_valid_source_map, validate_source_map
from app.source_analysis_v31_global_output_architecture.constants import (
    IDEA_KIND_POLICY,
    MODEL,
    NEXT_PROMPT_VERSION,
    NEXT_TRANSPORT_VERSION,
    PHASE,
    PROVIDER,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_global_output_architecture.membership import derived_src_union
from app.source_analysis_v31_global_preflight.validator import assign_canonical_ids


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if isinstance(item, str) and item]


def _local_record(
    inventory: Mapping[str, Any],
    input_id: str,
) -> Mapping[str, Any]:
    records = inventory.get("records") or inventory.get("by_id") or {}
    row = records.get(input_id) if isinstance(records, Mapping) else None
    return row if isinstance(row, Mapping) else {}


def _pick(values: list[str], allowed: tuple[str, ...]) -> str:
    for item in values:
        if item in allowed:
            return item
    return ""


def compact_to_source_map_payload(
    transport: Mapping[str, Any],
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    local_src = {
        str(key): [str(ref) for ref in _as_list(value) if isinstance(ref, str)]
        for key, value in (inventory.get("src_by_input") or {}).items()
    }
    if not local_src:
        for input_id, row in (inventory.get("records") or {}).items():
            if isinstance(row, Mapping):
                local_src[str(input_id)] = _strings(row.get("source_refs") or row.get("s"))

    topic_local_to_global: dict[str, str] = {}
    topics: list[dict[str, Any]] = []
    for topic in _as_list(transport.get("t")):
        if not isinstance(topic, Mapping):
            continue
        handle = str(topic.get("h") or "")
        members = _strings(topic.get("m"))
        for member in members:
            topic_local_to_global[member] = handle
        refs = derived_src_union(members, local_src)
        value = str(topic.get("v") or "")
        topics.append(
            {
                "topic_id": handle,
                "label": value,
                "summary": value,
                "source_refs": refs,
            }
        )

    idea_local_to_global: dict[str, str] = {}
    ideas: list[dict[str, Any]] = []
    for idea in _as_list(transport.get("i")):
        if not isinstance(idea, Mapping):
            continue
        handle = str(idea.get("h") or "")
        members = _strings(idea.get("m"))
        for member in members:
            idea_local_to_global[member] = handle
        refs = derived_src_union(members, local_src)
        topic_refs: list[str] = []
        for member in members:
            row = _local_record(inventory, member)
            for link in _strings(row.get("links") or row.get("l")):
                mapped = topic_local_to_global.get(link)
                if mapped and mapped not in topic_refs:
                    topic_refs.append(mapped)
        importance = str(idea.get("p") or "")
        if importance not in IMPORTANCE_LEVELS:
            importance = "supporting"
        ideas.append(
            {
                "idea_id": handle,
                "summary": str(idea.get("v") or ""),
                "kind": "",
                "importance": importance,
                "topic_refs": topic_refs,
                "relations": [],
                "source_refs": refs,
            }
        )

    examples: list[dict[str, Any]] = []
    for example in _as_list(transport.get("x")):
        if not isinstance(example, Mapping):
            continue
        locals_ = _strings(example.get("l"))
        first = _local_record(inventory, locals_[0]) if locals_ else {}
        meta = _strings(first.get("metadata") or first.get("m"))
        examples.append(
            {
                "example_id": str(example.get("h") or ""),
                "kind": _pick(meta, EXAMPLE_KINDS) or "example",
                "summary": str(first.get("value") or first.get("v") or ""),
                "supports_idea_refs": _strings(example.get("g")),
                "source_refs": derived_src_union(locals_, local_src),
            }
        )

    references: list[dict[str, Any]] = []
    for item in _as_list(transport.get("f")):
        if not isinstance(item, Mapping):
            continue
        locals_ = _strings(item.get("l"))
        first = _local_record(inventory, locals_[0]) if locals_ else {}
        meta = _strings(first.get("metadata") or first.get("m"))
        value = str(first.get("value") or first.get("v") or "")
        references.append(
            {
                "reference_id": str(item.get("h") or ""),
                "kind": _pick(meta, REFERENCE_KINDS) or "other",
                "raw_reference": value,
                "normalized_reference": value,
                "completeness": _pick(meta, REFERENCE_COMPLETENESS) or "partial",
                "source_refs": derived_src_union(locals_, local_src),
            }
        )

    uncertainties: list[dict[str, Any]] = []
    for item in _as_list(transport.get("u")):
        if not isinstance(item, Mapping):
            continue
        locals_ = _strings(item.get("l"))
        first = _local_record(inventory, locals_[0]) if locals_ else {}
        meta = _strings(first.get("metadata") or first.get("m"))
        uncertainties.append(
            {
                "uncertainty_id": str(item.get("h") or ""),
                "kind": _pick(meta, UNCERTAINTY_KINDS) or "ambiguous_meaning",
                "description": str(first.get("value") or first.get("v") or ""),
                "severity": _pick(meta, SEVERITY_LEVELS) or "medium",
                "source_refs": derived_src_union(locals_, local_src),
            }
        )

    gm = transport.get("gm") if isinstance(transport.get("gm"), Mapping) else {}
    voice_text = str(gm.get("vo") or "").strip()
    voice = AuthorVoiceProfile(
        distinctive_traits=(voice_text,) if voice_text else (),
        teaching_style=voice_text,
    ).to_dict()
    return {
        "source_analysis": {
            "main_theme": str(gm.get("th") or ""),
            "author_intent": {
                "summary": str(gm.get("in") or ""),
                "confidence": str(gm.get("ic") or ""),
                "kinds": [],
            },
            "target_audience": {
                "summary": str(gm.get("au") or ""),
                "confidence": str(gm.get("ac") or ""),
                "kinds": [],
            },
        },
        "topics": topics,
        "ideas": ideas,
        "examples": examples,
        "references": references,
        "uncertainties": uncertainties,
        "repetitions": [],
        "author_voice_profile": voice,
    }


def reconstruct_source_map(
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
        prompt_version=NEXT_PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        provider=PROVIDER,
        model=MODEL,
        strategy="global-consolidation-output-architecture-a39",
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
    return {
        "ok": not validation_errors and ensure_ok and empty_kind,
        "source_map": source_map,
        "payload": serialized,
        "canonical_json": json.dumps(serialized, ensure_ascii=False, sort_keys=True),
        "assigned_provider_to_canonical": assigned_ids,
        "idea_kind_policy": IDEA_KIND_POLICY,
        "all_idea_kinds_empty": empty_kind,
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


__all__ = ["compact_to_source_map_payload", "reconstruct_source_map"]
