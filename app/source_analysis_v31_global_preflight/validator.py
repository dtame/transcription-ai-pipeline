"""Validateur déterministe du transport global. Aucun appel provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import (
    CONFIDENCE_LEVELS,
    IMPORTANCE_LEVELS,
    RELATION_KINDS,
    format_example_id,
    format_idea_id,
    format_reference_id,
    format_repetition_id,
    format_topic_id,
    format_uncertainty_id,
)
from app.source_analysis_local_v3.source_refs import is_canonical_src
from app.source_analysis_v31_global_preflight.constants import (
    ALLOWED_DROP_REASONS,
    FORBIDDEN_DROP_REASONS,
    GLOBAL_TRANSPORT_VERSION,
    IDEA_DISPOSITION_COVERAGE_REQUIRED,
    MODE,
    PHASE,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_global_preflight.normalize import src_number
from app.source_analysis_v31_global_preflight.transport import (
    DISP_FIELDS,
    GM_FIELDS,
    NODE_FIELDS,
    REL_FIELDS,
    ROOT_FIELDS,
)

ALLOWED_OPS = frozenset(
    {
        "KEEP",
        "MERGE_EQUIVALENT",
        "LINK_RELATED",
        "OTHER",
        "DROP",
        "REPRESENTED_AS_RELATION_OR_OTHER_APPROVED_OBJECT",
        "EXPLICITLY_DROPPED_WITH_REASON",
    }
)
SUBSTANTIVE_NODE_KINDS = frozenset(
    {"TOPIC", "IDEA", "EXAMPLE", "REFERENCE", "UNCERTAINTY", "REPETITION"}
)
_CANONICAL_FORMATTERS = {
    "TOPIC": format_topic_id,
    "IDEA": format_idea_id,
    "EXAMPLE": format_example_id,
    "REFERENCE": format_reference_id,
    "UNCERTAINTY": format_uncertainty_id,
    "REPETITION": format_repetition_id,
}


def earliest_src_key(refs: list[str]) -> tuple[int, str]:
    nums = [src_number(ref) for ref in refs]
    nums = [num for num in nums if num is not None]
    if not nums:
        return (10**9, "")
    return (min(nums), refs[0] if refs else "")


def assign_canonical_ids(nodes: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {kind: [] for kind in _CANONICAL_FORMATTERS}
    for node in nodes:
        kind = str(node.get("k") or "")
        if kind in grouped:
            grouped[kind].append(node)
    assigned: list[dict[str, Any]] = []
    for kind, formatter in _CANONICAL_FORMATTERS.items():
        ordered = sorted(
            grouped[kind],
            key=lambda node: (
                earliest_src_key(list(node.get("s") or [])),
                str(node.get("h") or ""),
            ),
        )
        for index, node in enumerate(ordered, start=1):
            row = dict(node)
            row["canonical_id"] = formatter(index)
            assigned.append(row)
    return assigned


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def validate_global_transport(
    payload: Mapping[str, Any] | None,
    *,
    idea_input_ids: list[str],
    allowed_input_ids: set[str],
    allowed_source_refs: set[str],
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return {
            "ok": False,
            "errors": ["transport must be an object"],
            "idea_disposition_coverage": 0.0,
        }
    extra = [key for key in payload if key not in ROOT_FIELDS]
    if extra:
        errors.append(f"unknown root fields: {extra}")
    gm = payload.get("gm")
    if not isinstance(gm, Mapping):
        errors.append("gm missing")
        gm = {}
    for field in GM_FIELDS:
        value = gm.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"gm.{field} empty")
    if gm.get("ic") and gm.get("ic") not in CONFIDENCE_LEVELS:
        errors.append("gm.ic invalid confidence")
    if gm.get("ac") and gm.get("ac") not in CONFIDENCE_LEVELS:
        errors.append("gm.ac invalid confidence")

    nodes = _as_list(payload.get("n"))
    handles: dict[str, Mapping[str, Any]] = {}
    for index, node in enumerate(nodes):
        loc = f"n[{index}]"
        if not isinstance(node, Mapping):
            errors.append(f"{loc} not an object")
            continue
        missing = [field for field in NODE_FIELDS if field not in node]
        if missing:
            errors.append(f"{loc} missing {missing}")
        handle = str(node.get("h") or "")
        kind = str(node.get("k") or "")
        if not handle:
            errors.append(f"{loc} empty handle")
        elif handle in handles:
            errors.append(f"duplicate global handle {handle}")
        else:
            handles[handle] = node
        if kind not in SUBSTANTIVE_NODE_KINDS:
            errors.append(f"{loc} unknown kind {kind}")
        refs = [str(item) for item in _as_list(node.get("s"))]
        if kind in {"IDEA", "EXAMPLE", "REFERENCE", "UNCERTAINTY", "REPETITION", "TOPIC"}:
            if not refs:
                errors.append(f"{loc} {kind} missing SRC")
        for ref in refs:
            if not is_canonical_src(ref):
                errors.append(f"{loc} noncanonical SRC {ref}")
            elif ref not in allowed_source_refs:
                errors.append(f"{loc} unknown SRC {ref}")
        if kind == "IDEA":
            meta = [str(item) for item in _as_list(node.get("m"))]
            importance = meta[0] if meta else ""
            if importance not in IMPORTANCE_LEVELS:
                errors.append(f"{loc} IDEA importance missing/invalid")

    relations = _as_list(payload.get("r"))
    for index, rel in enumerate(relations):
        loc = f"r[{index}]"
        if not isinstance(rel, Mapping):
            errors.append(f"{loc} not an object")
            continue
        missing = [field for field in REL_FIELDS if field not in rel]
        if missing:
            errors.append(f"{loc} missing {missing}")
        rel_type = str(rel.get("t") or "")
        if rel_type not in RELATION_KINDS:
            errors.append(f"{loc} invalid relation type")
        left = str(rel.get("a") or "")
        right = str(rel.get("b") or "")
        if left not in handles:
            errors.append(f"{loc} unknown handle {left}")
        if right not in handles:
            errors.append(f"{loc} unknown handle {right}")
        for ref in _as_list(rel.get("s")):
            if not is_canonical_src(str(ref)) or str(ref) not in allowed_source_refs:
                errors.append(f"{loc} unsupported SRC {ref}")

    dispositions = _as_list(payload.get("d"))
    seen_inputs: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(dispositions):
        loc = f"d[{index}]"
        if not isinstance(row, Mapping):
            errors.append(f"{loc} not an object")
            continue
        missing = [field for field in DISP_FIELDS if field not in row]
        if missing:
            errors.append(f"{loc} missing {missing}")
        input_id = str(row.get("i") or "")
        op = str(row.get("o") or "")
        handle = str(row.get("g") or "")
        reason = str(row.get("w") or "")
        if input_id in seen_inputs:
            errors.append(f"duplicate disposition for {input_id}")
        seen_inputs[input_id] = row
        if input_id and input_id not in allowed_input_ids:
            errors.append(f"unknown local handle {input_id}")
        if op not in ALLOWED_OPS:
            errors.append(f"{loc} unknown operation {op}")
        if op in {"DROP", "EXPLICITLY_DROPPED_WITH_REASON"}:
            if reason in FORBIDDEN_DROP_REASONS or reason == "not important":
                errors.append(f"{loc} forbidden drop reason")
            if reason not in ALLOWED_DROP_REASONS:
                errors.append(f"{loc} drop reason not in allowed set")
        if op in {"KEEP", "MERGE_EQUIVALENT"} and handle and handle not in handles:
            errors.append(f"{loc} unknown global handle {handle}")
        if op == "MERGE_EQUIVALENT":
            node = handles.get(handle) if handle else None
            if node is not None:
                node_refs = set(str(item) for item in _as_list(node.get("s")))
                if not node_refs:
                    errors.append(f"{loc} merge node missing SRC union")

    missing_ideas = [item for item in idea_input_ids if item not in seen_inputs]
    if missing_ideas:
        errors.append(f"silent drop of IDEA ids: {missing_ideas[:12]}")
    coverage = (
        100.0 * (len(idea_input_ids) - len(missing_ideas)) / len(idea_input_ids)
        if idea_input_ids
        else 100.0
    )
    if coverage < float(IDEA_DISPOSITION_COVERAGE_REQUIRED):
        errors.append("IDEA disposition coverage below 100%")

    return {
        "ok": not errors,
        "errors": errors,
        "idea_disposition_coverage": coverage,
        "disposition_count": len(seen_inputs),
        "node_count": len(handles),
        "relation_count": len(relations),
    }


def build_validator_contract(normalized: Mapping[str, Any]) -> dict[str, Any]:
    idea_ids = list(normalized.get("idea_input_ids") or [])
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "transport_version": GLOBAL_TRANSPORT_VERSION,
        "implemented_offline": True,
        "provider_called": False,
        "checks": [
            "schema/transport validity",
            "all input IDEA dispositions accounted for",
            "all output substantive elements traceable",
            "SRC validity",
            "no unknown local handles",
            "no unknown SRC",
            "no dangling global handles",
            "no duplicate global owners",
            "no silent drops",
            "merge SRC union required",
            "uncertainties preserved (review + validator)",
            "examples not promoted to unsupported claims (review + kind check)",
        ],
        "completeness": {
            "primary": "local IDEA disposition coverage = 100%",
            "idea_input_ids": len(idea_ids),
            "required_percent": IDEA_DISPOSITION_COVERAGE_REQUIRED,
            "other_kinds": "preferred 100% disposition for TOPIC/EXAMPLE/REFERENCE/UNCERTAINTY/RELATION",
        },
        "traceability": {
            "every_global_idea_has_canonical_src": True,
            "every_global_example_has_src": True,
            "reference_uncertainty_repetition_traceable": True,
        },
        "no_invention": (
            "Reject nodes whose SRC support cannot be established against "
            "allowed local SRC set. Semantic review still required."
        ),
        "canonical_reconstruction": {
            "path": "global transport → validate → assign canonical ids by earliest SRC → normalize_source_map → validate_source_map",
            "provider_canonical_ids": False,
            "gaps": [
                "SourceMap has no disposition map; keep as audit sidecar",
                "Idea.kind may remain empty",
                "Idea.importance is required on published SourceMap",
                "window identity must not become topics/chapters",
            ],
        },
        "publication_gate": [
            "provider response valid",
            "global transport valid",
            "disposition coverage complete",
            "semantic review acceptable",
            "canonical reconstruction PASS",
            "canonical SourceMap validation PASS",
            "tests green",
        ],
        "atomicity": True,
        "no_partial_publication": True,
    }


__all__ = [
    "assign_canonical_ids",
    "build_validator_contract",
    "earliest_src_key",
    "validate_global_transport",
]
