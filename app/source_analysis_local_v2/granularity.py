"""window-granularity-1.2-kind-specific — politique locale v2.

Ne mute pas window-granularity-1.0 ni l'identité historique 1.1-minimal.
Les plafonds 1.1-minimal restent figés pour reproduire A.28 FAIL.
"""

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
    GRANULARITY_POLICY_VERSION_12_KIND_SPECIFIC,
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

# Historical window-granularity-1.1-minimal (A.11–A.29). Immutable.
V11_MINIMAL_THEME_TEXT_HARD_LIMIT = 200
V11_MINIMAL_EXAMPLE_V_TEXT_HARD_LIMIT = 200

V11_MINIMAL_TEXT_HARD_LIMITS: dict[str, int] = {
    "theme": V11_MINIMAL_THEME_TEXT_HARD_LIMIT,
    "intent": V10_TEXT_LIMITS["intent"],
    "aud": V10_TEXT_LIMITS["aud"],
    "TOPIC.v": V10_TEXT_LIMITS["TOPIC.v"],
    "TOPIC.m0": V10_TEXT_LIMITS["TOPIC.m0"],
    "IDEA.v": V10_TEXT_LIMITS["IDEA.v"],
    "EXAMPLE.v": V11_MINIMAL_EXAMPLE_V_TEXT_HARD_LIMIT,
    "REFERENCE.v": V10_TEXT_LIMITS["REFERENCE.v"],
    "UNCERTAINTY.v": V10_TEXT_LIMITS["UNCERTAINTY.v"],
    "RELATION.v": V10_TEXT_LIMITS["RELATION.v"],
    "metadata_item": V10_TEXT_LIMITS["metadata_item"],
}

# window-granularity-1.2-kind-specific (A.30). Kind-specific, not universal.
THEME_TEXT_HARD_LIMIT = 225
INTENT_TEXT_HARD_LIMIT = V10_TEXT_LIMITS["intent"]
AUD_TEXT_HARD_LIMIT = V10_TEXT_LIMITS["aud"]
TOPIC_V_TEXT_HARD_LIMIT = V10_TEXT_LIMITS["TOPIC.v"]
TOPIC_M0_TEXT_HARD_LIMIT = V10_TEXT_LIMITS["TOPIC.m0"]
IDEA_V_TEXT_HARD_LIMIT = V10_TEXT_LIMITS["IDEA.v"]
EXAMPLE_V_TEXT_HARD_LIMIT = 225
REFERENCE_V_TEXT_HARD_LIMIT = V10_TEXT_LIMITS["REFERENCE.v"]
UNCERTAINTY_V_TEXT_HARD_LIMIT = V10_TEXT_LIMITS["UNCERTAINTY.v"]
RELATION_V_TEXT_HARD_LIMIT = V10_TEXT_LIMITS["RELATION.v"]
METADATA_ITEM_TEXT_HARD_LIMIT = V10_TEXT_LIMITS["metadata_item"]

TEXT_HARD_LIMITS: dict[str, int] = {
    "theme": THEME_TEXT_HARD_LIMIT,
    "intent": INTENT_TEXT_HARD_LIMIT,
    "aud": AUD_TEXT_HARD_LIMIT,
    "TOPIC.v": TOPIC_V_TEXT_HARD_LIMIT,
    "TOPIC.m0": TOPIC_M0_TEXT_HARD_LIMIT,
    "IDEA.v": IDEA_V_TEXT_HARD_LIMIT,
    "EXAMPLE.v": EXAMPLE_V_TEXT_HARD_LIMIT,
    "REFERENCE.v": REFERENCE_V_TEXT_HARD_LIMIT,
    "UNCERTAINTY.v": UNCERTAINTY_V_TEXT_HARD_LIMIT,
    "RELATION.v": RELATION_V_TEXT_HARD_LIMIT,
    "metadata_item": METADATA_ITEM_TEXT_HARD_LIMIT,
}

assert V10_TEXT_LIMITS["theme"] == 200
assert V10_TEXT_LIMITS["EXAMPLE.v"] == 200
assert V11_MINIMAL_TEXT_HARD_LIMITS["theme"] == 200
assert V11_MINIMAL_TEXT_HARD_LIMITS["EXAMPLE.v"] == 200
assert V11_MINIMAL_TEXT_HARD_LIMITS["IDEA.v"] == 280
assert TEXT_HARD_LIMITS["theme"] == 225
assert TEXT_HARD_LIMITS["EXAMPLE.v"] == 225
assert TEXT_HARD_LIMITS["IDEA.v"] == 280
assert TEXT_HARD_LIMITS["TOPIC.v"] == 80
assert TEXT_HARD_LIMITS["RELATION.v"] == 40
assert TEXT_HARD_LIMITS["REFERENCE.v"] == 220
assert TEXT_HARD_LIMITS["UNCERTAINTY.v"] == 280
assert TEXT_HARD_LIMITS["intent"] == 280
assert TEXT_HARD_LIMITS["aud"] == 280
assert len(set(TEXT_HARD_LIMITS.values())) > 1


def granularity_policy() -> dict[str, Any]:
    return {
        "policy_version": GRANULARITY_POLICY_VERSION_12_KIND_SPECIFIC,
        "historical_1_1_minimal": GRANULARITY_POLICY_VERSION,
        "historical_1_0_unchanged": True,
        "not_a_reuse_of_1_0": True,
        "reason_new_version": (
            "A.30 raises only theme and EXAMPLE.v from 200 to 225. "
            "window-granularity-1.1-minimal stays frozen so A.28 FAIL "
            "remains reproducible."
        ),
        "local_kinds": list(LOCAL_KINDS),
        "deferred_kinds": list(DEFERRED_KINDS),
        "soft_targets": dict(SOFT_TARGETS),
        "hard_ceilings": dict(HARD_CEILINGS),
        "total_soft_target": TOTAL_SOFT_TARGET,
        "total_hard_ceiling": TOTAL_HARD_CEILING,
        "source_refs_hard_max": SOURCE_REFS_HARD_MAX,
        "text_hard_limits": dict(TEXT_HARD_LIMITS),
        "historical_1_1_minimal_text_hard_limits": dict(V11_MINIMAL_TEXT_HARD_LIMITS),
        "overflow_token": OVERFLOW_TOKEN,
        "overflow_uncertainty_kind": OVERFLOW_UNCERTAINTY_KIND,
        "overflow_uncertainty_severity": OVERFLOW_UNCERTAINTY_SEVERITY,
        "limits_provider_enforced": False,
        "limits_application_validated_after_parse": True,
        "local_semantic_merge": False,
        "local_string_truncation": False,
        "idea_not_increased": HARD_CEILINGS["IDEA"] <= 64,
        "relation_not_increased": HARD_CEILINGS["RELATION"] <= 36,
        "universal_ceiling": False,
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


def _text_violations(
    transport: Mapping[str, Any],
    limits: Mapping[str, int],
) -> list[str]:
    errors: list[str] = []
    for field in ("theme", "intent", "aud"):
        value = transport.get(field)
        limit = limits.get(field)
        if isinstance(value, str) and limit is not None and len(value) > limit:
            errors.append(f"{field} : {len(value)} caractères > {limit}")
    records = transport.get("records")
    if not isinstance(records, list):
        return errors
    for index, item in enumerate(records):
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get("k") or "")
        value = item.get("v")
        if isinstance(value, str) and value != OVERFLOW_TOKEN:
            limit = limits.get(f"{kind}.v")
            if limit is not None and len(value) > limit:
                errors.append(f"records[{index}].v ({kind}) : {len(value)} > {limit}")
        metadata = item.get("m") or []
        if isinstance(metadata, list):
            meta_limit = limits["metadata_item"]
            for meta_index, raw in enumerate(metadata):
                if not isinstance(raw, str):
                    continue
                if kind == "TOPIC" and meta_index == 0:
                    topic_limit = limits["TOPIC.m0"]
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


def validate_transport_granularity_with_limits(
    transport: Mapping[str, Any],
    limits: Mapping[str, int],
) -> None:
    """Strict reject. Identifies field/record, actual count, allowed maximum."""
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
    errors.extend(_text_violations(transport, limits))
    if errors:
        raise WindowGranularityLimitExceeded(" | ".join(errors))


def validate_v2_transport_granularity(transport: Mapping[str, Any]) -> None:
    validate_transport_granularity_with_limits(transport, TEXT_HARD_LIMITS)


def validate_v11_minimal_transport_granularity(transport: Mapping[str, Any]) -> None:
    """Replay A.28/A.29 policy. Does not use current 1.2 limits."""
    validate_transport_granularity_with_limits(transport, V11_MINIMAL_TEXT_HARD_LIMITS)


__all__ = [
    "AUD_TEXT_HARD_LIMIT",
    "EXAMPLE_V_TEXT_HARD_LIMIT",
    "IDEA_V_TEXT_HARD_LIMIT",
    "INTENT_TEXT_HARD_LIMIT",
    "METADATA_ITEM_TEXT_HARD_LIMIT",
    "REFERENCE_V_TEXT_HARD_LIMIT",
    "RELATION_V_TEXT_HARD_LIMIT",
    "TEXT_HARD_LIMITS",
    "THEME_TEXT_HARD_LIMIT",
    "TOPIC_M0_TEXT_HARD_LIMIT",
    "TOPIC_V_TEXT_HARD_LIMIT",
    "UNCERTAINTY_V_TEXT_HARD_LIMIT",
    "V11_MINIMAL_EXAMPLE_V_TEXT_HARD_LIMIT",
    "V11_MINIMAL_TEXT_HARD_LIMITS",
    "V11_MINIMAL_THEME_TEXT_HARD_LIMIT",
    "granularity_policy",
    "result_signals_overflow",
    "transport_signals_overflow",
    "validate_transport_granularity_with_limits",
    "validate_v11_minimal_transport_granularity",
    "validate_v2_transport_granularity",
]
