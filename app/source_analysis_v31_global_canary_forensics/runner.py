"""Assemble le dossier A.36. 0 provider. 0 consolidation. 0 canary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_canary_forensics.analysis import (
    classify_a35_failures,
    disposition_semantics,
    drop_contract_analysis,
    fixture_expectation_review,
    redesign_decision,
    repetition_policy,
    root_causes,
)
from app.source_analysis_v31_global_canary_forensics.constants import (
    A34_SCHEMA_ADAPTED,
    A34_SCHEMA_HASH,
    A34_SCHEMA_RAW,
    A34_STATUS_PRESERVED,
    A35_ACTUAL_CALLS,
    A35_AUTHORIZED_CALLS,
    A35_COST_USD,
    A35_DROP_PROSE,
    A35_ELAPSED_SECONDS,
    A35_FINISH_REASON,
    A35_GRAMMAR_ACCEPTED,
    A35_HTTP_STATUS,
    A35_REQUEST_ID,
    A35_RETRIES,
    A35_STATUS_PRESERVED,
    A35_SUCCESSFUL_CALLS,
    A35_THINKING_TOKENS,
    CANONICAL_DROP_TOKEN,
    DROP_REASON_CLASS,
    FIXTURE_OVERCONSTRAINED,
    LINK_RELATED_CONTRACT,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MODE,
    MODEL,
    NEW_GRAMMAR_CANARY_REQUIRED,
    NEXT_PROMPT_VERSION,
    NEXT_SCHEMA_ADAPTED_BYTES,
    NEXT_SCHEMA_HASH,
    NEXT_SCHEMA_RAW_BYTES,
    NEXT_TRANSPORT_VERSION,
    OLD_PROMPT_VERSION,
    OLD_TRANSPORT_VERSION,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_LOCAL_ESTIMATE_TOKENS,
    PRODUCTION_MAX_OUTPUT_TOKENS,
    PRODUCTION_NORMALIZED_CHARS,
    PRODUCTION_PROVIDER_ADJUSTED_TOKENS,
    PROJECT_NAME,
    PROPOSED_ARCHITECTURE,
    READINESS_DECISION,
    READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
    REAL_CONSOLIDATION_CALLS,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    RELATION_POLICY_OPTION,
    RELATION_QUALITY_TECHNICAL_DEBT,
    REPETITION_REQUIREMENT,
    SCHEMA_CHANGED,
    SCHEMA_VERSION,
    SELECTED_DISPOSITION_MODEL,
    SOURCE_MAP_STATUS,
    THINKING_MODE,
    THINKING_POLICY,
)
from app.source_analysis_v31_global_canary_forensics.evidence import (
    production_source_map_present,
    verify_a35_identity,
)
from app.source_analysis_v31_global_canary_forensics.fixture import (
    fakeai_catalog,
    interpret_transport_v11,
    next_fixture_payload,
    pipeline_pass,
)
from app.source_analysis_v31_global_canary_forensics.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_global_canary_forensics.prompt_v101 import (
    prompt_v101_bundle,
    prompt_v10_bundle_frozen,
)
from app.source_analysis_v31_global_canary_forensics.replay import (
    replay_a35_under_v10_contract,
    replay_drop_only_counterfactual,
)
from app.source_analysis_v31_global_canary_forensics.transport_v11 import (
    measure_global_schema_v11,
)
from app.source_analysis_v31_global_preflight.transport import measure_global_schema


def _public_schema(measured: dict[str, Any]) -> dict[str, Any]:
    skip = {"schema", "adapted_schema", "raw", "adapted"}
    return {key: value for key, value in measured.items() if key not in skip}


def _evaluate_fakeai() -> dict[str, Any]:
    catalog = fakeai_catalog()
    results: dict[str, Any] = {}
    for name, payload in catalog.items():
        interpreted = interpret_transport_v11(payload, signature=f"fakeai-{name}")
        passed = pipeline_pass(interpreted)
        results[name] = {
            "pipeline_pass": passed,
            "structured_parse": interpreted.get("structured_parse"),
            "decoder": interpreted.get("decoder"),
            "handle_validation": interpreted.get("handle_validation"),
            "global_validator": interpreted.get("global_validator"),
            "traceability": interpreted.get("traceability"),
            "canonical_reconstruction": interpreted.get("canonical_reconstruction"),
            "canonical_validation": interpreted.get("canonical_validation"),
            "semantic_review": (interpreted.get("semantic_review") or {}).get("status"),
            "silent_drops": interpreted.get("silent_drops"),
            "coverage": interpreted.get("idea_disposition_coverage"),
            "errors": (interpreted.get("validator") or {}).get("errors")
            or interpreted.get("errors")
            or [],
        }
        if name == "VALID":
            results[name]["reconstruction_ok"] = interpreted.get(
                "canonical_reconstruction"
            )
    expected_pass = {"VALID"}
    ok = results["VALID"]["pipeline_pass"] is True and all(
        results[name]["pipeline_pass"] is False
        for name in results
        if name not in expected_pass
    )
    return {"ok": ok, "cases": results}


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.36",
    baseline_tests: str | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    identity = verify_a35_identity(project_name, sortie_dir=sortie_dir)
    replay = replay_a35_under_v10_contract(project_name, sortie_dir=sortie_dir)
    failures = classify_a35_failures(replay)
    drop = drop_contract_analysis()
    dispositions = disposition_semantics()
    repetition = repetition_policy()
    fixture_review = fixture_expectation_review()
    redesign = redesign_decision()
    v10_schema = measure_global_schema()
    v11_schema = measure_global_schema_v11()
    prompt_old = prompt_v10_bundle_frozen()
    prompt_new = prompt_v101_bundle()
    counterfactual = replay_drop_only_counterfactual(
        project_name, sortie_dir=sortie_dir
    )
    fakeai = _evaluate_fakeai()
    next_fixture = next_fixture_payload()
    source_map_present = production_source_map_present(
        project_name, sortie_dir=sortie_dir
    ) or source_map_path(project_name, sortie_dir=sortie_dir).is_file()
    v10_unchanged = (
        v10_schema.get("raw_bytes") == A34_SCHEMA_RAW
        and v10_schema.get("adapted_bytes") == A34_SCHEMA_ADAPTED
        and v10_schema.get("hash") == A34_SCHEMA_HASH
        and prompt_old.get("prompt_version") == OLD_PROMPT_VERSION
    )
    v11_matches = (
        v11_schema.get("raw_bytes") == NEXT_SCHEMA_RAW_BYTES
        and v11_schema.get("adapted_bytes") == NEXT_SCHEMA_ADAPTED_BYTES
        and v11_schema.get("hash") == NEXT_SCHEMA_HASH
        and not v11_schema.get("unsupported_constructs")
    )
    pass_gate = all(
        [
            identity.get("ok"),
            replay.get("reproduced_a35_failure"),
            replay.get("historical_status_unchanged") == "FAIL",
            v10_unchanged,
            v11_matches,
            fakeai.get("ok"),
            counterfactual.get("result") == "PASS",
            REAL_PROVIDER_CALLS_THIS_PHASE == 0,
            not source_map_present,
            READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY == "NO",
        ]
    )
    readiness = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "decision": READINESS_DECISION,
        "READY_FOR_SECOND_GLOBAL_GRAMMAR_CANARY": READINESS_DECISION
        == "READY_FOR_SECOND_GLOBAL_GRAMMAR_CANARY",
        "READY_FOR_GLOBAL_CONTRACT_CANARY_NO_NEW_GRAMMAR": False,
        "NEEDS_MORE_OFFLINE_REDESIGN": False,
        "BLOCKED": not pass_gate,
        "READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY": READY_FOR_REAL_GLOBAL_CONSOLIDATION_CANARY,
        "new_grammar_canary_required": NEW_GRAMMAR_CANARY_REQUIRED,
        "schema_changed": SCHEMA_CHANGED,
        "do_not_execute_automatically": True,
        "next_action": "HUMAN REVIEW",
        "real_consolidation_executed": False,
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
    }
    header = {
        "result": "PASS" if pass_gate else "FAIL",
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_consolidation_calls": REAL_CONSOLIDATION_CALLS,
        "real_window_calls": REAL_WINDOW_CALLS,
        "a34_status": A34_STATUS_PRESERVED,
        "a35_status": A35_STATUS_PRESERVED,
        "a35_request": A35_REQUEST_ID,
        "a35_grammar_accepted": "YES" if A35_GRAMMAR_ACCEPTED else "NO",
        "a35_transport_parse": replay.get("structured_parse"),
        "a35_root_validator_violations": failures["root_contract_violations"],
        "a35_cascade_violations": failures["cascade_failures"],
        "drop_root_cause": "PROMPT_MACHINE_ENUM_AMBIGUITY + SCHEMA_UNDERCONSTRAINED",
        "drop_field_class": DROP_REASON_CLASS,
        "a35_drop_prose": A35_DROP_PROSE,
        "canonical_drop_token": CANONICAL_DROP_TOKEN,
        "drop_only_counterfactual": counterfactual.get("result"),
        "keep_vs_link_related": (
            "KEEP was semantically valid; LINK_RELATED was not mandatory"
        ),
        "link_related_contract": LINK_RELATED_CONTRACT,
        "repetition_finding": REPETITION_REQUIREMENT,
        "fixture_overconstrained": "YES" if FIXTURE_OVERCONSTRAINED else "NO",
        "selected_disposition_model": SELECTED_DISPOSITION_MODEL,
        "old_transport": OLD_TRANSPORT_VERSION,
        "next_transport": NEXT_TRANSPORT_VERSION,
        "old_schema_raw_adapted": f"{A34_SCHEMA_RAW} / {A34_SCHEMA_ADAPTED}",
        "next_schema_raw_adapted": f"{NEXT_SCHEMA_RAW_BYTES} / {NEXT_SCHEMA_ADAPTED_BYTES}",
        "next_schema_hash": NEXT_SCHEMA_HASH,
        "schema_changed": "YES" if SCHEMA_CHANGED else "NO",
        "new_grammar_canary_required": "YES" if NEW_GRAMMAR_CANARY_REQUIRED else "NO",
        "old_prompt": OLD_PROMPT_VERSION,
        "next_prompt": NEXT_PROMPT_VERSION,
        "model": MODEL,
        "thinking": THINKING_MODE,
        "thinking_policy": THINKING_POLICY,
        "production_max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
        "one_global_call": "PRESERVED",
        "architecture": PROPOSED_ARCHITECTURE,
        "idea_disposition_coverage_required": "100%",
        "silent_drops_allowed": 0,
        "relation_policy": f"{RELATION_POLICY_OPTION} — NON-AUTHORITATIVE HINTS",
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "tests": tests,
        "baseline_tests": baseline_tests,
        "new_failures": "pending" if "offline A.36" == tests else "0",
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
        "readiness": READINESS_DECISION,
        "next_action": "HUMAN REVIEW",
        "identity_ok": identity.get("ok"),
        "v10_unchanged": v10_unchanged,
        "v11_matches": v11_matches,
        "fakeai_ok": fakeai.get("ok"),
        "reproduced_a35_failure": replay.get("reproduced_a35_failure"),
        "mode": MODE,
        "a35_facts": {
            "authorized_calls": A35_AUTHORIZED_CALLS,
            "actual_calls": A35_ACTUAL_CALLS,
            "successful_calls": A35_SUCCESSFUL_CALLS,
            "retries": A35_RETRIES,
            "pastoral_data_sent": False,
            "http": A35_HTTP_STATUS,
            "finish": A35_FINISH_REASON,
            "thinking_tokens": A35_THINKING_TOKENS,
            "cost_usd": A35_COST_USD,
            "elapsed_seconds": A35_ELAPSED_SECONDS,
            "canary_max_output": 2048,
            "production_max_output": PRODUCTION_MAX_OUTPUT_TOKENS,
            "context_budget": {
                "chars": PRODUCTION_NORMALIZED_CHARS,
                "local_tokens": PRODUCTION_LOCAL_ESTIMATE_TOKENS,
                "provider_adjusted": PRODUCTION_PROVIDER_ADJUSTED_TOKENS,
            },
        },
        "root_causes": root_causes(),
        "source_map_present": source_map_present,
        "real_provider_calls_this_phase": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "real_consolidation_calls": REAL_CONSOLIDATION_CALLS,
    }
    forensics = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "identity": identity,
        "replay": {
            key: replay.get(key)
            for key in (
                "structured_parse",
                "decoder",
                "handle_validation",
                "idea_disposition_coverage",
                "silent_drops",
                "traceability",
                "global_validator",
                "canonical_reconstruction",
                "semantic_review",
                "validator_errors",
                "root_validator_violations",
                "cascade_validator_violations",
                "drop_row",
                "inventory",
                "reproduced_a35_failure",
                "historical_status_unchanged",
                "repaired",
            )
        },
        "failure_inventory": failures,
        "a35_status": "FAIL unchanged",
        "request_id": A35_REQUEST_ID,
    }
    return {
        "header": header,
        "forensics": forensics,
        "dispositions": dispositions,
        "drop_contract": drop,
        "repetition": repetition,
        "fixture_review": fixture_review,
        "redesign": redesign,
        "schema": {
            **_public_schema(v11_schema),
            "version": NEXT_TRANSPORT_VERSION,
            "raw_bytes": v11_schema.get("raw_bytes"),
            "adapted_bytes": v11_schema.get("adapted_bytes"),
            "hash": v11_schema.get("hash"),
            "delta_vs_1_0": {
                "raw_bytes": v11_schema.get("raw_delta_bytes"),
                "adapted_bytes": v11_schema.get("adapted_delta_bytes"),
                "raw_percent": v11_schema.get("raw_delta_percent"),
                "adapted_percent": v11_schema.get("adapted_delta_percent"),
            },
            "prompt": prompt_new,
        },
        "next_fixture": next_fixture,
        "counterfactual": {
            key: counterfactual.get(key)
            for key in counterfactual
            if key != "transport"
        },
        "fakeai": fakeai,
        "readiness": readiness,
        "test_delta": {},
        "replay_full": replay,
    }


__all__ = ["build_bundle"]
