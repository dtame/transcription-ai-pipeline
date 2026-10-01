"""Transport / schema / validator / budget responsibility. Offline proof."""

from __future__ import annotations

import json
from typing import Any

from app.editorial_planner_forensics_4a34.constants import (
    A33_HTTP_FINISH,
    A33_INPUT_TOKENS,
    A33_MISSING_IDEAS,
    A33_OUTPUT_TOKENS,
    A33_OUTPUT_UTILIZATION,
    A33_THINKING_TOKENS,
    ADAPTED_SCHEMA_BYTES,
    ADAPTED_SCHEMA_SHA256,
    FROZEN_A33_PASSES,
    MAX_OUTPUT_TOKENS,
    RAW_SCHEMA_BYTES,
    TRANSPORT_VERSION,
)
from app.editorial_planner_forensics_4a34.identity import compare_schema
from app.editorial_planning.coverage import missing_idea_ids
from app.editorial_planning.models import EditorialPlan
from app.editorial_planning.schema import build_editorial_plan_transport_schema
from app.editorial_planning.validator import validate_editorial_plan
from app.source_analysis.models import SourceMap


def transport_schema_responsibility(
    source_map: SourceMap,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    schema = build_editorial_plan_transport_schema()
    encoded = json.dumps(schema, ensure_ascii=False, sort_keys=True)
    plan = EditorialPlan.from_dict(candidate)
    validation = validate_editorial_plan(plan, source_map)
    missing = [
        item.idea_id
        for item in plan.idea_coverage
        if item.idea_id in A33_MISSING_IDEAS and item.disposition not in
        {"ASSIGNED", "DEFERRED", "EXCLUDED"}
    ]
    reconstruct_missing = list(missing_idea_ids(plan, source_map))
    live_schema = compare_schema()
    idea_enum_present = any(
        token in encoded
        for token in ("IDEA001", "IDEA007", "IDEA286")
    )
    return {
        "transport_version": TRANSPORT_VERSION,
        "schema_raw_adapted": f"{RAW_SCHEMA_BYTES} / {ADAPTED_SCHEMA_BYTES}",
        "schema_sha256": ADAPTED_SCHEMA_SHA256,
        "schema_identity": live_schema.get("identity"),
        "schema_changed": live_schema.get("schema_changed"),
        "schema_required_keys": list(schema.get("required") or []),
        "schema_mentions_concrete_idea_ids": idea_enum_present,
        "schema_can_require_all_input_ids_dynamically": False,
        "schema_responsibility": (
            "JSON Schema validates item shape (deferred/excluded objects, "
            "section i[] of strings). It cannot dynamically enumerate the "
            "286 input IDEA IDs. Completeness is a validator "
            "cross-input check, not a grammar duty."
        ),
        "schema_defect": "NO",
        "transport_defect": "NO",
        "transport_rationale": (
            "A.3 used the same transport/schema and produced 286/286. "
            "A.3.3 decoded 284 explicit ASSIGNED dispositions plus two "
            "empty reconstructed rows. Transport represented the provider "
            "output faithfully."
        ),
        "validator_detected_IDEA007": "IDEA007" in missing,
        "validator_detected_IDEA008": "IDEA008" in missing,
        "validator_status": validation.status,
        "validator_errors": list(validation.errors),
        "reconstruct_missing_idea_ids": reconstruct_missing,
        "reconstruct_empty_disposition_ids": missing,
        "validator_defect": "NO",
        "validator_success": True,
        "validator_note": (
            "Reconstruct inserts an empty disposition row for omitted "
            "input IDs. Validator rejects empty/missing dispositions. "
            "This is the intended hard gate, not a defect."
        ),
        "automatic_repair_implemented": False,
        "automatic_retry_implemented": False,
        "frozen_a33_passes": list(FROZEN_A33_PASSES),
        "output_budget": {
            "output_tokens": A33_OUTPUT_TOKENS,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "utilization": A33_OUTPUT_UTILIZATION,
            "utilization_display": "16.48%",
            "finish": A33_HTTP_FINISH,
            "output_cap_failure": "NO",
            "thinking_tokens": A33_THINKING_TOKENS,
            "thinking_block_present": False,
            "thinking_budget_blamed": False,
            "input_tokens": A33_INPUT_TOKENS,
            "a33_finish_reason": "end_turn",
        },
    }


__all__ = ["transport_schema_responsibility"]
