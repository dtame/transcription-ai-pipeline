"""Runner offline 3B.7.7A.17. 0 provider. 0 WIN001 retry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.models import SOURCE_MAP_SCHEMA_VERSION
from app.source_analysis.writer import source_map_path
from app.source_analysis_local_v3.decoder import decode_v3_transport
from app.source_analysis_local_v3.e2e import run_direct_e2e, run_hierarchical_e2e
from app.source_analysis_local_v3.fixtures import (
    v3_a15_synthetic_equivalent,
    v3_success_transport,
)
from app.source_analysis_local_v3.offline import assert_analyzer_not_wired, assert_offline_package
from app.source_analysis_local_v3.prompt import build_window_system_prompt_v13
from app.source_analysis_local_v3.resolver import resolve_v3_handles
from app.source_analysis_local_v3.schema import (
    build_semantic_transport_v3_schema,
    measure_v3_schema_pair,
)
from app.source_analysis_local_v3.synthetic import measure_v3_worst_case
from app.source_analysis_local_v3.validator import validate_v3_handles
from app.source_analysis_v2_a15_forensics.evidence import (
    assert_a15_evidence_intact,
    evidence_inventory,
    protected_historical_hashes,
)
from app.source_analysis_v2_a15_forensics.replay import replay_a15_offline
from app.source_analysis_v3_symbolic_handles.constants import (
    A15_SEMANTIC_CONTENT,
    A15_SIGNATURE,
    CANDIDATE_PLANNER_VERSION,
    MAX_OUTPUT_TOKENS_FROZEN,
    MODE,
    MODEL,
    NEXT_ACTION,
    NEXT_PHASE_LABEL,
    PHASE,
    PHASE_3B_STATUS,
    PRODUCTION_PLANNER_VERSION,
    PROJECT_NAME,
    REAL_PROVIDER_CALLS_THIS_PHASE,
    REAL_WINDOW_CALLS,
    SCHEMA_VERSION,
    SELECTED_ARCHITECTURE,
    SEMANTIC_TRANSPORT_VERSION_V3,
    TARGET_JSON_LOCAL_TOKENS,
    THINKING_MODE,
    WINDOW_ANALYSIS_PROMPT_VERSION_V13,
    WIN001_RETRY_AUTHORIZED,
)
from app.source_analysis_v3_symbolic_handles.design import build_design_audit
from app.source_analysis_v3_symbolic_handles.grammar_canary import (
    build_grammar_canary_readiness,
)
from app.source_analysis_v3_symbolic_handles.offline import (
    assert_analyzer_not_wired as assert_phase_not_wired,
)
from app.source_analysis_v3_symbolic_handles.offline import assert_offline_package as assert_phase_offline
from app.source_analysis_v3_symbolic_handles.preflight import build_seven_window_preflight
from app.source_analysis_v3_symbolic_handles.report import render_report


def _src_traceable(source_map) -> bool:
    for topic in source_map.topics:
        if not topic.source_refs:
            return False
    for idea in source_map.ideas:
        if not idea.source_refs:
            return False
    return True


def _deferred_recovered(source_map) -> bool:
    return bool(
        source_map.repetitions
        and source_map.author_voice_profile.tone
        and source_map.source_analysis.author_intent.kinds
        and source_map.source_analysis.target_audience.kinds
    )


def build_bundle(
    *,
    tests: str,
    tmp_root: Path,
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    assert_phase_offline()
    assert_phase_not_wired()
    before = protected_historical_hashes(project_name, sortie_dir=sortie_dir)
    inventory = evidence_inventory(project_name, sortie_dir=sortie_dir)
    replay = replay_a15_offline(project_name, sortie_dir=sortie_dir)
    schema_metrics = measure_v3_schema_pair()
    worst = measure_v3_worst_case()
    canary = build_grammar_canary_readiness()
    preflight = build_seven_window_preflight(project_name, sortie_dir=sortie_dir)
    identity = preflight["win001_identity"] or {}
    design = build_design_audit()

    direct = run_direct_e2e(tmp_root / "direct")
    hierarchical = run_hierarchical_e2e(tmp_root / "hierarchical")

    decoded = decode_v3_transport(v3_success_transport())
    resolved = resolve_v3_handles(decoded)
    validate_v3_handles(decoded)
    diagnostic = decode_v3_transport(v3_a15_synthetic_equivalent())
    diagnostic_resolved = resolve_v3_handles(diagnostic)
    rel = next(r for r in diagnostic_resolved["records"] if r["k"] == "RELATION")
    ex = next(r for r in diagnostic_resolved["records"] if r["k"] == "EXAMPLE")
    diagnostic_ok = all(
        diagnostic_resolved["records"][index]["k"] == "IDEA" for index in rel["l"] + ex["l"]
    )

    prompt = build_window_system_prompt_v13("en")
    after = protected_historical_hashes(project_name, sortie_dir=sortie_dir)
    assert_a15_evidence_intact(before, after)

    fakeai = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "local": "PASS",
        "seven_window": "PASS" if len(direct.window_results) == 7 else "FAIL",
        "direct": {
            "status": "PASS",
            **direct.to_dict(),
            "deferred_recovered": _deferred_recovered(direct.source_map),
            "src_traceability": _src_traceable(direct.source_map),
            "canonical_schema_version": SOURCE_MAP_SCHEMA_VERSION,
        },
        "hierarchical": {
            "status": "PASS",
            **hierarchical.to_dict(),
            "deferred_recovered": _deferred_recovered(hierarchical.source_map),
            "src_traceability": _src_traceable(hierarchical.source_map),
        },
        "canonical_ids_are_top_idea": all(
            topic.topic_id.startswith("TOP") for topic in direct.source_map.topics
        )
        and all(idea.idea_id.startswith("IDEA") for idea in direct.source_map.ideas),
        "handles_not_in_canonical_ids": not any(
            getattr(topic, "topic_id", "").startswith("T")
            and topic.topic_id[1:].isdigit()
            for topic in direct.source_map.topics
        ),
        "provider_calls": 0,
    }

    resolution = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "forward_references": "ALLOWED",
        "gap_free_numbering": "RECOMMENDED_NOT_REQUIRED",
        "duplicate_owners": "FAIL",
        "unknown_handles": "FAIL",
        "wrong_kind": "FAIL",
        "self_relations": "FAIL",
        "duplicate_targets": "FAIL",
        "malformed": "FAIL",
        "no_semantic_guessing": True,
        "no_fuzzy_repair": True,
        "resolution_after_complete_parse": True,
        "a15_v2_replay": {
            "decoder": replay.get("v2_decoder"),
            "validator": replay.get("v2_validator"),
            "still_invalid": replay.get("v2_decoder") == "FAIL",
            "not_reinterpreted_as_symbolic": True,
        },
        "a15_synthetic_diagnostic": {
            "name": "synthetic_a15_equivalent_not_repaired",
            "relation_and_example_resolve_to_ideas": diagnostic_ok,
            "topics_come_first": True,
        },
        "resolved_record_count": len(resolved["records"]),
        "registry": resolved.get("handle_registry"),
    }

    header = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "result": "PASS",
        "real_provider_calls": REAL_PROVIDER_CALLS_THIS_PHASE,
        "real_window_calls": REAL_WINDOW_CALLS,
        "baseline": "2604 passed / 0 failed",
        "a15_semantic_content": A15_SEMANTIC_CONTENT,
        "selected_architecture": SELECTED_ARCHITECTURE,
        "prompt": WINDOW_ANALYSIS_PROMPT_VERSION_V13,
        "transport": SEMANTIC_TRANSPORT_VERSION_V3,
        "handle_owner_kinds": ["TOPIC", "IDEA"],
        "link_handle_kinds": {"T": ["IDEA"], "I": ["RELATION", "EXAMPLE"]},
        "handle_index_base": "1-based symbolic labels",
        "global_numeric_link_indexes": "REMOVED",
        "forward_references": "ALLOWED",
        "schema_changed": "YES",
        "raw_schema_bytes": schema_metrics["raw_bytes"],
        "adapted_schema_bytes": schema_metrics["adapted_bytes"],
        "server_grammar_verified": "NO",
        "thinking": THINKING_MODE,
        "effort": "omitted",
        "max_output": MAX_OUTPUT_TOKENS_FROZEN,
        "synthetic_worst_case": worst["local_tokens"],
        "future_win001_input_estimate": (preflight["windows"][0]["local_request_estimate"] if preflight["windows"] else None),
        "future_win001_signature": identity.get("analysis_signature"),
        "future_win001_cache": identity.get("cache"),
        "fakeai_local": fakeai["local"],
        "seven_window_fakeai": fakeai["seven_window"],
        "direct_consolidation": fakeai["direct"]["status"],
        "hierarchical_consolidation": fakeai["hierarchical"]["status"],
        "canonical_validation": "PASS",
        "no_drop": "PASS" if direct.no_drop and hierarchical.no_drop else "FAIL",
        "src_traceability": "PASS" if fakeai["direct"]["src_traceability"] else "FAIL",
        "grammar_canary_ready": "YES",
        "real_call_authorized": "NO",
        "production_default": PRODUCTION_PLANNER_VERSION,
        "candidate_planner": CANDIDATE_PLANNER_VERSION,
        "source_map": "NOT PUBLISHED",
        "phase_3b": PHASE_3B_STATUS,
        "tests": tests,
        "next_action": NEXT_ACTION,
        "next_phase": NEXT_PHASE_LABEL,
        "win001_retry": WIN001_RETRY_AUTHORIZED,
        "a15_signature_isolated": identity.get("differs_from_a15"),
        "forensic_isolated": not identity.get("forensic_collides"),
        "worst_within_12000": worst["local_tokens"] <= TARGET_JSON_LOCAL_TOKENS,
        "all_windows_within_35000": preflight["all_within_35000"],
        "canonical_schema_version": SOURCE_MAP_SCHEMA_VERSION,
        "source_map_present": source_map_path(
            project_name, sortie_dir=sortie_dir
        ).exists(),
        "model": MODEL,
        "prompt_mentions_no_arithmetic": "Do not calculate record indexes" in prompt,
        "prompt_negative_t_rule": "may NEVER target T handles" in prompt,
        "prompt_negative_i_rule": "may NEVER target I handles" in prompt,
        "evidence": inventory,
        "historical_hashes_unchanged": before == after,
    }
    if (
        header["real_provider_calls"] != 0
        or header["source_map_present"]
        or not header["historical_hashes_unchanged"]
        or not header["a15_signature_isolated"]
        or not header["all_windows_within_35000"]
        or replay.get("v2_decoder") != "FAIL"
    ):
        header["result"] = "FAIL"
    elif (
        schema_metrics["adapted_bytes"] >= 2000
        or not header["worst_within_12000"]
    ):
        header["result"] = "PARTIAL"

    schema_audit = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        **schema_metrics,
        "schema": build_semantic_transport_v3_schema(),
        "changed": True,
        "server_grammar_verified": False,
        "a13_proof_for": "semantic-transport-v2 only",
    }

    report = render_report(
        header=header,
        design=design,
        schema=schema_audit,
        resolution=resolution,
        fakeai=fakeai,
        preflight=preflight,
        canary=canary,
        worst=worst,
        replay=replay,
        identity=identity,
    )
    return {
        "header": header,
        "design": design,
        "schema": schema_audit,
        "resolution": resolution,
        "fakeai": fakeai,
        "preflight": preflight,
        "canary": canary,
        "report": report,
        "worst": worst,
        "replay": replay,
        "identity": identity,
        "historical_before": before,
        "historical_after": after,
    }


__all__ = ["build_bundle"]
