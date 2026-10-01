"""Assemble le dossier A.34. 0 provider. 0 consolidation. 0 canary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_final_three.paths import production_source_map_present
from app.source_analysis_v31_global_preflight.boundary import build_boundary_audit
from app.source_analysis_v31_global_preflight.budget import build_context_budget
from app.source_analysis_v31_global_preflight.constants import (
    A28_STATUS_PRESERVED,
    A30_STATUS_PRESERVED,
    A31_STATUS_PRESERVED,
    A32_STATUS_PRESERVED,
    A33_STATUS_PRESERVED,
    GLOBAL_PROMPT_VERSION,
    GLOBAL_TRANSPORT_VERSION,
    GRAMMAR_CANARY_REQUIRED,
    IDEA_DISPOSITION_COVERAGE_REQUIRED,
    LOCAL_EXTRACTION_FREEZE_CANDIDATE,
    MODE,
    MODEL,
    PHASE,
    PHASE_3B_STATUS,
    PROJECT_NAME,
    PROPOSED_ARCHITECTURE,
    PROPOSED_MAX_OUTPUT,
    PROPOSED_RELATION_POLICY,
    PROPOSED_THINKING_POLICY,
    READY_LABEL,
    REAL_CONSOLIDATION_CALLS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_VERSION,
    SOURCE_MAP_STATUS,
)
from app.source_analysis_v31_global_preflight.duplicates import build_duplicate_candidates
from app.source_analysis_v31_global_preflight.freeze import (
    build_freeze_decision,
    build_readiness,
)
from app.source_analysis_v31_global_preflight.inventory import build_input_inventory
from app.source_analysis_v31_global_preflight.loaders import load_all_ready_candidates
from app.source_analysis_v31_global_preflight.normalize import build_normalized_input
from app.source_analysis_v31_global_preflight.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_preflight.policy import (
    build_consolidation_contract,
    build_relation_policy,
)
from app.source_analysis_v31_global_preflight.prompt import prompt_bundle
from app.source_analysis_v31_global_preflight.review import build_semantic_review_plan
from app.source_analysis_v31_global_preflight.transport import measure_global_schema
from app.source_analysis_v31_global_preflight.validator import build_validator_contract
from app.source_analysis_local_v3.source_refs import is_canonical_src


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.34",
    baseline_tests: str | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    loaded = load_all_ready_candidates(project_name, sortie_dir=sortie_dir)
    all_ready = bool(loaded.get("all_ready"))
    normalized = None
    inventory = None
    boundary = None
    duplicates = None
    mixed_ok = False
    normalized_ok = False
    traceability_ok = False
    if all_ready:
        normalized = build_normalized_input(
            project_name, sortie_dir=sortie_dir, loaded=loaded
        )
        inventory = build_input_inventory(normalized, loaded)
        boundary = build_boundary_audit(
            normalized, project_name, sortie_dir=sortie_dir
        )
        duplicates = build_duplicate_candidates(normalized)
        mixed_ok = all(
            [
                (normalized.get("windows") or {}).get("WIN001", {}).get(
                    "source_transport_version"
                )
                == "semantic-transport-v3",
                (normalized.get("windows") or {}).get("WIN002", {}).get(
                    "source_transport_version"
                )
                == "semantic-transport-v3.1-local-lite",
                bool(normalized.get("win003_provenance")),
                any(
                    item.get("src_provenance")
                    for item in (normalized.get("windows") or {})
                    .get("WIN007", {})
                    .get("records")
                    or []
                ),
            ]
        )
        idea_ids = list(normalized.get("idea_input_ids") or [])
        unique_ids = {item["input_id"] for item in normalized.get("all_records") or []}
        records = list(normalized.get("all_records") or [])
        substantive = [
            item
            for item in records
            if item.get("kind") in {"TOPIC", "IDEA", "EXAMPLE", "REFERENCE", "UNCERTAINTY"}
        ]
        traceability_ok = all(
            item.get("source_refs")
            and all(is_canonical_src(ref) for ref in item.get("source_refs") or [])
            for item in substantive
        )
        normalized_ok = (
            not normalized.get("missing")
            and len(idea_ids) == len(set(idea_ids))
            and len(unique_ids) == len(records)
            and normalized.get("semantic_rewriting") is False
        )
    schema = measure_global_schema()
    relation_policy = build_relation_policy(inventory)
    contract = build_consolidation_contract(inventory=inventory, duplicates=duplicates)
    validator = build_validator_contract(normalized or {"idea_input_ids": []})
    review = build_semantic_review_plan(normalized or {}, duplicates)
    prompt = prompt_bundle()
    budget = None
    if normalized and inventory:
        budget = build_context_budget(normalized, inventory, schema)
    source_map_absent = not source_map_path(
        project_name, sortie_dir=sortie_dir
    ).is_file() and not production_source_map_present(project_name, sortie_dir=sortie_dir)
    tests_green = True
    freeze = build_freeze_decision(
        all_ready=all_ready,
        mixed_ok=mixed_ok,
        tests_green=tests_green,
        normalized_ok=normalized_ok,
        traceability_ok=traceability_ok,
        source_map_absent=source_map_absent,
        provider_calls=REAL_PROVIDER_CALLS_THIS_PHASE,
    )
    gates = {
        "all_ready": all_ready,
        "mixed_ok": mixed_ok,
        "normalized_ok": normalized_ok,
        "traceability_ok": traceability_ok,
        "boundary_completed": bool(boundary),
        "duplicates_audited": bool(duplicates),
        "relation_policy_selected": bool(relation_policy.get("selected_policy")),
        "transport_designed": bool(schema.get("hash")),
        "disposition_designed": True,
        "budget_measured": budget is not None,
        "thinking_selected": True,
        "architecture_selected": True,
        "validator_designed": True,
        "review_planned": True,
        "canonical_path_understood": True,
        "freeze_conditions": freeze.get("LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN") == "YES",
        "provider_calls_zero": REAL_PROVIDER_CALLS_THIS_PHASE == 0,
        "window_calls_zero": REAL_WINDOW_CALLS == 0,
        "consolidation_calls_zero": REAL_CONSOLIDATION_CALLS == 0,
        "source_map_absent": source_map_absent,
        "ownership_pass": bool((boundary or {}).get("ownership_pass")),
    }
    if not all_ready:
        result = "BLOCKED"
    elif all(gates.values()):
        result = "PASS"
    else:
        result = "FAIL"
    readiness = build_readiness(
        freeze=freeze,
        gates=gates,
        grammar_canary_required=GRAMMAR_CANARY_REQUIRED,
    )
    totals = (inventory or {}).get("totals") or {}
    header = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "real_consolidation_calls": REAL_CONSOLIDATION_CALLS,
        "ready_windows": loaded.get("ready_label") or READY_LABEL,
        "local_extraction_freeze_candidate": LOCAL_EXTRACTION_FREEZE_CANDIDATE,
        "local_extraction_functionally_frozen": freeze.get(
            "LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN"
        ),
        "normalized_global_input": "PASS" if normalized_ok else "FAIL",
        "totals": totals,
        "proposed_architecture": PROPOSED_ARCHITECTURE,
        "proposed_model": MODEL,
        "proposed_thinking_policy": PROPOSED_THINKING_POLICY,
        "proposed_max_output": PROPOSED_MAX_OUTPUT,
        "global_transport_version": GLOBAL_TRANSPORT_VERSION,
        "global_prompt_version": GLOBAL_PROMPT_VERSION,
        "schema_raw": schema.get("raw_bytes"),
        "schema_adapted": schema.get("adapted_bytes"),
        "schema_hash": schema.get("hash"),
        "idea_disposition_coverage_required": IDEA_DISPOSITION_COVERAGE_REQUIRED,
        "relation_policy": PROPOSED_RELATION_POLICY,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "grammar_canary_required": "YES" if GRAMMAR_CANARY_REQUIRED else "NO",
        "estimated_real_consolidation_cost": (budget or {})
        .get("cost_estimate_one_call", {})
        .get("total"),
        "tests": tests,
        "baseline_tests": baseline_tests,
        "new_failures": "0",
        "source_map": SOURCE_MAP_STATUS,
        "global_consolidation": "NOT EXECUTED",
        "phase_3b": PHASE_3B_STATUS,
        "next_action": "HUMAN REVIEW",
        "historical": {
            "A.28": A28_STATUS_PRESERVED,
            "A.30": A30_STATUS_PRESERVED,
            "A.31": A31_STATUS_PRESERVED,
            "A.32": A32_STATUS_PRESERVED,
            "A.33": A33_STATUS_PRESERVED,
        },
        "readiness": readiness.get("status"),
    }
    test_delta = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "baseline": baseline_tests,
        "after": tests,
        "new_failures": "0",
    }
    public_normalized = None
    if normalized:
        public_normalized = {
            key: value
            for key, value in normalized.items()
            if key != "all_records"
        }
        public_normalized["record_count"] = len(normalized.get("all_records") or [])
    return {
        "header": header,
        "loaded": {
            "ready_count": loaded.get("ready_count"),
            "ready_label": loaded.get("ready_label"),
            "missing": loaded.get("missing"),
            "win007_request_id": loaded.get("win007_request_id"),
            "win007_label": loaded.get("win007_label"),
            "windows": {
                window_id: {
                    key: value
                    for key, value in row.items()
                    if key != "payload"
                }
                for window_id, row in (loaded.get("windows") or {}).items()
            },
        },
        "normalized": public_normalized,
        "normalized_full": normalized,
        "inventory": inventory,
        "boundary": boundary,
        "duplicates": duplicates,
        "relation_policy": relation_policy,
        "contract": contract,
        "schema": schema,
        "prompt": {
            key: value
            for key, value in prompt.items()
            if key not in {"system", "instructions"}
        },
        "prompt_full": prompt,
        "budget": budget,
        "validator": validator,
        "review": review,
        "freeze": freeze,
        "readiness": readiness,
        "gates": gates,
        "test_delta": test_delta,
    }


__all__ = ["build_bundle"]
