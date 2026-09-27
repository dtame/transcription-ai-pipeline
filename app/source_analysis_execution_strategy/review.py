"""
Comparaison déterministe des stratégies d'exécution — Phase 3B.6.

Aucun horodatage, aucun UUID, aucun réseau.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.file_utils import content_hash
from app.project_state import load_project_state
from app.source_analysis import state as state_module
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.writer import source_map_path
from app.source_analysis_execution_strategy.architecture import (
    inspect_async_batch,
    inspect_cache,
    inspect_plan_windows,
    inspect_protected_contracts,
    inspect_single_response_assumption,
    inspect_streaming,
)
from app.source_analysis_execution_strategy.constants import (
    ATTEMPT_1_ERROR,
    ATTEMPT_1_PROVIDER_BODY,
    ATTEMPT_1_READ_TIMEOUT_SECONDS,
    ATTEMPT_2_CONNECT_TIMEOUT_SECONDS,
    ATTEMPT_2_ELAPSED_MS,
    ATTEMPT_2_ERROR,
    ATTEMPT_2_PROVIDER_BODY,
    ATTEMPT_2_READ_TIMEOUT_SECONDS,
    ATTEMPT_2_REQUESTS_TIMEOUT,
    ATTEMPT_2_TIMEOUT_KIND,
    BASELINE_FAILED,
    BASELINE_PASSED,
    FINAL_FAILED,
    FINAL_PASSED,
    CANDIDATE_WINDOW_INPUT_BUDGETS,
    EXPECTED_CLEAN_SHA256,
    EXPECTED_DURATION_SECONDS,
    EXPECTED_GENERATION_C_ANTHROPIC_SHA256,
    EXPECTED_GENERATION_C_RAW_SHA256,
    EXPECTED_INPUT_MODE,
    EXPECTED_INPUT_TOKENS,
    EXPECTED_MAX_OUTPUT_TOKENS,
    EXPECTED_MODEL,
    EXPECTED_PROMPT_SHA256,
    EXPECTED_PROMPT_VERSION,
    EXPECTED_PROVIDER,
    EXPECTED_REMAINING_MARGIN,
    EXPECTED_SEGMENTS,
    EXPECTED_STAGE,
    EXPECTED_STRATEGY,
    EXPECTED_TRANSCRIPT_ID,
    EXPECTED_USABLE_INPUT_BUDGET,
    EXPECTED_WORDS,
    EXTERNAL_PROVIDER_RESEARCH_REQUIRED,
    FORBIDDEN_TIMEOUT_ESCALATIONS,
    INPUT_COST_PER_1M,
    MODE,
    NEXT_PHASE,
    NEXT_PHASE_LABEL,
    OUTPUT_COST_PER_1M,
    PHASE,
    PHASE_3B_STATUS,
    PRICING_CURRENCY,
    PRICING_EFFECTIVE_DATE,
    PRIMARY_CLASSIFICATION,
    PROVIDER_CALLS,
    RECOMMENDED_STRATEGY,
    SCHEMA_VERSION,
    SECONDARY_CLASSIFICATIONS,
    SOURCE_MAP_PUBLISHED,
    THIRD_GLOBAL_TIMEOUT_ESCALATION_ALLOWED,
)
from app.source_analysis_timeout_config.audit import generation_c_hashes

_EMPTY_NETWORK = {
    "anthropic": 0,
    "openai": 0,
    "whisper": 0,
    "ollama": 0,
    "lm_studio": 0,
    "other": 0,
}


def inspect_project_state(project_name: str, *, sortie_dir=None) -> dict[str, Any]:
    del sortie_dir
    state = load_project_state(project_name)
    block = state_module.load_state_block(state)
    if not isinstance(block, Mapping):
        return {"status": "", "error": None, "present": False}
    return {
        "status": str(block.get("status") or ""),
        "error": block.get("error"),
        "present": True,
        "strategy": block.get("strategy"),
        "prompt_version": block.get("prompt_version"),
    }


def source_map_present(project_name: str, *, sortie_dir=None) -> bool:
    return source_map_path(project_name, sortie_dir=sortie_dir).exists()


def _input_cost(tokens: int) -> str:
    value = (int(tokens) / 1_000_000.0) * float(INPUT_COST_PER_1M)
    return f"{value:.7f}".rstrip("0").rstrip(".") if value else "0"


def build_options(simulation: Mapping[str, Any]) -> dict[str, Any]:
    results = list(simulation.get("results") or [])
    window_counts = {row["budget"]: row["window_count"] for row in results}
    global_tokens = int(
        (simulation.get("global_estimate") or {}).get(
            "estimated_input_tokens", EXPECTED_INPUT_TOKENS
        )
    )
    overhead = int(
        (simulation.get("global_estimate") or {}).get("prompt_overhead_tokens", 0)
    )
    return {
        "global_sync": {
            "option": "A",
            "name": "Global synchronous request with larger timeout",
            "disposition": "NOT_RECOMMENDED_AS_NEXT_EXECUTION_STRATEGY",
            "third_timeout_escalation": "PROHIBITED",
            "forbidden_candidates": list(FORBIDDEN_TIMEOUT_ESCALATIONS),
            "evidence": {
                "attempt_1_timeout_seconds": ATTEMPT_1_READ_TIMEOUT_SECONDS,
                "attempt_2_timeout_seconds": ATTEMPT_2_READ_TIMEOUT_SECONDS,
                "attempt_1_body": ATTEMPT_1_PROVIDER_BODY,
                "attempt_2_body": ATTEMPT_2_PROVIDER_BODY,
                "attempt_2_used_tuple": True,
                "scalar_timeout_bug_explains_attempt_2": False,
            },
            "calls": 1,
            "input_volume": "one complete clean transcript + prompts",
            "resume": False,
            "cacheability": "whole_analysis_only",
            "diagnostic_visibility": "none_until_complete_body",
            "semantic_quality": "highest_if_it_completed",
            "implementation_complexity": "none_already_exists",
        },
        "global_streaming": {
            "option": "B",
            "name": "Global request with streaming transport",
            "disposition": "DEFERRED_NOT_IMPLEMENTED",
            "repository_support": inspect_streaming(),
            "external_verification_required": True,
            "would_preserve_generation_c": "UNKNOWN_REQUIRES_EXTERNAL_VERIFICATION",
            "would_solve_generation_workload": False,
            "calls": 1,
            "resume": False,
            "cacheability": "whole_analysis_only",
            "diagnostic_visibility": "possible_if_chunks_arrive",
            "implementation_complexity": "new_transport_plus_unknown_structured_output_behavior",
        },
        "async_batch": {
            "option": "C",
            "name": "Provider asynchronous / batch / job execution",
            "disposition": "NOT_IMPLEMENTED",
            "repository_support": inspect_async_batch(),
            "external_verification_required": True,
            "calls": 1,
            "resume": "UNKNOWN_IF_PROVIDER_SUPPORTS",
            "would_solve_generation_workload": False,
            "implementation_complexity": "new_provider_protocol_plus_unknown_api",
        },
        "multi_window_local_merge": {
            "option": "D",
            "name": "Deterministic multi-window Source Analysis + local merge",
            "disposition": "REJECTED_AS_PRIMARY",
            "reason": (
                "Local code may make STRUCTURAL decisions only. Exact-string "
                "dedupe of topics/ideas cannot merge synonymous labels without "
                "silent semantic judgment."
            ),
            "window_counts_by_budget": window_counts,
            "calls": "N window calls; 0 consolidation AI calls",
            "duplicated_prompt_overhead": overhead,
            "can_merge_without_semantic_loss": False,
            "implementation_complexity": "window runner + local merge; validator reuse",
        },
        "hierarchical_map_reduce": {
            "option": "E",
            "name": "Hierarchical map-reduce Source Analysis",
            "disposition": "STRONG_ALTERNATIVE",
            "level_1": "independent window analysis, Generation C reusable",
            "level_2": "consolidate compact semantic maps, not the transcript",
            "reduces_original_transcript_in_final_pass": True,
            "window_counts_by_budget": window_counts,
            "calls": "N Level-1 + 1 Level-2",
            "implementation_complexity": "window runner + Level-2 schema/prompt + cache",
        },
        "hybrid_window_global_consolidation": {
            "option": "F",
            "name": "Window analysis + deterministic normalize + AI consolidation",
            "disposition": "RECOMMENDED",
            "level_1": "Generation C window analysis, existing decoder/normalizer/validator",
            "local": "structural IDs, coverage, ordering by first SRC appearance",
            "level_2": "one compact AI consolidation for semantic globals",
            "reduces_original_transcript_in_final_pass": True,
            "preserves_global_semantic_reasoning": True,
            "window_counts_by_budget": window_counts,
            "global_input_tokens_estimate": global_tokens,
            "calls": "N Level-1 + 1 consolidation",
            "implementation_complexity": (
                "window runner, per-window cache, compact consolidation "
                "representation, Level-2 prompt/schema, final local IDs"
            ),
        },
    }


def _structural_vs_semantic() -> dict[str, Any]:
    return {
        "principle": (
            "Local code may make STRUCTURAL decisions. Local code must not "
            "silently make SEMANTIC editorial/analytical decisions intended "
            "for the AI."
        ),
        "structural_local": [
            "metadata copied from transcript (id, duration, language)",
            "stats recountable from merged records",
            "source coverage union of window SRC sets",
            "canonical final IDs assigned locally by first source appearance",
            "ordering of records by first SRC in the clean transcript",
            "sparse SRC identity preservation",
            "rejecting refs outside CLEAN_SOURCE_SET",
        ],
        "semantic_requires_ai": [
            "duplicate topics expressed differently",
            "same idea expressed across windows",
            "cross-window idea relations",
            "examples supporting ideas in another window",
            "repetitions across distant windows",
            "global author intent",
            "global target audience",
            "global main theme",
            "global author voice profile",
            "uncertainties spanning boundaries",
        ],
        "global_metadata_policy": {
            "main_theme": "final_consolidation_only",
            "author_intent": "final_consolidation_only",
            "target_audience": "final_consolidation_only",
            "author_voice_profile": "final_consolidation_only",
            "window_local_copies": (
                "may be emitted as Level-1 observations and fed to the "
                "consolidator; they are not published as the final SourceMap"
            ),
            "reason": (
                "These fields are global semantic judgments. Voting or "
                "concatenating window-local values would be editorial."
            ),
        },
        "topics": {
            "exact_string_dedupe_sufficient": False,
            "example_collision": [
                "faith during trials",
                "using faith in adversity",
            ],
            "consolidator_needs": [
                "window topic label",
                "summary",
                "source_refs (real sparse SRC IDs)",
                "window index",
            ],
        },
        "ideas": {
            "final_ids": "local deterministic canonical IDs by first SRC",
            "window_ids": "local to the window / provider records",
            "consolidator_needs": [
                "summary",
                "kind",
                "importance",
                "source_refs",
                "first_src",
                "window index",
                "window-local relations as SRC-anchored hints, not global indexes",
            ],
        },
        "relations": {
            "generation_c_uses_record_indexes": True,
            "window_indexes_cannot_become_global": True,
            "safe_strategy": (
                "Level-1 relations stay window-local. Level-2 re-emits "
                "relations using SRC-anchored records or newly assigned "
                "global identities after merge. Local code remaps to "
                "canonical idea IDs after consolidation."
            ),
        },
        "source_refs": {
            "real_sparse_src_ids_remain_permanent": True,
            "never_renumber_transcript_srcs": True,
        },
        "traceability": {
            "every_final_substantive_element_needs_real_src_refs": True,
            "multi_window_must_not_weaken": True,
        },
        "completeness": {
            "final_map_must_represent_complete_clean_transcript": True,
            "low_importance_windows_cannot_be_dropped": True,
        },
    }


def _cost_model(simulation: Mapping[str, Any]) -> dict[str, Any]:
    global_tokens = int(
        (simulation.get("global_estimate") or {}).get(
            "estimated_input_tokens", EXPECTED_INPUT_TOKENS
        )
    )
    overhead = int(
        (simulation.get("global_estimate") or {}).get("prompt_overhead_tokens", 0)
    )
    results = list(simulation.get("results") or [])
    window_input_totals: dict[str, Any] = {}
    for row in results:
        total = sum(
            int(window["estimated_input_tokens"]) for window in row.get("windows") or []
        )
        window_input_totals[str(row["budget"])] = {
            "window_count": row["window_count"],
            "sum_estimated_input_tokens": total,
            "illustrative_input_cost": _input_cost(total),
            "plus_unknown_consolidation_input": True,
        }
    return {
        "pricing": {
            "provider": EXPECTED_PROVIDER,
            "model": EXPECTED_MODEL,
            "currency": PRICING_CURRENCY,
            "input_cost_per_1m_tokens": INPUT_COST_PER_1M,
            "output_cost_per_1m_tokens": OUTPUT_COST_PER_1M,
            "effective_date": PRICING_EFFECTIVE_DATE,
            "long_context_regime_modeled": False,
            "unknown_must_not_become_zero": True,
            "output_usage": "unknown_do_not_invent",
        },
        "global_sync_or_streaming_or_batch": {
            "calls": 1,
            "estimated_input_tokens": global_tokens,
            "illustrative_input_cost": _input_cost(global_tokens),
            "output_cost": None,
            "total_cost": None,
        },
        "windowed": {
            "duplicated_system_prompt_per_window": True,
            "prompt_overhead_tokens_per_call": overhead,
            "by_budget": window_input_totals,
            "output_cost": None,
            "total_cost": None,
        },
        "note": (
            "Windowed input is larger than one global input because the "
            "system/task prompt is duplicated. Output tokens remain unknown. "
            "No complete total is claimed. Long-context regimes are unmodeled."
        ),
    }


def _level2_scenarios(simulation: Mapping[str, Any]) -> dict[str, Any]:
    results = list(simulation.get("results") or [])
    scenarios = []
    for per_window in (2000, 5000, 10000, 20000):
        row = {
            "label": "STRUCTURAL_SCENARIO_ESTIMATE_ONLY",
            "assumed_level1_output_tokens_per_window": per_window,
            "prediction": False,
            "by_budget": {},
        }
        for item in results:
            n = int(item["window_count"])
            row["by_budget"][str(item["budget"])] = {
                "windows": n,
                "illustrative_level2_input_tokens": n * per_window,
                "excludes_consolidation_instructions": True,
                "excludes_original_transcript": True,
            }
        scenarios.append(row)
    return {
        "actual_level1_outputs_exist": False,
        "content_invented": False,
        "scenarios": scenarios,
        "note": (
            "No real Level-1 outputs exist. These figures are labeled "
            "structural scenarios only. Linear canary extrapolation is "
            "not used."
        ),
    }


def build_review_audit(
    *,
    simulation: Mapping[str, Any],
    project_name: str | None = None,
    sortie_dir=None,
) -> dict[str, Any]:
    hashes = generation_c_hashes()
    streaming = inspect_streaming()
    batch = inspect_async_batch()
    state = (
        inspect_project_state(project_name, sortie_dir=sortie_dir)
        if project_name
        else {"status": "failed", "error": "AITimeoutError", "present": True}
    )
    published = (
        source_map_present(project_name, sortie_dir=sortie_dir)
        if project_name
        else False
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "mode": MODE,
        "evidence": {
            "attempt_1": {
                "read_timeout_seconds": ATTEMPT_1_READ_TIMEOUT_SECONDS,
                "provider_body": ATTEMPT_1_PROVIDER_BODY,
                "error": ATTEMPT_1_ERROR,
                "http_timeout_form": "scalar",
            },
            "attempt_2": {
                "connect_timeout_seconds": ATTEMPT_2_CONNECT_TIMEOUT_SECONDS,
                "read_timeout_seconds": ATTEMPT_2_READ_TIMEOUT_SECONDS,
                "requests_timeout": list(ATTEMPT_2_REQUESTS_TIMEOUT),
                "elapsed_ms": ATTEMPT_2_ELAPSED_MS,
                "timeout_kind": ATTEMPT_2_TIMEOUT_KIND,
                "provider_body": ATTEMPT_2_PROVIDER_BODY,
                "error": ATTEMPT_2_ERROR,
                "http_timeout_form": "tuple",
                "scalar_timeout_bug_still_plausible": False,
            },
        },
        "current_problem": {
            "observation": (
                "A global non-streaming request containing the complete clean "
                "transcript did not yield a response body within either "
                "3600 s or 7200 s."
            ),
            "primary_classification": PRIMARY_CLASSIFICATION,
            "secondary_classifications": list(SECONDARY_CLASSIFICATIONS),
            "not_concluded": [
                "Anthropic cannot process it",
                "Anthropic processed it but a proxy discarded it",
                "model generation itself took >7200 s",
            ],
            "third_global_timeout_retry": "PROHIBITED",
            "context_capacity_is_the_blocker": False,
        },
        "global_context": {
            "fits": True,
            "estimated_input_tokens": EXPECTED_INPUT_TOKENS,
            "usable_budget": EXPECTED_USABLE_INPUT_BUDGET,
            "margin": EXPECTED_REMAINING_MARGIN,
            "measured_simulation_tokens": (simulation.get("global_estimate") or {}).get(
                "estimated_input_tokens"
            ),
            "max_output_tokens": EXPECTED_MAX_OUTPUT_TOKENS,
            "corpus_fits_but_single_call_failed_twice": True,
        },
        "resolved_and_not_current_blocker": {
            "generation_c_grammar_compatibility": "VERIFIED",
            "prompt_1_3_canonical_vocabulary_contract": "VERIFIED",
            "clean_derived_provenance": "VERIFIED",
            "sparse_src_support": "VERIFIED",
            "context_size_admission": "PASS",
            "connect_read_timeout_separation": "VERIFIED",
            "canonical_decoder_design": "VERIFIED",
            "canonical_sourcemap_validator": "VERIFIED",
            "canary_pipeline": "PASS",
        },
        "input": {
            "transcript_id": EXPECTED_TRANSCRIPT_ID,
            "mode": EXPECTED_INPUT_MODE,
            "segments": EXPECTED_SEGMENTS,
            "words": EXPECTED_WORDS,
            "duration_seconds": EXPECTED_DURATION_SECONDS,
            "sha256": EXPECTED_CLEAN_SHA256,
        },
        "integrity": {
            "prompt_version": SOURCE_ANALYZER_PROMPT_VERSION,
            "prompt_sha256_historical": EXPECTED_PROMPT_SHA256,
            "generation_c": hashes,
            "expected_raw_sha256": EXPECTED_GENERATION_C_RAW_SHA256,
            "expected_anthropic_sha256": EXPECTED_GENERATION_C_ANTHROPIC_SHA256,
            "protected_contracts": inspect_protected_contracts(),
            "expected_provider": EXPECTED_PROVIDER,
            "expected_model": EXPECTED_MODEL,
            "expected_stage": EXPECTED_STAGE,
            "expected_strategy": EXPECTED_STRATEGY,
            "expected_prompt_version": EXPECTED_PROMPT_VERSION,
        },
        "architecture": {
            "single_response_assumption": inspect_single_response_assumption(),
            "plan_windows": inspect_plan_windows(),
            "cache": inspect_cache(),
            "streaming": streaming,
            "async_batch": batch,
        },
        "options": build_options(simulation),
        "window_simulation": {
            "candidate_budgets": list(CANDIDATE_WINDOW_INPUT_BUDGETS),
            "overlap_segments": (simulation.get("planner_notes") or {}).get(
                "overlap_used"
            ),
            "planner_notes": simulation.get("planner_notes") or {},
            "results": simulation.get("results") or [],
            "global_estimate": simulation.get("global_estimate") or {},
            "observation": (
                "plan_windows overlap={overlap} produced window counts "
                "{counts}. Prompt overhead tokens={overhead}. "
                "{limitation}"
            ).format(
                overlap=(simulation.get("planner_notes") or {}).get("overlap_used"),
                counts={
                    row["budget"]: row["window_count"]
                    for row in (simulation.get("results") or [])
                },
                overhead=(simulation.get("global_estimate") or {}).get(
                    "prompt_overhead_tokens"
                ),
                limitation=(simulation.get("planner_notes") or {}).get(
                    "limitation", ""
                ),
            ),
        },
        "consolidation": _structural_vs_semantic(),
        "level2_input_scenarios": _level2_scenarios(simulation),
        "cache_resume": inspect_cache(),
        "cost": _cost_model(simulation),
        "reliability": {
            "global_sync": {
                "single_point_failure": True,
                "resume": False,
                "cacheability": "all_or_nothing",
                "diagnostic_visibility": "none_mid_call",
                "partial_progress": False,
            },
            "hybrid": {
                "single_point_failure": False,
                "resume": "per_window_if_signatures_added",
                "cacheability": "per_window_plus_consolidation",
                "diagnostic_visibility": "per_call",
                "partial_progress": True,
            },
        },
        "semantic_quality": {
            "global_sync": "single coherent pass if it completed",
            "local_merge_only": "structural ok, semantic loss likely",
            "hybrid": (
                "window fidelity plus one global semantic consolidation; "
                "cross-window relations depend on Level-2 quality"
            ),
        },
        "implementation_complexity": {
            "global_sync_longer_timeout": "none_but_prohibited",
            "streaming": "transport + unknown structured-output behavior",
            "async_batch": "new provider protocol, not in repo",
            "hybrid": (
                "window runner, cache signatures, consolidation "
                "representation, Level-2 prompt/schema, tests; "
                "Prompt 1.3 / Generation C / decoder / validator stay protected"
            ),
        },
        "recommended_strategy": RECOMMENDED_STRATEGY,
        "external_provider_research_required": EXTERNAL_PROVIDER_RESEARCH_REQUIRED,
        "external_knowledge_gaps": [
            "Anthropic streaming + json_schema structured outputs guarantees",
            "Anthropic Message Batches structured-output support",
            "upstream/proxy maximum execution behavior",
            "whether a silent non-streaming generation continues after client timeout",
        ],
        "external_research_not_required_to_select_architecture": True,
        "next_phase": NEXT_PHASE,
        "next_phase_label": NEXT_PHASE_LABEL,
        "project_state": state,
        "source_map_present": published,
        "tests": {
            "baseline_passed": BASELINE_PASSED,
            "baseline_failed": BASELINE_FAILED,
            "final_passed": FINAL_PASSED,
            "final_failed": FINAL_FAILED,
        },
        "execution": {
            "provider_calls": PROVIDER_CALLS,
            "engine_generate": 0,
            "source_map_published": SOURCE_MAP_PUBLISHED,
            "attempt_3_executed": False,
            "timeout_increased": False,
            "production_architecture_changed": False,
            "phase_3b_status": PHASE_3B_STATUS,
        },
        "network": dict(_EMPTY_NETWORK),
    }


def review_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"
    return content_hash(encoded)


def build_deterministic_review(
    simulation: Mapping[str, Any],
    *,
    project_name: str | None = None,
    sortie_dir=None,
) -> tuple[dict[str, Any], str, str]:
    first = build_review_audit(
        simulation=simulation, project_name=project_name, sortie_dir=sortie_dir
    )
    second = build_review_audit(
        simulation=simulation, project_name=project_name, sortie_dir=sortie_dir
    )
    sha1 = review_sha256(first)
    sha2 = review_sha256(second)
    first["determinism"] = {
        "run1_sha256": sha1,
        "run2_sha256": sha2,
        "identical": sha1 == sha2,
        "timestamps": False,
        "uuid": False,
        "randomness": False,
    }
    return first, sha1, sha2
