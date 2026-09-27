"""
Normalisation versionnée V3 → v3.1-local-lite.

Déterministe. Abandonne le sous-type IDEA optionnel. N'invente rien.
Ne mute pas le candidat historique.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from app.source_analysis.errors import WindowTransportValidationError
from app.source_analysis.models import IDEA_KINDS, IMPORTANCE_LEVELS
from app.source_analysis.window_models import WindowIntermediateRecord, WindowSemanticResult
from app.source_analysis_local_v3.constants import (
    SEMANTIC_TRANSPORT_VERSION_V3,
    SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V140,
)
from app.source_analysis_local_v3.fixtures import to_v31_local_lite_transport


def drop_local_idea_subtype(metadata: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    values = list(metadata)
    if len(values) != 2:
        raise WindowTransportValidationError(
            f"migration V3→local-lite : IDEA.m attendu [kind, importance], reçu {values!r}"
        )
    kind, importance = values
    if kind not in IDEA_KINDS:
        raise WindowTransportValidationError(
            f"migration V3→local-lite : sous-type invalide {kind!r}"
        )
    if importance not in IMPORTANCE_LEVELS:
        raise WindowTransportValidationError(
            f"migration V3→local-lite : importance invalide {importance!r}"
        )
    return (importance,)


def normalize_v3_transport_to_local_lite(
    payload: Mapping[str, Any],
    *,
    source_transport_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if source_transport_version != SEMANTIC_TRANSPORT_VERSION_V3:
        raise WindowTransportValidationError(
            "migration locale-lite exige une source semantic-transport-v3 "
            f"(reçu {source_transport_version!r})"
        )
    dropped: list[dict[str, str]] = []
    out = to_v31_local_lite_transport(dict(payload))
    for index, (before, after) in enumerate(
        zip(payload.get("records") or [], out.get("records") or [])
    ):
        if before.get("k") != "IDEA":
            continue
        meta = list(before.get("m") or [])
        if len(meta) == 2:
            dropped.append(
                {
                    "record_index": str(index),
                    "handle": str(before.get("h") or ""),
                    "dropped_subtype": meta[0],
                    "kept_importance": meta[1],
                }
            )
            if after.get("m") != [meta[1]]:
                raise WindowTransportValidationError(
                    "migration V3→local-lite : importance non préservée"
                )
    provenance = {
        "source_transport_version": SEMANTIC_TRANSPORT_VERSION_V3,
        "target_transport_version": SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
        "operation": "DROP_OPTIONAL_LOCAL_IDEA_SUBTYPE",
        "invented_semantics": False,
        "dropped_subtypes": dropped,
        "preserved": ["idea_text", "importance", "src", "topic", "handles", "relationships"],
    }
    return out, provenance


def normalize_v3_window_result_to_local_lite(
    result: WindowSemanticResult,
) -> tuple[WindowSemanticResult, dict[str, Any]]:
    if result.transport_version != SEMANTIC_TRANSPORT_VERSION_V3:
        raise WindowTransportValidationError(
            f"{result.window_id} : migration exige V3, reçu {result.transport_version}"
        )
    records: list[WindowIntermediateRecord] = []
    dropped: list[dict[str, str]] = []
    for record in result.records:
        if record.kind != "IDEA":
            records.append(record)
            continue
        new_meta = drop_local_idea_subtype(record.metadata)
        dropped.append(
            {
                "record_id": record.record_id,
                "dropped_subtype": record.metadata[0],
                "kept_importance": new_meta[0],
            }
        )
        records.append(replace(record, metadata=new_meta))
    derived = replace(
        result,
        transport_version=SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
        prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V140,
        records=tuple(records),
    )
    provenance = {
        "window_id": result.window_id,
        "source_transport_version": SEMANTIC_TRANSPORT_VERSION_V3,
        "source_prompt_version": result.prompt_version,
        "target_transport_version": SEMANTIC_TRANSPORT_VERSION_V31_LOCAL_LITE,
        "target_prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V140,
        "label": "DERIVED_COMPATIBILITY_LOCAL_LITE",
        "operation": "DROP_OPTIONAL_LOCAL_IDEA_SUBTYPE",
        "invented_semantics": False,
        "dropped_subtypes": dropped,
        "original_signature": result.window_analysis_signature,
    }
    return derived, provenance


__all__ = [
    "drop_local_idea_subtype",
    "normalize_v3_transport_to_local_lite",
    "normalize_v3_window_result_to_local_lite",
]
