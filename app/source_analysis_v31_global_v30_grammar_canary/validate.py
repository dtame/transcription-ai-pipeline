"""Interprétation canary A.44 : decoder 3.0 + REUSE/SYNTHESIZE + type-boundary."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.ai.structured import validate_payload
from app.source_analysis.models import scan_editorial_structure
from app.source_analysis_v31_global_drop_domain.analysis import inspect_handles_including_drop
from app.source_analysis_v31_global_drop_domain.gate import publication_eligibility
from app.source_analysis_v31_global_output_architecture.constants import (
    DROP_REASONS_V20,
    TEXT_LIMITS,
)
from app.source_analysis_v31_global_reuse_output.decoder import decode_global_transport_v30
from app.source_analysis_v31_global_reuse_output.reconstruct import (
    expand_reused_idea_text,
    local_idea_text,
    reconstruct_source_map_v30,
)
from app.source_analysis_v31_global_reuse_output.transport_v30 import (
    build_global_consolidation_schema_v30,
)
from app.source_analysis_v31_global_reuse_output.validate import (
    idea_mode,
    validate_global_transport_v30,
)
from app.source_analysis_v31_global_v20_grammar_canary.validate import (
    derived_disposition_audit,
    derived_src_audit,
    json_blob,
    membership_audit,
)
from app.source_analysis_v31_global_v201_contract_canary.type_boundary import (
    type_boundary_audit,
)
from app.source_analysis_v31_global_v30_grammar_canary.constants import (
    RELATION_HINT_ID,
    SYNTHESIZED_IDEA_MAX_CHARS,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v30_grammar_canary.fixture import (
    SyntheticConsolidationFixtureV30,
)


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if isinstance(item, str) and item]


def _has_v(idea: Mapping[str, Any]) -> bool:
    return "v" in idea and str(idea.get("v") or "").strip() != ""


def reuse_synthesis_audit(
    transport: Mapping[str, Any] | None,
    *,
    inventory: Mapping[str, Any],
    reconstructed: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    single_with_v = 0
    multi_without_v = 0
    reuse_exact = 0
    reuse_total = 0
    merge_exact = 0
    merge_total = 0
    merge_v_lengths: list[int] = []
    if not isinstance(transport, Mapping):
        return {
            "status": "FAIL",
            "ideas": [],
            "single_member_global_ideas": 0,
            "multi_member_global_ideas": 0,
            "SINGLE_MEMBER_WITH_V": 0,
            "MULTI_MEMBER_WITHOUT_V": 0,
            "reuse_text_exact_equality": 0.0,
            "merge_text_equality": 0.0,
            "merge_v_max_length": 0,
            "errors": ["transport missing"],
        }
    expanded = expand_reused_idea_text(transport, inventory)
    reconstructed_ideas = (
        ((reconstructed or {}).get("payload") or {}).get("ideas") or []
        if reconstructed
        else []
    )
    by_src: dict[tuple[str, ...], dict[str, Any]] = {}
    for idea in reconstructed_ideas:
        if isinstance(idea, Mapping):
            by_src[tuple(_strings(idea.get("source_refs")))] = dict(idea)
    local_src = inventory.get("src_by_input") or {}
    errors: list[str] = []
    for index, idea in enumerate(_as_list(transport.get("i"))):
        if not isinstance(idea, Mapping):
            continue
        members = _strings(idea.get("m"))
        present = _has_v(idea)
        mode = idea_mode(idea)
        v_text = str(idea.get("v") or "") if present else ""
        v_len = len(v_text) if present else 0
        if present:
            merge_v_lengths.append(v_len)
        row = {
            "handle": idea.get("h"),
            "member_count": len(members),
            "members": members,
            "v_present": present,
            "v_length": v_len if present else None,
            "derived_mode": mode,
        }
        expanded_row = _as_list(expanded.get("i"))[index] if index < len(
            _as_list(expanded.get("i"))
        ) else {}
        if len(members) == 1:
            reuse_total += 1
            expected = local_idea_text(inventory, members[0])
            if present:
                single_with_v += 1
                errors.append(f"FORBIDDEN_SINGLE_MEMBER_REWRITE:{idea.get('h')}")
            elif str((expanded_row or {}).get("v") or "") == expected:
                reuse_exact += 1
            else:
                errors.append(f"REUSE_TEXT_MISMATCH:{idea.get('h')}")
            src_key = tuple(local_src.get(members[0]) or [])
            canonical = by_src.get(src_key) or {}
            summary = str(canonical.get("summary") or "")
            row["canonical_text"] = summary
            row["expected_local_text"] = expected
            row["canonical_equals_local"] = summary == expected if summary else (
                str((expanded_row or {}).get("v") or "") == expected
            )
            if summary and summary != expected:
                errors.append(f"CANONICAL_REUSE_MISMATCH:{idea.get('h')}")
                row["canonical_equals_local"] = False
            elif row["canonical_equals_local"] and not present:
                pass
        elif len(members) >= 2:
            merge_total += 1
            if not present:
                multi_without_v += 1
                errors.append(f"MISSING_SYNTHESIS_TEXT:{idea.get('h')}")
            elif v_len > SYNTHESIZED_IDEA_MAX_CHARS:
                errors.append(f"MERGE_V_TOO_LONG:{idea.get('h')}")
            else:
                merge_exact += 1
            from app.source_analysis_v31_global_reuse_output.validate import (
                derived_src_union,
            )

            src_key = tuple(derived_src_union(members, local_src))
            canonical = by_src.get(src_key) or {}
            summary = str(canonical.get("summary") or "")
            row["canonical_text"] = summary
            row["provider_v"] = v_text
            row["canonical_equals_provider_v"] = (
                summary == v_text if summary and present else (present and v_text == v_text)
            )
            if summary and present and summary != v_text:
                errors.append(f"CANONICAL_MERGE_MISMATCH:{idea.get('h')}")
                row["canonical_equals_provider_v"] = False
                merge_exact = max(0, merge_exact - 1)
        rows.append(row)
    reuse_pct = 100.0 * reuse_exact / reuse_total if reuse_total else 100.0
    merge_pct = 100.0 * merge_exact / merge_total if merge_total else 100.0
    ok = (
        single_with_v == 0
        and multi_without_v == 0
        and reuse_pct == 100.0
        and merge_pct == 100.0
        and not errors
    )
    return {
        "status": "PASS" if ok else "FAIL",
        "ideas": rows,
        "single_member_global_ideas": reuse_total,
        "multi_member_global_ideas": merge_total,
        "SINGLE_MEMBER_WITH_V": single_with_v,
        "MULTI_MEMBER_WITHOUT_V": multi_without_v,
        "reuse_text_exact_equality": reuse_pct,
        "merge_text_equality": merge_pct,
        "merge_v_max_length": max(merge_v_lengths) if merge_v_lengths else 0,
        "errors": errors,
    }


def review_semantic_v30(
    transport: Mapping[str, Any] | None,
    fixture: SyntheticConsolidationFixtureV30,
    *,
    boundary: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(transport, Mapping):
        return {"status": "FAIL", "notes": ["transport missing"]}
    ideas = [item for item in _as_list(transport.get("i")) if isinstance(item, Mapping)]
    drops = [item for item in _as_list(transport.get("drop")) if isinstance(item, Mapping)]
    uncertainties = [item for item in _as_list(transport.get("u")) if isinstance(item, Mapping)]
    examples = [item for item in _as_list(transport.get("x")) if isinstance(item, Mapping)]
    gm = transport.get("gm") if isinstance(transport.get("gm"), Mapping) else {}
    notes: list[str] = []
    expanded = expand_reused_idea_text(transport, fixture.inventory())
    expanded_ideas = [
        item for item in _as_list(expanded.get("i")) if isinstance(item, Mapping)
    ]

    by_member: dict[str, str] = {}
    for idea in ideas:
        handle = str(idea.get("h") or "")
        for member in _strings(idea.get("m")):
            by_member[member] = handle
    drop_ids = {str(row.get("i") or "") for row in drops}

    single_keep = by_member.get("SYN:I011") and "SYN:I011" not in drop_ids
    merge_same = (
        by_member.get("SYN:I012")
        and by_member.get("SYN:I012") == by_member.get("SYN:I013")
        and "SYN:I012" not in drop_ids
        and "SYN:I013" not in drop_ids
    )
    watering = by_member.get("SYN:I011")
    compost = by_member.get("SYN:I012")
    basil = by_member.get("SYN:I014")
    tools = by_member.get("SYN:I015")
    rain = by_member.get("SYN:I017")
    groups = [item for item in (watering, compost, basil, tools, rain) if item]
    distinct_ok = len(set(groups)) == 5
    if not distinct_ok:
        notes.append("distinct ideas appear merged")
    drop_ok = "SYN:I016" in drop_ids and "SYN:I016" not in by_member
    drop_reasons = [str(row.get("w") or "") for row in drops]
    drop_reason_ok = all(reason in DROP_REASONS_V20 for reason in drop_reasons)
    if not drop_ok:
        notes.append("drop of SYN:I016 missing or overlapped")
    if not drop_reason_ok:
        notes.append(f"invalid drop reasons {drop_reasons}")

    idea_texts = [str(item.get("v") or "").lower() for item in expanded_ideas]
    lost = []
    for input_id, token in (
        ("SYN:I011", "dawn"),
        ("SYN:I012", "compost"),
        ("SYN:I014", "basil"),
        ("SYN:I015", "tools"),
        ("SYN:I017", "barrel"),
    ):
        if input_id in by_member and not any(token in value for value in idea_texts):
            lost.append(input_id)
    if lost:
        notes.append(f"possible lost ideas {lost}")

    broadened = False
    records = fixture.records
    for idea in expanded_ideas:
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

    merge_faithful = True
    for idea in ideas:
        members = _strings(idea.get("m"))
        if len(members) < 2:
            continue
        v_text = str(idea.get("v") or "").lower()
        if not v_text.strip():
            merge_faithful = False
            notes.append("merge missing v")
            continue
        if "compost" not in v_text:
            merge_faithful = False
            notes.append("merge text does not represent compost members")
        if len(v_text) > SYNTHESIZED_IDEA_MAX_CHARS:
            merge_faithful = False
            notes.append("merge v exceeds 180")

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
        if _has_v(idea) and len(str(idea.get("v") or "")) > TEXT_LIMITS["idea"]:
            length_ok = False
    if not length_ok:
        notes.append("text length bound exceeded")
    blob = json_blob(transport)
    other_present = "OTHER" in blob
    link_present = "LINK_RELATED" in blob
    if other_present:
        notes.append("OTHER present")
    if link_present:
        notes.append("LINK_RELATED present")

    relation_ignored = (
        boundary.get("RELATION_HINT_IN_MEMBERS") == "NO"
        and boundary.get("RELATION_HINT_IN_DROP") == "NO"
    )
    if not relation_ignored:
        notes.append("relation hint entered IDEA membership or drop[]")
    non_idea_ok = (
        int(boundary.get("NON_IDEA_IN_MEMBERS") or 0) == 0
        and int(boundary.get("NON_IDEA_IN_DROP") or 0) == 0
        and int(boundary.get("TOPIC_IDEA_DOMAIN_VIOLATIONS") or 0) == 0
        and int(boundary.get("EXAMPLE_IDEA_DOMAIN_VIOLATIONS") or 0) == 0
        and int(boundary.get("REFERENCE_IDEA_DOMAIN_VIOLATIONS") or 0) == 0
        and int(boundary.get("UNCERTAINTY_IDEA_DOMAIN_VIOLATIONS") or 0) == 0
    )
    if not non_idea_ok:
        notes.append("non-IDEA object entered IDEA membership or drop[]")

    editorial = not scan_editorial_structure(transport).get("ok")
    if editorial:
        notes.append("editorial structure suspected")

    reasonable = (
        bool(single_keep)
        and bool(merge_same)
        and distinct_ok
        and drop_ok
        and drop_reason_ok
        and not lost
        and not broadened
        and merge_faithful
        and not frost_promoted
        and not example_promoted
        and bool(uncertainties)
        and metadata_ok
        and length_ok
        and not other_present
        and not link_present
        and relation_ignored
        and non_idea_ok
        and not editorial
    )
    return {
        "status": "PASS" if reasonable else "FAIL",
        "single_member_preserved": bool(single_keep),
        "equivalent_ideas_merged": bool(merge_same),
        "distinct_ideas_not_merged": distinct_ok,
        "drop_legitimate": drop_ok and drop_reason_ok,
        "no_substantive_omission": not lost,
        "merge_text_faithful": merge_faithful,
        "global_proposition_does_not_broaden": not broadened,
        "uncertainty_preserved": bool(uncertainties) and not frost_promoted,
        "relation_hint_ignored_by_idea_accountability": relation_ignored,
        "non_idea_kinds_absent_from_idea_domain": non_idea_ok,
        "metadata_reasonable": metadata_ok,
        "notes": notes,
        "not_production_quality_proof": True,
    }


def _wrap_reconstruction(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not result:
        return result
    relations_present = bool(result.get("relations_present"))
    result["empty_relations_valid"] = bool(result.get("ok")) and not relations_present
    return result


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
        "reuse_text_exact": result.get("reuse_text_exact"),
        "reused_ideas": result.get("reused_ideas"),
        "validate_source_map": result.get("validate_source_map"),
        "ensure_valid_source_map": result.get("ensure_valid_source_map"),
        "errors": result.get("errors"),
        "phase": result.get("phase"),
        "source_map_published": False,
        "ideas": ideas,
        "relations_present": result.get("relations_present"),
        "repetitions_present": result.get("repetitions_present"),
    }


def interpret_canary_response_v30(
    parsed: dict[str, Any] | None,
    *,
    fixture: SyntheticConsolidationFixtureV30,
    raw_text: str | None = None,
    signature: str = "",
) -> dict[str, Any]:
    decoded = decode_global_transport_v30(parsed, raw_text=raw_text)
    working = (
        decoded.get("transport") if isinstance(decoded.get("transport"), dict) else parsed
    )
    schema = build_global_consolidation_schema_v30()
    structured = "FAIL"
    if isinstance(working, dict):
        try:
            validate_payload(working, schema)
            structured = "PASS"
        except Exception as exc:  # noqa: BLE001 — forensic, no repair
            structured = "FAIL"
            decoded.setdefault("errors", []).append(str(exc))
    transport = working if isinstance(working, dict) else None
    handles = inspect_handles_including_drop(
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
    validator = validate_global_transport_v30(
        transport,
        idea_input_ids=list(fixture.idea_input_ids),
        allowed_input_ids=set(fixture.allowed_input_ids),
        local_kind_by_input=fixture.kind_by_input,
    )
    reconstructed = None
    replay_status = "FAIL"
    if isinstance(transport, dict):
        first = _wrap_reconstruction(
            reconstruct_source_map_v30(
                transport,
                fixture.inventory(),
                fixture.transcript,
                signature=signature or "a44-v30",
            )
        )
        second = _wrap_reconstruction(
            reconstruct_source_map_v30(
                transport,
                fixture.inventory(),
                fixture.transcript,
                signature=signature or "a44-v30",
            )
        )
        reconstructed = first
        replay_status = (
            "PASS"
            if first
            and first.get("canonical_json")
            and first.get("canonical_json") == (second or {}).get("canonical_json")
            and first.get("ok")
            else "FAIL"
        )
    contract = reuse_synthesis_audit(
        transport,
        inventory=fixture.inventory(),
        reconstructed=reconstructed,
    )
    boundary = type_boundary_audit(
        transport,
        kind_by_input=fixture.kind_by_input,
        relation_hint_id=RELATION_HINT_ID,
    )
    pub = publication_eligibility(
        global_validator_ok=validator.get("ok") is True,
        canonical_reconstruction_ok=bool(reconstructed and reconstructed.get("ok")),
    )
    semantic = review_semantic_v30(transport, fixture, boundary=boundary)
    reconstruction_ok = bool(reconstructed and reconstructed.get("ok"))
    invalid_transport_gate = (
        "PASS"
        if (
            pub.get("publication_eligible") is False
            and (
                validator.get("ok") is not True
                or not reconstruction_ok
                or pub.get("source_map_authorized") is False
            )
        )
        else "FAIL"
    )
    if validator.get("ok") is True:
        invalid_transport_gate = (
            "PASS"
            if pub.get("blocked_because_invalid_transport") is False
            and pub.get("publication_eligible") is False
            else "FAIL"
        )
    other = dispositions.get("other_count") or 0
    link_related = dispositions.get("link_related_count") or 0
    exact_dup = dispositions.get("exact_duplicate_drop_count") or 0
    if isinstance(transport, dict):
        blob = json_blob(transport)
        if "OTHER" in blob:
            other = max(int(other), 1)
        if "LINK_RELATED" in blob:
            link_related = max(int(link_related), 1)
    ledger_absent = True
    if isinstance(transport, dict) and ("d" in transport):
        ledger_absent = False
    errors = list(decoded.get("errors") or [])
    errors.extend(validator.get("errors") or [])
    errors.extend(src_audit.get("errors") or [])
    errors.extend(contract.get("errors") or [])
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
        "reuse_synthesis": contract,
        "SINGLE_MEMBER_WITH_V": contract.get("SINGLE_MEMBER_WITH_V"),
        "MULTI_MEMBER_WITHOUT_V": contract.get("MULTI_MEMBER_WITHOUT_V"),
        "single_member_global_ideas": contract.get("single_member_global_ideas"),
        "multi_member_global_ideas": contract.get("multi_member_global_ideas"),
        "reuse_text_exact_equality": contract.get("reuse_text_exact_equality"),
        "merge_text_equality": contract.get("merge_text_equality"),
        "merge_v_max_length": contract.get("merge_v_max_length"),
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
        "type_boundary": boundary,
        "NON_IDEA_IN_MEMBERS": boundary.get("NON_IDEA_IN_MEMBERS"),
        "NON_IDEA_IN_DROP": boundary.get("NON_IDEA_IN_DROP"),
        "RELATION_HINT_IN_MEMBERS": boundary.get("RELATION_HINT_IN_MEMBERS"),
        "RELATION_HINT_IN_DROP": boundary.get("RELATION_HINT_IN_DROP"),
        "TOPIC_IDEA_DOMAIN_VIOLATIONS": boundary.get("TOPIC_IDEA_DOMAIN_VIOLATIONS"),
        "EXAMPLE_IDEA_DOMAIN_VIOLATIONS": boundary.get("EXAMPLE_IDEA_DOMAIN_VIOLATIONS"),
        "REFERENCE_IDEA_DOMAIN_VIOLATIONS": boundary.get(
            "REFERENCE_IDEA_DOMAIN_VIOLATIONS"
        ),
        "UNCERTAINTY_IDEA_DOMAIN_VIOLATIONS": boundary.get(
            "UNCERTAINTY_IDEA_DOMAIN_VIOLATIONS"
        ),
        "publication": pub,
        "invalid_transport_publication_gate": invalid_transport_gate,
        "transport": transport,
        "errors": errors,
        "transport_version": TRANSPORT_VERSION,
        "prompt_version": "global-consolidation-3.0",
        "repaired": False,
    }


__all__ = [
    "interpret_canary_response_v30",
    "review_semantic_v30",
    "reuse_synthesis_audit",
]
