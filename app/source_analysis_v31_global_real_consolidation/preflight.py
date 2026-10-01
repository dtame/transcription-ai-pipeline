"""Preflight A.38. 0 provider. Fail-closed avant le unique appel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis_v31_global_real_consolidation.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_REQUEST_ID,
    A37_STATUS_PRESERVED,
    AUTHORIZATION_SCOPE,
    GLOBAL_TRANSPORT_1_1_GRAMMAR_PROOF,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    PHASE,
    PROJECT_NAME,
    READY_WINDOWS,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_VERSION,
)
from app.source_analysis_v31_global_real_consolidation.engine import credential_available
from app.source_analysis_v31_global_real_consolidation.guard import (
    GlobalRealConsolidationError,
    validate_authorization_scope,
    validate_project_name,
)
from app.source_analysis_v31_global_real_consolidation.identity import verify_schema_identity
from app.source_analysis_v31_global_real_consolidation.input_contract import (
    assert_frozen_inventory,
    load_normalized_bundle,
    serialize_twice,
)
from app.source_analysis_v31_global_real_consolidation.paths import (
    production_source_map_present,
)
from app.source_analysis_v31_global_real_consolidation.payload import (
    build_audited_request,
    dry_run_identity_tuple,
)


def run_preflight(
    project_name: str = PROJECT_NAME,
    *,
    authorization_scope: str | None = None,
    sortie_dir: Path | None = None,
    require_credential: bool = False,
) -> dict[str, Any]:
    validate_authorization_scope(authorization_scope)
    validate_project_name(project_name)
    if production_source_map_present(project_name, sortie_dir=sortie_dir):
        raise GlobalRealConsolidationError(
            "BLOCKED_PRECALL: production analysis/source_map.json already exists."
        )
    if GLOBAL_TRANSPORT_1_1_GRAMMAR_PROOF != "PASS":
        raise GlobalRealConsolidationError(
            "BLOCKED_PRECALL: GLOBAL_TRANSPORT_1_1_GRAMMAR_PROOF is not PASS."
        )
    bundle = load_normalized_bundle(project_name, sortie_dir=sortie_dir)
    inventory_check = assert_frozen_inventory(
        bundle["normalized"], bundle["inventory"], bundle["boundary"]
    )
    determinism = serialize_twice(bundle["normalized"])
    schema = verify_schema_identity(project_name, sortie_dir=sortie_dir)
    built = build_audited_request(
        bundle["normalized"], project_name=project_name, sortie_dir=sortie_dir
    )
    built_again = build_audited_request(
        bundle["normalized"], project_name=project_name, sortie_dir=sortie_dir
    )
    if dry_run_identity_tuple(built["audit"]) != dry_run_identity_tuple(built_again["audit"]):
        raise GlobalRealConsolidationError(
            "BLOCKED_PRECALL: request identity is not deterministic."
        )
    if require_credential and not credential_available():
        raise GlobalRealConsolidationError(
            "Anthropic credential unavailable — STOP WITHOUT PROVIDER CALL."
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "project_name": project_name,
        "ok": True,
        "ready_windows": list(READY_WINDOWS),
        "grammar_proof": GLOBAL_TRANSPORT_1_1_GRAMMAR_PROOF,
        "a37_request_id": A37_REQUEST_ID,
        "history": {
            "A34": A34_STATUS_PRESERVED,
            "A35": A35_STATUS_PRESERVED,
            "A36": A36_STATUS_PRESERVED,
            "A37": A37_STATUS_PRESERVED,
        },
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "inventory": inventory_check,
        "determinism": determinism,
        "schema": {
            "raw_bytes": schema.get("raw_bytes"),
            "adapted_bytes": schema.get("adapted_bytes"),
            "hash": schema.get("hash"),
            "schema_identity": schema.get("schema_identity"),
        },
        "payload_audit": built["audit"],
        "request_identity": built["audit"].get("request_identity"),
        "normalized": bundle["normalized"],
        "loaded": bundle["loaded"],
        "boundary": bundle["boundary"],
        "input_inventory": bundle["inventory"],
        "built": built,
        "source_map_present": False,
        "lock_present": False,
        "authorized_calls": 1,
        "actual_calls": 0,
        "successful_calls": 0,
        "failed_calls": 0,
        "retries": 0,
    }


__all__ = ["run_preflight"]
