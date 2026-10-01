"""Audit des handles globaux T1/I1/E1/F1/U1/P1. Aucune réparation."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.source_analysis_v31_global_grammar_canary.constants import (
    HANDLE_PREFIX_BY_KIND,
    NODE_KINDS,
)

_HANDLE_RE = re.compile(r"^[TIEFUP][1-9][0-9]*$")


def inspect_global_handles(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    owners: dict[str, str] = {}
    owner_list: list[str] = []
    references: list[str] = []
    unknown: list[str] = []
    wrong_kind: list[str] = []
    duplicate_owners: list[str] = []
    malformed: list[str] = []
    dangling: list[str] = []

    nodes = []
    if isinstance(payload, Mapping):
        raw_nodes = payload.get("n") or []
        if isinstance(raw_nodes, list):
            nodes = [item for item in raw_nodes if isinstance(item, dict)]

    for node in nodes:
        handle = node.get("h")
        kind = str(node.get("k") or "")
        if not isinstance(handle, str) or not handle:
            malformed.append(f"{kind}.h={handle!r}")
            continue
        if not _HANDLE_RE.fullmatch(handle):
            malformed.append(handle)
            continue
        expected_prefix = HANDLE_PREFIX_BY_KIND.get(kind)
        if expected_prefix and not handle.startswith(expected_prefix):
            wrong_kind.append(f"{kind}->{handle}")
        if handle in owners:
            duplicate_owners.append(handle)
        else:
            owners[handle] = kind
            owner_list.append(handle)
        if kind not in NODE_KINDS:
            wrong_kind.append(f"unknown-kind:{kind}:{handle}")

    def _check_ref(raw: Any, *, context: str) -> None:
        if not isinstance(raw, str) or not raw:
            return
        references.append(raw)
        if not _HANDLE_RE.fullmatch(raw):
            malformed.append(f"{context}:{raw}")
            return
        if raw not in owners:
            unknown.append(raw)
            dangling.append(raw)
        elif context.startswith("r.") and context.endswith(".kind"):
            return

    if isinstance(payload, Mapping):
        for index, rel in enumerate(payload.get("r") or []):
            if not isinstance(rel, dict):
                continue
            _check_ref(rel.get("a"), context=f"r[{index}].a")
            _check_ref(rel.get("b"), context=f"r[{index}].b")
            left = rel.get("a")
            right = rel.get("b")
            rel_type = str(rel.get("t") or "")
            if (
                rel_type
                and isinstance(left, str)
                and isinstance(right, str)
                and left in owners
                and right in owners
            ):
                left_kind = owners[left]
                right_kind = owners[right]
                if rel_type in {"supports", "explains", "develops", "qualifies", "contrasts_with"}:
                    if left_kind == "IDEA" and right_kind not in {"IDEA", "TOPIC"}:
                        wrong_kind.append(f"{rel_type}:{left}->{right}")
                if rel_type == "illustrates" and left_kind != "EXAMPLE":
                    wrong_kind.append(f"illustrates:{left}->{right}")
        for index, row in enumerate(payload.get("d") or []):
            if not isinstance(row, dict):
                continue
            handle = row.get("g")
            if isinstance(handle, str) and handle:
                _check_ref(handle, context=f"d[{index}].g")
        for node in nodes:
            if str(node.get("k") or "") != "REPETITION":
                continue
            for item in node.get("m") or []:
                if isinstance(item, str) and _HANDLE_RE.fullmatch(item):
                    _check_ref(item, context=f"{node.get('h')}.m")

    root_violations = (
        len(unknown)
        + len(wrong_kind)
        + len(duplicate_owners)
        + len(malformed)
        + len(dangling)
    )
    return {
        "owners": owners,
        "owner_handles": owner_list,
        "references": references,
        "unknown_handles": unknown,
        "wrong_kind_handles": wrong_kind,
        "duplicate_owners": duplicate_owners,
        "malformed_handles": malformed,
        "dangling_references": dangling,
        "counts": {
            "owners": len(owner_list),
            "references": len(references),
            "unknown": len(unknown),
            "wrong_kind": len(wrong_kind),
            "duplicate_owners": len(duplicate_owners),
            "malformed": len(malformed),
            "dangling": len(dangling),
        },
        "root_violations": root_violations,
        "handle_validation": "PASS" if root_violations == 0 else "FAIL",
        "repaired": False,
    }


__all__ = ["inspect_global_handles"]
