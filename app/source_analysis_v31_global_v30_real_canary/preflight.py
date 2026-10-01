"""Preflight A.46 : identité A.45 rejouée immédiatement avant réseau. 0 POST."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.writer import source_map_path
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_v31_global_v30_exact_preflight.costing import (
    production_cost_estimate,
)
from app.source_analysis_v31_global_v30_exact_preflight.estimator import (
    calibrated_output_budget,
    input_budget,
)
from app.source_analysis_v31_global_v30_exact_preflight.fakeai import production_inventory
from app.source_analysis_v31_global_v30_exact_preflight.guard import authorize_future_call
from app.source_analysis_v31_global_v30_exact_preflight.inventory import (
    exact_inventory_payload,
    idea_handle_identity,
    load_exact_windows,
    verify_idea_source_refs,
    window_manifest,
)
from app.source_analysis_v31_global_v30_exact_preflight.payload import (
    build_audited_request,
    dry_run_identity_tuple,
)
from app.source_analysis_v31_global_v30_real_canary.constants import (
    A45_CONSERVATIVE_COST_USD,
    A45_CONSERVATIVE_OUTPUT,
    A45_ESTIMATED_INPUT,
    A45_EXPECTED_COST_USD,
    A45_EXPECTED_OUTPUT,
    A45_HARD_COST_USD,
    A45_HARD_OUTPUT,
    A45_INVENTORY_ARTIFACT,
    A45_NORMALIZED_INPUT_HASH,
    A45_REQUEST_HASH,
    A45_REQUEST_IDENTITY_ARTIFACT,
    A45_USABLE_INPUT_BUDGET,
    A45_WINDOW_MANIFEST_ARTIFACT,
    AUTHORIZATION_SCOPE,
    CONNECT_TIMEOUT_SECONDS,
    EXPECTED_EXAMPLE,
    EXPECTED_IDEA,
    EXPECTED_REFERENCE,
    EXPECTED_RELATION,
    EXPECTED_TOPIC,
    EXPECTED_TOTAL_RECORDS,
    EXPECTED_UNCERTAINTY,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MATERIAL_BOUND_DELTA_RATIO,
    MAX_ANTHROPIC_POST,
    MAX_ATTEMPTS,
    MAX_ENGINE_GENERATE,
    MODEL,
    PHASE,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PROJECT_NAME,
    PROMPT_VERSION,
    PROVIDER,
    READ_TIMEOUT_SECONDS,
    READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY,
    READY_WINDOWS,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SAFETY_70,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    SCHEMA_VERSION,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_v30_real_canary.engine import credential_available
from app.source_analysis_v31_global_v30_real_canary.guard import (
    GlobalRealCanaryError,
    reject_contract_drift,
    validate_authorization_scope,
    validate_project_name,
    validate_ready_windows,
)
from app.source_analysis_v31_global_v30_real_canary.paths import (
    production_source_map_present,
)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _materially_worse(observed: float, approved: float, *, ratio: float) -> bool:
    if approved <= 0:
        return True
    return (observed - approved) / approved > ratio


def run_preflight(
    project_name: str = PROJECT_NAME,
    *,
    authorization_scope: str = AUTHORIZATION_SCOPE,
    sortie_dir: Path | None = None,
    require_credential: bool = False,
) -> dict[str, Any]:
    validate_project_name(project_name)
    validate_authorization_scope(authorization_scope)
    if production_source_map_present(project_name, sortie_dir=sortie_dir) or source_map_path(
        project_name, sortie_dir=sortie_dir
    ).is_file():
        raise GlobalRealCanaryError(
            "BLOCKED_PRECALL: production analysis/source_map.json already present."
        )
    windows = load_exact_windows(project_name, sortie_dir=sortie_dir)
    normalized = windows["normalized"]
    validate_ready_windows(list(READY_WINDOWS))
    idea_identity = idea_handle_identity(normalized)
    src_audit = verify_idea_source_refs(normalized)
    window_rows = window_manifest(windows["loaded"], normalized)
    inventory_payload = exact_inventory_payload(
        inventory_check=windows["inventory_check"],
        idea_identity=idea_identity,
        src_audit=src_audit,
        window_rows=window_rows,
    )
    observed = inventory_payload.get("observed") or {}
    if (
        int(observed.get("total_records") or 0) != EXPECTED_TOTAL_RECORDS
        or int(observed.get("TOPIC") or 0) != EXPECTED_TOPIC
        or int(observed.get("IDEA") or 0) != EXPECTED_IDEA
        or int(observed.get("RELATION") or 0) != EXPECTED_RELATION
        or int(observed.get("EXAMPLE") or 0) != EXPECTED_EXAMPLE
        or int(observed.get("REFERENCE") or 0) != EXPECTED_REFERENCE
        or int(observed.get("UNCERTAINTY") or 0) != EXPECTED_UNCERTAINTY
    ):
        raise GlobalRealCanaryError(
            "BLOCKED_PRECALL: inventory mismatch "
            f"observed={observed}."
        )
    if int(idea_identity.get("count") or 0) != EXPECTED_IDEA:
        raise GlobalRealCanaryError("BLOCKED_PRECALL: IDEA handle count mismatch.")
    built_a = build_audited_request(
        normalized,
        window_set_sha256=str(window_rows["window_set_sha256"]),
        project_name=project_name,
        sortie_dir=sortie_dir,
    )
    built_b = build_audited_request(
        normalized,
        window_set_sha256=str(window_rows["window_set_sha256"]),
        project_name=project_name,
        sortie_dir=sortie_dir,
    )
    if dry_run_identity_tuple(built_a["audit"]) != dry_run_identity_tuple(built_b["audit"]):
        raise GlobalRealCanaryError("BLOCKED_PRECALL: exact request is not deterministic.")
    audit = built_a["audit"]
    actual_input_hash = str(audit.get("normalized_input_hash") or "")
    actual_request_hash = str(audit.get("request_identity") or "")
    if actual_input_hash != A45_NORMALIZED_INPUT_HASH:
        raise GlobalRealCanaryError(
            "BLOCKED_PRECALL: normalized input hash mismatch "
            f"actual={actual_input_hash} expected={A45_NORMALIZED_INPUT_HASH}."
        )
    if actual_request_hash != A45_REQUEST_HASH:
        raise GlobalRealCanaryError(
            "BLOCKED_PRECALL: request hash mismatch "
            f"actual={actual_request_hash} expected={A45_REQUEST_HASH}."
        )
    schema_metrics = built_a["schema_metrics"]
    if (
        int(audit.get("raw_bytes") or 0) != SCHEMA_RAW_BYTES
        or int(audit.get("adapted_bytes") or 0) != SCHEMA_ADAPTED_BYTES
        or str(audit.get("schema_hash") or "") != SCHEMA_HASH
        or schema_metrics.get("schema_identity") != "MATCH"
    ):
        raise GlobalRealCanaryError("BLOCKED_PRECALL: schema identity mismatch.")
    reject_contract_drift(
        prompt_version=PROMPT_VERSION,
        transport_version=TRANSPORT_VERSION,
        schema_hash=str(audit.get("schema_hash") or ""),
        model=str(audit.get("model") or ""),
        thinking_mode=THINKING_MODE if audit.get("thinking_type") == "disabled" else str(
            audit.get("thinking_type")
        ),
        max_output=int(audit.get("max_tokens") or 0),
    )
    audit_root = audit_dir(project_name, sortie_dir=sortie_dir)
    a45_identity = _load_json(audit_root / A45_REQUEST_IDENTITY_ARTIFACT)
    if a45_identity:
        stored_hash = str(a45_identity.get("request_identity") or "")
        stored_input = str(a45_identity.get("normalized_input_hash") or "")
        if stored_hash and stored_hash != actual_request_hash:
            raise GlobalRealCanaryError(
                "BLOCKED_PRECALL: live request hash differs from A.45 artifact."
            )
        if stored_input and stored_input != actual_input_hash:
            raise GlobalRealCanaryError(
                "BLOCKED_PRECALL: live input hash differs from A.45 artifact."
            )
    a45_windows = _load_json(audit_root / A45_WINDOW_MANIFEST_ARTIFACT)
    if a45_windows:
        stored_set = str(a45_windows.get("window_set_sha256") or "")
        if stored_set and stored_set != str(window_rows.get("window_set_sha256") or ""):
            raise GlobalRealCanaryError(
                "BLOCKED_PRECALL: window set hash differs from A.45 manifest."
            )
        stored_rows = a45_windows.get("windows") or []
        live_rows = window_rows.get("windows") or []
        if len(stored_rows) == 7 and len(live_rows) == 7:
            for stored, live in zip(stored_rows, live_rows):
                if stored.get("sha256") != live.get("sha256") or stored.get(
                    "window_id"
                ) != live.get("window_id"):
                    raise GlobalRealCanaryError(
                        "BLOCKED_PRECALL: READY window identity differs from A.45."
                    )
    a45_inventory = _load_json(audit_root / A45_INVENTORY_ARTIFACT)
    if a45_inventory:
        stored_handles = (a45_inventory.get("idea_accountability_input") or {}).get(
            "handle_set_sha256"
        )
        if stored_handles and stored_handles != idea_identity.get("handle_set_sha256"):
            raise GlobalRealCanaryError(
                "BLOCKED_PRECALL: IDEA handle set hash differs from A.45."
            )
    output_budget = calibrated_output_budget()
    inputs = input_budget(
        local_prompt_tokens=int(audit.get("local_input_estimate_tokens") or 0),
        payload_tokens=int(audit.get("payload_local_estimate_tokens") or 0),
        request_chars=int(audit.get("provider_visible_chars") or 0),
        request_bytes=int(audit.get("provider_visible_bytes") or 0),
        compact_chars=int(audit.get("compact_chars") or 0),
    )
    estimated_input = int(inputs.get("primary_estimated_input") or 0)
    if _materially_worse(
        estimated_input, A45_ESTIMATED_INPUT, ratio=MATERIAL_BOUND_DELTA_RATIO
    ):
        raise GlobalRealCanaryError(
            "BLOCKED_PRECALL: estimated input materially worse than A.45 "
            f"actual={estimated_input} a45={A45_ESTIMATED_INPUT}."
        )
    if estimated_input >= A45_USABLE_INPUT_BUDGET:
        raise GlobalRealCanaryError("BLOCKED_PRECALL: estimated input exceeds 80000.")
    hard_output = int(output_budget.get("hard_planning") or 0)
    if hard_output > SAFETY_70:
        raise GlobalRealCanaryError(
            f"BLOCKED_PRECALL: hard output {hard_output} > {SAFETY_70}."
        )
    if _materially_worse(hard_output, A45_HARD_OUTPUT, ratio=MATERIAL_BOUND_DELTA_RATIO):
        raise GlobalRealCanaryError(
            "BLOCKED_PRECALL: hard output materially worse than A.45 "
            f"actual={hard_output} a45={A45_HARD_OUTPUT}."
        )
    cost = production_cost_estimate(input_tokens=estimated_input, budget=output_budget)
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    inventory = production_inventory(normalized, transcript)
    if require_credential and not credential_available():
        raise GlobalRealCanaryError(
            "BLOCKED_PRECALL: Anthropic credential unavailable."
        )
    authorize_future_call(
        {
            "normalized_input_hash": actual_input_hash,
            "request_hash": actual_request_hash,
            "provider_visible_hash": audit.get("provider_visible_hash"),
            "window_set_sha256": window_rows.get("window_set_sha256"),
            "prompt_version": PROMPT_VERSION,
            "prompt_hash": audit.get("prompt_hash"),
            "transport_version": TRANSPORT_VERSION,
            "schema_hash": audit.get("schema_hash"),
            "model": MODEL,
            "thinking_mode": THINKING_MODE,
            "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "retries": 0,
            "max_engine_generate": MAX_ENGINE_GENERATE,
            "hard_planning": hard_output,
        },
        {
            "normalized_input_hash": A45_NORMALIZED_INPUT_HASH,
            "request_hash": A45_REQUEST_HASH,
            "provider_visible_hash": audit.get("provider_visible_hash"),
            "window_set_sha256": window_rows.get("window_set_sha256"),
            "prompt_version": PROMPT_VERSION,
            "prompt_hash": audit.get("prompt_hash"),
            "transport_version": TRANSPORT_VERSION,
            "schema_hash": SCHEMA_HASH,
            "model": MODEL,
            "thinking_mode": THINKING_MODE,
            "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "approved_hard_planning": hard_output,
            "material_bound_delta_ratio": MATERIAL_BOUND_DELTA_RATIO,
        },
    )
    request_identity = "MATCH"
    return {
        "ok": True,
        "phase": PHASE,
        "schema_version": SCHEMA_VERSION,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "human_authorization": {
            "A45_READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY": (
                READY_FOR_ONE_REAL_GLOBAL_CONSOLIDATION_CANARY
            ),
            "A46_EXECUTES_THAT_EXACT_APPROVED_REQUEST": True,
            "second_request_authorized": False,
            "do_not_generalize": True,
        },
        "windows": window_rows,
        "inventory": inventory_payload,
        "idea_handles": idea_identity,
        "src_audit": src_audit,
        "normalized": normalized,
        "loaded": windows["loaded"],
        "built": built_a,
        "payload_audit": {
            key: value for key, value in audit.items() if key != "identity_fields"
        },
        "schema_metrics": schema_metrics,
        "input_budget": inputs,
        "output_budget": output_budget,
        "cost": cost,
        "inventory_runtime": inventory,
        "transcript": transcript,
        "normalized_input_hash": actual_input_hash,
        "request_hash": actual_request_hash,
        "provider_visible_hash": audit.get("provider_visible_hash"),
        "request_identity": request_identity,
        "a45_normalized_input_hash": A45_NORMALIZED_INPUT_HASH,
        "a45_request_hash": A45_REQUEST_HASH,
        "model": MODEL,
        "provider": PROVIDER,
        "prompt_version": PROMPT_VERSION,
        "transport_version": TRANSPORT_VERSION,
        "thinking_mode": THINKING_MODE,
        "max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "connect_timeout_seconds": CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": READ_TIMEOUT_SECONDS,
        "retries": 0,
        "max_engine_generate": MAX_ENGINE_GENERATE,
        "max_anthropic_post": MAX_ANTHROPIC_POST,
        "max_attempts": MAX_ATTEMPTS,
        "estimated_input": estimated_input,
        "expected_output": int(output_budget.get("p50_expected") or A45_EXPECTED_OUTPUT),
        "conservative_output": int(
            output_budget.get("conservative") or A45_CONSERVATIVE_OUTPUT
        ),
        "hard_output": hard_output,
        "a45_estimated_input": A45_ESTIMATED_INPUT,
        "a45_expected_output": A45_EXPECTED_OUTPUT,
        "a45_conservative_output": A45_CONSERVATIVE_OUTPUT,
        "a45_hard_output": A45_HARD_OUTPUT,
        "a45_expected_cost": A45_EXPECTED_COST_USD,
        "a45_conservative_cost": A45_CONSERVATIVE_COST_USD,
        "a45_hard_cost": A45_HARD_COST_USD,
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "ready_windows": list(READY_WINDOWS),
        "credential_available": credential_available(),
        "source_map_present": False,
    }


__all__ = ["run_preflight"]
