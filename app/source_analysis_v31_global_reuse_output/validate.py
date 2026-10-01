"""Validateur transport 3.0 — REUSE/SYNTHESIZE + membership inverse. 0 provider."""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis.models import CONFIDENCE_LEVELS, IMPORTANCE_LEVELS
from app.source_analysis_v31_global_output_architecture.constants import (
    DROP_REASONS_V20,
    MAX_EXAMPLE_IDEA_REFS,
    MAX_LOCAL_IDS_PER_SATELLITE,
    MAX_MEMBERS_PER_IDEA,
    MAX_MEMBERS_PER_TOPIC,
    TEXT_LIMITS,
)
from app.source_analysis_v31_global_output_architecture.membership import (
    derive_dispositions,
    derived_src_union,
)
from app.source_analysis_v31_global_preflight.transport import GM_FIELDS
from app.source_analysis_v31_global_reuse_output.constants import (
    NEXT_TRANSPORT_VERSION,
    SYNTHESIZED_IDEA_MAX_CHARS,
)
from app.source_analysis_v31_global_reuse_output.transport_v30 import (
    DROP_FIELDS,
    EXAMPLE_FIELDS,
    IDEA_OPTIONAL_FIELDS,
    IDEA_REQUIRED_FIELDS,
    REF_FIELDS,
    ROOT_FIELDS,
    TOPIC_FIELDS,
    UNC_FIELDS,
)


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if isinstance(item, str) and item]


def idea_mode(idea: Mapping[str, Any]) -> str:
    members = _strings(idea.get("m"))
    has_text = isinstance(idea.get("v"), str) and str(idea.get("v") or "").strip() != ""
    if len(members) >= 2:
        return "SYNTHESIZE"
    if len(members) == 1 and not has_text:
        return "REUSE"
    if len(members) == 1 and has_text:
        return "FORBIDDEN_REWRITE"
    return "INVALID"


def validate_global_transport_v30(
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
    idea_limit = int(limits.get("idea") or SYNTHESIZED_IDEA_MAX_CHARS)
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
        errors.append("historical 1.1 root keys are not part of transport 3.0")
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
    # Product bound: TEXT_LIMITS["intent"] == GLOBAL_INTENT_MAX_CHARS (320).
    # 240 was the A.39 compactness instruction, not a semantic requirement.
    length_map = {"th": "theme", "in": "intent", "au": "audience", "vo": "voice"}
    for field, limit_key in length_map.items():
        value = str(gm.get(field) or "")
        if len(value) > limits[limit_key]:
            errors.append(f"gm.{field} exceeds {limits[limit_key]} chars")

    handles: dict[str, str] = {}
    idea_members: list[str] = []
    seen_members: set[str] = set()
    reuse_count = 0
    synthesize_count = 0

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
        missing = [field for field in IDEA_REQUIRED_FIELDS if field not in idea]
        if missing:
            errors.append(f"{ctx} missing {missing}")
        unknown_fields = [
            key
            for key in idea
            if key not in IDEA_REQUIRED_FIELDS and key not in IDEA_OPTIONAL_FIELDS
        ]
        if unknown_fields:
            errors.append(f"{ctx} unknown fields {unknown_fields}")
        handle = str(idea.get("h") or "")
        _take_handle(handle, "IDEA", ctx)
        if idea.get("p") not in IMPORTANCE_LEVELS:
            errors.append(f"{ctx}.p invalid importance")
        if "s" in idea:
            errors.append(f"{ctx}: provider must not emit SRC arrays")
        members = _strings(idea.get("m"))
        if not members:
            errors.append(f"{ctx}: empty membership")
        if len(members) > MAX_MEMBERS_PER_IDEA:
            errors.append(f"{ctx}: too many members")
        has_text = "v" in idea
        text = str(idea.get("v") or "") if has_text else ""
        if len(members) == 1:
            if has_text and text.strip():
                errors.append(f"FORBIDDEN_SINGLE_MEMBER_REWRITE:{handle or ctx}")
            elif has_text and not text.strip():
                errors.append(f"{ctx}: empty v is not allowed; omit v to REUSE")
            else:
                reuse_count += 1
        elif len(members) >= 2:
            if not has_text or not text.strip():
                errors.append(f"MISSING_SYNTHESIS_TEXT:{handle or ctx}")
            elif len(text) > idea_limit:
                errors.append(f"{ctx}.v exceeds {idea_limit} chars")
            else:
                synthesize_count += 1
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
    missing_ids = [item for item in required if item not in accounted]
    if missing_ids:
        for item in missing_ids:
            errors.append(f"SILENT_DROP:{item}")
    coverage = 0.0
    if required:
        coverage = 100.0 * (len(required) - len(missing_ids)) / len(required)

    derived = derive_dispositions(payload)
    return {
        "ok": not errors,
        "errors": errors,
        "idea_disposition_coverage": coverage,
        "silent_drops": missing_ids,
        "unknown_members": [item for item in errors if item.startswith("UNKNOWN_MEMBER:")],
        "duplicate_members": [
            item for item in errors if item.startswith("DUPLICATE_MEMBERSHIP:")
        ],
        "forbidden_rewrites": [
            item for item in errors if item.startswith("FORBIDDEN_SINGLE_MEMBER_REWRITE:")
        ],
        "missing_synthesis": [
            item for item in errors if item.startswith("MISSING_SYNTHESIS_TEXT:")
        ],
        "reuse_count": reuse_count,
        "synthesize_count": synthesize_count,
        "drop_count": len([item for item in dropped if item]),
        "accounted_idea_ids": sorted(accounted),
        "derived_dispositions": derived,
        "transport_version": NEXT_TRANSPORT_VERSION,
        "exact_set_equality": not missing_ids and set(accounted) == set(required),
    }


__all__ = [
    "derive_dispositions",
    "derived_src_union",
    "idea_mode",
    "validate_global_transport_v30",
]
