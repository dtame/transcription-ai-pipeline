"""Inventaire de tout m[] — pas seulement les quatre IDEA/example connues."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from app.source_analysis.models import (
    EXAMPLE_KINDS,
    IDEA_KINDS,
    IMPORTANCE_LEVELS,
    REFERENCE_COMPLETENESS,
    REFERENCE_KINDS,
    RELATION_KINDS,
    SEVERITY_LEVELS,
    UNCERTAINTY_KINDS,
)
from app.source_analysis_v3_a22_forensics.constants import (
    IDEA_KIND_COUNTS_EXPECTED,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)


def _records(transport: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(transport, Mapping):
        return []
    return [item for item in (transport.get("records") or []) if isinstance(item, Mapping)]


def audit_all_metadata(transport: Mapping[str, Any] | None) -> dict[str, Any]:
    records = _records(transport)
    idea_kinds: Counter[str | None] = Counter()
    invalid: list[dict[str, Any]] = []
    by_kind: dict[str, list[list[str]]] = {}
    for index, item in enumerate(records):
        kind = str(item.get("k") or "")
        raw_m = item.get("m")
        meta = [str(slot) for slot in raw_m] if isinstance(raw_m, list) else []
        by_kind.setdefault(kind, []).append(meta)
        if kind == "IDEA":
            token = meta[0] if meta else None
            idea_kinds[token] += 1
            if (
                len(meta) != 2
                or meta[0] not in IDEA_KINDS
                or meta[1] not in IMPORTANCE_LEVELS
            ):
                invalid.append(
                    {
                        "index": index,
                        "k": kind,
                        "h": item.get("h"),
                        "m": meta,
                        "v": item.get("v"),
                        "reason": "idea_metadata_invalid",
                    }
                )
        elif kind == "EXAMPLE":
            if len(meta) != 1 or meta[0] not in EXAMPLE_KINDS:
                invalid.append(
                    {
                        "index": index,
                        "k": kind,
                        "m": meta,
                        "v": item.get("v"),
                        "reason": "example_metadata_invalid",
                    }
                )
        elif kind == "REFERENCE":
            if (
                len(meta) != 3
                or meta[0] not in REFERENCE_KINDS
                or meta[1] not in REFERENCE_COMPLETENESS
            ):
                invalid.append(
                    {
                        "index": index,
                        "k": kind,
                        "m": meta,
                        "v": item.get("v"),
                        "reason": "reference_metadata_invalid",
                    }
                )
        elif kind == "UNCERTAINTY":
            if (
                len(meta) != 2
                or meta[0] not in UNCERTAINTY_KINDS
                or meta[1] not in SEVERITY_LEVELS
            ):
                invalid.append(
                    {
                        "index": index,
                        "k": kind,
                        "m": meta,
                        "v": item.get("v"),
                        "reason": "uncertainty_metadata_invalid",
                    }
                )
        elif kind == "RELATION":
            if meta or str(item.get("v") or "") not in RELATION_KINDS:
                invalid.append(
                    {
                        "index": index,
                        "k": kind,
                        "m": meta,
                        "v": item.get("v"),
                        "reason": "relation_metadata_or_type_invalid",
                    }
                )
        elif kind == "TOPIC":
            if len(meta) != 1 or not meta[0]:
                invalid.append(
                    {
                        "index": index,
                        "k": kind,
                        "m": meta,
                        "v": item.get("v"),
                        "reason": "topic_metadata_invalid",
                    }
                )
    counted = {
        name: int(idea_kinds.get(name, 0))
        for name in list(IDEA_KINDS) + ["example"]
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "idea_count": sum(idea_kinds.values()),
        "idea_kind_counts": counted,
        "idea_kind_counts_expected": dict(IDEA_KIND_COUNTS_EXPECTED),
        "matches_expected_idea_counts": counted == dict(IDEA_KIND_COUNTS_EXPECTED),
        "invalid_metadata_rows": invalid,
        "invalid_idea_example_count": sum(
            1 for row in invalid if row["reason"] == "idea_metadata_invalid"
        ),
        "other_metadata_violations": [
            row for row in invalid if row["reason"] != "idea_metadata_invalid"
        ],
        "other_metadata_violation_count": sum(
            1 for row in invalid if row["reason"] != "idea_metadata_invalid"
        ),
        "all_m_values_by_kind": {
            kind: sorted({tuple(row) for row in rows}, key=lambda item: item)
            for kind, rows in by_kind.items()
        },
        "latent_invalid_vocabulary_beyond_four_ideas": False,
    }


__all__ = ["audit_all_metadata"]
