"""Interprétation canary A.40 : decoder 2.0 + membership + dispositions dérivées."""

from __future__ import annotations

from typing import Any, Mapping

from app.ai.structured import validate_payload
from app.source_analysis_v31_global_output_architecture.constants import (
    DROP_REASONS_V20,
    TEXT_LIMITS,
)
from app.source_analysis_v31_global_output_architecture.membership import (
    derive_dispositions,
    derived_src_union,
    validate_global_transport_v20,
)
from app.source_analysis_v31_global_output_architecture.transport_v20 import (
    build_global_consolidation_schema_v20,
)
from app.source_analysis_v31_global_v20_grammar_canary.constants import (
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v20_grammar_canary.decoder import (
    decode_global_transport_v20,
)
from app.source_analysis_v31_global_v20_grammar_canary.fixture import (
    SyntheticConsolidationFixtureV20,
)
from app.source_analysis_v31_global_v20_grammar_canary.handles import (
    inspect_global_handles_v20,
)
from app.source_analysis_v31_global_v20_grammar_canary.reconstruct import (
    reconstruct_source_map_v20,
)


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if isinstance(item, str) and item]


def membership_audit(
    transport: Mapping[str, Any] | None,
    *,
    idea_input_ids: list[str],
) -> dict[str, Any]:
    local_ids = [item for item in idea_input_ids if item]
    members: list[str] = []
    dropped: list[str] = []
    if isinstance(transport, Mapping):
        for idea in _as_list(transport.get("i")):
            if isinstance(idea, Mapping):
                members.extend(_strings(idea.get("m")))
        for row in _as_list(transport.get("drop")):
            if isinstance(row, Mapping):
                dropped.append(str(row.get("i") or ""))
    member_set = [item for item in members if item]
    drop_set = [item for item in dropped if item]
    distinct_members = sorted(set(member_set))
    unknown_members = [item for item in distinct_members if item not in set(local_ids)]
    unknown_drops = [item for item in drop_set if item not in set(local_ids)]
    seen: set[str] = set()
    duplicate_members = []
    for item in member_set:
        if item in seen:
            duplicate_members.append(item)
        seen.add(item)
    overlap = sorted(set(member_set) & set(drop_set))
    accounted = set(member_set) | set(drop_set)
    missing = [item for item in local_ids if item not in accounted]
    set_equal = set(local_ids) == accounted and not overlap
    coverage = 0.0
    if local_ids:
        coverage = 100.0 * (len(local_ids) - len(missing)) / len(local_ids)
    return {
        "local_idea_count": len(local_ids),
        "member_occurrences": len(member_set),
        "distinct_member_ids": len(distinct_members),
        "drop_count": len(drop_set),
        "unknown_members": unknown_members,
        "unknown_drops": unknown_drops,
        "duplicate_members": duplicate_members,
        "missing_members": missing,
        "member_drop_overlap": overlap,
        "set_equality": set_equal,
        "accountability_coverage": coverage,
        "provider_disposition_ledger": "ABSENT",
    }


def derived_disposition_audit(
    transport: Mapping[str, Any] | None,
    *,
    idea_input_ids: list[str],
) -> dict[str, Any]:
    derived = derive_dispositions(transport or {})
    keep = [key for key, row in derived.items() if row.get("o") == "KEEP"]
    merge = [key for key, row in derived.items() if row.get("o") == "MERGE_EQUIVALENT"]
    drop = [key for key, row in derived.items() if row.get("o") == "DROP"]
    required = [item for item in idea_input_ids if item]
    coverage = 0.0
    if required:
        coverage = 100.0 * len([item for item in required if item in derived]) / len(required)
    other = sum(1 for row in derived.values() if row.get("o") == "OTHER")
    link_related = sum(1 for row in derived.values() if row.get("o") == "LINK_RELATED")
    exact_duplicate_drop = sum(
        1
        for row in derived.values()
        if row.get("o") == "DROP" and row.get("w") == "exact_duplicate"
    )
    unknown_reasons = [
        row.get("w")
        for row in derived.values()
        if row.get("o") == "DROP" and row.get("w") not in DROP_REASONS_V20
    ]
    return {
        "derived": derived,
        "keep_count": len(keep),
        "merge_equivalent_count": len(merge),
        "drop_count": len(drop),
        "keep_ids": keep,
        "merge_ids": merge,
        "drop_ids": drop,
        "coverage": coverage,
        "other_count": other,
        "link_related_count": link_related,
        "exact_duplicate_drop_count": exact_duplicate_drop,
        "unknown_drop_reasons": unknown_reasons,
        "drop_enum": "PASS" if not unknown_reasons else "FAIL",
    }


def derived_src_audit(
    transport: Mapping[str, Any] | None,
    *,
    src_by_input: Mapping[str, list[str]],
) -> dict[str, Any]:
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    if not isinstance(transport, Mapping):
        return {"ok": False, "status": "FAIL", "errors": ["transport missing"], "rows": []}
    for idea in _as_list(transport.get("i")):
        if not isinstance(idea, Mapping):
            continue
        members = _strings(idea.get("m"))
        derived = derived_src_union(members, src_by_input)
        expected: list[str] = []
        seen: set[str] = set()
        for member in members:
            for ref in src_by_input.get(member) or []:
                if ref not in seen:
                    seen.add(ref)
                    expected.append(ref)
        if derived != expected:
            errors.append(str(idea.get("h") or ""))
        if len(derived) != len(set(derived)):
            errors.append(f"duplicate SRC {idea.get('h')}")
        rows.append(
            {
                "handle": idea.get("h"),
                "members": members,
                "derived": derived,
                "expected": expected,
                "ok": derived == expected,
            }
        )
    return {
        "ok": not errors,
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "rows": rows,
    }


def review_semantic_v20(
    transport: Mapping[str, Any] | None,
    fixture: SyntheticConsolidationFixtureV20,
) -> dict[str, Any]:
    if not isinstance(transport, Mapping):
        return {"status": "FAIL", "notes": ["transport missing"]}
    ideas = [item for item in _as_list(transport.get("i")) if isinstance(item, Mapping)]
    drops = [item for item in _as_list(transport.get("drop")) if isinstance(item, Mapping)]
    uncertainties = [item for item in _as_list(transport.get("u")) if isinstance(item, Mapping)]
    examples = [item for item in _as_list(transport.get("x")) if isinstance(item, Mapping)]
    gm = transport.get("gm") if isinstance(transport.get("gm"), Mapping) else {}
    notes: list[str] = []

    by_member: dict[str, str] = {}
    for idea in ideas:
        handle = str(idea.get("h") or "")
        for member in _strings(idea.get("m")):
            by_member[member] = handle
    drop_ids = {str(row.get("i") or "") for row in drops}

    single_keep = by_member.get("SYN:I001") and "SYN:I001" not in drop_ids
    merge_same = (
        by_member.get("SYN:I002")
        and by_member.get("SYN:I002") == by_member.get("SYN:I003")
        and "SYN:I002" not in drop_ids
        and "SYN:I003" not in drop_ids
    )
    distinct_ok = True
    watering = by_member.get("SYN:I001")
    compost = by_member.get("SYN:I002")
    basil = by_member.get("SYN:I004")
    tools = by_member.get("SYN:I005")
    rain = by_member.get("SYN:I007")
    groups = [item for item in (watering, compost, basil, tools, rain) if item]
    if len(set(groups)) != 5:
        distinct_ok = False
        notes.append("distinct ideas appear merged")
    drop_ok = "SYN:I006" in drop_ids and "SYN:I006" not in by_member
    drop_reasons = [str(row.get("w") or "") for row in drops]
    drop_reason_ok = all(reason in DROP_REASONS_V20 for reason in drop_reasons)
    if not drop_ok:
        notes.append("drop of SYN:I006 missing or overlapped")
    if not drop_reason_ok:
        notes.append(f"invalid drop reasons {drop_reasons}")

    idea_texts = [str(item.get("v") or "").lower() for item in ideas]
    lost = []
    for input_id, text in (
        ("SYN:I001", "dawn"),
        ("SYN:I002", "compost"),
        ("SYN:I004", "basil"),
        ("SYN:I005", "tools"),
        ("SYN:I007", "barrel"),
    ):
        if input_id in by_member and not any(text in value for value in idea_texts):
            lost.append(input_id)
    if lost:
        notes.append(f"possible lost ideas {lost}")

    broadened = False
    records = fixture.records
    for idea in ideas:
        members = _strings(idea.get("m"))
        member_blob = " ".join(
            str((records.get(member) or {}).get("v") or "").lower() for member in members
        )
        value = str(idea.get("v") or "").lower()
        tokens = [token for token in value.split() if len(token) > 6]
        extra = [token for token in tokens if token not in member_blob]
        if extra and len(extra) > 2:
            broadened = True
            notes.append(f"{idea.get('h')} may broaden {extra[:4]}")

    frost_promoted = any("frost" in text for text in idea_texts)
    example_promoted = any(
        "chewed" in text or "twice each week" in text for text in idea_texts
    )
    if frost_promoted:
        notes.append("uncertainty promoted to IDEA")
    if example_promoted:
        notes.append("example text appears as IDEA")
    if not uncertainties:
        notes.append("no uncertainty object")
    if not examples:
        notes.append("no example object")
    metadata_ok = all(
        [
            bool(str(gm.get("th") or "").strip()),
            bool(str(gm.get("in") or "").strip()),
            bool(str(gm.get("au") or "").strip()),
            bool(str(gm.get("vo") or "").strip()),
        ]
    )
    if not metadata_ok:
        notes.append("global metadata incomplete")
    length_ok = True
    if len(str(gm.get("th") or "")) > TEXT_LIMITS["theme"]:
        length_ok = False
    for idea in ideas:
        if len(str(idea.get("v") or "")) > TEXT_LIMITS["idea"]:
            length_ok = False
    if not length_ok:
        notes.append("text length bound exceeded")
    other_present = "OTHER" in json_blob(transport)
    link_present = "LINK_RELATED" in json_blob(transport)
    if other_present:
        notes.append("OTHER present")
    if link_present:
        notes.append("LINK_RELATED present")

    reasonable = (
        bool(single_keep)
        and bool(merge_same)
        and distinct_ok
        and drop_ok
        and drop_reason_ok
        and not lost
        and not broadened
        and not frost_promoted
        and not example_promoted
        and bool(uncertainties)
        and metadata_ok
        and length_ok
        and not other_present
        and not link_present
    )
    return {
        "status": "PASS" if reasonable else "FAIL",
        "single_member_preserved": bool(single_keep),
        "equivalent_ideas_merged": bool(merge_same),
        "distinct_ideas_not_merged": distinct_ok,
        "drop_legitimate": drop_ok and drop_reason_ok,
        "no_substantive_omission": not lost,
        "global_proposition_does_not_broaden": not broadened,
        "uncertainty_preserved": bool(uncertainties) and not frost_promoted,
        "metadata_reasonable": metadata_ok,
        "notes": notes,
        "not_production_quality_proof": True,
    }


def json_blob(payload: Mapping[str, Any]) -> str:
    import json

    return json.dumps(dict(payload), ensure_ascii=False)


def interpret_canary_response_v20(
    parsed: dict[str, Any] | None,
    *,
    fixture: SyntheticConsolidationFixtureV20,
    raw_text: str | None = None,
    signature: str = "",
) -> dict[str, Any]:
    decoded = decode_global_transport_v20(parsed, raw_text=raw_text)
    working = (
        decoded.get("transport") if isinstance(decoded.get("transport"), dict) else parsed
    )
    schema = build_global_consolidation_schema_v20()
    structured = "FAIL"
    if isinstance(working, dict):
        try:
            validate_payload(working, schema)
            structured = "PASS"
        except Exception as exc:  # noqa: BLE001 — forensic, no repair
            structured = "FAIL"
            decoded.setdefault("errors", []).append(str(exc))
    transport = working if isinstance(working, dict) else None
    handles = inspect_global_handles_v20(
        transport,
        allowed_input_ids=set(fixture.allowed_input_ids),
        kind_by_input=fixture.kind_by_input,
    )
    membership = membership_audit(
        transport, idea_input_ids=list(fixture.idea_input_ids)
    )
    dispositions = derived_disposition_audit(
        transport, idea_input_ids=list(fixture.idea_input_ids)
    )
    src_audit = derived_src_audit(transport, src_by_input=fixture.src_by_input)
    validator = validate_global_transport_v20(
        transport,
        idea_input_ids=list(fixture.idea_input_ids),
        allowed_input_ids=set(fixture.allowed_input_ids),
        local_kind_by_input=fixture.kind_by_input,
    )
    reconstructed = None
    replay_status = "FAIL"
    if isinstance(transport, dict):
        first = reconstruct_source_map_v20(
            transport,
            fixture.inventory(),
            fixture.transcript,
            signature=signature or "a40-v20",
        )
        second = reconstruct_source_map_v20(
            transport,
            fixture.inventory(),
            fixture.transcript,
            signature=signature or "a40-v20",
        )
        reconstructed = first
        replay_status = (
            "PASS"
            if first.get("canonical_json")
            and first.get("canonical_json") == second.get("canonical_json")
            and first.get("ok")
            else "FAIL"
        )
    semantic = review_semantic_v20(transport, fixture)
    other = dispositions.get("other_count") or 0
    link_related = dispositions.get("link_related_count") or 0
    exact_dup = dispositions.get("exact_duplicate_drop_count") or 0
    if isinstance(transport, dict):
        blob = json_blob(transport)
        if '"OTHER"' in blob or "OTHER" in str(transport.get("drop")):
            other = max(int(other), 1 if "OTHER" in blob else 0)
        if "LINK_RELATED" in blob:
            link_related = max(int(link_related), 1)
    ledger_absent = True
    if isinstance(transport, dict) and ("d" in transport):
        ledger_absent = False
    errors = list(decoded.get("errors") or [])
    errors.extend(validator.get("errors") or [])
    errors.extend(src_audit.get("errors") or [])
    return {
        "structured_parse": structured,
        "decoder": decoded.get("decoder"),
        "handle_validation": handles.get("handle_validation"),
        "handles": handles,
        "inventory": decoded.get("inventory"),
        "membership": membership,
        "idea_disposition_coverage": membership.get("accountability_coverage"),
        "silent_drops": len(membership.get("missing_members") or []),
        "unknown_members": len(membership.get("unknown_members") or []),
        "duplicate_members": len(membership.get("duplicate_members") or []),
        "missing_members": len(membership.get("missing_members") or []),
        "member_drop_overlap": len(membership.get("member_drop_overlap") or []),
        "set_equality": membership.get("set_equality"),
        "derived_dispositions": dispositions,
        "keep_count": dispositions.get("keep_count"),
        "merge_equivalent_count": dispositions.get("merge_equivalent_count"),
        "drop_count": dispositions.get("drop_count"),
        "other_count": other,
        "link_related_count": link_related,
        "exact_duplicate_drop_count": exact_dup,
        "drop_enum": dispositions.get("drop_enum"),
        "derived_src": src_audit,
        "derived_src_union": src_audit.get("status"),
        "provider_src_arrays": (decoded.get("inventory") or {}).get("provider_src_arrays"),
        "provider_disposition_ledger": "ABSENT" if ledger_absent else "PRESENT",
        "validator": validator,
        "global_validator": "PASS" if validator.get("ok") else "FAIL",
        "reconstruction": _public_reconstruction(reconstructed),
        "canonical_reconstruction": (
            "PASS" if reconstructed and reconstructed.get("ok") else "FAIL"
        ),
        "canonical_validation": (
            reconstructed.get("ensure_valid_source_map") if reconstructed else "FAIL"
        ),
        "empty_relations_valid": (
            reconstructed.get("empty_relations_valid") if reconstructed else False
        ),
        "deterministic_replay": replay_status,
        "replay": {"status": replay_status, "second_provider_call": False},
        "semantic_review": semantic,
        "transport": transport,
        "errors": errors,
        "transport_version": TRANSPORT_VERSION,
        "repaired": False,
    }


def _public_reconstruction(result: dict[str, Any] | None) -> dict[str, Any]:
    if not result:
        return {}
    payload = result.get("payload") or {}
    ideas = payload.get("ideas") if isinstance(payload, dict) else []
    return {
        "ok": result.get("ok"),
        "canonical_json": result.get("canonical_json"),
        "assigned_provider_to_canonical": result.get("assigned_provider_to_canonical"),
        "all_idea_kinds_empty": result.get("all_idea_kinds_empty"),
        "empty_relations_valid": result.get("empty_relations_valid"),
        "validate_source_map": result.get("validate_source_map"),
        "ensure_valid_source_map": result.get("ensure_valid_source_map"),
        "errors": result.get("errors"),
        "phase": result.get("phase"),
        "source_map_published": False,
        "ideas": ideas,
        "relations_present": result.get("relations_present"),
        "repetitions_present": result.get("repetitions_present"),
    }


__all__ = [
    "derived_disposition_audit",
    "derived_src_audit",
    "interpret_canary_response_v20",
    "membership_audit",
    "review_semantic_v20",
]
