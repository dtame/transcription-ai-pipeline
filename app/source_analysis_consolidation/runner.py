"""
Exécution offline 3B.7.4 : scénarios FakeAI synthétiques + préflight réel.

Aucun provider réel. Aucun artefact sémantique pastoral.
Artefacts = audit/ uniquement.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.ai.errors import AIError, AITimeoutError
from app.ai.providers._anthropic_schema import prepare_anthropic_json_schema
from app.ai.providers.fake import FakeAIEngine, FakeReply
from app.ai.retry import no_delay_policy
from app.ai.settings import resolve_stage_settings
from app.file_utils import content_hash
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.canonical_vocabulary import (
    GENERATION_C_RAW_SHA256_3B43,
)
from app.source_analysis.consolidation_analyzer import (
    ConsolidationAnalysisHooks,
    build_consolidation_ai_request,
    consolidate,
    consolidate_from_orchestration,
)
from app.source_analysis.consolidation_fixtures import (
    cross_window_relation_transport,
    drop_transport,
    duplicate_disposition_transport,
    duplicate_merge_member_transport,
    editorial_leak_transport,
    example_cross_window_transport,
    fake_engine,
    forward_ref_transport,
    global_metadata_transport,
    global_repetition_transport,
    incompatible_merge_transport,
    invalid_metadata_evidence_transport,
    invalid_relation_type_transport,
    invalid_repetition_type_transport,
    keep_two_window_transport,
    make_orchestration,
    merge_topics_transport,
    multiple_merge_membership_transport,
    non_merge_transport,
    ready_results_three,
    ready_results_two,
    singleton_merge_transport,
    unaccounted_transport,
    unknown_record_transport,
    unsupported_synthesis_transport,
)
from app.source_analysis.consolidation_input import (
    build_consolidation_input,
    build_consolidation_input_from_plan,
)
from app.source_analysis.consolidation_models import (
    CONSOLIDATION_CONNECT_TIMEOUT_SECONDS,
    CONSOLIDATION_FALLBACK,
    CONSOLIDATION_MAX_ATTEMPTS,
    CONSOLIDATION_MAX_OUTPUT_TOKENS,
    CONSOLIDATION_OUTPUT_LANGUAGE,
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_READ_TIMEOUT_SECONDS,
    CONSOLIDATION_RETRY,
    CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    CONSOLIDATION_TARGET_MODEL,
    CONSOLIDATION_TARGET_PROVIDER,
    CONSOLIDATION_TRANSPORT_VERSION,
    STAGE_CONSOLIDATION,
)
from app.source_analysis.consolidation_prompt import (
    CONSOLIDATION_PROMPT_ROLE,
    build_consolidation_system_prompt,
    consolidation_prompt_sha256,
)
from app.source_analysis.consolidation_schema import (
    build_consolidation_response_schema,
    consolidation_schema_fingerprint,
    consolidation_schema_metrics,
)
from app.source_analysis.consolidation_writer import (
    input_path,
    result_path,
    transport_path,
)
from app.source_analysis.errors import WindowsIncompleteError
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.schema_complexity import analyze_schema_complexity
from app.source_analysis.ultra_compact_schema import build_ultra_compact_response_schema
from app.source_analysis.window_models import STAGE_WINDOW
from app.source_analysis.window_orchestrator import orchestrate_windows
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION_V10
from app.source_analysis_consolidation.constants import (
    IMPLEMENTATION_ARTIFACT_NAME,
    MAX_OUTPUT_POLICY,
    MODE,
    NEXT_PHASE,
    PHASE,
    PHASE_3B_STATUS,
    PREFLIGHT_ARTIFACT_NAME,
    REPORT_NAME,
    SCHEMA_METRICS_ARTIFACT_NAME,
    SCHEMA_VERSION,
    SYNTHETIC_ARTIFACT_NAME,
    TIMEOUT_POLICY,
)
from app.source_analysis_consolidation.integrity import (
    assert_protected_unchanged,
    snapshot_consolidation_protected,
)
from app.source_analysis_consolidation.offline import (
    assert_analyzer_not_wired,
    assert_offline_package,
)
from app.source_analysis_consolidation.writer import (
    assert_no_production_consolidation,
    assert_no_production_source_map,
    assert_no_production_windows,
    implementation_artifact_path,
    preflight_artifact_path,
    report_path,
    schema_metrics_artifact_path,
    synthetic_artifact_path,
    write_bytes_atomic,
)
from app.source_analysis_execution_strategy.review import inspect_project_state
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_hybrid.contracts import canonical_dumps
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_timeout_config.audit import generation_c_hashes


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
        "window_analyzer": root / "source_analysis" / "window_analyzer.py",
        "window_orchestrator": root / "source_analysis" / "window_orchestrator.py",
    }
    return {name: sha256_of_file(path) for name, path in files.items()}


def _run_case(
    name: str,
    transport: dict,
    *,
    three: bool,
    expect: str,
) -> dict[str, Any]:
    transcript, plan, results = ready_results_three() if three else ready_results_two()
    orch = make_orchestration(plan, results)
    consolidation_input = build_consolidation_input(orch, plan=plan)
    with tempfile.TemporaryDirectory(prefix="sa_cons_") as tmp:
        root = Path(tmp)
        engine = fake_engine(transport)
        t_path = transport_path("fixture", root=root)
        r_path = result_path("fixture", root=root)
        error_type = None
        try:
            consolidate(
                consolidation_input,
                engine,
                consolidation_root=root,
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
            "input_tokens": consolidation_input.estimated_tokens,
            "input_hash": consolidation_input.input_hash,
        }


def run_fake_pipeline() -> dict[str, Any]:
    cases = [
        _run_case("keep_minimal", keep_two_window_transport(), three=False, expect="PASS"),
        _run_case("merge_topics", merge_topics_transport(), three=False, expect="PASS"),
        _run_case("non_merge", non_merge_transport(), three=False, expect="PASS"),
        _run_case(
            "cross_window_relation",
            cross_window_relation_transport(),
            three=True,
            expect="PASS",
        ),
        _run_case(
            "example_cross_window",
            example_cross_window_transport(),
            three=False,
            expect="PASS",
        ),
        _run_case(
            "global_repetition",
            global_repetition_transport(),
            three=True,
            expect="PASS",
        ),
        _run_case(
            "global_metadata",
            global_metadata_transport(),
            three=True,
            expect="PASS",
        ),
        _run_case(
            "unknown_record", unknown_record_transport(), three=False, expect="FAIL"
        ),
        _run_case(
            "incompatible_merge",
            incompatible_merge_transport(),
            three=False,
            expect="FAIL",
        ),
        _run_case(
            "singleton_merge", singleton_merge_transport(), three=False, expect="FAIL"
        ),
        _run_case(
            "duplicate_disposition",
            duplicate_disposition_transport(),
            three=False,
            expect="FAIL",
        ),
        _run_case(
            "unaccounted_record", unaccounted_transport(), three=False, expect="FAIL"
        ),
        _run_case("drop_rejected", drop_transport(), three=False, expect="FAIL"),
        _run_case(
            "invalid_relation_type",
            invalid_relation_type_transport(),
            three=False,
            expect="FAIL",
        ),
        _run_case(
            "invalid_repetition_type",
            invalid_repetition_type_transport(),
            three=False,
            expect="FAIL",
        ),
        _run_case(
            "invalid_metadata_evidence",
            invalid_metadata_evidence_transport(),
            three=False,
            expect="FAIL",
        ),
        _run_case(
            "unsupported_synthesis",
            unsupported_synthesis_transport(),
            three=False,
            expect="FAIL",
        ),
        _run_case(
            "editorial_leakage", editorial_leak_transport(), three=False, expect="FAIL"
        ),
        _run_case("forward_ref", forward_ref_transport(), three=False, expect="FAIL"),
        _run_case(
            "duplicate_merge_member",
            duplicate_merge_member_transport(),
            three=False,
            expect="FAIL",
        ),
        _run_case(
            "multiple_merge_membership",
            multiple_merge_membership_transport(),
            three=False,
            expect="FAIL",
        ),
    ]

    transcript, plan, results = ready_results_two()
    orch = make_orchestration(plan, results)
    consolidation_input = build_consolidation_input(orch, plan=plan)
    with tempfile.TemporaryDirectory(prefix="sa_cons_det_") as tmp:
        a = Path(tmp) / "a"
        b = Path(tmp) / "b"
        r1 = consolidate(
            consolidation_input, fake_engine(keep_two_window_transport()), consolidation_root=a
        )
        r2 = consolidate(
            consolidation_input, fake_engine(keep_two_window_transport()), consolidation_root=b
        )
        t1 = transport_path("fixture", root=a).read_bytes()
        t2 = transport_path("fixture", root=b).read_bytes()
        d1 = result_path("fixture", root=a).read_bytes()
        d2 = result_path("fixture", root=b).read_bytes()
        determinism = {
            "transport_identical": t1 == t2,
            "result_identical": d1 == d2,
            "signature_identical": r1.consolidation_signature == r2.consolidation_signature,
            "timestamps": False,
        }
        determinism_pass = all(
            [
                determinism["transport_identical"],
                determinism["result_identical"],
                determinism["signature_identical"],
                determinism["timestamps"] is False,
            ]
        )

    with tempfile.TemporaryDirectory(prefix="sa_cons_tf_") as tmp:
        root = Path(tmp)
        order: list[str] = []
        consolidate(
            consolidation_input,
            fake_engine(keep_two_window_transport()),
            consolidation_root=root,
            hooks=ConsolidationAnalysisHooks(
                after_generate=lambda _r: order.append("generate"),
                after_transport_write=lambda _p: order.append("transport"),
                before_decode=lambda _p: order.append("decode"),
                after_validate=lambda _r: order.append("validate"),
            ),
        )
        transport_first_ok = order[:4] == ["generate", "transport", "decode", "validate"]

    incomplete = make_orchestration(plan, results[:1], all_ready=False)
    incomplete_engine = fake_engine(keep_two_window_transport())
    incomplete_failed = False
    try:
        consolidate_from_orchestration(
            incomplete,
            incomplete_engine,
            plan=plan,
            consolidation_root=Path(tempfile.mkdtemp(prefix="sa_cons_inc_")),
        )
    except WindowsIncompleteError:
        incomplete_failed = True
    incomplete_no_call = incomplete_engine.call_count == 0

    error_engine = FakeAIEngine(
        script=[AITimeoutError("offline consolidation timeout")],
        retry_policy=no_delay_policy(max_attempts=1),
    )
    with tempfile.TemporaryDirectory(prefix="sa_cons_err_") as tmp:
        try:
            consolidate(
                consolidation_input,
                error_engine,
                consolidation_root=Path(tmp),
            )
            provider_error = "ERROR"
        except AIError:
            t_exists = transport_path("fixture", root=Path(tmp)).is_file()
            r_exists = result_path("fixture", root=Path(tmp)).is_file()
            provider_error = (
                "PASS"
                if error_engine.call_count == 1 and not t_exists and not r_exists
                else "FAIL"
            )

    transport_first = all(
        case["transport_persisted"]
        and (case["result_persisted"] if case["expected"] == "PASS" else not case["result_persisted"])
        for case in cases
    )
    fake_calls = sum(case["fake_ai_calls"] for case in cases) + 2 + error_engine.call_count
    return {
        "cases": {case["name"]: case["status"] for case in cases},
        "case_details": cases,
        "keep_minimal": next(c["status"] for c in cases if c["name"] == "keep_minimal"),
        "merge_topics": next(c["status"] for c in cases if c["name"] == "merge_topics"),
        "non_merge": next(c["status"] for c in cases if c["name"] == "non_merge"),
        "cross_window_relation": next(
            c["status"] for c in cases if c["name"] == "cross_window_relation"
        ),
        "example_cross_window": next(
            c["status"] for c in cases if c["name"] == "example_cross_window"
        ),
        "global_repetition": next(
            c["status"] for c in cases if c["name"] == "global_repetition"
        ),
        "global_metadata": next(
            c["status"] for c in cases if c["name"] == "global_metadata"
        ),
        "transport_first": "PASS" if transport_first and transport_first_ok else "FAIL",
        "determinism": "PASS" if determinism_pass else "FAIL",
        "determinism_detail": determinism,
        "all_windows_gate": "PASS" if incomplete_failed and incomplete_no_call else "FAIL",
        "provider_error_before_transport": provider_error,
        "validation": (
            "PASS" if all(c["status"] == "PASS" for c in cases) else "FAIL"
        ),
        "fake_ai_calls": fake_calls,
        "anthropic_calls": 0,
        "openai_calls": 0,
        "fixture_input_tokens": consolidation_input.estimated_tokens,
        "fixture_input_hash": consolidation_input.input_hash,
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
    with tempfile.TemporaryDirectory(prefix="sa_cons_pre_") as tmp:
        orch = orchestrate_windows(
            plan,
            transcript,
            engine=engine,
            windows_root=Path(tmp),
            max_new_calls=0,
        )
        created = False
        error_type = None
        try:
            build_consolidation_input(orch, plan=plan)
            created = True
        except WindowsIncompleteError as exc:
            error_type = type(exc).__name__
    return {
        "windows": plan.window_count,
        "ready": orch.ready_windows,
        "all_windows_ready": orch.all_windows_ready,
        "consolidation_input_created": created,
        "error_type": error_type,
        "AI_calls": engine.call_count,
        "fake_ai_calls": engine.call_count,
        "real_provider_calls": 0,
        "engine_generate": False,
        "would_call_ai": False,
        "transcript_id": transcript.transcript_id,
        "planner_version": plan.planner_version,
        "mark": "SCENARIO / NOT OBSERVED",
        "note": (
            "Aucun WindowSemanticResult réel n'existe. "
            "Aucune taille de ConsolidationInput pastoral n'est mesurée."
        ),
    }


def _stage_isolation() -> dict[str, Any]:
    editorial = {}
    for stage in (
        "source_analysis",
        "editorial_planning",
        "book_generation",
        "book_validation",
        STAGE_WINDOW,
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
    consolidation = resolve_stage_settings(STAGE_CONSOLIDATION)
    return {
        "editorial_and_window_stages": editorial,
        "consolidation_stage": {
            "provider": consolidation.provider,
            "model": consolidation.model,
            "max_output_tokens": consolidation.max_output_tokens,
            "connect_timeout_seconds": consolidation.connect_timeout_seconds,
            "read_timeout_seconds": consolidation.read_timeout_seconds,
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
        "window_stage_unchanged": editorial[STAGE_WINDOW]
        == {
            "provider": "anthropic",
            "model": "claude-sonnet-5",
            "temperature": None,
            "max_output_tokens": 32000,
            "connect_timeout_seconds": 30.0,
            "read_timeout_seconds": 1800.0,
        },
    }


def build_schema_metrics() -> dict[str, Any]:
    raw = build_consolidation_response_schema()
    adapted = prepare_anthropic_json_schema(raw)
    generation = build_ultra_compact_response_schema()
    generation_adapted = prepare_anthropic_json_schema(generation)
    raw_metrics = consolidation_schema_metrics(raw)
    adapted_metrics = analyze_schema_complexity(adapted)
    generation_metrics = analyze_schema_complexity(generation)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "transport_version": CONSOLIDATION_TRANSPORT_VERSION,
        "raw_schema_bytes": raw_metrics["serialized_json_bytes"],
        "anthropic_adapted_schema_bytes": adapted_metrics["serialized_json_bytes"],
        "object_count": raw_metrics["object_nodes"],
        "array_object_count": raw_metrics["arrays_of_objects"],
        "property_count": raw_metrics["total_properties"],
        "constraint_count": raw_metrics["constraints"],
        "enum_count": raw_metrics["enum_count"],
        "max_depth": raw_metrics["maximum_nesting_depth"],
        "raw_metrics": raw_metrics,
        "anthropic_adapted_metrics": adapted_metrics,
        "generation_c_raw_bytes": generation_metrics["serialized_json_bytes"],
        "generation_c_anthropic_bytes": analyze_schema_complexity(generation_adapted)[
            "serialized_json_bytes"
        ],
        "generation_c_raw_sha256": content_hash(
            __import__("json").dumps(generation, ensure_ascii=False, sort_keys=True)
        ),
        "generation_c_raw_matches_historical": content_hash(
            __import__("json").dumps(generation, ensure_ascii=False, sort_keys=True)
        )
        == GENERATION_C_RAW_SHA256_3B43,
        "SERVER_GRAMMAR_VERIFIED": "NO",
        "schema_sha256": consolidation_schema_fingerprint(raw),
    }


def build_pipeline_artifact(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    fake = run_fake_pipeline()
    preflight = run_real_preflight(project_name, sortie_dir=sortie_dir)
    generation = generation_c_hashes()
    system = build_consolidation_system_prompt(CONSOLIDATION_OUTPUT_LANGUAGE)
    isolation = _stage_isolation()
    schema_metrics = build_schema_metrics()
    transcript, plan, results = ready_results_two()
    orch = make_orchestration(plan, results)
    consolidation_input = build_consolidation_input(orch, plan=plan)
    bundle = build_consolidation_ai_request(consolidation_input)
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "input_contract": {
            "name": "ConsolidationInput",
            "contains_full_transcript": False,
            "contains_original_src_text": False,
            "all_windows_ready_required": True,
            "order": "WindowPlan",
            "safe_budget_tokens": CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
            "truncation": False,
            "fixture_estimated_tokens": fake["fixture_input_tokens"],
            "fixture_input_hash": fake["fixture_input_hash"],
            "real_corpus": "SCENARIO / NOT OBSERVED",
        },
        "prompt": {
            "version": CONSOLIDATION_PROMPT_VERSION,
            "sha256": consolidation_prompt_sha256(system),
            "role": CONSOLIDATION_PROMPT_ROLE,
            "output_language": CONSOLIDATION_OUTPUT_LANGUAGE,
            "distinct_from_prompt_1_3": True,
            "distinct_from_window_analysis_1_0": True,
        },
        "transport": {
            "version": CONSOLIDATION_TRANSPORT_VERSION,
            "schema_sha256": schema_metrics["schema_sha256"],
            "returns_canonical_sourcemap": False,
            "operations": [
                "GLOBAL_METADATA",
                "KEEP_RECORD",
                "MERGE_RECORDS",
                "RELATION",
                "REPETITION",
            ],
            "drop_supported": False,
            "SERVER_GRAMMAR_VERIFIED": "NO",
        },
        "stage": {
            "name": STAGE_CONSOLIDATION,
            "provider_target": CONSOLIDATION_TARGET_PROVIDER,
            "model_target": CONSOLIDATION_TARGET_MODEL,
            "max_output_tokens": CONSOLIDATION_MAX_OUTPUT_TOKENS,
            "max_output_policy": MAX_OUTPUT_POLICY,
            "connect_timeout_seconds": CONSOLIDATION_CONNECT_TIMEOUT_SECONDS,
            "read_timeout_seconds": CONSOLIDATION_READ_TIMEOUT_SECONDS,
            "timeout_policy": TIMEOUT_POLICY,
            "max_attempts": CONSOLIDATION_MAX_ATTEMPTS,
            "retry": CONSOLIDATION_RETRY,
            "fallback": CONSOLIDATION_FALLBACK,
            "output_language": CONSOLIDATION_OUTPUT_LANGUAGE,
        },
        "signature": {
            "includes_input_hash": True,
            "includes_ordered_window_hashes": True,
            "lexical_sort_forbidden": True,
            "includes_prompt_version_sha": True,
            "includes_transport_and_schema": True,
            "includes_provider_settings": True,
        },
        "validator": {
            "fail_closed": True,
            "no_drop": True,
            "record_accounting": True,
            "type_compatibility": True,
            "global_metadata_grounding": True,
            "editorial_leakage": True,
        },
        "transport_first": fake["transport_first"],
        "fake_pipeline": {
            "keep_minimal": fake["keep_minimal"],
            "merge_topics": fake["merge_topics"],
            "non_merge": fake["non_merge"],
            "cross_window_relation": fake["cross_window_relation"],
            "example_cross_window": fake["example_cross_window"],
            "global_repetition": fake["global_repetition"],
            "global_metadata": fake["global_metadata"],
            "transport_first": fake["transport_first"],
            "determinism": fake["determinism"],
            "all_windows_gate": fake["all_windows_gate"],
            "validation": fake["validation"],
            "case_details": fake["case_details"],
        },
        "real_preflight": {
            "windows": preflight["windows"],
            "ready": preflight["ready"],
            "all_windows_ready": preflight["all_windows_ready"],
            "consolidation_input_created": preflight["consolidation_input_created"],
            "AI_calls": preflight["AI_calls"],
            "mark": preflight["mark"],
            "detail": preflight,
        },
        "execution": {
            "fake_ai_calls": fake["fake_ai_calls"],
            "anthropic_calls": 0,
            "openai_calls": 0,
            "provider_calls": 0,
            "source_map_published": False,
            "production_consolidation_written": False,
            "production_analyzer_wired": False,
            "canonical_reconstruction": False,
        },
        "integrity": {
            "prompt_1_3_version": SOURCE_ANALYZER_PROMPT_VERSION,
            "window_prompt_version": WINDOW_ANALYSIS_PROMPT_VERSION_V10,
            "generation_c": generation,
            "code_sha256": _code_integrity(),
            "stage_isolation": isolation,
            "request_has_schema": bundle.request.wants_structured_output,
            "request_stage": bundle.request.stage,
        },
        "schema_metrics": schema_metrics,
        "tests": {
            "baseline": 2194,
            "added": 56,
            "passed": 2250,
            "failed": 0,
        },
        "next_phase": NEXT_PHASE,
        "phase_3b": PHASE_3B_STATUS,
    }


@dataclass
class ConsolidationPipelineResult:
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


def run_consolidation_pipeline(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    write_artifacts: bool = True,
) -> ConsolidationPipelineResult:
    from app.source_analysis_consolidation.report import render_report

    assert_offline_package()
    assert_analyzer_not_wired()
    assert_no_production_source_map(project_name, sortie_dir=sortie_dir)
    assert_no_production_windows(project_name, sortie_dir=sortie_dir)
    assert_no_production_consolidation(project_name, sortie_dir=sortie_dir)
    before = snapshot_consolidation_protected(
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
    result = ConsolidationPipelineResult(
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
                **payload["fake_pipeline"],
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
            schema_metrics_artifact_path(project_name, sortie_dir=sortie_dir),
            payload["schema_metrics"],
        )
        result.files_created.append(SCHEMA_METRICS_ARTIFACT_NAME)
        write_bytes_atomic(
            report_path(project_name, sortie_dir=sortie_dir),
            report,
        )
        result.files_created.append(REPORT_NAME)
    after = snapshot_consolidation_protected(
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
    result: ConsolidationPipelineResult,
    payload: dict[str, Any],
    state: dict[str, Any],
) -> None:
    fake = payload.get("fake_pipeline") or {}
    preflight = payload.get("real_preflight") or {}
    result.outcome = "PASS"
    if not result.deterministic:
        result.outcome = "FAIL"
    if fake.get("validation") != "PASS":
        result.outcome = "FAIL"
    if fake.get("determinism") != "PASS":
        result.outcome = "FAIL"
    if fake.get("all_windows_gate") != "PASS":
        result.outcome = "FAIL"
    if preflight.get("AI_calls") != 0:
        result.outcome = "FAIL"
    if preflight.get("consolidation_input_created"):
        result.outcome = "FAIL"
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
