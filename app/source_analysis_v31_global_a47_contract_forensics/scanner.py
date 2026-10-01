"""Scanner structurel éditorial A.47 + forensics lexicale A.46."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import (
    EXTRA_STRUCTURAL_EDITORIAL_KEYS,
    FORBIDDEN_EDITORIAL_FIELDS,
    forbidden_editorial_fields,
    scan_editorial_structure,
)
from app.source_analysis_v31_global_v30_real_canary.constants import EDITORIAL_MARKERS


def lexical_marker_hits(payload: object) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []

    def _walk(node: object, path: str) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                _walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, (list, tuple)):
            for index, item in enumerate(node):
                _walk(item, f"{path}[{index}]")
        elif isinstance(node, str):
            lower = node.lower()
            for marker in EDITORIAL_MARKERS:
                if marker in lower:
                    idx = lower.find(marker)
                    hits.append(
                        {
                            "path": path,
                            "marker": marker,
                            "fragment": node[max(0, idx - 40) : idx + 80],
                        }
                    )
                    break

    _walk(payload, "$")
    return hits


def classify_a46_editorial(
    transport: Mapping[str, Any],
    candidate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = {"transport": dict(transport), "candidate": dict(candidate or {})}
    structural = scan_editorial_structure(payload)
    canonical_keys = forbidden_editorial_fields(candidate or {})
    lexical = lexical_marker_hits(payload)
    occurrences: list[dict[str, Any]] = []
    if isinstance(candidate, Mapping):
        for idea in candidate.get("ideas") or []:
            if not isinstance(idea, Mapping):
                continue
            summary = str(idea.get("summary") or "")
            if "chapter" not in summary.lower():
                continue
            occurrences.append(
                {
                    "canonical_object": "IDEA",
                    "id": idea.get("idea_id"),
                    "local_member": "inherited REUSE text (single-member KEEP)",
                    "source_refs": list(idea.get("source_refs") or []),
                    "text_fragment": summary,
                }
            )
        for ref in candidate.get("references") or []:
            if not isinstance(ref, Mapping):
                continue
            raw_ref = str(ref.get("raw_reference") or "")
            if "chapter" not in raw_ref.lower():
                continue
            occurrences.append(
                {
                    "canonical_object": "REFERENCE",
                    "id": ref.get("reference_id"),
                    "local_member": "inherited local REFERENCE text",
                    "source_refs": list(ref.get("source_refs") or []),
                    "text_fragment": raw_ref,
                }
            )
    actual_structure = bool(structural.get("hits")) or bool(canonical_keys)
    classification = (
        "FALSE_POSITIVE_LEXICAL_SCAN" if lexical and not actual_structure else (
            "TRUE_EDITORIAL_STRUCTURE" if actual_structure else "CLEAN"
        )
    )
    return {
        "classification": classification,
        "a46_actual_forbidden_editorial_structure": "YES" if actual_structure else "NO",
        "lexical_chapter_false_positive": classification == "FALSE_POSITIVE_LEXICAL_SCAN",
        "structural": structural,
        "canonical_forbidden_keys": list(canonical_keys),
        "lexical_hits": lexical,
        "lexical_hit_count": len(lexical),
        "source_supported_occurrences": occurrences,
        "forbidden_field_tuple": list(FORBIDDEN_EDITORIAL_FIELDS),
        "extra_structural_keys": list(EXTRA_STRUCTURAL_EDITORIAL_KEYS),
        "scans_text_values": False,
    }


__all__ = ["classify_a46_editorial", "lexical_marker_hits"]
