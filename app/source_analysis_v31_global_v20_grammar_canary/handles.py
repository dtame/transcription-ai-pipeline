"""Audit des handles transport 2.0. Aucune réparation."""

from __future__ import annotations

import re
from typing import Any, Mapping

_HANDLE_RE = re.compile(r"^[TIEFU][1-9][0-9]*$")
_PREFIX_KIND = {
    "T": "TOPIC",
    "I": "IDEA",
    "E": "EXAMPLE",
    "F": "REFERENCE",
    "U": "UNCERTAINTY",
}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if isinstance(item, str) and item]


def inspect_global_handles_v20(
    payload: Mapping[str, Any] | None,
    *,
    allowed_input_ids: set[str] | None = None,
    kind_by_input: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    owners: dict[str, str] = {}
    owner_list: list[str] = []
    references: list[str] = []
    local_members: list[str] = []
    local_semantic_refs: list[str] = []
    unknown: list[str] = []
    unknown_local: list[str] = []
    wrong_kind: list[str] = []
    duplicate_owners: list[str] = []
    malformed: list[str] = []
    dangling: list[str] = []
    allowed = allowed_input_ids or set()
    kinds = kind_by_input or {}

    def _take_owner(handle: Any, kind: str, context: str) -> None:
        if not isinstance(handle, str) or not handle:
            malformed.append(f"{context}.h={handle!r}")
            return
        if not _HANDLE_RE.fullmatch(handle):
            malformed.append(handle)
            return
        expected = _PREFIX_KIND.get(handle[0])
        if expected and expected != kind:
            wrong_kind.append(f"{kind}->{handle}")
        if handle in owners:
            duplicate_owners.append(handle)
        else:
            owners[handle] = kind
            owner_list.append(handle)

    def _check_global_ref(raw: Any, *, context: str, expected_kind: str | None = None) -> None:
        if not isinstance(raw, str) or not raw:
            return
        references.append(raw)
        if not _HANDLE_RE.fullmatch(raw):
            malformed.append(f"{context}:{raw}")
            return
        if raw not in owners:
            unknown.append(raw)
            dangling.append(raw)
        elif expected_kind and owners.get(raw) != expected_kind:
            wrong_kind.append(f"{context}:{raw}")

    def _check_local(raw: str, *, context: str, expected_kind: str | None = None) -> None:
        if expected_kind in {"TOPIC", "IDEA"}:
            local_members.append(raw)
        else:
            local_semantic_refs.append(raw)
        if allowed and raw not in allowed:
            unknown_local.append(f"{context}:{raw}")
        elif kinds and expected_kind and kinds.get(raw) not in {None, expected_kind}:
            wrong_kind.append(f"{context}:{raw}->{kinds.get(raw)}")

    if isinstance(payload, Mapping):
        for index, topic in enumerate(_as_list(payload.get("t"))):
            if not isinstance(topic, Mapping):
                continue
            _take_owner(topic.get("h"), "TOPIC", f"t[{index}]")
            for member in _strings(topic.get("m")):
                _check_local(member, context=f"t[{index}].m", expected_kind="TOPIC")
        for index, idea in enumerate(_as_list(payload.get("i"))):
            if not isinstance(idea, Mapping):
                continue
            _take_owner(idea.get("h"), "IDEA", f"i[{index}]")
            for member in _strings(idea.get("m")):
                _check_local(member, context=f"i[{index}].m", expected_kind="IDEA")
        for index, row in enumerate(_as_list(payload.get("x"))):
            if not isinstance(row, Mapping):
                continue
            _take_owner(row.get("h"), "EXAMPLE", f"x[{index}]")
            for local_id in _strings(row.get("l")):
                _check_local(local_id, context=f"x[{index}].l", expected_kind="EXAMPLE")
            for handle in _strings(row.get("g")):
                _check_global_ref(handle, context=f"x[{index}].g", expected_kind="IDEA")
        for index, row in enumerate(_as_list(payload.get("f"))):
            if not isinstance(row, Mapping):
                continue
            _take_owner(row.get("h"), "REFERENCE", f"f[{index}]")
            for local_id in _strings(row.get("l")):
                _check_local(local_id, context=f"f[{index}].l", expected_kind="REFERENCE")
        for index, row in enumerate(_as_list(payload.get("u"))):
            if not isinstance(row, Mapping):
                continue
            _take_owner(row.get("h"), "UNCERTAINTY", f"u[{index}]")
            for local_id in _strings(row.get("l")):
                _check_local(local_id, context=f"u[{index}].l", expected_kind="UNCERTAINTY")

    root_violations = (
        len(unknown)
        + len(unknown_local)
        + len(wrong_kind)
        + len(duplicate_owners)
        + len(malformed)
        + len(dangling)
    )
    return {
        "owners": owners,
        "owner_handles": owner_list,
        "global_references": references,
        "local_members": local_members,
        "local_semantic_object_references": local_semantic_refs,
        "unknown_handles": unknown,
        "unknown_local_ids": unknown_local,
        "wrong_kind_handles": wrong_kind,
        "duplicate_owners": duplicate_owners,
        "malformed_handles": malformed,
        "dangling_references": dangling,
        "counts": {
            "owners": len(owner_list),
            "global_references": len(references),
            "local_members": len(local_members),
            "local_semantic_refs": len(local_semantic_refs),
            "unknown": len(unknown),
            "unknown_local": len(unknown_local),
            "wrong_kind": len(wrong_kind),
            "duplicate_owners": len(duplicate_owners),
            "malformed": len(malformed),
            "dangling": len(dangling),
        },
        "root_violations": root_violations,
        "handle_validation": "PASS" if root_violations == 0 else "FAIL",
        "repaired": False,
    }


__all__ = ["inspect_global_handles_v20"]
