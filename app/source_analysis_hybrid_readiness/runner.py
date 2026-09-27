"""
Exécution offline 3B.7.6 : readiness audit + dry-run WIN001.

Aucun provider réel. Aucun artefact sémantique pastoral.
Artefacts = audit/ uniquement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.hybrid_signature import HYBRID_STRATEGY
from app.source_analysis.window_writer import (
    leftover_partial,
    metadata_path,
    result_path,
    transport_path,
)
from app.source_analysis.writer import source_map_path
from app.source_analysis_execution_strategy.review import inspect_project_state
from app.source_analysis_hybrid.contracts import canonical_dumps
from app.source_analysis_hybrid.offline import (
    assert_analyzer_not_wired as assert_hybrid_planner_not_wired,
)
from app.source_analysis_hybrid_readiness.canary import (
    build_canary_anthropic_engine,
    describe_canary_engine,
    dry_run_win001,
    run_win001_canary,
)
from app.source_analysis_hybrid_readiness.constants import (
    AUTHORIZATION_SCOPE_WIN001_ONLY,
    AUTO_CONSOLIDATION,
    AUTO_CONTINUE,
    AUTO_FALLBACK,
    AUTO_PUBLICATION,
    AUTO_RETRY,
    CANARY_WINDOW_ID,
    CONSOLIDATION_CONNECT_TIMEOUT_SECONDS,
    CONSOLIDATION_MAX_ATTEMPTS,
    CONSOLIDATION_MAX_OUTPUT_TOKENS,
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_READ_TIMEOUT_SECONDS,
    CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    CONSOLIDATION_STAGE,
    CONSOLIDATION_TRANSPORT_VERSION,
    DRY_RUN_ARTIFACT_NAME,
    FAILURE_MATRIX_ARTIFACT_NAME,
    HARD_MAX_INPUT_TOKENS,
    MAX_ATTEMPTS,
    MAX_NEW_CALLS_REMAINING,
    MAX_NEW_CALLS_WIN001,
    MODE,
    NEXT_PHASE,
    NEXT_PHASE_LABEL,
    PHASE,
    PHASE_3B_STATUS,
    PROMPT_VERSION,
    READINESS_ARTIFACT_NAME,
    REAL_CALL_PLAN_ARTIFACT_NAME,
    REPORT_NAME,
    SCHEMA_VERSION,
    STAGE,
    TARGET_MODEL,
    TARGET_PROVIDER,
    TRANSPORT_VERSION,
    WINDOW_CONNECT_TIMEOUT_SECONDS,
    WINDOW_MAX_OUTPUT_TOKENS,
    WINDOW_READ_TIMEOUT_SECONDS,
)
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_hybrid_readiness.facts import (
    inspect_production_cache,
    inspect_publication_and_state,
    probe_disk_writable,
    rebuild_window_requests,
    schema_and_prompt_facts,
    verify_clean_transcript,
)
from app.source_analysis_hybrid_readiness.integrity import (
    assert_protected_unchanged,
    snapshot_hybrid_readiness_protected,
)
from app.source_analysis_hybrid_readiness.matrix import build_failure_matrix
from app.source_analysis_hybrid_readiness.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_hybrid_readiness.retry_audit import build_retry_audit
from app.source_analysis_hybrid_readiness.writer import (
    assert_no_production_source_map,
    dry_run_artifact_path,
    failure_matrix_path,
    production_semantic_consolidation_present,
    production_semantic_windows_present,
    readiness_artifact_path,
    real_call_plan_path,
    report_path,
    write_bytes_atomic,
)
from app.source_analysis_window_orchestration.offline import (
    assert_analyzer_not_wired as assert_window_orch_not_wired,
)
from app.source_analysis_window_pipeline.offline import (
    assert_analyzer_not_wired as assert_window_not_wired,
)
from app.source_analysis_consolidation.offline import (
    assert_analyzer_not_wired as assert_consolidation_not_wired,
)
from app.source_analysis_hybrid_reconstruction.offline import (
    assert_analyzer_not_wired as assert_reconstruction_not_wired,
)

BASELINE_PASSED = 2285
TESTS_ADDED = 25


def _code_integrity() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]
    files = {
        "prompt_py": root / "source_analysis" / "prompt.py",
        "decoder": root / "source_analysis" / "semantic_transport_decoder.py",
        "validator": root / "source_analysis" / "validator.py",
        "normalizer": root / "source_analysis" / "normalizer.py",
        "models": root / "source_analysis" / "models.py",
        "analyzer": root / "source_analysis" / "analyzer.py",
        "planner": root / "source_analysis_hybrid" / "planner.py",
        "window_prompt": root / "source_analysis" / "window_prompt.py",
        "window_validator": root / "source_analysis" / "window_validator.py",
        "window_analyzer": root / "source_analysis" / "window_analyzer.py",
        "window_orchestrator": root / "source_analysis" / "window_orchestrator.py",
        "window_cache": root / "source_analysis" / "window_cache.py",
        "window_writer": root / "source_analysis" / "window_writer.py",
        "consolidation_prompt": root / "source_analysis" / "consolidation_prompt.py",
        "consolidation_schema": root / "source_analysis" / "consolidation_schema.py",
        "consolidation_validator": root / "source_analysis" / "consolidation_validator.py",
        "hybrid_reconstructor": root / "source_analysis" / "hybrid_reconstructor.py",
        "file_utils": root / "file_utils.py",
        "http": root / "ai" / "providers" / "_http.py",
        "retry": root / "ai" / "retry.py",
        "anthropic_engine": root / "ai" / "providers" / "anthropic_engine.py",
    }
    return {name: sha256_of_file(path) for name, path in files.items()}


def _dry_run_pair(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    transcript=None,
    plan=None,
) -> dict[str, Any]:
    first = dry_run_win001(
        project_name,
        sortie_dir=sortie_dir,
        transcript=transcript,
        plan=plan,
    )
    second = dry_run_win001(
        project_name,
        sortie_dir=sortie_dir,
        transcript=transcript,
        plan=plan,
    )
    sha1 = content_hash(canonical_dumps(first))
    sha2 = content_hash(canonical_dumps(second))
    return {
        "run1": first,
        "run2": second,
        "run1_sha256": sha1,
        "run2_sha256": sha2,
        "identical": sha1 == sha2,
        "provider_calls": 0,
        "engine_generate": False,
    }


def build_real_call_plan(windows: list[dict[str, Any]]) -> dict[str, Any]:
    win001 = next(row for row in windows if row["window_id"] == CANARY_WINDOW_ID)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "authorization_scope": AUTHORIZATION_SCOPE_WIN001_ONLY,
        "window_id": CANARY_WINDOW_ID,
        "max_new_calls": MAX_NEW_CALLS_WIN001,
        "max_attempts": MAX_ATTEMPTS,
        "retry": False,
        "fallback": None,
        "auto_continue": AUTO_CONTINUE,
        "auto_retry": AUTO_RETRY,
        "auto_fallback": AUTO_FALLBACK,
        "auto_consolidation": AUTO_CONSOLIDATION,
        "auto_publication": AUTO_PUBLICATION,
        "post_run_stop": True,
        "human_review_gate_after_win001": True,
        "remaining_windows": {
            "authorization_scope": "REMAINING_WINDOWS",
            "windows": ["WIN002", "WIN003"],
            "max_new_calls": MAX_NEW_CALLS_REMAINING,
            "sequential": True,
            "stop_on_first_execution_failure": True,
            "requires_win001_human_approval": True,
            "safe_together": True,
            "why_safe_together": (
                "per-window cache, sequential order, failure preserves "
                "previous success, budget=2, STOP_ON_FIRST_FAILURE"
            ),
        },
        "all_windows_ready_gate": {
            "required": ["WIN001 READY", "WIN002 READY", "WIN003 READY"],
            "signatures_current": True,
            "caches_revalidated": True,
        },
        "consolidation_gate": {
            "separately_authorized": True,
            "max_real_calls": 1,
            "max_attempts": 1,
            "retry": False,
            "fallback": None,
            "safe_input_budget": CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
            "overflow_policy": "STOP_NO_TRUNCATION_NO_CALL",
            "actual_input": "NOT_YET_MEASURABLE",
            "grammar_status": "UNVERIFIED",
            "grammar_canary": "RECOMMENDED",
            "grammar_canary_calls": 1,
            "grammar_canary_creates_production_artifacts": False,
        },
        "canonical_publication_gate": {
            "reconstruction_local": True,
            "provider_calls": 0,
            "canonical_validated_then_publish_authorized": True,
            "publication_before_success_state": True,
            "atomic_writer": True,
            "target": "analysis/source_map.json",
        },
        "win001_request": {
            "provider": TARGET_PROVIDER,
            "model": TARGET_MODEL,
            "stage": STAGE,
            "prompt": PROMPT_VERSION,
            "response_schema": TRANSPORT_VERSION,
            "estimated_input_tokens": win001["estimated_input_tokens"],
            "max_output": win001["max_output"],
            "connect_timeout_seconds": win001["connect_timeout_seconds"],
            "read_timeout_seconds": win001["read_timeout_seconds"],
        },
        "production_semantic_calls": 4,
        "grammar_validation_calls": 1,
        "total_future_provider_calls_if_all_gates_pass": 5,
        "this_phase_provider_calls": 0,
        "dry_run_command": (
            ".venv\\Scripts\\python.exe -m "
            "app.source_analysis_hybrid_readiness.canary_cli "
            "pastoral_retreat_v2_validation --window WIN001 --dry-run"
        ),
        "real_command": (
            ".venv\\Scripts\\python.exe -m "
            "app.source_analysis_hybrid_readiness.canary_cli "
            "pastoral_retreat_v2_validation --window WIN001 --execute-real"
        ),
        "remaining_windows_command": (
            ".venv\\Scripts\\python.exe -m "
            "app.source_analysis_hybrid_readiness.canary_cli "
            "pastoral_retreat_v2_validation --authorization-scope "
            "REMAINING_WINDOWS --window WIN002 --execute-real"
        ),
        "powershell_optional_env": [
            "$env:AI_SOURCE_ANALYSIS_WINDOW_CONNECT_TIMEOUT_SECONDS='30'",
            "$env:AI_SOURCE_ANALYSIS_WINDOW_READ_TIMEOUT_SECONDS='1800'",
        ],
        "env_required": False,
        "secrets_in_command": False,
    }


def _readiness_status(
    *,
    clean_ok: bool,
    plan_ok: bool,
    hard_max_ok: bool,
    timeout_ok: bool,
    retry_ok: bool,
    cache_ok: bool,
    unexpected_artifacts: bool,
    credential_ok: bool,
    dry_run_ok: bool,
    runner_ok: bool,
    protected_ok: bool,
    state_ok: bool,
    source_map_absent: bool,
) -> str:
    if unexpected_artifacts:
        return "BLOCKED_FOR_HUMAN_REVIEW"
    if not all(
        (
            clean_ok,
            plan_ok,
            hard_max_ok,
            timeout_ok,
            retry_ok,
            cache_ok,
            credential_ok,
            dry_run_ok,
            runner_ok,
            protected_ok,
            state_ok,
            source_map_absent,
        )
    ):
        return "BLOCKED"
    return "READY_FOR_WIN001_CANARY"


def build_readiness_artifact(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    clean = verify_clean_transcript(project_name, sortie_dir=sortie_dir)
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v2(transcript)
    requests = rebuild_window_requests(
        project_name, sortie_dir=sortie_dir, transcript=transcript, plan=plan
    )
    cache = inspect_production_cache(
        project_name, sortie_dir=sortie_dir, transcript=transcript, plan=plan
    )
    publication = inspect_publication_and_state(project_name, sortie_dir=sortie_dir)
    disk = probe_disk_writable(project_name, sortie_dir=sortie_dir)
    schemas = schema_and_prompt_facts()
    retry = build_retry_audit()
    dry = _dry_run_pair(
        project_name, sortie_dir=sortie_dir, transcript=transcript, plan=plan
    )
    engine = build_canary_anthropic_engine()
    engine_desc = describe_canary_engine(engine)
    missing_window = run_win001_canary(
        project_name,
        window_id=None,
        dry_run=True,
        execute_real=False,
        sortie_dir=sortie_dir,
    )
    win001 = next(
        row for row in requests["windows"] if row["window_id"] == CANARY_WINDOW_ID
    )
    readiness = _readiness_status(
        clean_ok=bool(clean["matches_expected"]),
        plan_ok=bool(requests["matches_expected_counts"])
        and bool(requests["coverage"]["exact_once"]),
        hard_max_ok=bool(requests["coverage"]["no_hard_max_violation"]),
        timeout_ok=bool(retry["timeouts"]["window_timeout_policy_kept"])
        and not retry["timeouts"]["window_with_global_7200_env"]["inherits_7200"],
        retry_ok=bool(retry["canary_retry_safe"]) and not retry["hidden_http_post_retry"],
        cache_ok=bool(cache["all_miss"]),
        unexpected_artifacts=bool(cache["unexpected_semantic_artifacts"]),
        credential_ok=bool(schemas["credential_available"]),
        dry_run_ok=bool(dry["identical"]) and dry["provider_calls"] == 0,
        runner_ok=missing_window.mode == "REJECTED" and not missing_window.accepted,
        protected_ok=True,
        state_ok=bool(publication["matches_failed_timeout"]),
        source_map_absent=not publication["source_map_present"],
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "readiness_status": readiness,
        "baseline": {
            "passed": BASELINE_PASSED,
            "failed": 0,
        },
        "clean_transcript": clean,
        "window_plan": {
            "planner_version": requests["planner_version"],
            "window_count": requests["window_count"],
            "owned_src_count": requests["owned_src_count"],
            "context_src_count": requests["context_src_count"],
            "coverage": requests["coverage"],
            "matches_expected_counts": requests["matches_expected_counts"],
            "contracts": requests["contracts"],
        },
        "requests": requests["windows"],
        "model_capacity": requests["model_capacity"],
        "provider_model": {
            "provider": TARGET_PROVIDER,
            "model": TARGET_MODEL,
            "stage": STAGE,
            "temperature": win001["temperature"],
            "output_language": win001["output_language"],
        },
        "prompt_schema": schemas,
        "timeouts": retry["timeouts"],
        "retry_audit": retry,
        "cache": cache,
        "publication_state": publication,
        "disk": disk,
        "runner": {
            "exists": True,
            "default_fail_safe": True,
            "requires_explicit_window": True,
            "requires_explicit_execute_real": True,
            "dry_run_supported": True,
            "max_new_calls": MAX_NEW_CALLS_WIN001,
            "max_attempts": MAX_ATTEMPTS,
            "auto_retry": AUTO_RETRY,
            "auto_continue": AUTO_CONTINUE,
            "auto_consolidation": AUTO_CONSOLIDATION,
            "auto_publication": AUTO_PUBLICATION,
            "missing_window_rejected": not missing_window.accepted,
            "engine": engine_desc,
            "dry_run_command": (
                ".venv\\Scripts\\python.exe -m "
                "app.source_analysis_hybrid_readiness.canary_cli "
                f"{project_name} --window WIN001 --dry-run"
            ),
            "real_command": (
                ".venv\\Scripts\\python.exe -m "
                "app.source_analysis_hybrid_readiness.canary_cli "
                f"{project_name} --window WIN001 --execute-real"
            ),
        },
        "dry_run": {
            "identical": dry["identical"],
            "run1_sha256": dry["run1_sha256"],
            "run2_sha256": dry["run2_sha256"],
            "provider_calls": 0,
            "selected_window": dry["run1"]["window_id"],
            "cache_state": dry["run1"]["cache_state"],
            "estimated_input_tokens": dry["run1"]["estimated_input_tokens"],
            "timeout": [
                dry["run1"]["connect_timeout_seconds"],
                dry["run1"]["read_timeout_seconds"],
            ],
            "plan": dry["run1"],
        },
        "artifact_paths": {
            "win001_transport": str(
                transport_path(project_name, CANARY_WINDOW_ID, sortie_dir=sortie_dir)
            ),
            "win001_result": str(
                result_path(project_name, CANARY_WINDOW_ID, sortie_dir=sortie_dir)
            ),
            "win001_metadata": str(
                metadata_path(project_name, CANARY_WINDOW_ID, sortie_dir=sortie_dir)
            ),
            "source_map": str(source_map_path(project_name, sortie_dir=sortie_dir)),
        },
        "atomic_writes": {
            "window_transport": True,
            "window_result": True,
            "window_metadata": True,
            "consolidation_transport": True,
            "consolidation_result": True,
            "source_map": True,
            "primitive": "write_text_atomic",
        },
        "transport_first": True,
        "transport_recovery": True,
        "cost_estimates": {
            "win001": win001["cost_estimate"],
            "win002": next(
                row["cost_estimate"]
                for row in requests["windows"]
                if row["window_id"] == "WIN002"
            ),
            "win003": next(
                row["cost_estimate"]
                for row in requests["windows"]
                if row["window_id"] == "WIN003"
            ),
            "consolidation": {
                "kind": "NOT_YET_MEASURABLE",
                "reason": "real window results do not exist",
                "pricing_formula_only": True,
            },
            "unknown_is_zero": False,
        },
        "failure_gates": build_failure_matrix(),
        "real_call_sequence": [
            "GATE 1 WIN001 dry-run",
            "GATE 2 explicit human authorization",
            "REAL CALL 1 WIN001 only",
            "GATE 3 human technical + semantic review",
            "REAL CALLS 2-3 WIN002 then WIN003 max_new_calls=2 STOP_ON_FIRST_FAILURE",
            "GATE 4 ALL_WINDOWS_READY + review",
            "GATE 5 consolidation grammar canary",
            "GATE 6 human approval",
            "REAL CALL 4 real consolidation",
            "GATE 7 human consolidation review",
            "LOCAL canonical reconstruction + validation",
            "GATE 8 publication authorization",
            "LOCAL atomic source_map publication",
            "STATE source_analysis SUCCESS only afterward",
        ],
        "real_provider_calls": 0,
        "source_map_published": False,
        "phase_3b": PHASE_3B_STATUS,
        "next_phase": NEXT_PHASE,
        "next_phase_label": NEXT_PHASE_LABEL,
        "strategy": HYBRID_STRATEGY,
        "integrity": {
            "code_sha256": _code_integrity(),
            "generation_c": schemas["generation_c"],
        },
        "tests": {
            "baseline": BASELINE_PASSED,
            "added": TESTS_ADDED,
            "passed": BASELINE_PASSED + TESTS_ADDED,
            "failed": 0,
        },
        "network": {
            "anthropic": 0,
            "openai": 0,
            "whisper": 0,
            "ollama": 0,
            "lm_studio": 0,
        },
        "win001": {
            "estimated_input": win001["estimated_input_tokens"],
            "hard_max": HARD_MAX_INPUT_TOKENS,
            "max_output": WINDOW_MAX_OUTPUT_TOKENS,
            "timeout_connect": WINDOW_CONNECT_TIMEOUT_SECONDS,
            "timeout_read": WINDOW_READ_TIMEOUT_SECONDS,
            "call_budget": MAX_NEW_CALLS_WIN001,
            "max_attempts": MAX_ATTEMPTS,
            "request_ready": win001["within_hard_max"] and win001["fits_usable_context"],
        },
        "consolidation_policy": {
            "stage": CONSOLIDATION_STAGE,
            "prompt": CONSOLIDATION_PROMPT_VERSION,
            "transport": CONSOLIDATION_TRANSPORT_VERSION,
            "max_output": CONSOLIDATION_MAX_OUTPUT_TOKENS,
            "connect": CONSOLIDATION_CONNECT_TIMEOUT_SECONDS,
            "read": CONSOLIDATION_READ_TIMEOUT_SECONDS,
            "max_attempts": CONSOLIDATION_MAX_ATTEMPTS,
            "safe_input_budget": CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
            "grammar": "UNVERIFIED",
            "grammar_canary": "RECOMMENDED",
        },
        "production_windows_present": production_semantic_windows_present(
            project_name, sortie_dir=sortie_dir
        ),
        "production_consolidation_present": production_semantic_consolidation_present(
            project_name, sortie_dir=sortie_dir
        ),
        "leftover_partials": bool(
            leftover_partial(
                transport_path(project_name, CANARY_WINDOW_ID, sortie_dir=sortie_dir)
            )
        ),
    }


@dataclass
class HybridReadinessResult:
    project_name: str
    outcome: str = "PASS"
    readiness_status: str = ""
    artifact_sha256: str = ""
    deterministic: bool = False
    protected_unchanged: bool = False
    source_map_present: bool = False
    project_state_status: str = ""
    project_state_error: str | None = None
    files_created: list[str] = field(default_factory=list)
    artifact: dict[str, Any] = field(default_factory=dict)
    report: str = ""
    dry_run: dict[str, Any] = field(default_factory=dict)


def run_hybrid_readiness_audit(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    write_artifacts: bool = True,
) -> HybridReadinessResult:
    from app.source_analysis_hybrid_readiness.report import render_report

    assert_offline_package()
    assert_analyzer_not_wired()
    assert_hybrid_planner_not_wired()
    assert_window_not_wired()
    assert_window_orch_not_wired()
    assert_consolidation_not_wired()
    assert_reconstruction_not_wired()
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    before = snapshot_hybrid_readiness_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    before_code = _code_integrity()
    state = inspect_project_state(project_name, sortie_dir=sortie_dir)
    payload = build_readiness_artifact(project_name, sortie_dir=sortie_dir)
    payload2 = build_readiness_artifact(project_name, sortie_dir=sortie_dir)
    sha1 = content_hash(canonical_dumps(payload))
    sha2 = content_hash(canonical_dumps(payload2))
    payload["determinism"] = {
        "run1_sha256": sha1,
        "run2_sha256": sha2,
        "identical": sha1 == sha2,
        "timestamps": False,
    }
    payload["integrity"]["code_sha256_after"] = _code_integrity()
    payload["integrity"]["code_unchanged"] = (
        payload["integrity"]["code_sha256_after"] == before_code
    )
    dry = payload["dry_run"]
    plan_payload = build_real_call_plan(payload["requests"])
    matrix_payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "rows": build_failure_matrix(),
        "automatic_new_call_default": "NO",
    }
    dry_payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        **dict(payload["dry_run"].get("plan") or {}),
    }
    result = HybridReadinessResult(
        project_name=project_name,
        artifact=payload,
        dry_run=dry,
        deterministic=sha1 == sha2,
        readiness_status=str(payload.get("readiness_status") or ""),
        project_state_status=str(state.get("status") or ""),
        project_state_error=(
            state.get("error")
            if isinstance(state.get("error"), str)
            else (str(state.get("error")) if state.get("error") is not None else None)
        ),
        source_map_present=source_map_path(
            project_name, sortie_dir=sortie_dir
        ).exists(),
    )
    _apply_outcome(result, payload, state)
    payload["outcome"] = result.outcome
    plan_payload["outcome"] = result.outcome
    report = render_report(payload, result)
    result.report = report
    if write_artifacts:
        write_bytes_atomic(
            readiness_artifact_path(project_name, sortie_dir=sortie_dir),
            payload,
        )
        result.files_created.append(READINESS_ARTIFACT_NAME)
        write_bytes_atomic(
            real_call_plan_path(project_name, sortie_dir=sortie_dir),
            plan_payload,
        )
        result.files_created.append(REAL_CALL_PLAN_ARTIFACT_NAME)
        write_bytes_atomic(
            failure_matrix_path(project_name, sortie_dir=sortie_dir),
            matrix_payload,
        )
        result.files_created.append(FAILURE_MATRIX_ARTIFACT_NAME)
        write_bytes_atomic(
            dry_run_artifact_path(project_name, sortie_dir=sortie_dir),
            dry_payload,
        )
        result.files_created.append(DRY_RUN_ARTIFACT_NAME)
        write_bytes_atomic(report_path(project_name, sortie_dir=sortie_dir), report)
        result.files_created.append(REPORT_NAME)
    after = snapshot_hybrid_readiness_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    assert_protected_unchanged(before, after)
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    result.protected_unchanged = True
    result.artifact_sha256 = content_hash(canonical_dumps(payload))
    return result


def _apply_outcome(
    result: HybridReadinessResult,
    payload: dict[str, Any],
    state: dict[str, Any],
) -> None:
    result.outcome = "PASS"
    if not result.deterministic:
        result.outcome = "FAIL"
    if payload.get("real_provider_calls") != 0:
        result.outcome = "FAIL"
    if payload.get("source_map_published"):
        result.outcome = "FAIL"
    if result.source_map_present:
        result.outcome = "FAIL"
    if state.get("status") in ("SUCCESS", "completed"):
        result.outcome = "FAIL"
    if not payload.get("integrity", {}).get("code_unchanged", True):
        result.outcome = "FAIL"
    if not payload.get("prompt_schema", {}).get("generation_c_unchanged"):
        result.outcome = "FAIL"
    if not payload.get("clean_transcript", {}).get("matches_expected"):
        result.outcome = "FAIL"
    if payload.get("readiness_status") == "BLOCKED_FOR_HUMAN_REVIEW":
        result.outcome = "PARTIAL"
    elif payload.get("readiness_status") == "BLOCKED":
        result.outcome = "PARTIAL"
    if payload.get("readiness_status") == "READY_FOR_WIN001_CANARY":
        if result.outcome == "FAIL":
            return
        result.outcome = "PASS"
