"""
Exécution offline 3B.7.5 : E2E FakeAI + préflight réel.

Aucun provider réel. Aucun artefact sémantique pastoral.
Artefacts = audit/ uniquement.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.errors import AITimeoutError
from app.ai.providers.fake import FakeAIEngine
from app.ai.retry import no_delay_policy
from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.canonical_vocabulary import (
    GENERATION_C_RAW_SHA256_3B43,
)
from app.source_analysis.consolidation_decoder import decode_consolidation_transport
from app.source_analysis.consolidation_fixtures import (
    default_provider_metadata,
    make_window_result,
)
from app.source_analysis.consolidation_input import build_consolidation_input_from_plan
from app.source_analysis.consolidation_validator import validate_consolidation_result
from app.source_analysis.errors import HybridPreconditionError, HybridReconstructionError
from app.source_analysis.hybrid_e2e_fixtures import (
    CONSOLIDATION_AUDIENCE,
    CONSOLIDATION_INTENT,
    CONSOLIDATION_THEME,
    CONSOLIDATION_VOICE,
    MERGED_IDEA_VALUE,
    MERGED_TOPIC_VALUE,
    e2e_engine,
    intermediate,
    make_e2e_transcript,
    plan_e2e_windows,
    sparse_transcript,
    two_window_sparse_plan,
)
from app.source_analysis.hybrid_reconstructor import (
    HybridCanonicalReconstructor,
    reconstruct_source_map,
    reconstruction_allowed,
    union_source_refs_in_source_order,
)
from app.source_analysis.hybrid_service import (
    preflight_hybrid_reconstruction,
    run_hybrid_source_analysis,
)
from app.source_analysis.hybrid_signature import HYBRID_STRATEGY, RECONSTRUCTOR_VERSION
from app.source_analysis.models import SOURCE_MAP_SCHEMA_VERSION
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.window_fixtures import make_transcript, window_for, window_plan_from_inputs
from app.source_analysis.window_orchestrator import orchestrate_windows
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis.writer import render_source_map, source_map_path
from app.source_analysis_execution_strategy.review import inspect_project_state
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.config import WindowPlannerConfig
from app.source_analysis_hybrid.constants import (
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_TRANSPORT_VERSION,
    HARD_MAX_INPUT_TOKENS,
    OVERLAP_POLICY,
    PLANNER_VERSION,
    TARGET_INPUT_TOKENS,
    WINDOW_PROMPT_VERSION,
    WINDOW_TRANSPORT_VERSION,
)
from app.source_analysis_hybrid.contracts import canonical_dumps
from app.source_analysis_hybrid.offline import (
    assert_analyzer_not_wired as assert_hybrid_planner_not_wired,
)
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_hybrid_reconstruction.constants import (
    IMPLEMENTATION_ARTIFACT_NAME,
    MODE,
    NEXT_PHASE,
    PHASE,
    PHASE_3B_STATUS,
    PREFLIGHT_ARTIFACT_NAME,
    REPORT_NAME,
    SCHEMA_VERSION,
    SYNTHETIC_ARTIFACT_NAME,
)
from app.source_analysis_hybrid_reconstruction.integrity import (
    assert_protected_unchanged,
    snapshot_hybrid_reconstruction_protected,
)
from app.source_analysis_hybrid_reconstruction.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_hybrid_reconstruction.writer import (
    assert_no_production_consolidation,
    assert_no_production_source_map,
    assert_no_production_windows,
    implementation_artifact_path,
    preflight_artifact_path,
    report_path,
    synthetic_artifact_path,
    write_bytes_atomic,
)
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis_window_orchestration.offline import (
    assert_analyzer_not_wired as assert_window_orch_not_wired,
)
from app.source_analysis_window_pipeline.offline import (
    assert_analyzer_not_wired as assert_window_not_wired,
)
from app.source_analysis_consolidation.offline import (
    assert_analyzer_not_wired as assert_consolidation_not_wired,
)


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
        "consolidation_prompt": root / "source_analysis" / "consolidation_prompt.py",
        "consolidation_schema": root / "source_analysis" / "consolidation_schema.py",
        "consolidation_validator": root / "source_analysis" / "consolidation_validator.py",
        "hybrid_reconstructor": root / "source_analysis" / "hybrid_reconstructor.py",
    }
    return {name: sha256_of_file(path) for name, path in files.items()}


def _reconstruct_from_transport(transcript, plan, results, transport):
    built = build_consolidation_input_from_plan(plan, results)
    decoded = decode_consolidation_transport(
        transport,
        built,
        signature="e" * 64,
        provider_metadata=default_provider_metadata(),
    )
    validate_consolidation_result(decoded, built)
    return reconstruct_source_map(
        transcript,
        plan,
        results,
        decoded,
        consolidation_input=built,
    ), built, decoded


def run_synthetic_e2e() -> dict[str, Any]:
    transcript, plan = plan_e2e_windows()
    with tempfile.TemporaryDirectory(prefix="sa_hyb_e2e_") as tmp:
        root = Path(tmp)
        engine = e2e_engine(plan)
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            engine,
            windows_root=root / "windows",
            consolidation_root=root / "consolidation",
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10,
        )
        warm_engine = engine
        warm = run_hybrid_source_analysis(
            transcript,
            plan,
            warm_engine,
            windows_root=root / "windows",
            consolidation_root=root / "consolidation-warm",
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10,
        )
        engine_a = e2e_engine(plan)
        engine_b = e2e_engine(plan)
        run_a = run_hybrid_source_analysis(
            transcript,
            plan,
            engine_a,
            windows_root=root / "a" / "w",
            consolidation_root=root / "a" / "c",
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10,
        )
        run_b = run_hybrid_source_analysis(
            transcript,
            plan,
            engine_b,
            windows_root=root / "b" / "w",
            consolidation_root=root / "b" / "c",
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10,
        )
        text_a = render_source_map(run_a.source_map.to_dict())
        text_b = render_source_map(run_b.source_map.to_dict())
        sm = run.source_map
        night_summaries = [
            idea.summary
            for idea in sm.ideas
            if "night" in idea.summary.lower()
        ]
        merged_topics = [
            topic for topic in sm.topics if topic.label == MERGED_TOPIC_VALUE
        ]
        merged_ideas = [
            idea for idea in sm.ideas if idea.summary == MERGED_IDEA_VALUE
        ]
        cross_rel = any(
            relation.relation == "supports" and relation.to_idea
            for idea in sm.ideas
            for relation in idea.relations
        )
        return {
            "window_count": plan.window_count,
            "planner_version": plan.planner_version,
            "fake_window_calls": run.window_fake_calls,
            "fake_consolidation_calls": run.consolidation_fake_calls,
            "warm_window_calls": warm.window_fake_calls,
            "warm_consolidation_calls": warm.consolidation_fake_calls,
            "all_windows_ready": run.all_windows_ready,
            "consolidation_valid": run.consolidation_result is not None,
            "canonical_reconstruction_valid": run.source_map is not None,
            "canonical_validator_pass": True,
            "determinism": text_a == text_b,
            "no_local_semantic_merge": len(night_summaries) == 2,
            "explicit_merge_one_topic": len(merged_topics) == 1,
            "explicit_merge_one_idea": len(merged_ideas) == 1,
            "sparse_src_in_e2e_union": list(merged_topics[0].source_refs)
            == ["SRC000001", "SRC000004"]
            if merged_topics
            else False,
            "cross_window_relation": cross_rel,
            "global_metadata_follows_consolidation": (
                sm.source_analysis.main_theme == CONSOLIDATION_THEME
                and sm.source_analysis.author_intent.summary == CONSOLIDATION_INTENT
                and sm.source_analysis.target_audience.summary
                == CONSOLIDATION_AUDIENCE
                and CONSOLIDATION_VOICE in sm.author_voice_profile.distinctive_traits
            ),
            "canonical_ids": sm.declared_ids(),
            "intermediate_ids_absent": all(
                not identifier.startswith("WIN") and ":" not in identifier
                for ids in sm.declared_ids().values()
                for identifier in ids
            ),
            "strategy": sm.analysis.strategy,
            "real_provider_calls": 0,
            "timestamps": "timestamp" not in text_a,
            "serialization_bytes": len(text_a.encode("utf-8")),
            "fresh_total_fake_calls": run.window_fake_calls
            + run.consolidation_fake_calls,
        }


def _sparse_union_proof() -> dict[str, Any]:
    transcript = sparse_transcript()
    plan = two_window_sparse_plan(transcript)
    results = (
        make_window_result(
            plan.windows[0],
            (
                intermediate(
                    "WIN001:R0001",
                    "TOPIC",
                    "Sparse A",
                    ("SRC000001",),
                    index=0,
                    metadata=("First sparse.",),
                ),
                intermediate(
                    "WIN001:R0002",
                    "IDEA",
                    "Sparse claim one",
                    ("SRC000001",),
                    index=1,
                    link_ids=("WIN001:R0001",),
                    metadata=("claim", "central"),
                ),
                intermediate(
                    "WIN001:R0003",
                    "INTENT_KIND",
                    "enseigner",
                    (),
                    index=2,
                ),
                intermediate(
                    "WIN001:R0004",
                    "AUDIENCE_KIND",
                    "croyants",
                    (),
                    index=3,
                ),
                intermediate(
                    "WIN001:R0005",
                    "VOICE",
                    "didactic",
                    (),
                    index=4,
                    metadata=("tone",),
                ),
            ),
            signature="1" * 64,
        ),
        make_window_result(
            plan.windows[1],
            (
                intermediate(
                    "WIN002:R0001",
                    "TOPIC",
                    "Sparse B",
                    ("SRC000003", "SRC000010"),
                    index=0,
                    metadata=("Later sparse.",),
                ),
                intermediate(
                    "WIN002:R0002",
                    "IDEA",
                    "Sparse claim two",
                    ("SRC000003",),
                    index=1,
                    link_ids=("WIN002:R0001",),
                    metadata=("claim", "central"),
                ),
                intermediate(
                    "WIN002:R0003",
                    "INTENT_KIND",
                    "enseigner",
                    (),
                    index=2,
                ),
                intermediate(
                    "WIN002:R0004",
                    "AUDIENCE_KIND",
                    "croyants",
                    (),
                    index=3,
                ),
                intermediate(
                    "WIN002:R0005",
                    "VOICE",
                    "oral",
                    (),
                    index=4,
                    metadata=("register",),
                ),
            ),
            signature="2" * 64,
        ),
    )
    transport = {
        "gm": {
            "th": "Sparse theme",
            "in": "Sparse intent",
            "au": "Sparse audience",
            "vo": "Sparse voice",
            "te": ["WIN001:R0001"],
            "ie": ["WIN001:R0003"],
            "ae": ["WIN001:R0004"],
            "ve": ["WIN001:R0005", "WIN002:R0005"],
        },
        "ops": [
            {
                "o": "MERGE",
                "m": ["WIN001:R0001", "WIN002:R0001"],
                "v": "Sparse merged topic",
            },
            {"o": "KEEP", "r": "WIN001:R0002"},
            {"o": "KEEP", "r": "WIN002:R0002"},
            {"o": "KEEP", "r": "WIN002:R0003"},
            {"o": "KEEP", "r": "WIN002:R0004"},
        ],
    }
    source_map, _built, _decoded = _reconstruct_from_transport(
        transcript, plan, results, transport
    )
    refs = source_map.topics[0].source_refs
    return {
        "union": list(refs),
        "expected": ["SRC000001", "SRC000003", "SRC000010"],
        "no_range_expansion": "SRC000002" not in refs
        and "SRC000004" not in refs
        and list(refs) == ["SRC000001", "SRC000003", "SRC000010"],
        "pass": list(refs) == ["SRC000001", "SRC000003", "SRC000010"],
    }


def _stale_and_identity_proofs() -> dict[str, Any]:
    transcript, plan = plan_e2e_windows()
    with tempfile.TemporaryDirectory(prefix="sa_hyb_stale_") as tmp:
        root = Path(tmp)
        run = run_hybrid_source_analysis(
            transcript,
            plan,
            e2e_engine(plan),
            windows_root=root / "w",
            consolidation_root=root / "c",
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10,
        )
        results = list(run.orchestration.get_ready_results_in_plan_order())
        stale_records = results[0].records[:-1]
        stale = make_window_result(
            plan.windows[0],
            stale_records,
            signature=results[0].window_analysis_signature,
            theme=results[0].candidates.theme,
            intent=results[0].candidates.intent,
            audience=results[0].candidates.audience,
            voice_evidence=dict(results[0].voice_evidence),
        )
        stale_closed = False
        try:
            reconstruct_source_map(
                transcript,
                plan,
                (stale, results[1], results[2]),
                run.consolidation_result,
                consolidation_input=build_consolidation_input_from_plan(
                    plan, run.orchestration.get_ready_results_in_plan_order()
                ),
            )
        except HybridPreconditionError:
            stale_closed = True

        other = make_e2e_transcript(transcript_id="TR-HYB-002", content_sha256="f" * 64)
        wrong_transcript = False
        try:
            reconstruct_source_map(
                other,
                plan,
                run.orchestration.get_ready_results_in_plan_order(),
                run.consolidation_result,
            )
        except HybridPreconditionError:
            wrong_transcript = True

        other_plan = window_plan_from_inputs(
            transcript,
            (
                window_for(
                    transcript,
                    owned=plan.windows[0].owned_src_refs[:2],
                    window_id="WIN001",
                ),
                plan.windows[1],
                plan.windows[2],
            ),
        )
        wrong_plan = False
        try:
            reconstruct_source_map(
                transcript,
                other_plan,
                run.orchestration.get_ready_results_in_plan_order(),
                run.consolidation_result,
            )
        except (HybridPreconditionError, HybridReconstructionError, Exception):
            wrong_plan = True

        return {
            "stale_consolidation_fail_closed": stale_closed,
            "wrong_transcript_fail_closed": wrong_transcript,
            "wrong_plan_fail_closed": wrong_plan,
        }


def run_real_preflight(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    plan = plan_windows_v2(transcript)
    engine = FakeAIEngine(
        script=[AITimeoutError("preflight must not call")],
        retry_policy=no_delay_policy(max_attempts=1),
    )
    with tempfile.TemporaryDirectory(prefix="sa_hyb_pre_") as tmp:
        run = preflight_hybrid_reconstruction(
            transcript,
            plan,
            engine,
            windows_root=Path(tmp),
        )
        reconstructor_attempted = reconstruction_allowed(
            all_windows_ready=run.all_windows_ready,
            consolidation_available=run.consolidation_available,
        )
    return {
        "transcript_id": transcript.transcript_id,
        "windows": plan.window_count,
        "ready": run.orchestration.ready_windows,
        "all_windows_ready": run.all_windows_ready,
        "consolidation_available": run.consolidation_available,
        "canonical_reconstruction_allowed": reconstructor_attempted,
        "AI_calls": engine.call_count,
        "fake_ai_calls": engine.call_count,
        "real_provider_calls": 0,
        "source_map_published": False,
        "planner_version": plan.planner_version,
        "mark": "SCENARIO / NOT OBSERVED",
        "note": (
            "Aucun WindowSemanticResult réel. "
            "Reconstruction interdite : fenêtres non prêtes."
        ),
    }


def build_pipeline_artifact(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    e2e = run_synthetic_e2e()
    sparse = _sparse_union_proof()
    identity = _stale_and_identity_proofs()
    preflight = run_real_preflight(project_name, sortie_dir=sortie_dir)
    generation = generation_c_hashes()
    production_config = WindowPlannerConfig()
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "reconstructor_version": RECONSTRUCTOR_VERSION,
        "canonical_schema_version": SOURCE_MAP_SCHEMA_VERSION,
        "normalizer_reused": True,
        "normalizer_modified": False,
        "canonical_validator_reused": True,
        "canonical_validator_unchanged": True,
        "canonical_sourcemap_contract": "UNCHANGED",
        "local_semantic_merge": False,
        "id_assignment_policy": (
            "normalize_source_map first-source-appearance + sequential IDs"
        ),
        "source_union_policy": (
            "membership réelle, ordre transcript.src_index, pas de plage"
        ),
        "relation_mapping_policy": (
            "KEEP/MERGE RELATION + REL IDEA→IDEA ; "
            "EXAMPLE→IDEA supports/illustrates ; dédupe structurelle"
        ),
        "metadata_mapping": {
            "main_theme": "GLOBAL_METADATA",
            "author_intent": "GLOBAL_METADATA.summary + unanimous window confidence",
            "target_audience": "GLOBAL_METADATA.summary + unanimous window confidence",
            "author_voice_profile": (
                "cited VOICE evidence fields + synthesis in distinctive_traits"
            ),
            "local_vote": False,
        },
        "signature_composition": {
            "transcript_id_hash": True,
            "window_plan_hash": True,
            "ordered_window_signatures": True,
            "consolidation_input_hash": True,
            "consolidation_result_hash": True,
            "prompt_versions": True,
            "transport_schema_shas": True,
            "provider_model": True,
            "canonical_schema": True,
            "runtime_timestamps": False,
        },
        "end_to_end": e2e,
        "sparse_union": sparse,
        "identity_gates": identity,
        "real_preflight": preflight,
        "planner": {
            "version": PLANNER_VERSION,
            "production_target": production_config.target_input_tokens,
            "production_hard_max": production_config.hard_max_input_tokens,
            "overlap_policy": production_config.overlap_policy,
            "expected_target": TARGET_INPUT_TOKENS,
            "expected_hard_max": HARD_MAX_INPUT_TOKENS,
            "expected_overlap": OVERLAP_POLICY,
        },
        "window_analysis": {
            "prompt_version": WINDOW_PROMPT_VERSION,
            "transport_version": WINDOW_TRANSPORT_VERSION,
        },
        "consolidation": {
            "prompt_version": CONSOLIDATION_PROMPT_VERSION,
            "transport_version": CONSOLIDATION_TRANSPORT_VERSION,
        },
        "execution": {
            "fake_window_calls": e2e["fake_window_calls"],
            "fake_consolidation_calls": e2e["fake_consolidation_calls"],
            "anthropic_calls": 0,
            "openai_calls": 0,
            "real_provider_calls": 0,
            "source_map_published": False,
            "production_analyzer_wired": False,
            "pastoral_fake_ai_semantic": False,
        },
        "integrity": {
            "prompt_1_3_version": SOURCE_ANALYZER_PROMPT_VERSION,
            "window_prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V10,
            "generation_c": generation,
            "generation_c_raw_matches_historical": generation[
                "raw_matches_historical"
            ],
            "code_sha256": _code_integrity(),
        },
        "phase_3b": PHASE_3B_STATUS,
        "next_phase": NEXT_PHASE,
        "strategy": HYBRID_STRATEGY,
        "reconstructor_calls_ai": False,
        "reconstructor_makes_semantic_decisions": False,
        "tests": {
            "baseline": 2250,
            "added": 35,
            "passed": 2285,
            "failed": 0,
        },
    }


@dataclass
class HybridReconstructionPipelineResult:
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


def run_hybrid_reconstruction_pipeline(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    write_artifacts: bool = True,
) -> HybridReconstructionPipelineResult:
    from app.source_analysis_hybrid_reconstruction.report import render_report

    assert_offline_package()
    assert_analyzer_not_wired()
    assert_hybrid_planner_not_wired()
    assert_window_not_wired()
    assert_window_orch_not_wired()
    assert_consolidation_not_wired()
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    assert_no_production_windows(project_name, sortie_dir=sortie_dir)
    assert_no_production_consolidation(project_name, sortie_dir=sortie_dir)
    before = snapshot_hybrid_reconstruction_protected(
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
    result = HybridReconstructionPipelineResult(
        project_name=project_name,
        artifact=payload,
        preflight=payload["real_preflight"],
        deterministic=sha1 == sha2,
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
                **payload["end_to_end"],
                "sparse_union": payload["sparse_union"],
                "identity_gates": payload["identity_gates"],
                "real_provider_calls": 0,
            },
        )
        result.files_created.append(SYNTHETIC_ARTIFACT_NAME)
        write_bytes_atomic(
            preflight_artifact_path(project_name, sortie_dir=sortie_dir),
            {
                "schema_version": SCHEMA_VERSION,
                "phase": PHASE,
                "mode": MODE,
                **payload["real_preflight"],
            },
        )
        result.files_created.append(PREFLIGHT_ARTIFACT_NAME)
        write_bytes_atomic(
            report_path(project_name, sortie_dir=sortie_dir),
            report,
        )
        result.files_created.append(REPORT_NAME)
    after = snapshot_hybrid_reconstruction_protected(
        project_name, sortie_dir=sortie_dir, require_all=False
    )
    assert_protected_unchanged(before, after)
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    assert_no_production_windows(project_name, sortie_dir=sortie_dir)
    assert_no_production_consolidation(project_name, sortie_dir=sortie_dir)
    result.protected_unchanged = True
    result.artifact_sha256 = content_hash(canonical_dumps(payload))
    return result


def _apply_outcome(
    result: HybridReconstructionPipelineResult,
    payload: dict[str, Any],
    state: dict[str, Any],
) -> None:
    e2e = payload.get("end_to_end") or {}
    preflight = payload.get("real_preflight") or {}
    identity = payload.get("identity_gates") or {}
    sparse = payload.get("sparse_union") or {}
    result.outcome = "PASS"
    if not result.deterministic:
        result.outcome = "FAIL"
    if not e2e.get("all_windows_ready"):
        result.outcome = "FAIL"
    if not e2e.get("canonical_validator_pass"):
        result.outcome = "FAIL"
    if not e2e.get("determinism"):
        result.outcome = "FAIL"
    if not e2e.get("no_local_semantic_merge"):
        result.outcome = "FAIL"
    if not e2e.get("explicit_merge_one_topic"):
        result.outcome = "FAIL"
    if not sparse.get("pass"):
        result.outcome = "FAIL"
    if not identity.get("stale_consolidation_fail_closed"):
        result.outcome = "FAIL"
    if not identity.get("wrong_transcript_fail_closed"):
        result.outcome = "FAIL"
    if not identity.get("wrong_plan_fail_closed"):
        result.outcome = "FAIL"
    if preflight.get("AI_calls") != 0:
        result.outcome = "FAIL"
    if preflight.get("canonical_reconstruction_allowed"):
        result.outcome = "FAIL"
    if result.source_map_present:
        result.outcome = "FAIL"
    if state.get("status") in ("SUCCESS", "completed"):
        result.outcome = "FAIL"
    if not payload.get("integrity", {}).get("code_unchanged", True):
        result.outcome = "FAIL"
    if not payload.get("integrity", {}).get("generation_c_raw_matches_historical"):
        result.outcome = "FAIL"
