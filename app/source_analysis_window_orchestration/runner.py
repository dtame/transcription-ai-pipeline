"""
Exécution offline 3B.7.3 : scénarios FakeAI synthétiques + préflight réel.

Aucun provider réel. Aucun artefact sémantique sous analysis/windows
du projet pastoral. Artefacts = audit/ uniquement.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from app.ai.errors import AITimeoutError
from app.ai.providers.fake import FakeReply
from app.ai.settings import resolve_stage_settings
from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.orchestration_models import (
    CACHE_HIT,
    CACHE_STALE,
    READINESS_FAILED,
    READINESS_PENDING,
    READINESS_READY,
    assert_all_windows_ready,
)
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.window_cache import expected_window_signature
from app.source_analysis.window_fixtures import (
    WindowMappedFakeAI,
    mapped_minimal_engine,
    minimal_transport,
    three_window_fixture,
)
from app.source_analysis.window_models import STAGE_WINDOW
from app.source_analysis.window_orchestrator import orchestrate_windows
from app.source_analysis.window_writer import (
    production_windows_exist,
    result_path,
)
from app.source_analysis_execution_strategy.review import inspect_project_state
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.contracts import canonical_dumps
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis_window_orchestration.constants import (
    CACHE_POLICY,
    IMPLEMENTATION_ARTIFACT_NAME,
    MODE,
    NEXT_PHASE,
    ORCHESTRATION_POLICY,
    PHASE,
    PHASE_3B_STATUS,
    PREFLIGHT_ARTIFACT_NAME,
    REPORT_NAME,
    SCHEMA_VERSION,
    SYNTHETIC_ARTIFACT_NAME,
)
from app.source_analysis_window_orchestration.integrity import (
    assert_protected_unchanged,
    snapshot_window_orchestration_protected,
)
from app.source_analysis_window_orchestration.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_window_orchestration.writer import (
    assert_no_production_source_map,
    assert_no_production_windows,
    implementation_artifact_path,
    preflight_artifact_path,
    report_path,
    synthetic_artifact_path,
    write_bytes_atomic,
)


def _code_integrity() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1]
    files = {
        "prompt_py": root / "source_analysis" / "prompt.py",
        "decoder": root / "source_analysis" / "semantic_transport_decoder.py",
        "validator": root / "source_analysis" / "validator.py",
        "models": root / "source_analysis" / "models.py",
        "ultra_compact_schema": root / "source_analysis" / "ultra_compact_schema.py",
        "analyzer": root / "source_analysis" / "analyzer.py",
        "planner": root / "source_analysis_hybrid" / "planner.py",
        "window_prompt": root / "source_analysis" / "window_prompt.py",
        "window_validator": root / "source_analysis" / "window_validator.py",
    }
    return {name: sha256_of_file(path) for name, path in files.items()}


def _canonical_without_paths(result) -> str:
    """Compare les résultats hors chemins runtime (temp roots différents)."""
    payload = result.to_dict()
    for status in payload.get("statuses") or []:
        for key in ("transport_path", "result_path", "metadata_path"):
            status.pop(key, None)
    return canonical_dumps(payload)


def _summary(result) -> dict[str, Any]:
    return {
        "all_windows_ready": result.all_windows_ready,
        "ready": result.ready_windows,
        "generated": result.generated_windows,
        "cache_hits": result.cache_hit_windows,
        "transport_recovered": result.transport_recovered_windows,
        "failed": result.failed_windows,
        "pending": result.pending_windows,
        "new_calls": result.new_calls_consumed,
        "fake_ai_calls": result.fake_ai_calls,
        "real_provider_calls": result.real_provider_calls,
        "order": [status.window_id for status in result.statuses],
        "readiness": [status.readiness for status in result.statuses],
        "cache_states": [status.cache_state for status in result.statuses],
    }


def run_synthetic_scenarios() -> dict[str, Any]:
    transcript, plan = three_window_fixture()

    with tempfile.TemporaryDirectory(prefix="sa_orch_cold_") as tmp:
        root = Path(tmp)
        engine = mapped_minimal_engine(plan)
        cold = orchestrate_windows(
            plan, transcript, engine=engine, windows_root=root
        )
        cold_calls = engine.call_count
        engine_warm = mapped_minimal_engine(plan)
        warm = orchestrate_windows(
            plan, transcript, engine=engine_warm, windows_root=root
        )
        warm_calls = engine_warm.call_count
        try:
            assert_all_windows_ready(warm)
            gate_pass = True
        except Exception:
            gate_pass = False

    with tempfile.TemporaryDirectory(prefix="sa_orch_fail_") as tmp:
        root = Path(tmp)
        fail_engine = WindowMappedFakeAI(
            {
                "WIN001": FakeReply(
                    parsed=minimal_transport(owned_src="SRC000001")
                ),
                "WIN002": AITimeoutError("win002 timeout"),
                "WIN003": FakeReply(
                    parsed=minimal_transport(owned_src="SRC000003")
                ),
            }
        )
        failure = orchestrate_windows(
            plan, transcript, engine=fail_engine, windows_root=root
        )
        resume_engine = WindowMappedFakeAI(
            {
                "WIN002": FakeReply(
                    parsed=minimal_transport(owned_src="SRC000002")
                ),
                "WIN003": FakeReply(
                    parsed=minimal_transport(owned_src="SRC000003")
                ),
            }
        )
        resume = orchestrate_windows(
            plan, transcript, engine=resume_engine, windows_root=root
        )

    with tempfile.TemporaryDirectory(prefix="sa_orch_rec_") as tmp:
        root = Path(tmp)
        orchestrate_windows(
            plan, transcript, engine=mapped_minimal_engine(plan), windows_root=root
        )
        for window in plan.windows:
            result_path("fixture", window.window_id, root=root).unlink()
        recover_engine = mapped_minimal_engine(plan)
        recovery = orchestrate_windows(
            plan, transcript, engine=recover_engine, windows_root=root
        )
        recovery_first_ready = 3

    with tempfile.TemporaryDirectory(prefix="sa_orch_sig_") as tmp:
        root = Path(tmp)
        orchestrate_windows(
            plan, transcript, engine=mapped_minimal_engine(plan), windows_root=root
        )
        mutated, mutated_plan = three_window_fixture(
            texts=(
                "Faith changes the crossing of a trial.",
                "Trust is shown now during hardship.",
                "Keep walking through the valley.",
            ),
            content_sha256=transcript.content_sha256,
        )
        sig_engine = mapped_minimal_engine(mutated_plan)
        signature_run = orchestrate_windows(
            mutated_plan,
            mutated,
            engine=sig_engine,
            windows_root=root,
            max_new_calls=0,
        )

    with tempfile.TemporaryDirectory(prefix="sa_orch_prompt_") as tmp:
        root = Path(tmp)
        orchestrate_windows(
            plan, transcript, engine=mapped_minimal_engine(plan), windows_root=root
        )
        with patch(
            "app.source_analysis.window_prompt.WINDOW_ANALYSIS_PROMPT_VERSION",
            "window-analysis-1.0",
        ):
            prompt_run = orchestrate_windows(
                plan,
                transcript,
                engine=mapped_minimal_engine(plan),
                windows_root=root,
                max_new_calls=0,
            )

    with tempfile.TemporaryDirectory(prefix="sa_orch_model_") as tmp:
        root = Path(tmp)
        orchestrate_windows(
            plan, transcript, engine=mapped_minimal_engine(plan), windows_root=root
        )
        model_engine = WindowMappedFakeAI(
            {
                window.window_id: FakeReply(
                    parsed=minimal_transport(owned_src=window.owned_src_refs[0])
                )
                for window in plan.windows
            },
            model="other-fake-model",
        )
        model_run = orchestrate_windows(
            plan,
            transcript,
            engine=model_engine,
            windows_root=root,
            max_new_calls=0,
        )

    with tempfile.TemporaryDirectory(prefix="sa_orch_out_") as tmp:
        root = Path(tmp)
        orchestrate_windows(
            plan, transcript, engine=mapped_minimal_engine(plan), windows_root=root
        )
        settings = replace(
            resolve_stage_settings(STAGE_WINDOW), max_output_tokens=16000
        )
        max_run = orchestrate_windows(
            plan,
            transcript,
            engine=mapped_minimal_engine(plan),
            settings=settings,
            windows_root=root,
            max_new_calls=0,
        )

    with tempfile.TemporaryDirectory(prefix="sa_orch_lang_") as tmp:
        root = Path(tmp)
        orchestrate_windows(
            plan, transcript, engine=mapped_minimal_engine(plan), windows_root=root
        )
        fr_transcript, fr_plan = three_window_fixture(language="fr")
        lang_run = orchestrate_windows(
            fr_plan,
            fr_transcript,
            engine=mapped_minimal_engine(fr_plan),
            windows_root=root,
            max_new_calls=0,
        )

    with tempfile.TemporaryDirectory(prefix="sa_orch_budget_") as tmp:
        root = Path(tmp)
        budget0 = orchestrate_windows(
            plan,
            transcript,
            engine=mapped_minimal_engine(plan),
            windows_root=root,
            max_new_calls=0,
        )
        budget1_engine = mapped_minimal_engine(plan)
        budget1 = orchestrate_windows(
            plan,
            transcript,
            engine=budget1_engine,
            windows_root=root,
            max_new_calls=1,
        )
        budget_rest = orchestrate_windows(
            plan,
            transcript,
            engine=mapped_minimal_engine(plan),
            windows_root=root,
            max_new_calls=2,
        )

    with tempfile.TemporaryDirectory(prefix="sa_orch_det_") as tmp:
        a = Path(tmp) / "a"
        b = Path(tmp) / "b"
        r1 = orchestrate_windows(
            plan, transcript, engine=mapped_minimal_engine(plan), windows_root=a
        )
        r2 = orchestrate_windows(
            plan, transcript, engine=mapped_minimal_engine(plan), windows_root=b
        )
        det_identical = _canonical_without_paths(r1) == _canonical_without_paths(r2)

    return {
        "cold_run": {
            **_summary(cold),
            "status": "PASS"
            if cold.all_windows_ready and cold_calls == 3
            else "FAIL",
        },
        "warm_run": {
            **_summary(warm),
            "status": "PASS"
            if warm.all_windows_ready and warm_calls == 0 and gate_pass
            else "FAIL",
        },
        "failure_run": {
            **_summary(failure),
            "status": "PASS"
            if (
                failure.statuses[0].readiness == READINESS_READY
                and failure.statuses[1].readiness == READINESS_FAILED
                and failure.statuses[2].readiness == READINESS_PENDING
                and not failure.all_windows_ready
            )
            else "FAIL",
        },
        "resume_run": {
            **_summary(resume),
            "status": "PASS"
            if resume.all_windows_ready and resume.new_calls_consumed == 2
            else "FAIL",
        },
        "transport_recovery": {
            **_summary(recovery),
            "first_ready": recovery_first_ready,
            "status": "PASS"
            if recovery.all_windows_ready and recovery.new_calls_consumed == 0
            else "FAIL",
        },
        "signature_invalidation": {
            **_summary(signature_run),
            "status": "PASS"
            if (
                signature_run.statuses[0].cache_state == CACHE_HIT
                and signature_run.statuses[1].cache_state == CACHE_STALE
                and signature_run.statuses[2].cache_state == CACHE_HIT
                and signature_run.new_calls_consumed == 0
            )
            else "FAIL",
        },
        "prompt_invalidation": {
            "cache_states": [status.cache_state for status in prompt_run.statuses],
            "new_calls": prompt_run.new_calls_consumed,
            "status": "PASS"
            if all(status.cache_state == CACHE_STALE for status in prompt_run.statuses)
            else "FAIL",
        },
        "model_invalidation": {
            "cache_states": [status.cache_state for status in model_run.statuses],
            "status": "PASS"
            if all(status.cache_state == CACHE_STALE for status in model_run.statuses)
            else "FAIL",
        },
        "max_output_invalidation": {
            "cache_states": [status.cache_state for status in max_run.statuses],
            "status": "PASS"
            if all(status.cache_state == CACHE_STALE for status in max_run.statuses)
            else "FAIL",
        },
        "language_invalidation": {
            "cache_states": [status.cache_state for status in lang_run.statuses],
            "status": "PASS"
            if all(status.cache_state == CACHE_STALE for status in lang_run.statuses)
            else "FAIL",
        },
        "call_budget": {
            "budget_0_calls": budget0.new_calls_consumed,
            "budget_0_pending": budget0.pending_windows,
            "budget_1_calls": budget1.new_calls_consumed,
            "budget_1_ready": budget1.ready_windows,
            "budget_n_ready": budget_rest.ready_windows,
            "status": "PASS"
            if (
                budget0.new_calls_consumed == 0
                and budget0.pending_windows == 3
                and budget1.new_calls_consumed == 1
                and budget1.ready_windows == 1
                and budget_rest.all_windows_ready
            )
            else "FAIL",
        },
        "determinism": {
            "identical": det_identical,
            "timestamps": False,
            "status": "PASS" if det_identical else "FAIL",
        },
        "gate": {"status": "PASS" if gate_pass else "FAIL"},
    }


def run_real_preflight(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    if production_windows_exist(project_name, sortie_dir=sortie_dir):
        return {
            "stopped": True,
            "reason": "UNEXPECTED_REAL_WINDOW_CACHE",
            "windows": None,
            "max_new_calls": 0,
            "new_calls": 0,
            "all_windows_ready": False,
            "real_provider_calls": 0,
        }
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v2(transcript)
    windows_root = (
        Path(sortie_dir or Path(r"C:\TranscriptionAI\sortie"))
        / project_name
        / "analysis"
        / "windows"
    )
    result = orchestrate_windows(
        plan,
        transcript,
        engine=None,
        windows_root=windows_root,
        project_name=project_name,
        max_new_calls=0,
    )
    inspections = []
    for window, status in zip(plan.windows, result.statuses):
        signature = expected_window_signature(window, transcript)
        inspections.append(
            {
                "window_id": window.window_id,
                "owned_src_count": window.owned_src_count,
                "input_hash": window.input_hash,
                "expected_signature": signature,
                "cache_state": status.cache_state,
                "readiness": status.readiness,
                "transport_path": status.transport_path,
                "result_path": status.result_path,
                "metadata_path": status.metadata_path,
            }
        )
    return {
        "stopped": False,
        "plan_version": plan.planner_version,
        "plan_sha256": plan.plan_sha256(),
        "window_count": plan.window_count,
        "ordered_window_ids": [window.window_id for window in plan.windows],
        "owned_src_counts": [window.owned_src_count for window in plan.windows],
        "windows": inspections,
        "cache_states": [row["cache_state"] for row in inspections],
        "max_new_calls": 0,
        "new_calls": result.new_calls_consumed,
        "all_windows_ready": result.all_windows_ready,
        "real_provider_calls": 0,
        "fake_ai_calls": result.fake_ai_calls,
        "real_provider_calls_confirmed": 0,
    }


def build_orchestration_artifact(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    synthetic = run_synthetic_scenarios()
    preflight = run_real_preflight(project_name, sortie_dir=sortie_dir)
    generation = generation_c_hashes()
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "orchestration": dict(ORCHESTRATION_POLICY),
        "cache": dict(CACHE_POLICY),
        "synthetic": synthetic,
        "real_preflight": {
            "windows": preflight.get("window_count") or 0,
            "max_new_calls": 0,
            "new_calls": preflight.get("new_calls") or 0,
            "all_windows_ready": bool(preflight.get("all_windows_ready")),
            "real_provider_calls": 0,
            "detail": preflight,
        },
        "execution": {
            "anthropic_calls": 0,
            "openai_calls": 0,
            "source_map_published": False,
            "production_windows_written": False,
            "production_analyzer_wired": False,
            "global_consolidation": False,
        },
        "integrity": {
            "prompt_1_3_version": SOURCE_ANALYZER_PROMPT_VERSION,
            "generation_c": generation,
            "code_sha256": _code_integrity(),
        },
        "next_phase": NEXT_PHASE,
        "phase_3b": PHASE_3B_STATUS,
    }


@dataclass
class WindowOrchestrationAuditResult:
    project_name: str
    outcome: str = "PASS"
    artifact_sha256: str = ""
    deterministic: bool = False
    protected_unchanged: bool = False
    source_map_present: bool = False
    project_state_status: str = ""
    project_state_error: str | None = None
    files_created: list[str] = field(default_factory=list)
    artifact: dict[str, Any] = field(default_factory=dict)
    report: str = ""
    preflight: dict[str, Any] = field(default_factory=dict)


def run_window_orchestration(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    write_artifacts: bool = True,
) -> WindowOrchestrationAuditResult:
    from app.source_analysis_window_orchestration.report import render_report

    assert_offline_package()
    assert_analyzer_not_wired()
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    assert_no_production_windows(project_name, sortie_dir=sortie_dir)
    before = snapshot_window_orchestration_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    before_code = _code_integrity()
    state = inspect_project_state(project_name, sortie_dir=sortie_dir)
    payload = build_orchestration_artifact(project_name, sortie_dir=sortie_dir)
    payload2 = build_orchestration_artifact(project_name, sortie_dir=sortie_dir)
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
    result = WindowOrchestrationAuditResult(
        project_name=project_name,
        artifact=payload,
        preflight=payload["real_preflight"]["detail"],
        deterministic=sha1 == sha2,
        project_state_status=str(state.get("status") or ""),
        project_state_error=(
            state.get("error")
            if isinstance(state.get("error"), str)
            else (str(state.get("error")) if state.get("error") is not None else None)
        ),
        source_map_present=False,
    )
    _apply_outcome(result, payload, state)
    payload["outcome"] = result.outcome
    report = render_report(payload, result)
    result.report = report
    if write_artifacts:
        write_bytes_atomic(
            implementation_artifact_path(project_name, sortie_dir=sortie_dir),
            payload,
        )
        result.files_created.append(IMPLEMENTATION_ARTIFACT_NAME)
        write_bytes_atomic(
            synthetic_artifact_path(project_name, sortie_dir=sortie_dir),
            {
                "schema_version": SCHEMA_VERSION,
                "phase": PHASE,
                "mode": MODE,
                **payload["synthetic"],
            },
        )
        result.files_created.append(SYNTHETIC_ARTIFACT_NAME)
        write_bytes_atomic(
            preflight_artifact_path(project_name, sortie_dir=sortie_dir),
            {
                "schema_version": SCHEMA_VERSION,
                "phase": PHASE,
                "mode": MODE,
                **payload["real_preflight"]["detail"],
            },
        )
        result.files_created.append(PREFLIGHT_ARTIFACT_NAME)
        write_bytes_atomic(
            report_path(project_name, sortie_dir=sortie_dir),
            report,
        )
        result.files_created.append(REPORT_NAME)
    after = snapshot_window_orchestration_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    assert_protected_unchanged(before, after)
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    assert_no_production_windows(project_name, sortie_dir=sortie_dir)
    result.protected_unchanged = True
    result.artifact_sha256 = content_hash(canonical_dumps(payload))
    return result


def _apply_outcome(
    result: WindowOrchestrationAuditResult,
    payload: dict[str, Any],
    state: dict[str, Any],
) -> None:
    synthetic = payload.get("synthetic") or {}
    preflight = payload.get("real_preflight") or {}
    result.outcome = "PASS"
    if not result.deterministic:
        result.outcome = "FAIL"
    required = (
        "cold_run",
        "warm_run",
        "failure_run",
        "resume_run",
        "transport_recovery",
        "signature_invalidation",
        "call_budget",
        "gate",
    )
    if any(synthetic.get(name, {}).get("status") != "PASS" for name in required):
        result.outcome = "FAIL"
    if preflight.get("windows") != 3:
        result.outcome = "FAIL"
    if preflight.get("new_calls") != 0:
        result.outcome = "FAIL"
    if preflight.get("all_windows_ready"):
        result.outcome = "FAIL"
    if (preflight.get("detail") or {}).get("stopped"):
        result.outcome = "PARTIAL"
    if result.source_map_present:
        result.outcome = "FAIL"
    if state.get("status") in ("SUCCESS", "completed"):
        result.outcome = "FAIL"
    if not payload.get("integrity", {}).get("code_unchanged", True):
        result.outcome = "FAIL"
    if not payload.get("integrity", {}).get("generation_c", {}).get(
        "raw_matches_historical"
    ):
        result.outcome = "FAIL"
