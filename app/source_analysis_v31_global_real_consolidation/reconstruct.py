"""Reconstruction déterministe transport 1.1 → SourceMap candidat. 0 publication."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.source_analysis.models import AnalysisProvenance
from app.source_analysis.normalizer import normalize_source_map
from app.source_analysis.transcript_input import TranscriptInput
from app.source_analysis.validator import ensure_valid_source_map, validate_source_map
from app.source_analysis_v31_global_grammar_canary.reconstruct import (
    transport_to_source_map_payload,
)
from app.source_analysis_v31_global_preflight.validator import assign_canonical_ids
from app.source_analysis_v31_global_real_consolidation.constants import (
    IDEA_KIND_POLICY,
    MODEL,
    PHASE,
    PROMPT_VERSION,
    PROVIDER,
    SCHEMA_VERSION,
    TRANSPORT_VERSION,
)


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
        prompt_version=PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        provider=PROVIDER,
        model=MODEL,
        strategy="global-consolidation-real-canary-a38",
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
            "transport_version": TRANSPORT_VERSION,
            "prompt_version": PROMPT_VERSION,
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
        "transport_version": TRANSPORT_VERSION,
        "prompt_version": PROMPT_VERSION,
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
        "transport_version": result.get("transport_version"),
        "prompt_version": result.get("prompt_version"),
        "phase": result.get("phase"),
    }


__all__ = [
    "reconstruct_source_map",
    "replay_reconstruction",
    "source_map_public_view",
]
