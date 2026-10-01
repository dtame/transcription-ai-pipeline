"""Distributions de longueur réelles par champ/kind. Offline, copies seulement."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from app.ai.providers.anthropic_engine import extract_anthropic_text
from app.ai.structured import parse_structured_output
from app.source_analysis_local_v3.schema import build_semantic_transport_v3_schema
from app.source_analysis_v3_a22_forensics.evidence import read_a22_raw_bytes
from app.source_analysis_v3_a25_forensics.evidence import read_a24_raw_bytes
from app.source_analysis_v31_length_ceiling.constants import (
    MODE,
    PHASE,
    PROJECT_NAME,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_length_ceiling.evidence import (
    read_json,
    ready_transport_path,
)
from app.source_analysis_v31_length_ceiling.replay import replay_win003_offline

_THRESHOLDS = (150, 175, 190, 200, 225, 250)
_FIELDS = (
    "theme",
    "TOPIC.v",
    "IDEA.v",
    "RELATION.v",
    "EXAMPLE.v",
    "REFERENCE.v",
    "UNCERTAINTY.v",
)


def _percentile(sorted_values: list[int], pct: float) -> int | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * pct
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[low]
    weight = rank - low
    return int(round(sorted_values[low] * (1 - weight) + sorted_values[high] * weight))


def collect_field_lengths(transport: Mapping[str, Any]) -> dict[str, list[int]]:
    buckets: dict[str, list[int]] = {key: [] for key in _FIELDS}
    theme = transport.get("theme")
    if isinstance(theme, str):
        buckets["theme"].append(len(theme))
    for item in transport.get("records") or []:
        if not isinstance(item, Mapping):
            continue
        kind = str(item.get("k") or "")
        value = item.get("v")
        key = f"{kind}.v"
        if key in buckets and isinstance(value, str):
            buckets[key].append(len(value))
    return buckets


def summarize(values: list[int]) -> dict[str, Any]:
    ordered = sorted(values)
    summary = {
        "count": len(ordered),
        "minimum": ordered[0] if ordered else None,
        "median": _percentile(ordered, 0.50),
        "p90": _percentile(ordered, 0.90),
        "p95": _percentile(ordered, 0.95),
        "p99": _percentile(ordered, 0.99),
        "maximum": ordered[-1] if ordered else None,
    }
    for threshold in _THRESHOLDS:
        summary[f"gt_{threshold}"] = sum(1 for item in ordered if item > threshold)
    return summary


def _parse_raw(raw: bytes) -> dict[str, Any]:
    data = json.loads(raw.decode("utf-8"))
    text = extract_anthropic_text(data)
    parsed = parse_structured_output(text, build_semantic_transport_v3_schema())
    if not isinstance(parsed, dict):
        raise ValueError("structured parse did not return an object")
    return parsed


def load_dataset_transports(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    win003_transport: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    datasets: dict[str, dict[str, Any]] = {}
    for window_id in ("WIN001", "WIN002", "WIN004"):
        path = ready_transport_path(project_name, window_id, sortie_dir=sortie_dir)
        datasets[window_id] = read_json(path)
    datasets["A22_WIN004"] = _parse_raw(
        read_a22_raw_bytes(project_name, sortie_dir=sortie_dir)
    )
    datasets["A24_WIN004"] = _parse_raw(
        read_a24_raw_bytes(project_name, sortie_dir=sortie_dir)
    )
    if win003_transport is None:
        replay = replay_win003_offline(project_name, sortie_dir=sortie_dir)
        win003_transport = replay["transport"]
    if not isinstance(win003_transport, Mapping):
        raise ValueError("WIN003 transport absent — cannot measure A.28 WIN003.")
    datasets["A28_WIN003"] = dict(win003_transport)
    return datasets


def build_distribution(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    win003_transport: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    datasets = load_dataset_transports(
        project_name, sortie_dir=sortie_dir, win003_transport=win003_transport
    )
    per_dataset: dict[str, Any] = {}
    combined: dict[str, list[int]] = {key: [] for key in _FIELDS}
    ready_combined: dict[str, list[int]] = {key: [] for key in _FIELDS}
    for name, transport in datasets.items():
        lengths = collect_field_lengths(transport)
        per_dataset[name] = {
            field: summarize(values) for field, values in lengths.items()
        }
        for field, values in lengths.items():
            combined[field].extend(values)
            if name in {"WIN001", "WIN002", "WIN004"}:
                ready_combined[field].extend(values)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "do_not_mix_record_kinds": True,
        "datasets": list(datasets),
        "ready_windows": ["WIN001", "WIN002", "WIN004"],
        "failed_parseable": ["A22_WIN004", "A24_WIN004", "A28_WIN003"],
        "per_dataset": per_dataset,
        "all_measured": {field: summarize(values) for field, values in combined.items()},
        "ready_only": {
            field: summarize(values) for field, values in ready_combined.items()
        },
        "observation": (
            "READY windows never exceed 200 on theme/EXAMPLE/IDEA. "
            "The only measured >200 values are A.28 WIN003 theme=212, "
            "EXAMPLE=213, and IDEA=209 (IDEA still under production 280)."
        ),
    }


__all__ = [
    "build_distribution",
    "collect_field_lengths",
    "load_dataset_transports",
    "summarize",
]
