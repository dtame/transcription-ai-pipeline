"""Audit des dispositions IDEA A.35. 100 % coverage, 0 silent drop."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from app.source_analysis_v31_global_grammar_canary.constants import (
    ALLOWED_DROP_REASONS,
    FORBIDDEN_DROP_REASONS,
)
from app.source_analysis_v31_global_grammar_canary.fixture import (
    SyntheticConsolidationFixture,
)
from app.source_analysis_v31_global_preflight.constants import (
    IDEA_DISPOSITION_COVERAGE_REQUIRED,
)
from app.source_analysis_v31_global_preflight.validator import ALLOWED_OPS


def audit_dispositions(
    payload: Mapping[str, Any] | None,
    fixture: SyntheticConsolidationFixture,
) -> dict[str, Any]:
    dispositions = []
    if isinstance(payload, Mapping):
        raw = payload.get("d") or []
        if isinstance(raw, list):
            dispositions = [item for item in raw if isinstance(item, dict)]

    by_input: dict[str, dict[str, Any]] = {}
    unknown_local: list[str] = []
    duplicate: list[str] = []
    forbidden_drop: list[str] = []
    invalid_drop: list[str] = []
    for row in dispositions:
        input_id = str(row.get("i") or "")
        if input_id in by_input:
            duplicate.append(input_id)
        by_input[input_id] = row
        if input_id and input_id not in fixture.allowed_input_ids:
            unknown_local.append(input_id)
        op = str(row.get("o") or "")
        reason = str(row.get("w") or "")
        if op in {"DROP", "EXPLICITLY_DROPPED_WITH_REASON"}:
            if reason in FORBIDDEN_DROP_REASONS or reason == "not important":
                forbidden_drop.append(input_id)
            if reason not in ALLOWED_DROP_REASONS:
                invalid_drop.append(input_id)

    idea_ids = list(fixture.idea_input_ids)
    missing_ideas = [item for item in idea_ids if item not in by_input]
    coverage = (
        100.0 * (len(idea_ids) - len(missing_ideas)) / len(idea_ids) if idea_ids else 100.0
    )
    silent_drops = missing_ideas

    nodes = []
    if isinstance(payload, Mapping):
        nodes = [item for item in (payload.get("n") or []) if isinstance(item, dict)]
    handles = {str(item.get("h") or ""): item for item in nodes}

    merge_groups: dict[str, list[str]] = defaultdict(list)
    keep_map: dict[str, str] = {}
    link_map: dict[str, str] = {}
    drop_map: dict[str, str] = {}
    for input_id, row in by_input.items():
        op = str(row.get("o") or "")
        handle = str(row.get("g") or "")
        if op == "KEEP":
            keep_map[input_id] = handle
        elif op == "MERGE_EQUIVALENT":
            merge_groups[handle].append(input_id)
        elif op == "LINK_RELATED":
            link_map[input_id] = handle
        elif op in {"DROP", "EXPLICITLY_DROPPED_WITH_REASON"}:
            drop_map[input_id] = str(row.get("w") or "")

    merge_union_ok = True
    merge_union_errors: list[str] = []
    local_by_id = {item["id"]: item for item in _records(fixture)}
    for handle, inputs in merge_groups.items():
        node = handles.get(handle)
        node_refs = set(str(item) for item in (node.get("s") or []) if node) if node else set()
        expected_refs: set[str] = set()
        for input_id in inputs:
            expected_refs.update(local_by_id.get(input_id, {}).get("s") or [])
        if not expected_refs.issubset(node_refs):
            merge_union_ok = False
            merge_union_errors.append(
                f"{handle}: missing SRC union {sorted(expected_refs - node_refs)}"
            )
        if len(inputs) < 2:
            merge_union_errors.append(f"{handle}: MERGE_EQUIVALENT with <2 inputs")

    link_merged_wrongly = []
    merge_handles = set(merge_groups)
    for input_id, handle in link_map.items():
        if handle in merge_handles:
            # LINK_RELATED may point at a related global idea, but must not
            # share the MERGE handle as if it were semantically merged.
            link_merged_wrongly.append(input_id)

    keep_ok = True
    keep_errors: list[str] = []
    for input_id, handle in keep_map.items():
        if input_id in idea_ids:
            node = handles.get(handle)
            if node is None or str(node.get("k") or "") != "IDEA":
                keep_ok = False
                keep_errors.append(f"{input_id} KEEP missing IDEA {handle}")

    unknown_ops = [
        str(row.get("o") or "")
        for row in dispositions
        if str(row.get("o") or "") not in ALLOWED_OPS
    ]

    ok = (
        coverage >= float(IDEA_DISPOSITION_COVERAGE_REQUIRED)
        and not silent_drops
        and not unknown_local
        and not duplicate
        and not forbidden_drop
        and not invalid_drop
        and not unknown_ops
        and merge_union_ok
        and not link_merged_wrongly
        and keep_ok
        and not merge_union_errors
    )
    return {
        "ok": ok,
        "idea_disposition_coverage": coverage,
        "silent_drops": silent_drops,
        "silent_drop_count": len(silent_drops),
        "unknown_local_ids": unknown_local,
        "duplicate_inputs": duplicate,
        "forbidden_drop": forbidden_drop,
        "invalid_drop_reason": invalid_drop,
        "unknown_ops": unknown_ops,
        "keep": keep_map,
        "keep_ok": keep_ok,
        "keep_errors": keep_errors,
        "merge_groups": {key: list(value) for key, value in merge_groups.items()},
        "merge_union_ok": merge_union_ok,
        "merge_union_errors": merge_union_errors,
        "link_related": link_map,
        "link_related_non_merge": not link_merged_wrongly,
        "link_merged_wrongly": link_merged_wrongly,
        "drop": drop_map,
        "rows": dispositions,
        "status": "PASS" if ok else "FAIL",
    }


def _records(fixture: SyntheticConsolidationFixture) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window in fixture.compact.get("windows") or []:
        for item in window.get("records") or []:
            rows.append(item)
    return rows


__all__ = ["audit_dispositions"]
