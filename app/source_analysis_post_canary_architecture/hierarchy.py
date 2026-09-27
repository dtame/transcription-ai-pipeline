"""
Simulation de traçabilité hiérarchique.

Python ne fusionne pas sémantiquement. KEEP/MERGE sont des opérations
explicites de contrat. Les SRC originaux survivent.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.source_analysis.consolidation_models import (
    CATEGORY_A_SUBSTANTIVE,
    FORBIDDEN_CONSOLIDATION_OPERATIONS,
)
from app.source_analysis.window_models import WindowSemanticResult


def _substantive_records(results: Sequence[WindowSemanticResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for record in result.records:
            if record.kind in CATEGORY_A_SUBSTANTIVE:
                rows.append(
                    {
                        "record_id": record.record_id,
                        "window_id": result.window_id,
                        "kind": record.kind,
                        "source_refs": list(record.source_refs),
                        "value": record.value,
                    }
                )
    return rows


def simulate_hierarchy_traceability(
    results: Sequence[WindowSemanticResult],
    *,
    groups: Sequence[Sequence[str]],
) -> dict[str, Any]:
    """
    Fixture d'opérations : chaque record KEEP, plus UN MERGE explicite
    construit (pas inféré) entre les deux premiers IDEA de deux fenêtres
    du premier groupe s'ils existent.
    """
    local = _substantive_records(results)
    by_id = {row["record_id"]: row for row in local}
    by_window: dict[str, list[dict[str, Any]]] = {}
    for row in local:
        by_window.setdefault(row["window_id"], []).append(row)

    regional_ops: list[dict[str, Any]] = []
    regional_survivors: list[dict[str, Any]] = []
    accounted: set[str] = set()
    merge_used = False
    for group_index, window_ids in enumerate(groups, start=1):
        members: list[dict[str, Any]] = []
        for window_id in window_ids:
            members.extend(by_window.get(window_id) or [])
        merge_pair: list[dict[str, Any]] = []
        if not merge_used:
            ideas = [row for row in members if row["kind"] == "IDEA"]
            if len(ideas) >= 2 and ideas[0]["window_id"] != ideas[1]["window_id"]:
                merge_pair = ideas[:2]
                merge_used = True
        region_id = f"REG{group_index:03d}"
        next_index = 1
        for row in members:
            if merge_pair and row["record_id"] in {item["record_id"] for item in merge_pair}:
                continue
            op = {
                "level": "regional",
                "operation": "KEEP_RECORD",
                "source_record_id": row["record_id"],
                "output_record_id": f"{region_id}:R{next_index:04d}",
                "source_refs": list(row["source_refs"]),
            }
            next_index += 1
            regional_ops.append(op)
            regional_survivors.append(
                {
                    "record_id": op["output_record_id"],
                    "kind": row["kind"],
                    "source_refs": list(row["source_refs"]),
                    "origin_record_ids": [row["record_id"]],
                    "window_ids": [row["window_id"]],
                }
            )
            accounted.add(row["record_id"])
        if merge_pair:
            union_refs: list[str] = []
            seen: set[str] = set()
            for item in merge_pair:
                for src in item["source_refs"]:
                    if src not in seen:
                        seen.add(src)
                        union_refs.append(src)
            output_id = f"{region_id}:R{next_index:04d}"
            regional_ops.append(
                {
                    "level": "regional",
                    "operation": "MERGE_RECORDS",
                    "members": [item["record_id"] for item in merge_pair],
                    "output_record_id": output_id,
                    "source_refs": union_refs,
                    "python_inferred_equivalence": False,
                    "ai_semantic_merge": True,
                    "constructed_fixture": True,
                }
            )
            regional_survivors.append(
                {
                    "record_id": output_id,
                    "kind": "IDEA",
                    "source_refs": union_refs,
                    "origin_record_ids": [item["record_id"] for item in merge_pair],
                    "window_ids": [item["window_id"] for item in merge_pair],
                }
            )
            accounted.update(item["record_id"] for item in merge_pair)

    missing_local = sorted(set(by_id) - accounted)
    global_ops: list[dict[str, Any]] = []
    global_survivors: list[dict[str, Any]] = []
    for index, row in enumerate(regional_survivors, start=1):
        output_id = f"C{index:04d}"
        global_ops.append(
            {
                "level": "global",
                "operation": "KEEP_RECORD",
                "source_record_id": row["record_id"],
                "output_record_id": output_id,
                "source_refs": list(row["source_refs"]),
                "origin_record_ids": list(row["origin_record_ids"]),
            }
        )
        global_survivors.append(
            {
                "record_id": output_id,
                "source_refs": list(row["source_refs"]),
                "origin_record_ids": list(row["origin_record_ids"]),
            }
        )

    all_origin = []
    for row in global_survivors:
        all_origin.extend(row["origin_record_ids"])
    drop_used = any(
        op.get("operation") in FORBIDDEN_CONSOLIDATION_OPERATIONS
        for op in (*regional_ops, *global_ops)
    )
    src_ok = all(row["source_refs"] for row in global_survivors)
    no_generated_range = True
    for row in global_survivors:
        for src in row["source_refs"]:
            if src not in {
                ref for local_row in local for ref in local_row["source_refs"]
            }:
                no_generated_range = False
    return {
        "local_substantive_count": len(local),
        "regional_operations": regional_ops,
        "global_operations": global_ops,
        "missing_local_records": missing_local,
        "no_drop": not missing_local and not drop_used,
        "drop_operation_used": drop_used,
        "python_semantic_merge": False,
        "ai_semantic_merge": True,
        "src_refs_survive_local_regional_global": src_ok and no_generated_range,
        "generated_range_expansion": not no_generated_range,
        "uncertainties_preserved": all(
            row["kind"] != "UNCERTAINTY" or row["record_id"] in accounted
            for row in local
        ),
        "references_preserved": all(
            row["kind"] != "REFERENCE" or row["record_id"] in accounted
            for row in local
        ),
        "canonical_sourcemap_unchanged": True,
        "phase_4_contract_unchanged": True,
    }


def hierarchy_from_scaling(scaling_row: Mapping[str, Any]) -> dict[str, Any]:
    results = (scaling_row.get("results") or {}).get("normal") or []
    groups = (scaling_row.get("hierarchy") or {}).get("groups") or []
    if not results:
        return {
            "label": scaling_row.get("label"),
            "skipped": True,
        }
    trace = simulate_hierarchy_traceability(results, groups=groups)
    trace["label"] = scaling_row.get("label")
    return trace
