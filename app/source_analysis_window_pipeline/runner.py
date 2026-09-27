"""
Exécution offline 3B.7.2 : FakeAI synthétique + préflight WIN001 réel.

Aucun provider réel. Aucun artefact sémantique sous analysis/windows
du projet pastoral. Artefacts = audit/ uniquement.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.ai.settings import resolve_stage_settings
from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.ultra_compact_schema import SEMANTIC_TRANSPORT_VERSION
from app.source_analysis.window_analyzer import (
    analyze_window,
    build_window_ai_request,
)
from app.source_analysis.window_fixtures import (
    context_only_transport,
    invalid_link_transport,
    invalid_src_transport,
    invalid_vocabulary_transport,
    make_transcript,
    minimal_transport,
    rich_transport,
    window_for,
)
from app.source_analysis.window_models import (
    STAGE_WINDOW,
    TARGET_MODEL,
    TARGET_PROVIDER,
    WINDOW_CONNECT_TIMEOUT_SECONDS,
    WINDOW_FALLBACK,
    WINDOW_MAX_ATTEMPTS,
    WINDOW_MAX_OUTPUT_TOKENS,
    WINDOW_READ_TIMEOUT_SECONDS,
    WINDOW_RETRY,
)
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
    build_window_system_prompt,
    window_prompt_sha256,
)
from app.source_analysis.window_writer import result_path, transport_path
from app.source_analysis_execution_strategy.review import inspect_project_state
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.constants import HARD_MAX_INPUT_TOKENS
from app.source_analysis_hybrid.materialize import materialize_window_content
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_hybrid.tokens import estimate_window_input_tokens
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis_window_pipeline.constants import (
    FAKE_ARTIFACT_NAME,
    MAX_OUTPUT_POLICY,
    MODE,
    NEXT_PHASE,
    PHASE,
    PHASE_3B_STATUS,
    PREFLIGHT_ARTIFACT_NAME,
    REPORT_NAME,
    SCHEMA_VERSION,
    TIMEOUT_POLICY,
)
from app.source_analysis_window_pipeline.integrity import (
    assert_protected_unchanged,
    snapshot_window_pipeline_protected,
)
from app.source_analysis_window_pipeline.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_window_pipeline.writer import (
    assert_no_production_source_map,
    assert_no_production_windows,
    fake_artifact_path,
    preflight_artifact_path,
    report_path,
    write_bytes_atomic,
)
from app.source_analysis_hybrid.contracts import canonical_dumps


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
    }
    return {name: sha256_of_file(path) for name, path in files.items()}


def _fake_engine(transport: dict) -> FakeAIEngine:
    return FakeAIEngine(
        script=[FakeReply(parsed=transport)],
        retry_policy=no_delay_policy(max_attempts=1),
    )


def _run_case(name: str, transport: dict, transcript, window, expect: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="sa_window_") as tmp:
        root = Path(tmp)
        engine = _fake_engine(transport)
        t_path = transport_path("fixture", window.window_id, root=root)
        r_path = result_path("fixture", window.window_id, root=root)
        error_type = None
        try:
            analyze_window(
                window,
                transcript,
                engine,
                windows_root=root,
            )
            status = "PASS"
        except Exception as exc:
            error_type = type(exc).__name__
            status = "FAIL_CLOSED" if expect == "FAIL" else "ERROR"
        transport_exists = t_path.is_file()
        result_exists = r_path.is_file()
        ok = (
            (expect == "PASS" and status == "PASS" and transport_exists and result_exists)
            or (
                expect == "FAIL"
                and status == "FAIL_CLOSED"
                and transport_exists
                and not result_exists
            )
        )
        return {
            "name": name,
            "status": "PASS" if ok else "FAIL",
            "expected": expect,
            "error_type": error_type,
            "transport_persisted": transport_exists,
            "result_persisted": result_exists,
            "fake_ai_calls": engine.call_count,
            "real_provider_calls": 0,
        }


def run_fake_pipeline() -> dict[str, Any]:
    transcript = make_transcript(
        (
            "Faith does not remove the trial; it changes how you walk through it.",
            "What remains standing is what you actually believe.",
            "A man who had lost everything still prayed each morning.",
        )
    )
    window = window_for(transcript)
    cases = [
        _run_case("minimal_fixture", minimal_transport(), transcript, window, "PASS"),
        _run_case("rich_fixture", rich_transport(), transcript, window, "PASS"),
        _run_case(
            "invalid_vocabulary",
            invalid_vocabulary_transport(),
            transcript,
            window,
            "FAIL",
        ),
        _run_case("invalid_src", invalid_src_transport(), transcript, window, "FAIL"),
        _run_case(
            "invalid_link",
            invalid_link_transport(),
            transcript,
            window,
            "FAIL",
        ),
    ]
    context_transcript = make_transcript(
        ("Owned sentence about faith.", "Boundary context only.")
    )
    context_window = window_for(
        context_transcript,
        owned=("SRC000001",),
        context=("SRC000002",),
    )
    cases.append(
        _run_case(
            "context_only",
            context_only_transport(context_src="SRC000002"),
            context_transcript,
            context_window,
            "FAIL",
        )
    )

    with tempfile.TemporaryDirectory(prefix="sa_window_det_") as tmp:
        root = Path(tmp)
        engine1 = _fake_engine(minimal_transport())
        result1 = analyze_window(window, transcript, engine1, windows_root=root / "a")
        engine2 = _fake_engine(minimal_transport())
        result2 = analyze_window(window, transcript, engine2, windows_root=root / "b")
        t1 = transport_path("fixture", window.window_id, root=root / "a").read_bytes()
        t2 = transport_path("fixture", window.window_id, root=root / "b").read_bytes()
        r1 = result_path("fixture", window.window_id, root=root / "a").read_bytes()
        r2 = result_path("fixture", window.window_id, root=root / "b").read_bytes()
        determinism = {
            "transport_identical": t1 == t2,
            "result_identical": r1 == r2,
            "signature_identical": (
                result1.window_analysis_signature == result2.window_analysis_signature
            ),
            "timestamps": False,
        }
        determinism_pass = (
            determinism["transport_identical"]
            and determinism["result_identical"]
            and determinism["signature_identical"]
            and determinism["timestamps"] is False
        )

    transport_first = all(
        case["transport_persisted"]
        and (case["result_persisted"] if case["expected"] == "PASS" else not case["result_persisted"])
        for case in cases
    )
    fake_calls = sum(case["fake_ai_calls"] for case in cases) + 2
    return {
        "cases": {case["name"]: case["status"] for case in cases},
        "case_details": cases,
        "minimal_fixture": next(c["status"] for c in cases if c["name"] == "minimal_fixture"),
        "rich_fixture": next(c["status"] for c in cases if c["name"] == "rich_fixture"),
        "transport_first": "PASS" if transport_first else "FAIL",
        "window_validation": (
            "PASS"
            if all(c["status"] == "PASS" for c in cases)
            else "FAIL"
        ),
        "determinism": "PASS" if determinism_pass else "FAIL",
        "determinism_detail": determinism,
        "fake_ai_calls": fake_calls,
        "anthropic_calls": 0,
        "openai_calls": 0,
    }


def run_real_preflight(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v2(transcript)
    window = plan.windows[0]
    content = materialize_window_content(transcript, window)
    bundle = build_window_ai_request(
        window, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10
    )
    planner_estimate = window.estimated_input_tokens
    planner_remeasure = estimate_window_input_tokens(
        transcript, content.owned_segments
    )
    actual = int(bundle.token_estimate["total_tokens"])
    drift = actual - int(planner_estimate)
    return {
        "window_id": window.window_id,
        "input_hash": window.input_hash,
        "owned_src_count": window.owned_src_count,
        "context_src_count": window.context_src_count,
        "first_owned_src_ref": window.first_owned_src_ref,
        "last_owned_src_ref": window.last_owned_src_ref,
        "prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V10,
        "prompt_sha256": window_prompt_sha256(bundle.system_prompt),
        "transport_version": SEMANTIC_TRANSPORT_VERSION,
        "schema_sha256": bundle.response_schema_sha256,
        "planner_version": window.planner_version,
        "planner_estimated_request_tokens": planner_estimate,
        "planner_1_3_remeasure_tokens": planner_remeasure,
        "estimated_request_tokens": actual,
        "system_tokens": bundle.token_estimate["system_tokens"],
        "user_tokens": bundle.token_estimate["user_tokens"],
        "framing_tokens": bundle.token_estimate["framing_tokens"],
        "owned_content_tokens": bundle.token_estimate["owned_content_tokens"],
        "context_content_tokens": bundle.token_estimate["context_content_tokens"],
        "estimator_method": bundle.token_estimate["method"],
        "token_delta_vs_planner": drift,
        "hard_max": HARD_MAX_INPUT_TOKENS,
        "within_hard_max": actual <= HARD_MAX_INPUT_TOKENS,
        "planner_prompt_drift": drift != 0,
        "drift_cause": (
            "window-analysis-1.0 framing differs from Prompt 1.3 used by "
            "WindowPlannerV2 token estimates; SRC rendering is identical "
            "(render_segment). Same estimate_tokens path."
            if drift != 0
            else "identical estimate"
        ),
        "max_output_tokens": WINDOW_MAX_OUTPUT_TOKENS,
        "provider_target": TARGET_PROVIDER,
        "model_target": TARGET_MODEL,
        "would_call_ai": True,
        "actual_real_provider_calls": 0,
        "real_provider_calls": 0,
        "engine_generate": False,
        "word_count": window.word_count,
        "plan_window_count": plan.window_count,
        "request_stage": bundle.request.stage,
        "request_has_schema": bundle.request.wants_structured_output,
        "output_language": transcript.primary_language,
    }


def _stage_isolation() -> dict[str, Any]:
    editorial = {}
    for stage in (
        "source_analysis",
        "editorial_planning",
        "book_generation",
        "book_validation",
    ):
        settings = resolve_stage_settings(stage)
        editorial[stage] = {
            "provider": settings.provider,
            "model": settings.model,
            "temperature": settings.temperature,
            "max_output_tokens": settings.max_output_tokens,
            "connect_timeout_seconds": settings.connect_timeout_seconds,
            "read_timeout_seconds": settings.read_timeout_seconds,
        }
    window = resolve_stage_settings(STAGE_WINDOW)
    return {
        "editorial_stages": editorial,
        "window_stage": {
            "provider": window.provider,
            "model": window.model,
            "max_output_tokens": window.max_output_tokens,
            "connect_timeout_seconds": window.connect_timeout_seconds,
            "read_timeout_seconds": window.read_timeout_seconds,
        },
        "source_analysis_unchanged": editorial["source_analysis"]
        == {
            "provider": "anthropic",
            "model": "claude-sonnet-5",
            "temperature": None,
            "max_output_tokens": None,
            "connect_timeout_seconds": None,
            "read_timeout_seconds": None,
        },
    }


def build_pipeline_artifact(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    fake = run_fake_pipeline()
    preflight = run_real_preflight(project_name, sortie_dir=sortie_dir)
    generation = generation_c_hashes()
    system = build_window_system_prompt(
        "en", version=WINDOW_ANALYSIS_PROMPT_VERSION_V10
    )
    isolation = _stage_isolation()
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "window_prompt": {
            "version": WINDOW_ANALYSIS_PROMPT_VERSION_V10,
            "sha256": window_prompt_sha256(system),
            "output_language": preflight["output_language"],
            "role": "SOURCE WINDOW ANALYST",
            "distinct_from_prompt_1_3": True,
        },
        "transport": {
            "version": SEMANTIC_TRANSPORT_VERSION,
            "generation_c_sha256": generation["raw_sha256"],
            "provider_schema_sha256": generation["anthropic_sha256"],
            "raw_matches_historical": generation["raw_matches_historical"],
            "anthropic_matches_historical": generation["anthropic_matches_historical"],
        },
        "stage": {
            "name": STAGE_WINDOW,
            "provider_target": TARGET_PROVIDER,
            "model_target": TARGET_MODEL,
            "max_output_tokens": WINDOW_MAX_OUTPUT_TOKENS,
            "max_output_policy": MAX_OUTPUT_POLICY,
            "connect_timeout_seconds": WINDOW_CONNECT_TIMEOUT_SECONDS,
            "read_timeout_seconds": WINDOW_READ_TIMEOUT_SECONDS,
            "timeout_policy": TIMEOUT_POLICY,
            "max_attempts": WINDOW_MAX_ATTEMPTS,
            "retry": WINDOW_RETRY,
            "fallback": WINDOW_FALLBACK,
        },
        "fake_pipeline": {
            "minimal_fixture": fake["minimal_fixture"],
            "rich_fixture": fake["rich_fixture"],
            "transport_first": fake["transport_first"],
            "window_validation": fake["window_validation"],
            "determinism": fake["determinism"],
            "case_details": fake["case_details"],
        },
        "real_preflight": {
            "window_id": preflight["window_id"],
            "owned_src_count": preflight["owned_src_count"],
            "context_src_count": preflight["context_src_count"],
            "estimated_request_tokens": preflight["estimated_request_tokens"],
            "hard_max": preflight["hard_max"],
            "within_hard_max": preflight["within_hard_max"],
            "would_call_ai": True,
            "real_provider_calls": 0,
            "detail": preflight,
        },
        "execution": {
            "fake_ai_calls": fake["fake_ai_calls"],
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
            "stage_isolation": isolation,
        },
        "next_phase": NEXT_PHASE,
        "phase_3b": PHASE_3B_STATUS,
    }


@dataclass
class WindowPipelineResult:
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


def run_window_pipeline(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    write_artifacts: bool = True,
) -> WindowPipelineResult:
    from app.source_analysis_window_pipeline.report import render_report

    assert_offline_package()
    assert_analyzer_not_wired()
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    assert_no_production_windows(project_name, sortie_dir=sortie_dir)
    before = snapshot_window_pipeline_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    before_code = _code_integrity()
    state = inspect_project_state(project_name, sortie_dir=sortie_dir)
    payload = build_pipeline_artifact(project_name, sortie_dir=sortie_dir)
    payload2 = build_pipeline_artifact(project_name, sortie_dir=sortie_dir)
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
    result = WindowPipelineResult(
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
            fake_artifact_path(project_name, sortie_dir=sortie_dir),
            payload,
        )
        result.files_created.append(FAKE_ARTIFACT_NAME)
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
    after = snapshot_window_pipeline_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    assert_protected_unchanged(before, after)
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    assert_no_production_windows(project_name, sortie_dir=sortie_dir)
    result.protected_unchanged = True
    result.artifact_sha256 = content_hash(canonical_dumps(payload))
    return result


def _apply_outcome(
    result: WindowPipelineResult,
    payload: dict[str, Any],
    state: dict[str, Any],
) -> None:
    fake = payload.get("fake_pipeline") or {}
    preflight = payload.get("real_preflight") or {}
    result.outcome = "PASS"
    if not result.deterministic:
        result.outcome = "FAIL"
    if fake.get("window_validation") != "PASS":
        result.outcome = "FAIL"
    if fake.get("determinism") != "PASS":
        result.outcome = "FAIL"
    if not preflight.get("within_hard_max"):
        result.outcome = "PARTIAL" if result.outcome == "PASS" else result.outcome
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
