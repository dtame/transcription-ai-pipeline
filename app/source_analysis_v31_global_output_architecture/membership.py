"""Validateur transport 2.0 — membership inverse. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import CONFIDENCE_LEVELS, IMPORTANCE_LEVELS
from app.source_analysis_v31_global_output_architecture.constants import (
    DROP_REASONS_V20,
    MAX_EXAMPLE_IDEA_REFS,
    MAX_LOCAL_IDS_PER_SATELLITE,
    MAX_MEMBERS_PER_IDEA,
    MAX_MEMBERS_PER_TOPIC,
    NEXT_TRANSPORT_VERSION,
    TEXT_LIMITS,
)
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    DROP_FIELDS,
    EXAMPLE_FIELDS,
    IDEA_FIELDS,
    REF_FIELDS,
    ROOT_FIELDS,
    TOPIC_FIELDS,
    UNC_FIELDS,
)
from app.source_analysis_v31_global_preflight.transport import GM_FIELDS


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if isinstance(item, str) and item]


def derive_dispositions(
    transport: Mapping[str, Any],
) -> dict[str, dict[str, str]]:
    derived: dict[str, dict[str, str]] = {}
    for idea in _as_list(transport.get("i")):
        if not isinstance(idea, Mapping):
            continue
        handle = str(idea.get("h") or "")
        members = _strings(idea.get("m"))
        op = "KEEP" if len(members) == 1 else "MERGE_EQUIVALENT"
        for member in members:
            derived[member] = {"i": member, "o": op, "g": handle, "w": "none"}
    for row in _as_list(transport.get("drop")):
        if not isinstance(row, Mapping):
            continue
        member = str(row.get("i") or "")
        reason = str(row.get("w") or "")
        if member:
            derived[member] = {"i": member, "o": "DROP", "g": "", "w": reason}
    return derived


def derived_src_union(
    member_ids: list[str],
    local_src_by_input: Mapping[str, list[str]],
) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for member in member_ids:
        for ref in local_src_by_input.get(member) or []:
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)
    return refs


def validate_global_transport_v20(
    payload: Mapping[str, Any] | None,
    *,
    idea_input_ids: list[str],
    allowed_input_ids: set[str],
    local_kind_by_input: Mapping[str, str] | None = None,
    text_limits: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    kinds = local_kind_by_input or {}
    limits = dict(TEXT_LIMITS if text_limits is None else text_limits)
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
    if "r" in payload or "d" in payload or "n" in payload:
        errors.append("historical 1.1 root keys are not part of transport 2.0")
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
    length_map = {
        "th": "theme",
        "in": "intent",
        "au": "audience",
        "vo": "voice",
    }
    for field, limit_key in length_map.items():
        value = str(gm.get(field) or "")
        if len(value) > limits[limit_key]:
            errors.append(f"gm.{field} exceeds {limits[limit_key]} chars")

    handles: dict[str, str] = {}
    idea_members: list[str] = []
    seen_members: set[str] = set()

    def _take_handle(handle: str, kind: str, context: str) -> None:
        if not handle:
            errors.append(f"{context}: empty handle")
            return
        if handle in handles:
            errors.append(f"duplicate handle {handle}")
        handles[handle] = kind

    for index, topic in enumerate(_as_list(payload.get("t"))):
        ctx = f"t[{index}]"
        if not isinstance(topic, Mapping):
            errors.append(f"{ctx} not an object")
            continue
        missing = [field for field in TOPIC_FIELDS if field not in topic]
        if missing:
            errors.append(f"{ctx} missing {missing}")
        handle = str(topic.get("h") or "")
        _take_handle(handle, "TOPIC", ctx)
        if len(str(topic.get("v") or "")) > limits["topic"]:
            errors.append(f"{ctx}.v exceeds {limits['topic']} chars")
        members = _strings(topic.get("m"))
        if not members:
            errors.append(f"{ctx}: empty membership")
        if len(members) > MAX_MEMBERS_PER_TOPIC:
            errors.append(f"{ctx}: too many members")
        for member in members:
            if member not in allowed_input_ids:
                errors.append(f"{ctx}: unknown member {member}")
            elif kinds and kinds.get(member) not in {None, "TOPIC"}:
                errors.append(f"{ctx}: {member} is not a local TOPIC")

    for index, idea in enumerate(_as_list(payload.get("i"))):
        ctx = f"i[{index}]"
        if not isinstance(idea, Mapping):
            errors.append(f"{ctx} not an object")
            continue
        missing = [field for field in IDEA_FIELDS if field not in idea]
        if missing:
            errors.append(f"{ctx} missing {missing}")
        handle = str(idea.get("h") or "")
        _take_handle(handle, "IDEA", ctx)
        if len(str(idea.get("v") or "")) > limits["idea"]:
            errors.append(f"{ctx}.v exceeds {limits['idea']} chars")
        if idea.get("p") not in IMPORTANCE_LEVELS:
            errors.append(f"{ctx}.p invalid importance")
        if "s" in idea:
            errors.append(f"{ctx}: provider must not emit SRC arrays")
        members = _strings(idea.get("m"))
        if not members:
            errors.append(f"{ctx}: empty membership")
        if len(members) > MAX_MEMBERS_PER_IDEA:
            errors.append(f"{ctx}: too many members")
        for member in members:
            if member in seen_members:
                errors.append(f"DUPLICATE_MEMBERSHIP:{member}")
            seen_members.add(member)
            idea_members.append(member)
            if member not in allowed_input_ids:
                errors.append(f"UNKNOWN_MEMBER:{member}")
            elif kinds and kinds.get(member) not in {None, "IDEA"}:
                errors.append(f"{ctx}: {member} is not a local IDEA")

    def _sat(key: str, fields: tuple[str, ...], kind: str, handle_kind: str) -> None:
        for index, row in enumerate(_as_list(payload.get(key))):
            ctx = f"{key}[{index}]"
            if not isinstance(row, Mapping):
                errors.append(f"{ctx} not an object")
                continue
            missing = [field for field in fields if field not in row]
            if missing:
                errors.append(f"{ctx} missing {missing}")
            _take_handle(str(row.get("h") or ""), handle_kind, ctx)
            locals_ = _strings(row.get("l"))
            if not locals_:
                errors.append(f"{ctx}: empty local ids")
            if len(locals_) > MAX_LOCAL_IDS_PER_SATELLITE:
                errors.append(f"{ctx}: too many local ids")
            for local_id in locals_:
                if local_id not in allowed_input_ids:
                    errors.append(f"{ctx}: unknown local id {local_id}")
                elif kinds and kinds.get(local_id) not in {None, kind}:
                    errors.append(f"{ctx}: {local_id} is not a local {kind}")
            if key == "x":
                refs = _strings(row.get("g"))
                if len(refs) > MAX_EXAMPLE_IDEA_REFS:
                    errors.append(f"{ctx}: too many idea refs")

    _sat("x", EXAMPLE_FIELDS, "EXAMPLE", "EXAMPLE")
    _sat("f", REF_FIELDS, "REFERENCE", "REFERENCE")
    _sat("u", UNC_FIELDS, "UNCERTAINTY", "UNCERTAINTY")

    dropped: list[str] = []
    for index, row in enumerate(_as_list(payload.get("drop"))):
        ctx = f"drop[{index}]"
        if not isinstance(row, Mapping):
            errors.append(f"{ctx} not an object")
            continue
        missing = [field for field in DROP_FIELDS if field not in row]
        if missing:
            errors.append(f"{ctx} missing {missing}")
        local_id = str(row.get("i") or "")
        reason = str(row.get("w") or "")
        if local_id in seen_members:
            errors.append(f"DUPLICATE_MEMBERSHIP:{local_id}")
        if local_id in dropped:
            errors.append(f"duplicate drop {local_id}")
        dropped.append(local_id)
        seen_members.add(local_id)
        if local_id not in allowed_input_ids:
            errors.append(f"UNKNOWN_MEMBER:{local_id}")
        elif kinds and kinds.get(local_id) not in {None, "IDEA"}:
            errors.append(f"{ctx}: {local_id} is not a local IDEA")
        if reason not in DROP_REASONS_V20:
            errors.append(f"{ctx}: invalid drop reason {reason}")
        if reason == "exact_duplicate":
            errors.append(f"{ctx}: exact_duplicate must be membership, not DROP")

    required = [item for item in idea_input_ids if item]
    accounted = set(idea_members) | set(dropped)
    missing = [item for item in required if item not in accounted]
    extras = sorted(item for item in accounted if item and item not in set(required))
    if missing:
        for item in missing:
            errors.append(f"SILENT_DROP:{item}")
    if extras and not kinds:
        pass
    coverage = 0.0
    if required:
        coverage = 100.0 * (len(required) - len(missing)) / len(required)

    derived = derive_dispositions(payload)
    return {
        "ok": not errors,
        "errors": errors,
        "idea_disposition_coverage": coverage,
        "silent_drops": missing,
        "unknown_members": [item for item in errors if item.startswith("UNKNOWN_MEMBER:")],
        "duplicate_members": [
            item for item in errors if item.startswith("DUPLICATE_MEMBERSHIP:")
        ],
        "accounted_idea_ids": sorted(accounted),
        "derived_dispositions": derived,
        "transport_version": NEXT_TRANSPORT_VERSION,
        "exact_set_equality": not missing and set(accounted) == set(required),
    }


__all__ = [
    "derive_dispositions",
    "derived_src_union",
    "validate_global_transport_v20",
]
