"""Audit de redondance et cohérence prompt/schéma. Ne mute pas 3.0."""

from __future__ import annotations

import re
from typing import Any, Mapping

from app.source_analysis_v31_global_reuse_output.prompt_v30 import prompt_v30_bundle
from app.source_analysis_v31_global_reuse_output.transport_v30 import (
    IDEA_OPTIONAL_FIELDS,
    IDEA_REQUIRED_FIELDS,
    ROOT_FIELDS,
    build_global_consolidation_schema_v30,
)
from app.source_analysis_v31_global_v30_exact_preflight.constants import (
    DROP_REASONS_V20,
    SYNTHESIZED_IDEA_MAX_CHARS,
)


_OBSOLETE = (
    "LINK_RELATED",
    "exact_duplicate",
    "disposition ledger",
    "single-member rewrite",
    "rewrite a single-member",
    '"r":',
    "emit global relations",
    "REPETITION nodes",
)

_REQUIRED_PROMPT = (
    "If a global idea has exactly one member, omit field v",
    "If a global idea has two or more members, emit v",
    "Do not emit global relations",
    "Do not emit a disposition ledger",
    "Do not emit SRC identifiers",
    "transport_artifact",
    "non_substantive_fragment",
    "Do not emit REPETITION nodes",
)


def audit_request_redundancy(
    *,
    compact: Mapping[str, Any],
    user_text: str,
    system_text: str,
) -> dict[str, Any]:
    records = []
    ids: list[str] = []
    for window in compact.get("windows") or []:
        for item in window.get("records") or []:
            records.append(item)
            ids.append(str(item.get("id") or ""))
    duplicate_ids = sorted({item for item in ids if item and ids.count(item) > 1})
    combined = system_text + "\n" + user_text
    obsolete_output_instructions: list[str] = []
    if "rewrite a single-member idea for style" in combined and "Do not rewrite a single-member idea" not in combined:
        obsolete_output_instructions.append("single-member rewrite exception")
    if re.search(r"(?<!Do not )emit r\[\]", combined) or "Emit global relations" in combined:
        obsolete_output_instructions.append("relation-output instructions")
    if "disposition ledger" in combined and "Do not emit a disposition ledger" not in combined:
        obsolete_output_instructions.append("disposition ledger")
    material = bool(duplicate_ids)
    readiness = "CLEAN"
    if material or obsolete_output_instructions:
        readiness = "NEEDS_REQUEST_CLEANUP"
    return {
        "duplicate_local_records": duplicate_ids,
        "duplicate_record_count": len(duplicate_ids),
        "record_count": len(records),
        "obsolete_hits": obsolete_output_instructions,
        "obsolete_output_instructions": obsolete_output_instructions,
        "historical_debug_payload": False,
        "unused_metadata": False,
        "frozen_3_0_mutated": False,
        "readiness": readiness,
        "material": material or bool(obsolete_output_instructions),
        "note": (
            "Redundancy is recorded only. A.45 does not silently modify "
            "frozen prompt 3.0 / transport 3.0."
        ),
    }


def audit_prompt_consistency() -> dict[str, Any]:
    prompt = prompt_v30_bundle()
    combined = str(prompt.get("system") or "") + str(prompt.get("instructions") or "")
    missing = [token for token in _REQUIRED_PROMPT if token not in combined]
    contradictions: list[str] = []
    if "omit field v" in combined and "rewrite a single-member idea" in combined:
        if "Do not rewrite a single-member idea" not in combined:
            contradictions.append("single-member rewrite contradiction")
    schema = build_global_consolidation_schema_v30()
    idea_props = schema["properties"]["i"]["items"]["properties"]
    schema_v_optional = "v" in idea_props and "v" not in schema["properties"]["i"]["items"]["required"]
    drop_enum = schema["properties"]["drop"]["items"]["properties"]["w"]["enum"]
    relations_absent = "r" not in schema["properties"]
    repetitions_absent = "n" not in schema["properties"]
    ledger_absent = "d" not in schema["properties"]
    ok = (
        not missing
        and not contradictions
        and schema_v_optional
        and list(drop_enum) == list(DROP_REASONS_V20)
        and relations_absent
        and repetitions_absent
        and ledger_absent
        and "v" in IDEA_OPTIONAL_FIELDS
        and "v" not in IDEA_REQUIRED_FIELDS
        and set(ROOT_FIELDS) == {"gm", "t", "i", "x", "f", "u", "drop"}
        and SYNTHESIZED_IDEA_MAX_CHARS == 180
    )
    return {
        "ok": ok,
        "missing_required_statements": missing,
        "contradictions": contradictions,
        "schema_v_optional": schema_v_optional,
        "drop_enum": list(drop_enum),
        "relations_absent_from_schema": relations_absent,
        "repetitions_absent_from_schema": repetitions_absent,
        "disposition_ledger_absent": ledger_absent,
        "prompt_version": prompt.get("prompt_version"),
        "previous_prompt_mutated": prompt.get("previous_prompt_mutated"),
        "status": "PASS" if ok else "FAIL",
    }


__all__ = ["audit_prompt_consistency", "audit_request_redundancy"]
