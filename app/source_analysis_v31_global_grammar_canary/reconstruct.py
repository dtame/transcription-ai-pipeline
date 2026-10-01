"""Reconstruction déterministe transport global → SourceMap. 0 provider."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.source_analysis.models import (
    EXAMPLE_KINDS,
    IMPORTANCE_LEVELS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    RELATION_KINDS,
    REPETITION_CHARACTERS,
    SEVERITY_LEVELS,
    UNCERTAINTY_KINDS,
    AnalysisProvenance,
    AuthorVoiceProfile,
    SourceMap,
)
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.validator import ensure_valid_source_map, validate_source_map
from app.source_analysis_v31_global_grammar_canary.constants import (
    GLOBAL_PROMPT_VERSION,
    GLOBAL_TRANSPORT_VERSION,
    IDEA_KIND_POLICY,
    MODEL,
    PHASE,
    PROVIDER,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_global_preflight.validator import assign_canonical_ids


def _meta_pick(values: list[str], allowed: tuple[str, ...] | frozenset[str]) -> str:
    for item in values:
        if item in allowed:
            return item
    return ""


def _handle_kind(handle: str, owners: Mapping[str, str]) -> str:
    return owners.get(handle, "")


def transport_to_source_map_payload(
    transport: Mapping[str, Any],
) -> dict[str, Any]:
    gm = transport.get("gm") if isinstance(transport.get("gm"), Mapping) else {}
    nodes = [item for item in (transport.get("n") or []) if isinstance(item, dict)]
    relations = [item for item in (transport.get("r") or []) if isinstance(item, dict)]
    owners = {str(item.get("h") or ""): str(item.get("k") or "") for item in nodes}

    topics: list[dict[str, Any]] = []
    ideas: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    uncertainties: list[dict[str, Any]] = []
    repetitions: list[dict[str, Any]] = []

    topic_refs_by_idea: dict[str, list[str]] = {}
    idea_relations: dict[str, list[dict[str, str]]] = {}
    example_supports: dict[str, list[str]] = {}

    for rel in relations:
        left = str(rel.get("a") or "")
        right = str(rel.get("b") or "")
        rel_type = str(rel.get("t") or "")
        left_kind = _handle_kind(left, owners)
        right_kind = _handle_kind(right, owners)
        if left_kind == "IDEA" and right_kind == "TOPIC":
            topic_refs_by_idea.setdefault(left, []).append(right)
        elif right_kind == "IDEA" and left_kind == "TOPIC":
            topic_refs_by_idea.setdefault(right, []).append(left)
        elif left_kind == "IDEA" and right_kind == "IDEA" and rel_type in RELATION_KINDS:
            idea_relations.setdefault(left, []).append(
                {"relation": rel_type, "to_idea": right}
            )
        elif left_kind == "EXAMPLE" and right_kind == "IDEA":
            example_supports.setdefault(left, []).append(right)
        elif right_kind == "EXAMPLE" and left_kind == "IDEA":
            example_supports.setdefault(right, []).append(left)

    for node in nodes:
        handle = str(node.get("h") or "")
        kind = str(node.get("k") or "")
        value = str(node.get("v") or "")
        refs = [str(item) for item in (node.get("s") or []) if isinstance(item, str)]
        meta = [str(item) for item in (node.get("m") or []) if isinstance(item, str)]
        if kind == "TOPIC":
            topics.append(
                {
                    "topic_id": handle,
                    "label": value,
                    "summary": value,
                    "source_refs": refs,
                }
            )
        elif kind == "IDEA":
            importance = _meta_pick(meta, IMPORTANCE_LEVELS) or "supporting"
            ideas.append(
                {
                    "idea_id": handle,
                    "summary": value,
                    "kind": "",
                    "importance": importance,
                    "topic_refs": list(dict.fromkeys(topic_refs_by_idea.get(handle, []))),
                    "relations": idea_relations.get(handle, []),
                    "source_refs": refs,
                }
            )
        elif kind == "EXAMPLE":
            examples.append(
                {
                    "example_id": handle,
                    "kind": _meta_pick(meta, EXAMPLE_KINDS) or "example",
                    "summary": value,
                    "supports_idea_refs": list(
                        dict.fromkeys(example_supports.get(handle, []))
                    ),
                    "source_refs": refs,
                }
            )
        elif kind == "REFERENCE":
            references.append(
                {
                    "reference_id": handle,
                    "kind": _meta_pick(meta, REFERENCE_KINDS) or "other",
                    "raw_reference": value,
                    "normalized_reference": value,
                    "completeness": _meta_pick(meta, REFERENCE_COMPLETENESS) or "partial",
                    "source_refs": refs,
                }
            )
        elif kind == "UNCERTAINTY":
            uncertainties.append(
                {
                    "uncertainty_id": handle,
                    "kind": _meta_pick(meta, UNCERTAINTY_KINDS) or "ambiguous_meaning",
                    "description": value,
                    "severity": _meta_pick(meta, SEVERITY_LEVELS) or "medium",
                    "source_refs": refs,
                }
            )
        elif kind == "REPETITION":
            idea_refs = [
                item
                for item in meta
                if _handle_kind(item, owners) == "IDEA"
            ]
            repetitions.append(
                {
                    "repetition_id": handle,
                    "character": _meta_pick(meta, REPETITION_CHARACTERS) or "oral",
                    "description": value,
                    "idea_refs": idea_refs,
                    "source_refs": refs,
                }
            )

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
        "repetitions": repetitions,
        "author_voice_profile": voice,
    }


def reconstruct_source_map(
    transport: Mapping[str, Any],
    transcript: TranscriptInput,
    *,
    signature: str,
) -> dict[str, Any]:
    assigned = assign_canonical_ids(
        [item for item in (transport.get("n") or []) if isinstance(item, dict)]
    )
    assigned_ids = {
        str(item.get("h") or ""): str(item.get("canonical_id") or "")
        for item in assigned
    }
    payload = transport_to_source_map_payload(transport)
    provenance = AnalysisProvenance(
        prompt_version=GLOBAL_PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        provider=PROVIDER,
        model=MODEL,
        strategy="global-consolidation-canary",
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
            "idea_kind_policy": IDEA_KIND_POLICY,
            "all_idea_kinds_empty": False,
            "provider_handles_used_as_final_ids": list(assigned_ids),
            "validate_source_map": "FAIL",
            "ensure_valid_source_map": "FAIL",
            "errors": [str(exc)],
            "ensure_error": str(exc),
            "transport_version": GLOBAL_TRANSPORT_VERSION,
            "phase": PHASE,
            "source_map_published": False,
        }
    empty_kind = all(idea.kind == "" for idea in source_map.ideas)
    final_ids = (
        [topic.topic_id for topic in source_map.topics]
        + [idea.idea_id for idea in source_map.ideas]
        + [example.example_id for example in source_map.examples]
        + [item.reference_id for item in source_map.references]
        + [item.uncertainty_id for item in source_map.uncertainties]
        + [item.repetition_id for item in source_map.repetitions]
    )
    provider_ids_leaked = [item for item in final_ids if item in assigned_ids]
    serialized = source_map.to_dict()
    canonical_bytes = json.dumps(serialized, ensure_ascii=False, sort_keys=True)
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
        "ok": not validation_errors and ensure_ok and empty_kind and not provider_ids_leaked,
        "source_map": source_map,
        "payload": serialized,
        "canonical_json": canonical_bytes,
        "assigned_provider_to_canonical": assigned_ids,
        "idea_kind_policy": IDEA_KIND_POLICY,
        "all_idea_kinds_empty": empty_kind,
        "provider_handles_used_as_final_ids": provider_ids_leaked,
        "validate_source_map": "PASS" if not validation_errors else "FAIL",
        "ensure_valid_source_map": "PASS" if ensure_ok else "FAIL",
        "errors": validation_errors,
        "ensure_error": ensure_error,
        "transport_version": GLOBAL_TRANSPORT_VERSION,
        "phase": PHASE,
        "source_map_published": False,
    }


def replay_reconstruction(
    transport: Mapping[str, Any],
    transcript: TranscriptInput,
    *,
    signature: str,
) -> dict[str, Any]:
    first = reconstruct_source_map(transport, transcript, signature=signature)
    second = reconstruct_source_map(transport, transcript, signature=signature)
    equal = first["canonical_json"] == second["canonical_json"]
    return {
        "ok": bool(first["ok"] and second["ok"] and equal),
        "byte_equivalent": equal,
        "first": {
            "validate_source_map": first["validate_source_map"],
            "ensure_valid_source_map": first["ensure_valid_source_map"],
            "all_idea_kinds_empty": first["all_idea_kinds_empty"],
            "errors": first["errors"],
        },
        "second": {
            "validate_source_map": second["validate_source_map"],
            "ensure_valid_source_map": second["ensure_valid_source_map"],
            "all_idea_kinds_empty": second["all_idea_kinds_empty"],
            "errors": second["errors"],
        },
        "status": "PASS" if first["ok"] and second["ok"] and equal else "FAIL",
    }


def source_map_public_view(result: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(result.get("payload") or {})
    return {
        "schema_version": payload.get("schema_version"),
        "transcript_id": payload.get("transcript_id"),
        "source_analysis": payload.get("source_analysis"),
        "topics": payload.get("topics"),
        "ideas": payload.get("ideas"),
        "examples": payload.get("examples"),
        "references": payload.get("references"),
        "uncertainties": payload.get("uncertainties"),
        "repetitions": payload.get("repetitions"),
        "author_voice_profile": payload.get("author_voice_profile"),
        "stats": payload.get("stats"),
        "analysis": payload.get("analysis"),
        "assigned_provider_to_canonical": result.get("assigned_provider_to_canonical"),
        "all_idea_kinds_empty": result.get("all_idea_kinds_empty"),
        "validate_source_map": result.get("validate_source_map"),
        "ensure_valid_source_map": result.get("ensure_valid_source_map"),
        "errors": result.get("errors"),
        "source_map_published": False,
    }


__all__ = [
    "reconstruct_source_map",
    "replay_reconstruction",
    "source_map_public_view",
    "transport_to_source_map_payload",
]
