"""
Politique de granularité sémantique des fenêtres — window-analysis-1.1.

Plafonds durs imposés localement. Cibles souples : instruction de prompt
seulement. Aucune fusion sémantique locale. Aucune troncature de chaîne.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from app.source_analysis.errors import (
    WindowGranularityLimitExceeded,
    WindowSemanticCapacityExceeded,
)
from app.source_analysis.ultra_compact_schema import ALLOWED_RECORD_KINDS
from app.source_analysis.window_models import WindowSemanticResult

POLICY_VERSION = "window-granularity-1.0"
OVERFLOW_TOKEN = "analysis_capacity_exceeded"
OVERFLOW_UNCERTAINTY_KIND = "interrupted_thought"
OVERFLOW_UNCERTAINTY_SEVERITY = "high"
GRANULARITY_PRINCIPLE = "ONE_RECORD_PER_DISTINCT_SUBSTANTIVE_SEMANTIC_UNIT"
AI_WITHIN_WINDOW_GROUPING = True
LOCAL_SEMANTIC_MERGE = False
LOCAL_STRING_TRUNCATION = False

# ~12.7k words / ~2787 SRC owned. Soft = densité normale. Hard = plafond.
SOFT_TARGETS: dict[str, int] = {
    "TOPIC": 8,
    "IDEA": 40,
    "RELATION": 18,
    "EXAMPLE": 10,
    "REFERENCE": 8,
    "UNCERTAINTY": 8,
    "REPETITION": 6,
    "VOICE": 14,
    "INTENT_KIND": 3,
    "AUDIENCE_KIND": 3,
}

HARD_CEILINGS: dict[str, int] = {
    "TOPIC": 14,
    "IDEA": 64,
    "RELATION": 36,
    "EXAMPLE": 18,
    "REFERENCE": 14,
    "UNCERTAINTY": 16,
    "REPETITION": 10,
    "VOICE": 22,
    "INTENT_KIND": 6,
    "AUDIENCE_KIND": 6,
}

TOTAL_SOFT_TARGET = 120
TOTAL_HARD_CEILING = 160
RELATION_HARD_CEILING = HARD_CEILINGS["RELATION"]
SOURCE_REFS_HARD_MAX = 48

# Caractères. Rejet si dépassé — jamais value[:N].
TEXT_HARD_LIMITS: dict[str, int] = {
    "theme": 200,
    "intent": 280,
    "aud": 280,
    "TOPIC.v": 80,
    "TOPIC.m0": 200,
    "IDEA.v": 280,
    "EXAMPLE.v": 200,
    "REFERENCE.v": 220,
    "UNCERTAINTY.v": 280,
    "REPETITION.v": 200,
    "RELATION.v": 40,
    "VOICE.v": 160,
    "INTENT_KIND.v": 40,
    "AUDIENCE_KIND.v": 40,
    "metadata_item": 64,
}

IDEA_SOFT_TARGET = SOFT_TARGETS["IDEA"]
IDEA_HARD_CEILING = HARD_CEILINGS["IDEA"]
TOPIC_SOFT_TARGET = SOFT_TARGETS["TOPIC"]
TOPIC_HARD_CEILING = HARD_CEILINGS["TOPIC"]

OUTPUT_BUDGET_LOCAL_TOKENS = 16000
MAX_OUTPUT_TOKENS_FROZEN = 32000
SAFETY_MARGIN_RATIO = 0.65
SAFETY_MARGIN_RATIONALE = (
    "Local estimate is ceil(chars/4), not Anthropic output tokenization. "
    "WIN001 input accounting was 2.16× local. JSON output is denser than "
    "prose, but the failed canary sat exactly on the 32000 ceiling. "
    "65% leaves ~35% headroom for estimator error, source_ref lists, "
    "and slightly longer semantic values without raising max_output."
)

KIND_ORDER = tuple(ALLOWED_RECORD_KINDS)


def granularity_policy() -> dict[str, Any]:
    return {
        "policy_version": POLICY_VERSION,
        "principle": GRANULARITY_PRINCIPLE,
        "ai_within_window_grouping": AI_WITHIN_WINDOW_GROUPING,
        "local_semantic_merge": LOCAL_SEMANTIC_MERGE,
        "local_string_truncation": LOCAL_STRING_TRUNCATION,
        "soft_targets": dict(SOFT_TARGETS),
        "hard_ceilings": dict(HARD_CEILINGS),
        "total_soft_target": TOTAL_SOFT_TARGET,
        "total_hard_ceiling": TOTAL_HARD_CEILING,
        "relation_hard_ceiling": RELATION_HARD_CEILING,
        "source_refs_hard_max": SOURCE_REFS_HARD_MAX,
        "text_hard_limits": dict(TEXT_HARD_LIMITS),
        "overflow_token": OVERFLOW_TOKEN,
        "overflow_uncertainty_kind": OVERFLOW_UNCERTAINTY_KIND,
        "overflow_uncertainty_severity": OVERFLOW_UNCERTAINTY_SEVERITY,
        "output_budget_local_tokens": OUTPUT_BUDGET_LOCAL_TOKENS,
        "max_output_tokens_frozen": MAX_OUTPUT_TOKENS_FROZEN,
        "safety_margin_ratio": SAFETY_MARGIN_RATIO,
        "safety_margin_rationale": SAFETY_MARGIN_RATIONALE,
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
        if isinstance(value, str):
            if value == OVERFLOW_TOKEN:
                continue
            limit_key = f"{kind}.v"
            limit = TEXT_HARD_LIMITS.get(limit_key)
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


def validate_window_transport_granularity(transport: Mapping[str, Any]) -> None:
    """
    Contrôles additifs. Ne remplace pas le decoder ni le validateur SRC.

    Overflow d'abord : le signal explicite prime sur les plafonds.
    """
    if transport_signals_overflow(transport):
        raise WindowSemanticCapacityExceeded(
            "signal analysis_capacity_exceeded — fenêtre NOT READY, "
            "aucun résultat canonique, aucun retry"
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


def validate_window_result_granularity(result: WindowSemanticResult) -> None:
    if result_signals_overflow(result):
        raise WindowSemanticCapacityExceeded(
            "signal analysis_capacity_exceeded — fenêtre NOT READY, "
            "aucun résultat canonique, aucun retry"
        )
    counts = Counter(record.kind for record in result.records)
    errors: list[str] = []
    if len(result.records) > TOTAL_HARD_CEILING:
        errors.append(
            f"total records {len(result.records)} > {TOTAL_HARD_CEILING}"
        )
    for kind, ceiling in HARD_CEILINGS.items():
        actual = int(counts.get(kind, 0))
        if actual > ceiling:
            errors.append(f"{kind} {actual} > plafond {ceiling}")
    for record in result.records:
        if record.value == OVERFLOW_TOKEN:
            continue
        limit = TEXT_HARD_LIMITS.get(f"{record.kind}.v")
        if limit is not None and len(record.value) > limit:
            errors.append(
                f"{record.record_id}.value ({record.kind}) : "
                f"{len(record.value)} > {limit}"
            )
        if len(record.source_refs) > SOURCE_REFS_HARD_MAX:
            errors.append(
                f"{record.record_id}.source_refs : "
                f"{len(record.source_refs)} > {SOURCE_REFS_HARD_MAX}"
            )
    if errors:
        raise WindowGranularityLimitExceeded(" | ".join(errors))


__all__ = [
    "AI_WITHIN_WINDOW_GROUPING",
    "GRANULARITY_PRINCIPLE",
    "HARD_CEILINGS",
    "IDEA_HARD_CEILING",
    "IDEA_SOFT_TARGET",
    "KIND_ORDER",
    "LOCAL_SEMANTIC_MERGE",
    "LOCAL_STRING_TRUNCATION",
    "MAX_OUTPUT_TOKENS_FROZEN",
    "OUTPUT_BUDGET_LOCAL_TOKENS",
    "OVERFLOW_TOKEN",
    "OVERFLOW_UNCERTAINTY_KIND",
    "OVERFLOW_UNCERTAINTY_SEVERITY",
    "POLICY_VERSION",
    "RELATION_HARD_CEILING",
    "SAFETY_MARGIN_RATIO",
    "SAFETY_MARGIN_RATIONALE",
    "SOFT_TARGETS",
    "SOURCE_REFS_HARD_MAX",
    "TEXT_HARD_LIMITS",
    "TOPIC_HARD_CEILING",
    "TOPIC_SOFT_TARGET",
    "TOTAL_HARD_CEILING",
    "TOTAL_SOFT_TARGET",
    "granularity_policy",
    "result_signals_overflow",
    "transport_signals_overflow",
    "validate_window_result_granularity",
    "validate_window_transport_granularity",
]
