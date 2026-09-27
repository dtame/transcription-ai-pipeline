"""window-granularity-1.1-minimal — politique locale v2. Ne mute pas 1.0."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from app.source_analysis.errors import (
    WindowGranularityLimitExceeded,
    WindowSemanticCapacityExceeded,
)
from app.source_analysis.window_granularity import TEXT_HARD_LIMITS as V10_TEXT_LIMITS
from app.source_analysis.window_models import WindowSemanticResult
from app.source_analysis_local_v2.constants import (
    DEFERRED_KINDS,
    GRANULARITY_POLICY_VERSION,
    HARD_CEILINGS,
    LOCAL_KINDS,
    OVERFLOW_TOKEN,
    OVERFLOW_UNCERTAINTY_KIND,
    OVERFLOW_UNCERTAINTY_SEVERITY,
    SOFT_TARGETS,
    SOURCE_REFS_HARD_MAX,
    TOTAL_HARD_CEILING,
    TOTAL_SOFT_TARGET,
)

TEXT_HARD_LIMITS: dict[str, int] = {
    "theme": V10_TEXT_LIMITS["theme"],
    "intent": V10_TEXT_LIMITS["intent"],
    "aud": V10_TEXT_LIMITS["aud"],
    "TOPIC.v": V10_TEXT_LIMITS["TOPIC.v"],
    "TOPIC.m0": V10_TEXT_LIMITS["TOPIC.m0"],
    "IDEA.v": V10_TEXT_LIMITS["IDEA.v"],
    "EXAMPLE.v": V10_TEXT_LIMITS["EXAMPLE.v"],
    "REFERENCE.v": V10_TEXT_LIMITS["REFERENCE.v"],
    "UNCERTAINTY.v": V10_TEXT_LIMITS["UNCERTAINTY.v"],
    "RELATION.v": V10_TEXT_LIMITS["RELATION.v"],
    "metadata_item": V10_TEXT_LIMITS["metadata_item"],
}


def granularity_policy() -> dict[str, Any]:
    return {
        "policy_version": GRANULARITY_POLICY_VERSION,
        "historical_1_0_unchanged": True,
        "not_a_reuse_of_1_0": True,
        "reason_new_version": (
            "window-granularity-1.0 includes deferred kinds "
            "(REPETITION/VOICE/INTENT_KIND/AUDIENCE_KIND)."
        ),
        "local_kinds": list(LOCAL_KINDS),
        "deferred_kinds": list(DEFERRED_KINDS),
        "soft_targets": dict(SOFT_TARGETS),
        "hard_ceilings": dict(HARD_CEILINGS),
        "total_soft_target": TOTAL_SOFT_TARGET,
        "total_hard_ceiling": TOTAL_HARD_CEILING,
        "source_refs_hard_max": SOURCE_REFS_HARD_MAX,
        "text_hard_limits": dict(TEXT_HARD_LIMITS),
        "overflow_token": OVERFLOW_TOKEN,
        "overflow_uncertainty_kind": OVERFLOW_UNCERTAINTY_KIND,
        "overflow_uncertainty_severity": OVERFLOW_UNCERTAINTY_SEVERITY,
        "limits_provider_enforced": False,
        "limits_application_validated_after_parse": True,
        "local_semantic_merge": False,
        "local_string_truncation": False,
        "idea_not_increased": HARD_CEILINGS["IDEA"] <= 64,
        "relation_not_increased": HARD_CEILINGS["RELATION"] <= 36,
    }


def transport_signals_overflow(transport: Mapping[str, Any]) -> bool:
    records = transport.get("records")
    if not isinstance(records, list):
        return False
    for item in records:
        if isinstance(item, Mapping) and str(item.get("v") or "") == OVERFLOW_TOKEN:
            return True
    return False


def result_signals_overflow(result: WindowSemanticResult) -> bool:
    return any(record.value == OVERFLOW_TOKEN for record in result.records)


def _count_kinds(records: list[Mapping[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in records:
        if isinstance(item, Mapping):
            counts[str(item.get("k") or "")] += 1
    return counts


def _text_violations(transport: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("theme", "intent", "aud"):
        value = transport.get(field)
        if isinstance(value, str) and len(value) > TEXT_HARD_LIMITS[field]:
            errors.append(
                f"{field} : {len(value)} caractères > {TEXT_HARD_LIMITS[field]}"
            )
    records = transport.get("records")
    if not isinstance(records, list):
        return errors
    for index, item in enumerate(records):
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get("k") or "")
        value = item.get("v")
        if isinstance(value, str) and value != OVERFLOW_TOKEN:
            limit = TEXT_HARD_LIMITS.get(f"{kind}.v")
            if limit is not None and len(value) > limit:
                errors.append(
                    f"records[{index}].v ({kind}) : {len(value)} > {limit}"
                )
        metadata = item.get("m") or []
        if isinstance(metadata, list):
            meta_limit = TEXT_HARD_LIMITS["metadata_item"]
            for meta_index, raw in enumerate(metadata):
                if not isinstance(raw, str):
                    continue
                if kind == "TOPIC" and meta_index == 0:
                    topic_limit = TEXT_HARD_LIMITS["TOPIC.m0"]
                    if len(raw) > topic_limit:
                        errors.append(
                            f"records[{index}].m[0] (TOPIC) : "
                            f"{len(raw)} > {topic_limit}"
                        )
                    continue
                if len(raw) > meta_limit:
                    errors.append(
                        f"records[{index}].m[{meta_index}] : "
                        f"{len(raw)} > {meta_limit}"
                    )
        refs = item.get("s") or []
        if isinstance(refs, list) and len(refs) > SOURCE_REFS_HARD_MAX:
            errors.append(
                f"records[{index}].s : {len(refs)} source_refs > "
                f"{SOURCE_REFS_HARD_MAX}"
            )
    return errors


def validate_v2_transport_granularity(transport: Mapping[str, Any]) -> None:
    if transport_signals_overflow(transport):
        raise WindowSemanticCapacityExceeded(
            "signal analysis_capacity_exceeded — fenêtre NOT READY, "
            "aucun résultat canonique, aucun retry provider"
        )
    records = transport.get("records")
    if not isinstance(records, list):
        return
    counts = _count_kinds(records)
    errors: list[str] = []
    total = len(records)
    if total > TOTAL_HARD_CEILING:
        errors.append(f"total records {total} > {TOTAL_HARD_CEILING}")
    for kind, ceiling in HARD_CEILINGS.items():
        actual = int(counts.get(kind, 0))
        if actual > ceiling:
            errors.append(f"{kind} {actual} > plafond {ceiling}")
    errors.extend(_text_violations(transport))
    if errors:
        raise WindowGranularityLimitExceeded(" | ".join(errors))


__all__ = [
    "TEXT_HARD_LIMITS",
    "granularity_policy",
    "result_signals_overflow",
    "transport_signals_overflow",
    "validate_v2_transport_granularity",
]
