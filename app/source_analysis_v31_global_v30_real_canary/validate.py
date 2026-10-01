"""Interprétation production A.46 : decoder 3.0 + 286 IDEA + reconstruction. 0 réparation."""

from __future__ import annotations

from typing import Any, Mapping

from app.ai.structured import validate_payload
from app.source_analysis_v31_global_drop_domain.analysis import inspect_handles_including_drop
from app.source_analysis_v31_global_reuse_output.decoder import decode_global_transport_v30
from app.source_analysis_v31_global_reuse_output.reconstruct import reconstruct_source_map_v30
from app.source_analysis_v31_global_reuse_output.transport_v30 import (
    build_global_consolidation_schema_v30,
)
from app.source_analysis_v31_global_reuse_output.validate import validate_global_transport_v30
from app.source_analysis_v31_global_v20_grammar_canary.validate import (
    derived_disposition_audit,
    derived_src_audit,
    json_blob,
    membership_audit,
)
from app.source_analysis_v31_global_v201_contract_canary.type_boundary import (
    type_boundary_audit,
)
from app.source_analysis_v31_global_v30_grammar_canary.validate import reuse_synthesis_audit
from app.source_analysis_v31_global_v30_real_canary.constants import (
    EXPECTED_IDEA,
    TRANSPORT_VERSION,
)


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
        "source_map_published": False,
        "payload": payload,
        "relations_present": result.get("relations_present"),
        "repetitions_present": result.get("repetitions_present"),
    }


def interpret_production_response(
    parsed: dict[str, Any] | None,
    *,
    inventory: Mapping[str, Any],
    raw_text: str | None = None,
    signature: str = "",
    text_limits: Mapping[str, int] | None = None,
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
    if decoded.get("structured_parse") == "PASS" and structured != "PASS":
        structured = decoded.get("structured_parse")
    elif decoded.get("structured_parse") == "PASS":
        structured = "PASS"
    transport = working if isinstance(working, dict) else None
    idea_ids = list(inventory.get("idea_input_ids") or [])
    allowed = set(inventory.get("allowed_input_ids") or [])
    kinds = inventory.get("kind_by_input") or {}
    handles = inspect_handles_including_drop(
        transport,
        allowed_input_ids=allowed,
        kind_by_input=dict(kinds),
    )
    membership = membership_audit(transport, idea_input_ids=idea_ids)
    dispositions = derived_disposition_audit(transport, idea_input_ids=idea_ids)
    src_audit = derived_src_audit(
        transport, src_by_input=inventory.get("src_by_input") or {}
    )
    validator = validate_global_transport_v30(
        transport,
        idea_input_ids=idea_ids,
        allowed_input_ids=allowed,
        local_kind_by_input=kinds,
        text_limits=text_limits,
    )
    reconstructed = None
    replay_status = "FAIL"
    second_payload = None
    if isinstance(transport, dict):
        first = _wrap_reconstruction(
            reconstruct_source_map_v30(
                transport,
                inventory,
                inventory["transcript"],
                signature=signature or "a46-v30",
            )
        )
        second = _wrap_reconstruction(
            reconstruct_source_map_v30(
                transport,
                inventory,
                inventory["transcript"],
                signature=signature or "a46-v30",
            )
        )
        reconstructed = first
        second_payload = second
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
        inventory=inventory,
        reconstructed=reconstructed,
    )
    boundary = type_boundary_audit(transport, kind_by_input=kinds, relation_hint_id="")
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
    accounted = int(membership.get("local_idea_count") or 0) - int(
        len(membership.get("missing_members") or [])
    )
    coverage = float(membership.get("accountability_coverage") or 0)
    idea_account = (
        f"{EXPECTED_IDEA} / {EXPECTED_IDEA}"
        if coverage >= 100.0 and accounted == EXPECTED_IDEA
        else f"{accounted} / {EXPECTED_IDEA}"
    )
    errors = list(decoded.get("errors") or [])
    errors.extend(validator.get("errors") or [])
    errors.extend(src_audit.get("errors") or [])
    errors.extend(contract.get("errors") or [])
    inventory_counts = decoded.get("inventory") or {}
    return {
        "structured_parse": structured,
        "decoder": decoded.get("decoder"),
        "handle_validation": handles.get("handle_validation"),
        "handles": handles,
        "inventory": inventory_counts,
        "membership": membership,
        "idea_disposition_coverage": coverage,
        "unknown_members": len(membership.get("unknown_members") or []),
        "duplicate_members": len(membership.get("duplicate_members") or []),
        "missing_members": len(membership.get("missing_members") or []),
        "member_drop_overlap": len(membership.get("member_drop_overlap") or []),
        "set_equality": membership.get("set_equality"),
        "idea_accountability": idea_account,
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
        "provider_src_arrays": inventory_counts.get("provider_src_arrays"),
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
        "source_map": reconstructed.get("source_map") if reconstructed else None,
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
        "replay": {
            "status": replay_status,
            "second_provider_call": False,
            "canonical_json_equal": replay_status == "PASS",
            "second_ok": bool(second_payload and second_payload.get("ok")),
        },
        "type_boundary": boundary,
        "NON_IDEA_IN_MEMBERS": boundary.get("NON_IDEA_IN_MEMBERS"),
        "NON_IDEA_IN_DROP": boundary.get("NON_IDEA_IN_DROP"),
        "RELATION_HINT_IN_MEMBERS": boundary.get("RELATION_HINT_IN_MEMBERS"),
        "RELATION_HINT_IN_DROP": boundary.get("RELATION_HINT_IN_DROP"),
        "transport": transport,
        "errors": errors,
        "transport_version": TRANSPORT_VERSION,
        "repaired": False,
        "topics": inventory_counts.get("topics")
        if isinstance(inventory_counts, dict)
        else None,
        "examples": inventory_counts.get("examples")
        if isinstance(inventory_counts, dict)
        else None,
        "references": inventory_counts.get("references")
        if isinstance(inventory_counts, dict)
        else None,
        "uncertainties": inventory_counts.get("uncertainties")
        if isinstance(inventory_counts, dict)
        else None,
    }


def technical_pass(validation: Mapping[str, Any]) -> bool:
    return all(
        [
            validation.get("structured_parse") == "PASS",
            validation.get("decoder") == "PASS",
            validation.get("handle_validation") == "PASS",
            validation.get("set_equality") is True,
            int(validation.get("unknown_members") or 0) == 0,
            int(validation.get("duplicate_members") or 0) == 0,
            int(validation.get("missing_members") or 0) == 0,
            int(validation.get("member_drop_overlap") or 0) == 0,
            float(validation.get("idea_disposition_coverage") or 0) >= 100.0,
            int(validation.get("SINGLE_MEMBER_WITH_V") or 0) == 0,
            int(validation.get("MULTI_MEMBER_WITHOUT_V") or 0) == 0,
            int(validation.get("NON_IDEA_IN_MEMBERS") or 0) == 0,
            int(validation.get("NON_IDEA_IN_DROP") or 0) == 0,
            int(validation.get("other_count") or 0) == 0,
            int(validation.get("link_related_count") or 0) == 0,
            int(validation.get("exact_duplicate_drop_count") or 0) == 0,
            validation.get("drop_enum") == "PASS",
            validation.get("derived_src_union") == "PASS",
            validation.get("global_validator") == "PASS",
            validation.get("canonical_reconstruction") == "PASS",
            validation.get("canonical_validation") == "PASS",
            validation.get("deterministic_replay") == "PASS",
            float(validation.get("reuse_text_exact_equality") or 0) >= 100.0,
            float(validation.get("merge_text_equality") or 0) >= 100.0,
            validation.get("empty_relations_valid") is True,
        ]
    )


__all__ = ["interpret_production_response", "technical_pass"]
