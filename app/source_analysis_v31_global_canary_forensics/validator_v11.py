"""Validateur transport 1.1. Historique 1.0 inchangé. Aucun appel provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import (
    CONFIDENCE_LEVELS,
    IMPORTANCE_LEVELS,
    RELATION_KINDS,
)
from app.source_analysis_local_v3.source_refs import is_canonical_src
from app.source_analysis_v31_global_canary_forensics.constants import (
    FORBIDDEN_DROP_REASONS,
    IDEA_DISPOSITION_COVERAGE_REQUIRED,
    NEXT_TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    DROP_REASON_CODES,
    NON_DROP_REASON_CODE,
    REASON_CODES,
    REPRESENTATION_OPS,
    RETIRED_OPS,
)
from app.source_analysis_v31_global_preflight.transport import (
    DISP_FIELDS,
    GM_FIELDS,
    NODE_FIELDS,
    REL_FIELDS,
    ROOT_FIELDS,
)

SUBSTANTIVE_NODE_KINDS = frozenset(
    {"TOPIC", "IDEA", "EXAMPLE", "REFERENCE", "UNCERTAINTY", "REPETITION"}
)
OTHER_APPROVED_KINDS = frozenset(
    {"TOPIC", "EXAMPLE", "REFERENCE", "UNCERTAINTY"}
)


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _no_heuristic_drop_normalization(reason: str) -> bool:
    """Refuse any non-exact token. No lowercase-and-guess, no substring map."""
    return reason in REASON_CODES


def validate_global_transport_v11(
    payload: Mapping[str, Any] | None,
    *,
    idea_input_ids: list[str],
    allowed_input_ids: set[str],
    allowed_source_refs: set[str],
    local_src_by_input: Mapping[str, list[str]] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return {
            "ok": False,
            "errors": ["transport must be an object"],
            "idea_disposition_coverage": 0.0,
            "transport_version": NEXT_TRANSPORT_VERSION,
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
        if kind in SUBSTANTIVE_NODE_KINDS and not refs:
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
    merge_groups: dict[str, list[str]] = {}
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
        if op in RETIRED_OPS:
            errors.append(f"{loc} retired operation {op}")
        elif op not in REPRESENTATION_OPS:
            errors.append(f"{loc} unknown operation {op}")
        if not _no_heuristic_drop_normalization(reason):
            errors.append(f"{loc} reason_code not an exact allowed token")
        if reason in FORBIDDEN_DROP_REASONS or reason == "not important":
            errors.append(f"{loc} forbidden drop reason")
        if op == "DROP":
            if handle:
                errors.append(f"{loc} DROP must have empty g")
            if reason not in DROP_REASON_CODES:
                errors.append(f"{loc} DROP reason_code must be an allowed DROP token")
        elif op in REPRESENTATION_OPS:
            if reason != NON_DROP_REASON_CODE:
                errors.append(f"{loc} non-DROP reason_code must be none")
        if op in {"KEEP", "MERGE_EQUIVALENT"}:
            if handle and handle not in handles:
                errors.append(f"{loc} unknown global handle {handle}")
        if op == "KEEP" and input_id in idea_input_ids:
            node = handles.get(handle) if handle else None
            if node is None or str(node.get("k") or "") != "IDEA":
                errors.append(f"{loc} KEEP IDEA missing surviving IDEA handle")
        if op == "MERGE_EQUIVALENT":
            if handle:
                merge_groups.setdefault(handle, []).append(input_id)
            node = handles.get(handle) if handle else None
            if node is not None and not _as_list(node.get("s")):
                errors.append(f"{loc} merge node missing SRC union")
        if op == "OTHER" and input_id in idea_input_ids:
            node = handles.get(handle) if handle else None
            kind = str(node.get("k") or "") if node is not None else ""
            if node is None or kind not in OTHER_APPROVED_KINDS:
                errors.append(
                    f"{loc} IDEA OTHER must point at another approved object handle"
                )

    for handle, inputs in merge_groups.items():
        if len(inputs) < 2:
            errors.append(f"MERGE_EQUIVALENT {handle} has <2 inputs")
        node = handles.get(handle)
        node_refs = set(
            str(item) for item in _as_list(node.get("s") if node is not None else [])
        )
        expected_refs: set[str] = set()
        for input_id in inputs:
            expected_refs.update(
                str(item) for item in (local_src_by_input or {}).get(input_id) or []
            )
        if expected_refs and not expected_refs.issubset(node_refs):
            errors.append(
                f"{handle}: missing SRC union {sorted(expected_refs - node_refs)}"
            )

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
        "silent_drop_count": len(missing_ideas),
        "silent_drops": missing_ideas,
        "disposition_count": len(seen_inputs),
        "node_count": len(handles),
        "relation_count": len(relations),
        "transport_version": NEXT_TRANSPORT_VERSION,
        "heuristic_normalization": False,
    }


__all__ = ["validate_global_transport_v11"]
