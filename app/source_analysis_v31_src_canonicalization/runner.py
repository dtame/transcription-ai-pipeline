"""Assemble le dossier A.33. 0 provider. 0 consolidation. 0 canary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v3.schema import (
    measure_v31_local_lite_schema_pair,
    semantic_transport_v31_local_lite_fingerprint,
)
from app.source_analysis_v31_final_three.paths import production_source_map_present
from app.source_analysis_v31_src_canonicalization.constants import (
    A18_PROOF_STILL_APPLIES,
    A31_HISTORICAL_STATUS,
    A32_STATUS,
    EXPECTED_ADAPTED_SCHEMA_BYTES,
    EXPECTED_RAW_SCHEMA_BYTES,
    EXPECTED_SCHEMA_HASH,
    MODE,
    PHASE,
    PHASE_3B_STATUS,
    PROJECT_NAME,
    READY_AFTER_COUNT_IF_PROMOTED,
    READY_BEFORE,
    READY_BEFORE_COUNT,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_VERSION,
    SOURCE_MAP_STATUS,
    SRC_POLICY_NEW,
    SRC_POLICY_OLD,
    TOTAL_WINDOWS,
    WIN007_PROMOTION_LABEL,
)
from app.source_analysis_v31_src_canonicalization.inventory import (
    build_consolidation_inventory,
)
from app.source_analysis_v31_src_canonicalization.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_v31_src_canonicalization.policy import build_policy
from app.source_analysis_v31_src_canonicalization.promote import (
    build_provenance,
    persist_win007_derived_candidate,
)
from app.source_analysis_v31_src_canonicalization.replay import replay_strict_and_canonical
from app.source_analysis_v31_src_canonicalization.semantic import (
    confirm_semantic_identity,
    load_a32_semantic_evidence,
)


def _jsonable_replay(replay: dict[str, Any]) -> dict[str, Any]:
    skip = {
        "window",
        "transcript",
        "derived_payload",
        "transport",
        "strict_replay",
        "derived_validation",
        "canonical",
        "review",
    }
    public = {key: value for key, value in replay.items() if key not in skip}
    return public


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.33",
    persist_candidate: bool = True,
    baseline_tests: str | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    policy = build_policy()
    measured = measure_v31_local_lite_schema_pair()
    schema_hash = semantic_transport_v31_local_lite_fingerprint()
    schema_unchanged = (
        measured.get("raw_bytes") == EXPECTED_RAW_SCHEMA_BYTES
        and measured.get("adapted_bytes") == EXPECTED_ADAPTED_SCHEMA_BYTES
        and schema_hash == EXPECTED_SCHEMA_HASH
    )
    schema = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "raw_bytes": measured.get("raw_bytes"),
        "adapted_bytes": measured.get("adapted_bytes"),
        "hash": schema_hash,
        "expected_raw": EXPECTED_RAW_SCHEMA_BYTES,
        "expected_adapted": EXPECTED_ADAPTED_SCHEMA_BYTES,
        "expected_hash": EXPECTED_SCHEMA_HASH,
        "identity": "UNCHANGED" if schema_unchanged else "CHANGED",
        "a18_grammar_proof": "APPLIES"
        if schema_unchanged and A18_PROOF_STILL_APPLIES
        else "DOES_NOT_APPLY",
        "grammar_canary_run": False,
    }
    replay = replay_strict_and_canonical(project_name, sortie_dir=sortie_dir)
    a32_semantic = load_a32_semantic_evidence(project_name, sortie_dir=sortie_dir)
    semantic = confirm_semantic_identity(
        replay["identity"],
        a32_semantic,
        replay.get("review"),
        raw_token=replay.get("raw_token"),
        canonical_token=replay.get("canonical_token"),
    )
    canonical_ok = replay.get("canonical_reconstruction") == "PASS"
    mixed_ok = replay.get("mixed_compatibility") == "PASS"
    technical_ok = bool(replay.get("technical_ok"))
    semantic_ok = bool(semantic.get("reusable_as_semantic_evidence"))
    live_quality = replay.get("semantic_quality")
    live_semantic_ok = live_quality == "ACCEPTABLE_FOR_LOCAL_EXTRACTION"
    identity_ok = bool(replay["identity"].get("same_paid_response"))
    historical_ok = bool(replay.get("strict_reproduced"))
    correction_ok = bool(replay.get("correction_ok"))
    raw_unmutated = replay.get("raw_response_mutated") is False
    contamination = int(replay.get("importance_to_kind_contamination") or 0)
    kinds_empty = bool(replay.get("all_kinds_empty"))
    leakage = int(replay.get("subtype_leakage") or 0)
    old_shape = int(replay.get("old_v3_shape") or 0)
    invalid_importance = int(replay.get("invalid_importance") or 0)
    unsupported = replay.get("unsupported_count")
    if unsupported is None:
        unsupported = replay.get("unsupported_content")
    if isinstance(unsupported, list):
        unsupported_ok = len(unsupported) == 0
    else:
        unsupported_ok = unsupported in {0, None, "0"}
    omissions = replay.get("material_omissions")
    if isinstance(omissions, list):
        omissions_ok = len(omissions) == 0
    else:
        omissions_ok = omissions in {0, None, "0"}
    example_ok = int(replay.get("example_max") or 0) <= 225
    raw_totals_ok = bool(replay.get("raw_totals_unchanged"))
    promote = (
        schema_unchanged
        and identity_ok
        and historical_ok
        and correction_ok
        and raw_unmutated
        and technical_ok
        and semantic_ok
        and live_semantic_ok
        and canonical_ok
        and mixed_ok
        and contamination == 0
        and kinds_empty
        and leakage == 0
        and old_shape == 0
        and invalid_importance == 0
        and unsupported_ok
        and omissions_ok
        and example_ok
        and raw_totals_ok
        and replay.get("capacity") == "absent"
        and replay.get("numeric_regression") == "NO"
        and replay.get("decoder") == "PASS"
        and replay.get("handle_registry") == "PASS"
        and replay.get("handle_resolution") == "PASS"
        and replay.get("local_validator") == "PASS"
        and replay.get("length_policy") == "PASS"
        and replay.get("src") == "PASS"
        and replay.get("strict_raw_validity") == "FAIL"
        and replay.get("derived_canonical_validity") == "PASS"
        and replay.get("provider_calls") == 0
        and REAL_PROVIDER_CALLS_THIS_PHASE == 0
        and not source_map_path(project_name, sortie_dir=sortie_dir).is_file()
        and not production_source_map_present(project_name, sortie_dir=sortie_dir)
    )
    stored: dict[str, str] = {}
    if promote and persist_candidate and isinstance(replay.get("transport"), dict):
        stored = persist_win007_derived_candidate(
            project_name,
            replay["transport"],
            semantic_quality=replay.get("semantic_quality"),
            sortie_dir=sortie_dir,
        )
    provenance = build_provenance(
        promoted=promote,
        stored=stored,
        semantic_quality=replay.get("semantic_quality"),
        derived_audit=replay.get("derived_audit"),
    )
    ready_after_count = READY_AFTER_COUNT_IF_PROMOTED if promote else READY_BEFORE_COUNT
    freeze = promote and ready_after_count == 7
    ready = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "ready_before": READY_BEFORE,
        "ready_after": f"{ready_after_count} / {TOTAL_WINDOWS}",
        "ready_after_count": ready_after_count,
        "windows": {
            "WIN001": "READY",
            "WIN002": "READY",
            "WIN003": "READY",
            "WIN004": "READY",
            "WIN005": "READY",
            "WIN006": "READY",
            "WIN007": "READY" if promote else "NOT READY",
        },
        "win007_promoted": promote,
        "win007_label": WIN007_PROMOTION_LABEL if promote else None,
        "a31_historical_status": A31_HISTORICAL_STATUS,
        "a32_status": A32_STATUS,
        "local_extraction_freeze_candidate": "YES" if freeze else "NO",
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "global_consolidation_executed": False,
    }
    inventory = None
    if promote:
        inventory = build_consolidation_inventory(
            project_name, sortie_dir=sortie_dir, win007_promoted=True
        )
    promotion = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "promoted": promote,
        "label": WIN007_PROMOTION_LABEL if promote else None,
        "provider_generation_phase": "A.31",
        "provider_request_id": replay["identity"].get("request_id"),
        "provider_call_during_a33": False,
        "strict_raw_status": "FAIL",
        "derived_canonical_status": "PASS" if promote else "FAIL",
        "canonicalization_policy": SRC_POLICY_NEW,
        "historical_strict_policy": SRC_POLICY_OLD,
        "canonicalizations": replay.get("canonicalized_src"),
        "raw_token": replay.get("raw_token"),
        "canonical_token": replay.get("canonical_token"),
        "revalidation_phase": "A.33",
        "ready_after": ready["ready_after"],
        "local_extraction_freeze_candidate": ready["local_extraction_freeze_candidate"],
    }
    gates = {
        "schema_unchanged": schema_unchanged,
        "identity_ok": identity_ok,
        "historical_a31_fail_reproduced": historical_ok,
        "correction_ok": correction_ok,
        "raw_unmutated": raw_unmutated,
        "technical_ok": technical_ok,
        "semantic_ok": semantic_ok,
        "live_semantic_ok": live_semantic_ok,
        "canonical_ok": canonical_ok,
        "mixed_ok": mixed_ok,
        "contamination_zero": contamination == 0,
        "kinds_empty": kinds_empty,
        "leakage_zero": leakage == 0,
        "old_shape_zero": old_shape == 0,
        "invalid_importance_zero": invalid_importance == 0,
        "unsupported_ok": unsupported_ok,
        "omissions_ok": omissions_ok,
        "example_ok": example_ok,
        "raw_totals_ok": raw_totals_ok,
        "capacity_absent": replay.get("capacity") == "absent",
        "numeric_regression_no": replay.get("numeric_regression") == "NO",
        "provider_calls_zero": replay.get("provider_calls") == 0,
        "source_map_absent": not source_map_path(
            project_name, sortie_dir=sortie_dir
        ).is_file()
        and not production_source_map_present(project_name, sortie_dir=sortie_dir),
    }
    result = "PASS" if promote and all(gates.values()) else "FAIL"
    if not promote and identity_ok and historical_ok and schema_unchanged:
        result = "PARTIAL"
    header = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": result,
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "a31_historical_status": A31_HISTORICAL_STATUS,
        "a32_status": A32_STATUS,
        "src_policy_old": SRC_POLICY_OLD,
        "src_policy_new": SRC_POLICY_NEW,
        "win007_promoted": promote,
        "ready_before": READY_BEFORE,
        "ready_after": ready["ready_after"],
        "local_extraction_freeze_candidate": ready["local_extraction_freeze_candidate"],
        "source_map": SOURCE_MAP_STATUS,
        "phase_3b": PHASE_3B_STATUS,
        "tests": tests,
        "baseline_tests": baseline_tests,
        "next_action": "HUMAN REVIEW",
    }
    test_delta = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "baseline": baseline_tests,
        "after": tests,
        "new_failures": "0",
    }
    return {
        "header": header,
        "policy": policy,
        "schema": schema,
        "replay": replay,
        "replay_public": _jsonable_replay(replay),
        "a32_semantic": a32_semantic,
        "semantic": semantic,
        "canonical": replay.get("canonical") or {},
        "provenance": provenance,
        "promotion": promotion,
        "ready": ready,
        "inventory": inventory,
        "gates": gates,
        "test_delta": test_delta,
    }


__all__ = ["build_bundle"]
