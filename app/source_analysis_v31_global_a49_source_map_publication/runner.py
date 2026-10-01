"""Assemble le dossier A.49. 0 provider. Publication atomique du candidat A.48."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.writer import source_map_path
from app.source_analysis_v31_global_a47_contract_forensics.evidence import (
    protected_a47_historical_hashes,
)
from app.source_analysis_v31_global_a48_offline_revalidation.replay import (
    replay_a46_under_corrected_contract,
)
from app.source_analysis_v2_grammar_canary.writer import write_bytes_atomic
from app.source_analysis_v31_global_a49_source_map_publication.constants import (
    A34_STATUS_PRESERVED,
    A35_STATUS_PRESERVED,
    A36_STATUS_PRESERVED,
    A37_STATUS_PRESERVED,
    A38_STATUS_PRESERVED,
    A39_STATUS_PRESERVED,
    A40_STATUS_PRESERVED,
    A41_FULL_SUITE_NOTE,
    A41_STATUS_PRESERVED,
    A42_STATUS_PRESERVED,
    A43_STATUS_PRESERVED,
    A44_STATUS_PRESERVED,
    A45_REQUEST_HASH,
    A45_STATUS_PRESERVED,
    A46_COST_USD,
    A46_INTENT_LENGTH,
    A46_STATUS_PRESERVED,
    A47_STATUS_PRESERVED,
    A48_STATUS_PRESERVED,
    A49_COST_USD,
    BYTE_IDENTITY_EXACT,
    EXPECTED_IDEA,
    FROZEN_LOCAL_ARCHITECTURE,
    FUTURE_PROMPT,
    GLOBAL_INTENT_MAX_CHARS,
    HISTORICAL_PROMPT,
    LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
    MODE,
    MODEL,
    NEXT_ACTION,
    PHASE,
    PROJECT_NAME,
    PROVIDER,
    PUBLICATION_MODE_CONFLICT,
    PUBLICATION_MODE_IDENTICAL,
    PUBLICATION_MODE_NEW,
    RELATION_QUALITY_TECHNICAL_DEBT,
    SCHEMA_ADAPTED_BYTES,
    SCHEMA_HASH,
    SCHEMA_RAW_BYTES,
    SCHEMA_VERSION,
    THINKING_MODE,
    TRANSPORT_VERSION,
)
from app.source_analysis_v31_global_a49_source_map_publication.gates import (
    evaluate_prepublication_gate,
    locate_validated_candidate,
)
from app.source_analysis_v31_global_a49_source_map_publication.identity import (
    file_identity,
)
from app.source_analysis_v31_global_a49_source_map_publication.offline import (
    assert_analyzer_not_wired,
    assert_no_phase4_artifacts,
    assert_offline_package,
)
from app.source_analysis_v31_global_a49_source_map_publication.paths import (
    a48_candidate_path,
    production_source_map_path,
)
from app.source_analysis_v31_global_a49_source_map_publication.publish import (
    publish_exact_bytes,
)
from app.source_analysis_v31_global_a49_source_map_publication.reload import (
    reload_published,
)
from app.source_analysis_v31_global_a49_source_map_publication.state_update import (
    load_state,
    update_project_state,
    update_report_json,
)
from app.source_analysis_v31_global_reuse_output.prompt_v301 import prompt_v301_bundle
from app.source_analysis_v31_global_reuse_output.transport_v30 import measure_global_schema_v30


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def ensure_a48_candidate(
    project_name: str = PROJECT_NAME, *, sortie_dir: Path | None = None
) -> Path:
    path = a48_candidate_path(project_name, sortie_dir=sortie_dir)
    if path.is_file():
        return path
    replay = replay_a46_under_corrected_contract(project_name, sortie_dir=sortie_dir)
    candidate = replay.get("candidate_payload") or {}
    if not isinstance(candidate, dict) or not candidate:
        raise FileNotFoundError(
            "Candidat A.48 absent et reconstruction vide : " + str(path)
        )
    write_bytes_atomic(path, dict(candidate))
    return locate_validated_candidate(project_name, sortie_dir=sortie_dir)


def build_bundle(
    project_name: str = PROJECT_NAME,
    *,
    sortie_dir: Path | None = None,
    tests: str = "offline A.49",
    test_delta: dict[str, Any] | None = None,
    pastoral_contract: bool = True,
    publication_eligible_override: str | None = None,
    update_state: bool = True,
) -> dict[str, Any]:
    assert_offline_package()
    assert_analyzer_not_wired()
    assert_no_phase4_artifacts()
    candidate_path = ensure_a48_candidate(project_name, sortie_dir=sortie_dir)
    candidate_bytes = candidate_path.read_bytes()
    candidate_identity = file_identity(candidate_path)
    gate = evaluate_prepublication_gate(
        candidate_bytes,
        project_name=project_name,
        sortie_dir=sortie_dir,
        pastoral_contract=pastoral_contract,
        publication_eligible=publication_eligible_override,
    )
    target = production_source_map_path(project_name, sortie_dir=sortie_dir)
    publication = publish_exact_bytes(
        target,
        candidate_bytes,
        authorized=bool(gate["authorized"]),
    )
    conflict = publication.get("mode") == PUBLICATION_MODE_CONFLICT
    published_ok = bool(publication.get("published")) and not conflict
    transcript = None
    if published_ok and pastoral_contract:
        from app.source_analysis_execution_strategy.windows import load_clean_transcript

        transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    reload = (
        reload_published(
            target,
            candidate_bytes=candidate_bytes,
            transcript=transcript,
        )
        if published_ok
        else {
            "json_parse": "FAIL",
            "model_load": "FAIL",
            "canonical_validation": "FAIL",
            "structural_scan": "FAIL",
            "traceability": "FAIL",
            "deterministic_identity": "FAIL",
            "byte_identity": "NOT_PUBLISHED",
            "published_sha256": "",
            "published_bytes": 0,
            "inventory": {},
            "idea_count": 0,
            "exists": target.is_file(),
            "path": str(target),
        }
    )
    new_failures = int((test_delta or {}).get("new_failure_count") or 0)
    tests_ok = new_failures == 0
    post_ok = (
        published_ok
        and reload.get("json_parse") == "PASS"
        and reload.get("model_load") == "PASS"
        and reload.get("canonical_validation") == "PASS"
        and reload.get("structural_scan") == "PASS"
        and reload.get("traceability") == "PASS"
        and reload.get("deterministic_identity") == "PASS"
        and reload.get("byte_identity") in {BYTE_IDENTITY_EXACT, "CANONICAL_SEMANTIC_IDENTITY"}
    )
    freeze = post_ok and tests_ok and not conflict
    if conflict:
        result = "BLOCKED"
    elif not gate["authorized"]:
        result = "BLOCKED"
    elif published_ok and not post_ok:
        result = "FAIL"
    elif freeze:
        result = "PASS"
    else:
        result = "PARTIAL"
    source_map_status = "PUBLISHED" if post_ok else "NOT PUBLISHED"
    phase_3b = "COMPLETE" if freeze else "INCOMPLETE"
    inventory = reload.get("inventory") or gate.get("inventory") or {}
    payload = candidate_identity.get("payload") or {}
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    prompt_in_artifact = str(analysis.get("prompt_version") or HISTORICAL_PROMPT)
    schema_in_artifact = str(analysis.get("schema_version") or SCHEMA_VERSION)
    signature = str(analysis.get("signature") or candidate_identity.get("sha256") or "")
    coverage = 0.0
    stats_block = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    try:
        coverage = float(stats_block.get("source_coverage_ratio") or 0.0)
    except (TypeError, ValueError):
        coverage = 0.0
    state_block: dict[str, Any] = {}
    report_file = None
    if freeze and update_state:
        inventory_for_state = dict(inventory)
        inventory_for_state["source_coverage_ratio"] = coverage
        state_block = update_project_state(
            project_name,
            source_map_path=target,
            sha256=str(reload.get("published_sha256") or candidate_identity.get("sha256") or ""),
            stats=inventory_for_state,
            signature=signature,
            prompt_version=prompt_in_artifact,
            schema_version=schema_in_artifact,
            sortie_dir=sortie_dir,
            frozen=True,
        )
        report_file = update_report_json(
            project_name,
            state=load_state(project_name, sortie_dir=sortie_dir),
            sortie_dir=sortie_dir,
        )
    measured = measure_global_schema_v30()
    prompt_next = prompt_v301_bundle()
    header = {
        "result": result,
        "phase": PHASE,
        "mode": MODE,
        "real_provider_calls": 0,
        "real_anthropic_calls": 0,
        "real_openai_calls": 0,
        "a48_status": A48_STATUS_PRESERVED,
        "publication_eligible": gate.get("publication_eligible"),
        "a46_raw_response_unchanged": "YES" if gate.get("raw_identity", {}).get("ok") else "NO",
        "validated_candidate_path": str(candidate_path),
        "validated_candidate_sha256": candidate_identity.get("sha256"),
        "validated_candidate_bytes": candidate_identity.get("utf8_bytes"),
        "pre_publication_canonical_validation": (gate.get("validation") or {}).get(
            "canonical_validation"
        ),
        "pre_publication_structural_scan": (gate.get("validation") or {}).get(
            "structural_scan"
        ),
        "pre_publication_traceability": (gate.get("validation") or {}).get("traceability"),
        "pre_publication_idea_accountability": (gate.get("accountability") or {}).get(
            "label"
        ),
        "target": str(target),
        "target_preexisted": "YES" if publication.get("preexisted") else "NO",
        "target_conflict": "YES" if publication.get("conflict") else "NO",
        "publication_mode": publication.get("mode"),
        "atomic_publication": publication.get("atomic_publication"),
        "published_sha256": reload.get("published_sha256") or "",
        "published_bytes": reload.get("published_bytes") or 0,
        "byte_identity": reload.get("byte_identity") or publication.get("byte_identity"),
        "post_write_json_parse": reload.get("json_parse"),
        "post_write_model_load": reload.get("model_load"),
        "post_write_canonical_validation": reload.get("canonical_validation"),
        "post_write_structural_scan": reload.get("structural_scan"),
        "post_write_traceability": reload.get("traceability"),
        "post_write_deterministic_identity": reload.get("deterministic_identity"),
        "published_topics": inventory.get("topics"),
        "published_ideas": inventory.get("ideas"),
        "published_examples": inventory.get("examples"),
        "published_references": inventory.get("references"),
        "published_uncertainties": inventory.get("uncertainties"),
        "published_repetitions": inventory.get("repetitions"),
        "global_intent_length": A46_INTENT_LENGTH,
        "global_intent_limit": GLOBAL_INTENT_MAX_CHARS,
        "historical_a46_cost": A46_COST_USD,
        "a49_cost": A49_COST_USD,
        "future_prompt": FUTURE_PROMPT,
        "transport": TRANSPORT_VERSION,
        "global_consolidation_core_architecture_functionally_frozen": (
            "YES" if freeze else "NO"
        ),
        "local_extraction_functionally_frozen": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "relation_quality_technical_debt": RELATION_QUALITY_TECHNICAL_DEBT,
        "tests": tests,
        "new_failures": (test_delta or {}).get("new_failure_count", "pending"),
        "source_map": source_map_status,
        "source_map_path": str(target) if post_ok else "",
        "source_map_sha256": reload.get("published_sha256") if post_ok else "",
        "phase_3b": phase_3b,
        "phase_3b_functionally_frozen": "YES" if freeze else "NO",
        "ready_for_phase_4_editorial_planner_design": "YES" if freeze else "NO",
        "next_action": NEXT_ACTION,
        "schema_raw": SCHEMA_RAW_BYTES,
        "schema_adapted": SCHEMA_ADAPTED_BYTES,
        "schema_hash": SCHEMA_HASH,
        "schema_identity_unchanged": measured.get("hash") == SCHEMA_HASH,
        "historical_request_hash": A45_REQUEST_HASH,
        "future_request_hash": (
            "NOT_REUSED — future projects construct their own request "
            "identity under prompt 3.0.1"
        ),
        "future_prompt_hash": prompt_next.get("combined_sha256"),
        "provider": PROVIDER,
        "model": MODEL,
        "thinking": THINKING_MODE,
        "expected_ideas": EXPECTED_IDEA,
        "production_source_map_helper": str(source_map_path(project_name, sortie_dir=sortie_dir)),
    }
    freeze_audit = {
        "PHASE_3B": phase_3b,
        "PHASE_3B_FUNCTIONALLY_FROZEN": "YES" if freeze else "NO",
        "GLOBAL_CONSOLIDATION_CORE_ARCHITECTURE_FUNCTIONALLY_FROZEN": (
            "YES" if freeze else "NO"
        ),
        "LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "RELATION_QUALITY_TECHNICAL_DEBT": RELATION_QUALITY_TECHNICAL_DEBT,
        "frozen_local_architecture": FROZEN_LOCAL_ARCHITECTURE,
        "future_production_global_consolidation": {
            "prompt": FUTURE_PROMPT,
            "transport": TRANSPORT_VERSION,
            "intent_max": GLOBAL_INTENT_MAX_CHARS,
            "thinking": THINKING_MODE,
            "model": MODEL,
        },
        "historical_a46_prompt": HISTORICAL_PROMPT,
        "do_not_reuse_pastoral_request_hash": True,
        "historical_request_hash": A45_REQUEST_HASH,
        "a41_full_suite_note": A41_FULL_SUITE_NOTE,
        "meaning": (
            "No more architecture changes to Phase 3B without a concrete "
            "regression or new requirement. Technical debt remains."
        ),
        "editorial_planner_not_started": True,
    }
    readiness = {
        "READY_FOR_PHASE_4_EDITORIAL_PLANNER_DESIGN": "YES" if freeze else "NO",
        "SOURCE_MAP": source_map_status,
        "PHASE_3B": phase_3b,
        "PHASE_3B_FUNCTIONALLY_FROZEN": "YES" if freeze else "NO",
        "GLOBAL_CONSOLIDATION_CORE_ARCHITECTURE_FUNCTIONALLY_FROZEN": (
            "YES" if freeze else "NO"
        ),
        "LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN": LOCAL_EXTRACTION_FUNCTIONALLY_FROZEN,
        "RELATION_QUALITY_TECHNICAL_DEBT": RELATION_QUALITY_TECHNICAL_DEBT,
        "A46_HISTORICAL_STATUS": A46_STATUS_PRESERVED,
        "A47_STATUS": A47_STATUS_PRESERVED,
        "A48_STATUS": A48_STATUS_PRESERVED,
        "A49_COST": A49_COST_USD,
        "HISTORICAL_A46_COST": A46_COST_USD,
        "do_not_call_provider": True,
        "do_not_start_phase_4": True,
        "next_action": NEXT_ACTION,
        "historical": {
            "A.34": A34_STATUS_PRESERVED,
            "A.35": A35_STATUS_PRESERVED,
            "A.36": A36_STATUS_PRESERVED,
            "A.37": A37_STATUS_PRESERVED,
            "A.38": A38_STATUS_PRESERVED,
            "A.39": A39_STATUS_PRESERVED,
            "A.40": A40_STATUS_PRESERVED,
            "A.41": A41_STATUS_PRESERVED,
            "A.42": A42_STATUS_PRESERVED,
            "A.43": A43_STATUS_PRESERVED,
            "A.44": A44_STATUS_PRESERVED,
            "A.45": A45_STATUS_PRESERVED,
            "A.46": A46_STATUS_PRESERVED,
            "A.47": A47_STATUS_PRESERVED,
            "A.48": A48_STATUS_PRESERVED,
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "header": header,
        "gate": gate,
        "candidate_identity": candidate_identity,
        "publication": publication,
        "reload": reload,
        "freeze": freeze_audit,
        "readiness": readiness,
        "state": state_block,
        "report_json": str(report_file) if report_file else "",
        "protected_historical": protected_a47_historical_hashes(
            project_name, sortie_dir=sortie_dir
        ),
        "test_delta": test_delta or {},
        "result": result,
        "published": post_ok,
        "candidate_path": str(candidate_path),
        "publication_modes": {
            "new": PUBLICATION_MODE_NEW,
            "identical": PUBLICATION_MODE_IDENTICAL,
            "conflict": PUBLICATION_MODE_CONFLICT,
        },
    }


__all__ = ["build_bundle", "ensure_a48_candidate"]
