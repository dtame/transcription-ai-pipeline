"""
Simulation offline WindowPlannerV2 sur le CLEAN transcript.

Aucun provider. Aucun source_map. Aucun Attempt #3.
Les artefacts vont sous audit/, jamais sous analysis/windows/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.writer import source_map_path
from app.source_analysis_execution_strategy.review import (
    inspect_project_state,
    source_map_present,
)
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.config import WindowPlannerConfig
from app.source_analysis_hybrid.constants import (
    DESIGN_3B7_WINDOWS,
    ESTIMATION_MODEL,
    HARD_MAX_INPUT_TOKENS,
    IMPLEMENTATION_ARTIFACT_NAME,
    MODE,
    NEXT_PHASE,
    OVERLAP_POLICY,
    PHASE,
    PLANNER_VERSION,
    PROVIDER_CALLS,
    REPORT_NAME,
    SCHEMA_VERSION,
    SOURCE_MAP_PUBLISHED,
    STRATEGY,
    TARGET_INPUT_TOKENS,
)
from app.source_analysis_hybrid.contracts import (
    ConsolidationContractSkeleton,
    WindowAnalysisPromptContract,
    canonical_dumps,
)
from app.source_analysis_hybrid.integrity import (
    assert_protected_unchanged,
    snapshot_window_planner_protected,
)
from app.source_analysis_hybrid.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_hybrid.planner import WindowPlannerV2
from app.source_analysis_hybrid.tokens import estimate_prompt_overhead
from app.source_analysis_hybrid.validation import plan_validation_report
from app.source_analysis_hybrid.writer import (
    assert_no_production_source_map,
    assert_no_production_windows,
    implementation_artifact_path,
    report_path,
    write_bytes_atomic,
)
from app.source_analysis_timeout_config.audit import generation_c_hashes


def _code_integrity() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    files = {
        "prompt_py": root / "source_analysis" / "prompt.py",
        "decoder": root / "source_analysis" / "semantic_transport_decoder.py",
        "validator": root / "source_analysis" / "validator.py",
        "models": root / "source_analysis" / "models.py",
        "context_strategy": root / "source_analysis" / "context_strategy.py",
        "analyzer": root / "source_analysis" / "analyzer.py",
    }
    return {name: sha256_of_file(path) for name, path in files.items()}


def _compare_design(plan_windows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    material = False
    for expected, actual in zip(DESIGN_3B7_WINDOWS, plan_windows):
        match = (
            actual.get("window_id") == expected["window_id"]
            and actual.get("owned_src_count") == expected["owned_src_count"]
            and actual.get("first_owned_src_ref") == expected["first_owned_src_ref"]
            and actual.get("last_owned_src_ref") == expected["last_owned_src_ref"]
            and actual.get("estimated_input_tokens") == expected["estimated_input_tokens"]
        )
        token_delta = int(actual.get("estimated_input_tokens") or 0) - int(
            expected["estimated_input_tokens"]
        )
        src_delta = int(actual.get("owned_src_count") or 0) - int(
            expected["owned_src_count"]
        )
        if src_delta != 0 or actual.get("window_id") != expected["window_id"]:
            material = True
        rows.append(
            {
                "window_id": expected["window_id"],
                "design_owned_src_count": expected["owned_src_count"],
                "actual_owned_src_count": actual.get("owned_src_count"),
                "design_estimated_input_tokens": expected["estimated_input_tokens"],
                "actual_estimated_input_tokens": actual.get("estimated_input_tokens"),
                "token_delta": token_delta,
                "src_delta": src_delta,
                "match": match,
            }
        )
    if len(plan_windows) != len(DESIGN_3B7_WINDOWS):
        material = True
    return {
        "expected_window_count": len(DESIGN_3B7_WINDOWS),
        "actual_window_count": len(plan_windows),
        "windows": rows,
        "all_match": all(row["match"] for row in rows)
        and len(plan_windows) == len(DESIGN_3B7_WINDOWS),
        "material_divergence": material,
    }


def _window_row(window) -> dict[str, Any]:
    return {
        "window_id": window.window_id,
        "owned_src_count": window.owned_src_count,
        "context_src_count": window.context_src_count,
        "first_owned_src_ref": window.first_owned_src_ref,
        "last_owned_src_ref": window.last_owned_src_ref,
        "estimated_input_tokens": window.estimated_input_tokens,
        "word_count": window.word_count,
        "content_tokens": window.content_tokens,
        "planner_estimate_tokens": window.planner_estimate_tokens,
        "input_hash": window.input_hash,
        "owned_src_ids_sha256": window.owned_src_ids_sha256,
        "owned_content_sha256": window.owned_content_sha256,
    }


@dataclass
class WindowPlannerImplementationResult:
    project_name: str
    outcome: str = "PASS"
    artifact_sha256: str = ""
    plan_sha256: str = ""
    deterministic: bool = False
    protected_unchanged: bool = False
    source_map_present: bool = False
    project_state_status: str = ""
    project_state_error: str | None = None
    files_created: list[str] = field(default_factory=list)
    artifact: dict[str, Any] = field(default_factory=dict)
    report: str = ""


def build_implementation_artifact(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> tuple[dict[str, Any], str, str]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    config = WindowPlannerConfig()
    planner = WindowPlannerV2(config, model=ESTIMATION_MODEL)
    overhead = estimate_prompt_overhead(transcript, model=ESTIMATION_MODEL)
    plan1 = planner.plan(transcript)
    plan2 = planner.plan(transcript)
    sha1 = plan1.plan_sha256()
    sha2 = plan2.plan_sha256()
    validation = plan_validation_report(plan1, transcript, config)
    windows = [_window_row(window) for window in plan1.windows]
    design = _compare_design(windows)
    generation = generation_c_hashes()
    code = _code_integrity()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "strategy": STRATEGY,
        "planner": {
            "name": "WindowPlannerV2",
            "version": PLANNER_VERSION,
            "target_input_tokens": TARGET_INPUT_TOKENS,
            "hard_max_input_tokens": HARD_MAX_INPUT_TOKENS,
            "overlap_policy": OVERLAP_POLICY,
            "prompt_overhead_tokens": overhead,
            "budget_includes_prompt_overhead": True,
            "budget_basis": "full_estimated_request_tokens",
        },
        "input": {
            "transcript_id": transcript.transcript_id,
            "mode": transcript.mode.value
            if hasattr(transcript.mode, "value")
            else str(transcript.mode),
            "segments": transcript.segment_count,
            "words": transcript.word_count,
            "duration_seconds": transcript.duration_seconds,
            "clean_source_count": transcript.segment_count,
            "sha256": transcript.content_sha256,
        },
        "plan": {
            "strategy": plan1.strategy,
            "planner_version": plan1.planner_version,
            "window_count": plan1.window_count,
            "owned_src_count": plan1.owned_src_count,
            "context_src_count": plan1.context_src_count,
            "estimated_input_tokens_min": plan1.estimated_input_tokens_min,
            "estimated_input_tokens_max": plan1.estimated_input_tokens_max,
            "estimated_input_tokens_mean": plan1.estimated_input_tokens_mean,
            "estimated_input_tokens_median": plan1.estimated_input_tokens_median,
            "plan_sha256": sha1,
            "windows": windows,
        },
        "validation": validation,
        "design_3b7_comparison": design,
        "determinism": {
            "run1_sha256": sha1,
            "run2_sha256": sha2,
            "identical": sha1 == sha2,
            "timestamps": False,
            "uuid": False,
            "randomness": False,
        },
        "contracts": {
            "window_analysis_prompt": WindowAnalysisPromptContract().to_dict(),
            "consolidation": ConsolidationContractSkeleton().to_dict(),
            "window_id_is_not_cache_signature": True,
            "window_input_signature_separated_from_analysis_signature": True,
        },
        "integrity": {
            "prompt_version": SOURCE_ANALYZER_PROMPT_VERSION,
            "generation_c": generation,
            "code_sha256": code,
        },
        "execution": {
            "provider_calls": PROVIDER_CALLS,
            "source_map_published": SOURCE_MAP_PUBLISHED,
            "production_analyzer_wired": False,
            "source_map_path_exists": source_map_path(
                project_name, sortie_dir=sortie_dir
            ).exists(),
        },
        "next_phase": NEXT_PHASE,
    }
    encoded = canonical_dumps(payload)
    return payload, sha1, content_hash(encoded)


def run_window_planner_implementation(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    write_artifacts: bool = True,
) -> WindowPlannerImplementationResult:
    from app.source_analysis_hybrid.report import render_report

    assert_offline_package()
    assert_analyzer_not_wired()
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    assert_no_production_windows(project_name, sortie_dir=sortie_dir)
    before = snapshot_window_planner_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    before_code = _code_integrity()
    state = inspect_project_state(project_name, sortie_dir=sortie_dir)
    payload, plan_sha, _artifact_sha = build_implementation_artifact(
        project_name, sortie_dir=sortie_dir
    )
    payload["integrity"]["code_sha256_after"] = _code_integrity()
    payload["integrity"]["code_unchanged"] = (
        payload["integrity"]["code_sha256_after"] == before_code
    )
    result = WindowPlannerImplementationResult(
        project_name=project_name,
        artifact=payload,
        plan_sha256=plan_sha,
        deterministic=payload["determinism"]["identical"],
        project_state_status=str(state.get("status") or ""),
        project_state_error=state.get("error")
        if isinstance(state.get("error"), str)
        else (
            str(state.get("error")) if state.get("error") is not None else None
        ),
        source_map_present=source_map_present(project_name, sortie_dir=sortie_dir),
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
            report_path(project_name, sortie_dir=sortie_dir),
            report,
        )
        result.files_created.append(REPORT_NAME)
    after = snapshot_window_planner_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    assert_protected_unchanged(before, after)
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    assert_no_production_windows(project_name, sortie_dir=sortie_dir)
    result.protected_unchanged = True
    result.artifact_sha256 = content_hash(canonical_dumps(payload))
    return result


def _apply_outcome(
    result: WindowPlannerImplementationResult,
    payload: dict[str, Any],
    state: dict[str, Any],
) -> None:
    validation = payload.get("validation") or {}
    design = payload.get("design_3b7_comparison") or {}
    result.outcome = "PASS"
    if not result.deterministic:
        result.outcome = "FAIL"
    if not validation.get("all_sources_owned_exactly_once"):
        result.outcome = "FAIL"
    if not validation.get("hard_max_respected"):
        result.outcome = "FAIL"
    if result.source_map_present:
        result.outcome = "FAIL"
    if state.get("status") in ("SUCCESS", "completed"):
        result.outcome = "FAIL"
    if not payload.get("integrity", {}).get("code_unchanged", True):
        result.outcome = "FAIL"
    if design.get("material_divergence") and result.outcome == "PASS":
        result.outcome = "PARTIAL"
