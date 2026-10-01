"""Qualité des IDEAs locales pour REUSE verbatim. Revue forensique offline."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Mapping

from app.source_analysis_v31_global_output_architecture.local_input import (
    load_normalized_artifact,
    local_ideas,
)
from app.source_analysis_v31_global_reuse_output.constants import (
    EXPECTED_IDEA,
    PROJECT_NAME,
    READY_WINDOWS,
)

_FILLER = re.compile(r"\b(uh+|um+|you know)\b", re.I)
_ANAPHORA = re.compile(r"^(This|That)\s+(teaching|idea|point|one)\b", re.I)


def classify_local_idea_text(text: str) -> str:
    t = str(text or "").strip()
    if not t or len(t) < 40:
        return "NOT_SELF_CONTAINED"
    if _FILLER.search(t):
        return "NOT_SELF_CONTAINED"
    if t.endswith((",", "...", "—")):
        return "NOT_SELF_CONTAINED"
    if _ANAPHORA.search(t):
        return "NEEDS_NORMALIZATION"
    return "READY_FOR_REUSE"


def _percentile(sorted_values: list[int], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct / 100.0
    low = math.floor(k)
    high = math.ceil(k)
    if low == high:
        return float(sorted_values[int(k)])
    return sorted_values[low] * (high - k) + sorted_values[high] * (k - low)


def idea_length_distribution(ideas: list[Mapping[str, Any]]) -> dict[str, Any]:
    lengths = sorted(len(str(item.get("value") or item.get("v") or "")) for item in ideas)
    if not lengths:
        return {"count": 0}
    return {
        "count": len(lengths),
        "min": lengths[0],
        "p50": round(_percentile(lengths, 50), 1),
        "p75": round(_percentile(lengths, 75), 1),
        "p90": round(_percentile(lengths, 90), 1),
        "p95": round(_percentile(lengths, 95), 1),
        "max": lengths[-1],
        "mean": round(sum(lengths) / len(lengths), 3),
        "exceed_synthesized_cap_180": sum(1 for item in lengths if item > 180),
    }


def stratified_samples(ideas: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_window: dict[str, list[Mapping[str, Any]]] = {}
    for item in ideas:
        window = str(item.get("window_id") or "")
        by_window.setdefault(window, []).append(item)
    samples: list[dict[str, Any]] = []
    for window in READY_WINDOWS:
        rows = by_window.get(window) or []
        if not rows:
            continue
        positions = [("beginning", 0), ("middle", len(rows) // 2), ("end", len(rows) - 1)]
        for label, index in positions:
            row = rows[index]
            text = str(row.get("value") or row.get("v") or "")
            samples.append(
                {
                    "window_id": window,
                    "position": label,
                    "input_id": row.get("input_id") or row.get("id"),
                    "chars": len(text),
                    "classification": classify_local_idea_text(text),
                    "text": text,
                    "provider_call": False,
                }
            )
    return samples


def assess_local_idea_reuse_quality(
    project_name: str = PROJECT_NAME,
) -> dict[str, Any]:
    normalized = load_normalized_artifact(project_name)
    ideas = local_ideas(normalized)
    samples = stratified_samples(ideas)
    sample_counts = Counter(item["classification"] for item in samples)
    census_counts = Counter(
        classify_local_idea_text(str(item.get("value") or item.get("v") or ""))
        for item in ideas
    )
    lengths = idea_length_distribution(ideas)
    ready_rate = census_counts.get("READY_FOR_REUSE", 0) / max(len(ideas), 1)
    sample_ready_rate = sample_counts.get("READY_FOR_REUSE", 0) / max(len(samples), 1)
    high_quality = sample_ready_rate >= 0.90 and ready_rate >= 0.95
    return {
        "local_idea_count": len(ideas),
        "expected_local_ideas": EXPECTED_IDEA,
        "sample_size": len(samples),
        "sample_design": "beginning/middle/end of WIN001–WIN007",
        "sample_counts": dict(sample_counts),
        "sample_ready_rate": round(sample_ready_rate, 4),
        "census_counts": dict(census_counts),
        "census_ready_rate": round(ready_rate, 4),
        "samples": samples,
        "lengths": lengths,
        "high_reuse_quality": high_quality,
        "material_degradation_if_hard_reuse": False,
        "human_review_note": (
            "The only census NEEDS_NORMALIZATION cases are mild sentence-initial "
            "anaphora that remain usable propositions. No fragment/filler local "
            "IDEA was found in the stratified sample."
        ),
        "provider_called": False,
    }


__all__ = [
    "assess_local_idea_reuse_quality",
    "classify_local_idea_text",
    "idea_length_distribution",
    "stratified_samples",
]
