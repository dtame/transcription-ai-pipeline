"""Forensics A.38 reuse-by-reference. Pas de réparation JSON. Pas de decode production."""

from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Mapping

from app.source_analysis_v31_global_output_architecture.evidence import read_a38_raw_text
from app.source_analysis_v31_global_output_architecture.forensics import inspect_raw_prefix
from app.source_analysis_v31_global_output_architecture.local_input import (
    expected_global_idea_range,
    load_duplicate_artifact,
    load_normalized_artifact,
    local_ideas,
)
from app.source_analysis_v31_global_reuse_output.constants import (
    EXPECTED_DROPS,
    EXPECTED_GLOBAL_IDEA_RANGE,
    EXPECTED_GLOBAL_IDEAS,
    EXPECTED_IDEA,
    EXPECTED_REUSED_IDEAS,
    EXPECTED_SYNTHESIZED_IDEAS,
    PROJECT_NAME,
)


def _norm(text: str) -> str:
    return " ".join(str(text or "").split()).casefold()


def classify_copy(global_text: str, local_text: str, ratio: float) -> str:
    if _norm(global_text) == _norm(local_text) or ratio >= 0.97:
        return "EXACT_OR_NEAR_REUSE"
    if ratio >= 0.85:
        return "LIGHT_NORMALIZATION"
    if ratio >= 0.50:
        return "MATERIAL_SYNTHESIS"
    return "UNDETERMINABLE"


def classify_a38_prefix_copies(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir=None,
) -> dict[str, Any]:
    raw = read_a38_raw_text(project_name, sortie_dir=sortie_dir)
    prefix = inspect_raw_prefix(raw)
    ideas = local_ideas(load_normalized_artifact(project_name, sortie_dir=sortie_dir))
    local_values = [str(item.get("value") or item.get("v") or "") for item in ideas]
    local_by_norm = {_norm(value): value for value in local_values if value}
    extracted = list((prefix.get("complete_objects") or {}).get("IDEA") or [])
    counts: Counter[str] = Counter()
    ratios: list[float] = []
    examples: dict[str, list[dict[str, Any]]] = {
        "EXACT_OR_NEAR_REUSE": [],
        "LIGHT_NORMALIZATION": [],
        "MATERIAL_SYNTHESIS": [],
        "UNDETERMINABLE": [],
    }
    for item in extracted:
        value = str(item.get("v") or "")
        if not value:
            counts["UNDETERMINABLE"] += 1
            continue
        exact = local_by_norm.get(_norm(value))
        if exact is not None:
            ratio = 1.0 if exact == value else SequenceMatcher(None, value, exact).ratio()
            label = classify_copy(value, exact, ratio)
            counts[label] += 1
            ratios.append(ratio)
            if len(examples[label]) < 3:
                examples[label].append(
                    {"ratio": round(ratio, 4), "global": value, "local": exact}
                )
            continue
        best_ratio = 0.0
        best_local = ""
        for local in local_values:
            if abs(len(local) - len(value)) > 40:
                continue
            ratio = SequenceMatcher(None, value, local).quick_ratio()
            if ratio < 0.75:
                continue
            ratio = SequenceMatcher(None, value, local).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_local = local
        if best_ratio <= 0:
            counts["UNDETERMINABLE"] += 1
            continue
        label = classify_copy(value, best_local, best_ratio)
        counts[label] += 1
        ratios.append(best_ratio)
        if len(examples[label]) < 3:
            examples[label].append(
                {
                    "ratio": round(best_ratio, 4),
                    "global": value,
                    "local": best_local,
                }
            )
    compared = sum(counts.values())
    mean_ratio = (sum(ratios) / len(ratios)) if ratios else 0.0
    kind_counts = prefix.get("kind_key_counts") or {}
    complete = prefix.get("complete_objects_by_kind") or {}
    truncated = max(
        0,
        int(kind_counts.get("IDEA") or 0) - int(complete.get("IDEA") or 0),
    )
    duplicates = load_duplicate_artifact(project_name, sortie_dir=sortie_dir)
    expected = expected_global_idea_range(duplicates)
    near = int(counts.get("EXACT_OR_NEAR_REUSE") or 0)
    light = int(counts.get("LIGHT_NORMALIZATION") or 0)
    material = int(counts.get("MATERIAL_SYNTHESIS") or 0)
    undetermined = int(counts.get("UNDETERMINABLE") or 0) + truncated
    return {
        "label": "RAW_PREFIX_FORENSIC_ESTIMATE",
        "not_canonical": True,
        "not_repaired": True,
        "raw_prefix_idea_keys": int(kind_counts.get("IDEA") or 0),
        "complete_idea_objects": int(complete.get("IDEA") or 0),
        "truncated_incomplete_ideas": truncated,
        "compared": compared,
        "mean_best_ratio": round(mean_ratio, 4),
        "classes": {
            "EXACT_OR_NEAR_REUSE": near,
            "LIGHT_NORMALIZATION": light,
            "MATERIAL_SYNTHESIS": material,
            "UNDETERMINABLE": undetermined,
        },
        "near_copy_rate": round(near / max(compared, 1), 4),
        "examples": examples,
        "a34_duplicate_audit": expected,
        "expected_production": {
            "local_ideas": EXPECTED_IDEA,
            "global_ideas_range": list(EXPECTED_GLOBAL_IDEA_RANGE),
            "expected_global_ideas": EXPECTED_GLOBAL_IDEAS,
            "expected_reused_single_member": EXPECTED_REUSED_IDEAS,
            "expected_synthesized_merges": EXPECTED_SYNTHESIZED_IDEAS,
            "expected_drops": EXPECTED_DROPS,
            "do_not_assume_similarity_equals_reuse_rate": True,
            "note": (
                "0.985 mean similarity describes copied wording, not merge rate. "
                "A.34 found 0 high-confidence duplicates and 1 source repetition, "
                "so expected merges stay near 1 and almost every distinct local "
                "IDEA can still REUSE without a provider rewrite."
            ),
        },
        "single_member_default": "REUSE",
        "multi_member_default": "SYNTHESIZE",
        "must_provider_emit_text_for_single_member": False,
    }


def reuse_by_reference_analysis(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir=None,
) -> dict[str, Any]:
    copies = classify_a38_prefix_copies(project_name, sortie_dir=sortie_dir)
    return {
        "primary_question": (
            "For a global IDEA whose membership contains exactly one local IDEA, "
            "must Anthropic emit a new proposition string?"
        ),
        "answer": "NO — canonical reconstruction can reuse the validated local IDEA text.",
        "a38": copies,
        "fidelity_principle": (
            "Reusing a validated local IDEA is safer than unnecessary paraphrase."
        ),
        "no_forced_merge": True,
    }


__all__ = [
    "classify_a38_prefix_copies",
    "classify_copy",
    "reuse_by_reference_analysis",
]
