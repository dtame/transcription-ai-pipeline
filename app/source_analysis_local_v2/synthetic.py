"""Worst-case synthétique V2. Recalculé, pas un chiffre figé."""

from __future__ import annotations

from typing import Any

from app.source_analysis_local_v2.constants import (
    DESIGN_SOURCE_REFS_WORST,
    HARD_CEILINGS,
    LOCAL_KINDS,
    MAX_OUTPUT_TOKENS_FROZEN,
    RESERVED_THINKING_TOKENS,
    SOURCE_REFS_HARD_MAX,
    TARGET_JSON_LOCAL_TOKENS,
    TOTAL_HARD_CEILING,
)
from app.source_analysis_local_v2.granularity import TEXT_HARD_LIMITS
from app.source_analysis_window_output_bounding.size_study import (
    build_scenario_transport,
    measure_transport,
)


def build_max_policy_v2_transport(
    *,
    source_refs: int = DESIGN_SOURCE_REFS_WORST,
    max_text: bool = True,
) -> dict[str, Any]:
    transport = build_scenario_transport(
        counts=dict(HARD_CEILINGS),
        idea_refs=source_refs,
        topic_refs=source_refs,
        other_refs=min(8, source_refs),
        max_text=max_text,
    )
    transport["records"] = [
        item
        for item in transport.get("records") or []
        if item.get("k") in LOCAL_KINDS
    ]
    return transport


def measure_v2_worst_case() -> dict[str, Any]:
    designed = build_max_policy_v2_transport()
    designed_m = measure_transport(designed)
    stress_48 = build_max_policy_v2_transport(source_refs=SOURCE_REFS_HARD_MAX)
    stress_m = measure_transport(stress_48)
    local = int(designed_m["local_estimated_tokens"])
    return {
        "designed_source_refs": DESIGN_SOURCE_REFS_WORST,
        "application_source_refs_hard_max": SOURCE_REFS_HARD_MAX,
        "per_kind_ceilings": dict(HARD_CEILINGS),
        "total_hard": TOTAL_HARD_CEILING,
        "text_limits": dict(TEXT_HARD_LIMITS),
        "designed": designed_m,
        "stress_48_refs": stress_m,
        "local_tokens": local,
        "target_json_local_tokens": TARGET_JSON_LOCAL_TOKENS,
        "within_json_target": local <= TARGET_JSON_LOCAL_TOKENS,
        "headroom_to_32000": MAX_OUTPUT_TOKENS_FROZEN - local,
        "thinking_reserve_design": RESERVED_THINKING_TOKENS,
        "json_plus_thinking_design": local + RESERVED_THINKING_TOKENS,
        "remaining_max_output_headroom": MAX_OUTPUT_TOKENS_FROZEN
        - (local + RESERVED_THINKING_TOKENS),
        "provider_enforced_json": False,
        "provider_enforced_thinking_reserve": False,
        "kind_counts": designed_m["kind_counts"],
        "record_count": designed_m["record_count"],
        "source_ref_note": (
            "Designed worst-case uses 12 refs/record (A.10 structural "
            "target). Application hard cap remains 48; a 48-ref fill is "
            "measured separately and is not the design target."
        ),
    }


__all__ = [
    "build_max_policy_v2_transport",
    "measure_v2_worst_case",
]
