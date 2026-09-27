"""Worst-case synthétique V3 + comparaison d'overhead vs V2."""

from __future__ import annotations

from typing import Any

from app.source_analysis_local_v2.synthetic import build_max_policy_v2_transport
from app.source_analysis_local_v3.constants import (
    MAX_OUTPUT_TOKENS_FROZEN,
    TARGET_JSON_LOCAL_TOKENS,
)
from app.source_analysis_local_v3.handles import recommended_handle
from app.source_analysis_window_output_bounding.size_study import measure_transport


def v2_records_to_v3_symbolic(transport: dict[str, Any]) -> dict[str, Any]:
    """
    Convertit un transport V2 interne (index) en V3 symbolique.

    Python assigne les handles par kind (T1… / I1…). Le provider ne calcule rien.
    """
    records = list(transport.get("records") or [])
    owners: list[str] = []
    kind_ordinal = {"TOPIC": 0, "IDEA": 0}
    for item in records:
        kind = str(item.get("k") or "")
        if kind in kind_ordinal:
            kind_ordinal[kind] += 1
            owners.append(recommended_handle(kind, kind_ordinal[kind]))
        else:
            owners.append("")
    converted = []
    for index, item in enumerate(records):
        kind = str(item.get("k") or "")
        raw_links = item.get("l") or []
        handles: list[str] = []
        for link in raw_links:
            if not isinstance(link, int) or isinstance(link, bool):
                continue
            if 0 <= link < len(owners) and owners[link]:
                handles.append(owners[link])
        converted.append(
            {
                "k": kind,
                "v": item.get("v"),
                "s": list(item.get("s") or []),
                "h": owners[index],
                "l": handles,
                "m": list(item.get("m") or []),
            }
        )
    return {
        "theme": transport.get("theme"),
        "intent": transport.get("intent"),
        "ic": transport.get("ic"),
        "aud": transport.get("aud"),
        "ac": transport.get("ac"),
        "records": converted,
    }


def build_max_policy_v3_transport(**kwargs) -> dict[str, Any]:
    return v2_records_to_v3_symbolic(build_max_policy_v2_transport(**kwargs))


def measure_handle_overhead() -> dict[str, Any]:
    v2 = build_max_policy_v2_transport()
    v3 = v2_records_to_v3_symbolic(v2)
    v2_m = measure_transport(v2)
    v3_m = measure_transport(v3)
    token_delta = int(v3_m["local_estimated_tokens"]) - int(v2_m["local_estimated_tokens"])
    byte_delta = int(v3_m["json_bytes"]) - int(v2_m["json_bytes"])
    v2_tokens = max(int(v2_m["local_estimated_tokens"]), 1)
    return {
        "v2": v2_m,
        "v3": v3_m,
        "byte_delta": byte_delta,
        "token_delta": token_delta,
        "percentage_overhead": round(100.0 * token_delta / v2_tokens, 4),
        "v3_within_json_target": int(v3_m["local_estimated_tokens"])
        <= TARGET_JSON_LOCAL_TOKENS,
        "target_json_local_tokens": TARGET_JSON_LOCAL_TOKENS,
        "max_output_tokens": MAX_OUTPUT_TOKENS_FROZEN,
    }


def measure_v3_worst_case() -> dict[str, Any]:
    overhead = measure_handle_overhead()
    local = int(overhead["v3"]["local_estimated_tokens"])
    return {
        **overhead,
        "local_tokens": local,
        "within_json_target": local <= TARGET_JSON_LOCAL_TOKENS,
        "headroom_to_32000": MAX_OUTPUT_TOKENS_FROZEN - local,
    }


__all__ = [
    "build_max_policy_v3_transport",
    "measure_handle_overhead",
    "measure_v3_worst_case",
    "v2_records_to_v3_symbolic",
]
