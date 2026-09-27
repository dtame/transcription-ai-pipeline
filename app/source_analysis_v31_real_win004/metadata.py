"""Audit exhaustif metadata local-lite IDEA m=[importance]. 0 provider."""

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
from app.source_analysis_v31_real_win004.constants import (
    A24_INVALID_IDEA_SHAPE,
    IDEA_SUBTYPE_TOKENS,
    MODE,
    OLD_V3_IDEA_SHAPE,
    PHASE,
    SCHEMA_VERSION,
)

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
        "idea_needles": ("relevant", "competence", "domain", "common", "good"),
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


def _as_meta(raw_m: Any) -> list[str]:
    if not isinstance(raw_m, list):
        return []
    return [str(slot) for slot in raw_m]


def audit_local_lite_idea_metadata(transport: Mapping[str, Any] | None) -> dict[str, Any]:
    records = _records(transport)
    idea_importance: Counter[str | None] = Counter()
    invalid: list[dict[str, Any]] = []
    leakage: list[dict[str, Any]] = []
    old_v3: list[dict[str, Any]] = []
    invalid_importance: list[dict[str, Any]] = []
    valid_importance_only = 0
    idea_count = 0
    by_kind: dict[str, list[list[str]]] = {}
    for index, item in enumerate(records):
        kind = str(item.get("k") or "")
        meta = _as_meta(item.get("m"))
        by_kind.setdefault(kind, []).append(meta)
        if kind != "IDEA":
            if kind == "EXAMPLE":
                if len(meta) != 1 or meta[0] not in EXAMPLE_KINDS:
                    invalid.append(
                        {
                            "index": index,
                            "k": kind,
                            "h": item.get("h"),
                            "m": meta,
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
                            "reason": "topic_metadata_invalid",
                        }
                    )
            continue

        idea_count += 1
        token = meta[0] if meta else None
        idea_importance[token] += 1
        shape = tuple(meta)
        subtype_in_any_slot = any(slot in IDEA_SUBTYPE_TOKENS for slot in meta)
        if subtype_in_any_slot:
            leakage.append(
                {
                    "index": index,
                    "h": item.get("h"),
                    "m": meta,
                    "v": item.get("v"),
                    "reason": "idea_subtype_leakage",
                }
            )
        if shape == OLD_V3_IDEA_SHAPE or (
            len(meta) == 2 and meta[0] in IDEA_KINDS and meta[1] in IMPORTANCE_LEVELS
        ):
            old_v3.append(
                {
                    "index": index,
                    "h": item.get("h"),
                    "m": meta,
                    "reason": "old_v3_idea_shape",
                }
            )
        if shape == A24_INVALID_IDEA_SHAPE:
            leakage.append(
                {
                    "index": index,
                    "h": item.get("h"),
                    "m": meta,
                    "reason": "a24_invalid_idea_shape",
                }
            )
        if len(meta) != 1:
            invalid.append(
                {
                    "index": index,
                    "k": kind,
                    "h": item.get("h"),
                    "m": meta,
                    "reason": "idea_local_lite_arity",
                }
            )
        elif token not in IMPORTANCE_LEVELS:
            invalid_importance.append(
                {
                    "index": index,
                    "h": item.get("h"),
                    "m": meta,
                    "reason": "invalid_importance",
                }
            )
            invalid.append(
                {
                    "index": index,
                    "k": kind,
                    "h": item.get("h"),
                    "m": meta,
                    "reason": "invalid_importance",
                }
            )
        elif token in IDEA_KINDS:
            leakage.append(
                {
                    "index": index,
                    "h": item.get("h"),
                    "m": meta,
                    "reason": "importance_is_subtype_token",
                }
            )
        else:
            valid_importance_only += 1

    local_lite_pass = (
        idea_count == valid_importance_only
        and not leakage
        and not old_v3
        and not invalid_importance
        and not invalid
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "idea_records": idea_count,
        "valid_importance_only_idea": valid_importance_only,
        "idea_subtype_leakage": len(leakage),
        "old_v3_idea_shape": len(old_v3),
        "invalid_importance": len(invalid_importance),
        "idea_importance_counts": {
            name: int(idea_importance.get(name, 0)) for name in IMPORTANCE_LEVELS
        },
        "leakage_rows": leakage,
        "old_v3_rows": old_v3,
        "invalid_importance_rows": invalid_importance,
        "invalid_metadata_rows": invalid,
        "other_metadata_violation_count": len(
            [row for row in invalid if not str(row.get("reason", "")).startswith("idea_")]
        ),
        "metadata_vocabulary_pass": local_lite_pass,
        "local_lite_metadata_pass": local_lite_pass,
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
    }


def probe_historical_patterns(transport: Mapping[str, Any] | None) -> dict[str, Any]:
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
            representation = "idea_and_example_separated"
        elif idea_hits:
            representation = "substantive_idea_proposition"
        elif example_hits:
            representation = "example_only"
        elif present:
            representation = "present_but_collapsed_or_ambiguous"
        else:
            representation = "not_observed"
        subtype_leak = any(
            any(slot in IDEA_SUBTYPE_TOKENS for slot in _as_meta(item.get("m")))
            for item in ideas
            if any(token in _norm(item.get("v")) for token in probe["example_needles"])
        )
        if subtype_leak:
            representation = "subtype_leakage"
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
    i44 = next((row for row in rows if row["id"] == "national_leader_economy"), None)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "patterns": rows,
        "i44_like": i44,
        "identical_wording_not_required": True,
    }


# Compatibilité avec les tests A.24 qui appellent audit_all_metadata.
audit_all_metadata = audit_local_lite_idea_metadata
probe_a22_four_patterns = probe_historical_patterns


__all__ = [
    "audit_all_metadata",
    "audit_idea_example_duplication",
    "audit_local_lite_idea_metadata",
    "probe_a22_four_patterns",
    "probe_historical_patterns",
]
