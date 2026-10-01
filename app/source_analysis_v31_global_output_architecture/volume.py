"""Répartition du volume de sortie A.38 sur le préfixe brut. Pas un decode."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.source_analysis_v31_global_output_architecture.constants import (
    A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN,
    A38_OUTPUT_TOKENS,
    EXPECTED_IDEA,
)


def _tokens(chars: int) -> int:
    return int(round(chars / A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN))


def _object_cost(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "count": 0,
            "chars": 0,
            "tokens": 0,
            "mean_chars": 0,
            "mean_tokens": 0,
            "mean_src_refs": 0,
            "src_chars": 0,
            "src_tokens": 0,
        }
    serialized = [json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows]
    chars = sum(len(item) for item in serialized)
    src_chars = 0
    src_count = 0
    for row in rows:
        refs = [str(item) for item in (row.get("s") or []) if isinstance(item, str)]
        src_count += len(refs)
        src_chars += len(json.dumps(refs, ensure_ascii=False, separators=(",", ":")))
    return {
        "count": len(rows),
        "chars": chars,
        "tokens": _tokens(chars),
        "mean_chars": round(chars / len(rows), 1),
        "mean_tokens": round(_tokens(chars) / len(rows), 2),
        "mean_src_refs": round(src_count / len(rows), 2),
        "src_chars": src_chars,
        "src_tokens": _tokens(src_chars),
        "label": "RAW_PREFIX_FORENSIC_ESTIMATE",
    }


def disposition_ledger_cost(idea_count: int = EXPECTED_IDEA) -> dict[str, Any]:
    row = {"i": "W007:I99", "o": "KEEP", "g": "I286", "w": "none"}
    typical = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    drop = json.dumps(
        {"i": "W007:I99", "o": "DROP", "g": "", "w": "non_substantive_fragment"},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    merge = json.dumps(
        {"i": "W007:I99", "o": "MERGE_EQUIVALENT", "g": "I12", "w": "none"},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    array_overhead = 8
    minimum_chars = idea_count * len(typical) + array_overhead
    typical_chars = int(idea_count * ((len(typical) + len(merge)) / 2) + array_overhead)
    worst_chars = idea_count * max(len(typical), len(drop), len(merge)) + array_overhead
    return {
        "idea_count": idea_count,
        "never_reached_in_a38": True,
        "minimum_chars": minimum_chars,
        "typical_chars": typical_chars,
        "worst_chars": worst_chars,
        "minimum_tokens": _tokens(minimum_chars),
        "typical_tokens": _tokens(typical_chars),
        "worst_tokens": _tokens(worst_chars),
        "shape": "transport-1.1 d[]",
    }


def relation_cost() -> dict[str, Any]:
    row = {
        "t": "supports",
        "a": "I12",
        "b": "I44",
        "s": ["SRC000001", "SRC000002"],
    }
    typical = len(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    return {
        "do_not_require_all_127_local_relations": True,
        "plausible_global_counts": {
            "low": 40,
            "expected": 80,
            "high": 120,
        },
        "tokens": {
            "low": _tokens(40 * typical),
            "expected": _tokens(80 * typical),
            "high": _tokens(120 * typical),
        },
        "never_reached_in_a38": True,
    }


def breakdown_from_prefix(prefix: Mapping[str, Any], raw_text: str) -> dict[str, Any]:
    complete = prefix.get("complete_objects") or {}
    topics = _object_cost(list(complete.get("TOPIC") or []))
    ideas = _object_cost(list(complete.get("IDEA") or []))
    gm_end = raw_text.find(',"n"')
    gm_chars = gm_end if gm_end > 0 else 400
    src_chars = int(topics.get("src_chars") or 0) + int(ideas.get("src_chars") or 0)
    syntax_chars = max(
        0,
        len(raw_text)
        - int(topics.get("chars") or 0)
        - int(ideas.get("chars") or 0)
        - gm_chars,
    )
    disp = disposition_ledger_cost()
    rel = relation_cost()
    return {
        "label": "RAW_PREFIX_FORENSIC_ESTIMATE",
        "not_canonical": True,
        "observed_output_tokens": A38_OUTPUT_TOKENS,
        "observed_chars": len(raw_text),
        "chars_per_provider_token": A38_CHARS_PER_PROVIDER_OUTPUT_TOKEN,
        "components": {
            "global_metadata": {
                "chars": gm_chars,
                "tokens": _tokens(gm_chars),
                "note": "theme/intent/audience/voice — low volume",
            },
            "TOPIC_objects": topics,
            "IDEA_objects": ideas,
            "EXAMPLE_objects": _object_cost([]),
            "REFERENCE_objects": _object_cost([]),
            "UNCERTAINTY_objects": _object_cost([]),
            "REPETITION_objects": _object_cost([]),
            "RELATION_objects": {
                "started": False,
                **rel,
            },
            "DISPOSITION_objects": {
                "started": False,
                **disp,
            },
            "source_reference_arrays": {
                "chars": src_chars,
                "tokens": _tokens(src_chars),
                "occurrences": prefix.get("src_identifier_occurrences"),
                "major_contributor": _tokens(src_chars) >= 4000,
            },
            "handles_and_json_syntax_residual": {
                "chars": syntax_chars,
                "tokens": _tokens(syntax_chars),
            },
        },
        "idea_output_cost": {
            "mean_serialized_chars": ideas.get("mean_chars"),
            "mean_serialized_tokens": ideas.get("mean_tokens"),
            "label": "RAW_PREFIX_FORENSIC_ESTIMATE",
        },
        "topic_output_cost": {
            "mean_serialized_chars": topics.get("mean_chars"),
            "mean_serialized_tokens": topics.get("mean_tokens"),
            "label": "RAW_PREFIX_FORENSIC_ESTIMATE",
        },
        "source_ref_duplication_is_major": _tokens(src_chars) >= 4000,
    }


__all__ = [
    "breakdown_from_prefix",
    "disposition_ledger_cost",
    "relation_cost",
]
