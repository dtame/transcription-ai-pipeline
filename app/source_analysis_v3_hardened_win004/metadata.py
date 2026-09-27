"""Audit exhaustif metadata + duplication IDEA/EXAMPLE + sondes A.22. 0 provider."""

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
from app.source_analysis_v3_hardened_win004.constants import MODE, PHASE, SCHEMA_VERSION

_FOUR_PATTERNS = (
    {
        "id": "colonial_tutors_shirt",
        "label": "colonial tutors / shirt demand",
        "needles": (("tutor", "shirt"), ("colonial", "shirt"), ("shirt", "demand")),
        "idea_needles": ("arbitrary", "coerc", "power", "soldier", "roman"),
        "example_needles": ("shirt", "tutor", "colonel"),
    },
    {
        "id": "minister_testimony_formula",
        "label": "minister testimony / formula",
        "needles": (("minister", "formula"), ("testimony", "formula"), ("marathon",)),
        "idea_needles": ("formula", "law", "testimony", "freeze"),
        "example_needles": ("prayer", "fasting", "breakthrough", "marathon"),
    },
    {
        "id": "pig_heart_liver",
        "label": "pig-heart/liver transplants",
        "needles": (("pig", "heart"), ("pig", "liver"), ("transplant",)),
        "idea_needles": ("flesh", "blood", "knowledge", "revelation"),
        "example_needles": ("pig", "heart", "liver", "transplant"),
    },
    {
        "id": "national_leader_economy",
        "label": "national leader / economy",
        "needles": (("economy",), ("biya",), ("leader", "economy")),
        "idea_needles": ("relevant", "competence", "domain"),
        "example_needles": ("economy", "biya", "leader"),
    },
)


def _records(transport: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(transport, Mapping):
        return []
    return [item for item in (transport.get("records") or []) if isinstance(item, Mapping)]


def _norm(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


def _tokens(text: Any) -> set[str]:
    return {token for token in _norm(text).replace("'", " ").split() if len(token) > 3}


def audit_all_metadata(transport: Mapping[str, Any] | None) -> dict[str, Any]:
    records = _records(transport)
    idea_kinds: Counter[str | None] = Counter()
    invalid: list[dict[str, Any]] = []
    by_kind: dict[str, list[list[str]]] = {}
    idea_example_rows: list[dict[str, Any]] = []
    for index, item in enumerate(records):
        kind = str(item.get("k") or "")
        raw_m = item.get("m")
        meta = [str(slot) for slot in raw_m] if isinstance(raw_m, list) else []
        by_kind.setdefault(kind, []).append(meta)
        if kind == "IDEA":
            token = meta[0] if meta else None
            idea_kinds[token] += 1
            if token == "example":
                idea_example_rows.append(
                    {
                        "index": index,
                        "h": item.get("h"),
                        "m": meta,
                        "v": item.get("v"),
                    }
                )
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
    counted = {name: int(idea_kinds.get(name, 0)) for name in IDEA_KINDS}
    counted["example"] = int(idea_kinds.get("example", 0))
    counted["invalid_other"] = sum(
        count
        for name, count in idea_kinds.items()
        if name not in IDEA_KINDS and name != "example"
    )
    other = [row for row in invalid if row["reason"] != "idea_metadata_invalid"]
    idea_invalid = [row for row in invalid if row["reason"] == "idea_metadata_invalid"]
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "idea_count": sum(idea_kinds.values()),
        "idea_kind_counts": counted,
        "idea_kind_example": counted["example"],
        "invalid_metadata_rows": invalid,
        "invalid_idea_rows": idea_invalid,
        "other_metadata_violations": other,
        "other_metadata_violation_count": len(other),
        "metadata_vocabulary_pass": not invalid,
        "idea_example_rows": idea_example_rows,
        "all_m_values_by_kind": {
            kind: sorted({tuple(row) for row in rows}, key=lambda item: item)
            for kind, rows in by_kind.items()
        },
    }


def audit_idea_example_duplication(
    transport: Mapping[str, Any] | None,
) -> dict[str, Any]:
    records = _records(transport)
    ideas = [
        (index, item)
        for index, item in enumerate(records)
        if str(item.get("k") or "") == "IDEA"
    ]
    examples = [
        (index, item)
        for index, item in enumerate(records)
        if str(item.get("k") or "") == "EXAMPLE"
    ]
    duplicates: list[dict[str, Any]] = []
    for idea_index, idea in ideas:
        idea_text = _norm(idea.get("v"))
        idea_tokens = _tokens(idea.get("v"))
        if not idea_text:
            continue
        for example_index, example in examples:
            example_text = _norm(example.get("v"))
            example_tokens = _tokens(example.get("v"))
            if not example_text:
                continue
            overlap = (
                len(idea_tokens & example_tokens) / max(len(idea_tokens), 1)
                if idea_tokens
                else 0.0
            )
            contained = idea_text in example_text or example_text in idea_text
            if contained or overlap >= 0.7:
                duplicates.append(
                    {
                        "idea_index": idea_index,
                        "idea_h": idea.get("h"),
                        "idea_v": idea.get("v"),
                        "idea_m": idea.get("m"),
                        "example_index": example_index,
                        "example_v": example.get("v"),
                        "example_m": example.get("m"),
                        "overlap": round(overlap, 3),
                        "contained": contained,
                    }
                )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "duplicate_pairs": duplicates,
        "duplicate_pair_count": len(duplicates),
        "diagnostic_only": True,
        "note": (
            "Semantic diagnostic: IDEA whose only role is to duplicate an "
            "already emitted EXAMPLE. Metadata may still be valid."
        ),
    }


def probe_a22_four_patterns(transport: Mapping[str, Any] | None) -> dict[str, Any]:
    records = _records(transport)
    ideas = [item for item in records if str(item.get("k") or "") == "IDEA"]
    examples = [item for item in records if str(item.get("k") or "") == "EXAMPLE"]
    idea_blob = " ".join(_norm(item.get("v")) for item in ideas)
    example_blob = " ".join(_norm(item.get("v")) for item in examples)
    all_blob = " ".join(_norm(item.get("v")) for item in records)
    rows: list[dict[str, Any]] = []
    for probe in _FOUR_PATTERNS:
        present = any(all(token in all_blob for token in pair) for pair in probe["needles"])
        idea_hits = [token for token in probe["idea_needles"] if token in idea_blob]
        example_hits = [
            token for token in probe["example_needles"] if token in example_blob
        ]
        if idea_hits and example_hits:
            representation = "both_appropriately_separated"
        elif idea_hits:
            representation = "valid_idea_proposition"
        elif example_hits:
            representation = "valid_example"
        elif present:
            representation = "present_but_collapsed_or_ambiguous"
        else:
            representation = "not_observed"
        idea_example_kind = any(
            (item.get("m") or [None])[0] == "example"
            for item in ideas
            if any(token in _norm(item.get("v")) for token in probe["example_needles"])
        )
        if idea_example_kind:
            representation = "problematic_collapse_or_duplication"
        rows.append(
            {
                "id": probe["id"],
                "label": probe["label"],
                "analogous_material_present": present or bool(idea_hits or example_hits),
                "idea_hits": idea_hits,
                "example_hits": example_hits,
                "representation": representation,
                "identical_wording_not_required": True,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "patterns": rows,
        "identical_wording_not_required": True,
    }


__all__ = [
    "audit_all_metadata",
    "audit_idea_example_duplication",
    "probe_a22_four_patterns",
]
