"""
Contrats de design 3B.7 — données déterministes, pas d'implémentation production.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.source_analysis_hybrid_design.constants import (
    BOUNDARY_CONTEXT_POLICY,
    CANONICAL_SOURCEMAP_CONTRACT,
    CANONICAL_VALIDATOR,
    CONSOLIDATION_CONNECT_TIMEOUT_SECONDS,
    CONSOLIDATION_MAX_OUTPUT_TOKENS,
    CONSOLIDATION_PROMPT_VERSION,
    CONSOLIDATION_READ_TIMEOUT_SECONDS,
    CONSOLIDATION_SAFE_INPUT_TOKENS,
    CONSOLIDATION_TRANSPORT_VERSION,
    EXECUTION_ORDER,
    EXPECTED_MODEL,
    EXPECTED_PROMPT_VERSION,
    EXPECTED_PROVIDER,
    HARD_MAX_INPUT_TOKENS,
    NEXT_PHASE,
    NEXT_PHASE_LABEL,
    OVERLAP_POLICY,
    PLANNER_VERSION,
    STAGE_AGGREGATE,
    STAGE_CONSOLIDATION,
    STAGE_WINDOW,
    TARGET_INPUT_TOKENS,
    TINY_TAIL_MIN_CONTENT_OVERHEAD_FACTOR,
    TINY_TAIL_MIN_FRACTION_OF_TARGET,
    WINDOW_CONNECT_TIMEOUT_SECONDS,
    WINDOW_MAX_OUTPUT_TOKENS,
    WINDOW_PROMPT_VERSION,
    WINDOW_READ_TIMEOUT_SECONDS,
    WINDOW_TRANSPORT_VERSION,
)


def window_design(simulation: Mapping[str, Any]) -> dict[str, Any]:
    selected = simulation["selected_policy"]
    return {
        "schema_version": "1.0",
        "phase": "3B.7",
        "mode": "OFFLINE_DESIGN",
        "planner": {
            "name": "WindowPlannerV2",
            "version": PLANNER_VERSION,
            "adopt_historical_plan_windows": False,
            "target_input_tokens": TARGET_INPUT_TOKENS,
            "hard_max_input_tokens": HARD_MAX_INPUT_TOKENS,
            "overlap_policy": OVERLAP_POLICY,
            "boundary_context_policy": BOUNDARY_CONTEXT_POLICY,
            "tiny_tail_policy": {
                "min_content_tokens": (
                    "max(2 * prompt_overhead, "
                    "0.15 * (target_input_tokens - prompt_overhead))"
                ),
                "min_fraction_of_target_content": TINY_TAIL_MIN_FRACTION_OF_TARGET,
                "overhead_factor": TINY_TAIL_MIN_CONTENT_OVERHEAD_FACTOR,
                "action": (
                    "merge last into previous if combined <= hard_max; "
                    "else steal SRC from previous until last >= min"
                ),
            },
            "boundary_rule": "SRC boundaries only; never split a SRC; never truncate",
            "oversized_src": "FAIL OVERSIZED_SRC; no silent split",
            "window_id": "WIN001..WINnnn by source appearance",
            "expected_windows": selected["expected_windows"],
            "windows": selected["windows"],
        },
        "window_input_contract": {
            "type": "WindowInput",
            "deterministic": True,
            "forbidden_in_canonical_contract": ["timestamp", "uuid", "host"],
            "fields": [
                "window_id",
                "transcript_id",
                "planner_version",
                "owned_src_refs",
                "context_src_refs",
                "first_owned_src",
                "last_owned_src",
                "estimated_input_tokens",
                "owned_src_ids_sha256",
                "owned_content_sha256",
                "input_hash",
            ],
        },
        "ownership": {
            "each_src_owned_exactly_once": True,
            "context_src_not_owned": True,
            "duplicate_semantic_ownership_forbidden": True,
            "overlap_policy": OVERLAP_POLICY,
            "why_no_owned_overlap": (
                "1-SRC technical overlap caused the tiny tail and is too "
                "small to restore discourse continuity. The consolidator "
                "owns cross-window meaning. Boundary-induced uncertainty "
                "is an explicit window output."
            ),
        },
        "window_analyzer": {
            "role": "analyst of this window only",
            "does_not_create": [
                "chapters",
                "book sections",
                "editorial plan",
                "book prose",
                "final TOP/IDEA/EX/REF/UNC/REP ids",
                "final global theme/intent/audience/voice",
            ],
            "transport": WINDOW_TRANSPORT_VERSION,
            "generation_c_reused": True,
            "generation_d_required": False,
            "prompt_version": WINDOW_PROMPT_VERSION,
            "prompt_1_3_modified": False,
            "provider": EXPECTED_PROVIDER,
            "model": EXPECTED_MODEL,
            "max_output_tokens": WINDOW_MAX_OUTPUT_TOKENS,
            "connect_timeout_seconds": WINDOW_CONNECT_TIMEOUT_SECONDS,
            "read_timeout_seconds": WINDOW_READ_TIMEOUT_SECONDS,
            "stage": STAGE_WINDOW,
            "output_language": "from transcript.primary_language; English for this corpus",
        },
        "window_prompt_rules": [
            "analyze only this window",
            "analyze owned SRCs; use context SRCs only if present and only as boundary context",
            "no unsupported inference",
            "preserve real SRC refs",
            "do not attempt global book structure",
            "do not treat a window theme as the global theme",
            "use canonical vocabulary tokens",
            "Generation C protocol rules",
            "no chapter / book title / editorial plan / publication prose",
        ],
        "window_semantic_output": {
            "transport": WINDOW_TRANSPORT_VERSION,
            "global_fields": "CANDIDATES_ONLY",
            "deferred_to_consolidation": [
                "main_theme",
                "author_intent",
                "target_audience",
                "author_voice_profile",
            ],
            "topics": "local candidates with real SRC refs; no final TOP ids",
            "ideas": "substantive ideas with real SRC refs; no Python paraphrase merge",
            "examples": "retain SRC evidence and local support link if present",
            "references": "source-grounded; no invented citations",
            "uncertainties": "include boundary-induced if needed; not auto-global",
            "repetitions": "in-window only; cross-window belongs to consolidator",
            "relations": "window-local record indexes remapped to WIN:R identities",
        },
        "window_record_identity": {
            "form": "WIN001:R0001",
            "scope": "intermediate only",
            "final_ids_remain": ["TOP", "IDEA", "EX", "REF", "UNC", "REP"],
        },
        "window_validation": {
            "schema": True,
            "transport_version": WINDOW_TRANSPORT_VERSION,
            "window_identity": True,
            "only_allowed_src_refs": True,
            "owned_vs_context_rules": True,
            "controlled_vocabulary": True,
            "record_links_in_window": True,
            "no_editorial_leakage": True,
            "completeness": "window-local; empty collections allowed; do not force ideas/examples",
        },
        "window_completeness": {
            "reuse_global_completeness_blindly": False,
            "substantial_source_zero_ideas_is_global_rule_only": True,
            "window_may_have": [
                "few ideas",
                "no examples",
                "no references",
                "no repetitions",
            ],
            "forbidden": "forcing hallucination to fill empty collections",
        },
        "cache": {
            "granularity": "per_window",
            "signature_includes": [
                "clean_transcript_sha256",
                "planner_version",
                "window_id",
                "owned_src_ids_sha256",
                "owned_content_sha256",
                "context_src_ids_sha256",
                "window_prompt_version",
                "window_prompt_sha256",
                "transport_schema_sha256",
                "provider",
                "model",
                "temperature",
                "max_output_tokens",
                "output_language",
                "stage_settings_window",
            ],
            "failed_window_does_not_invalidate_others": True,
            "invalidation": {
                "window_prompt_change": "all window caches",
                "generation_c_change": "all window caches",
                "planner_boundary_change": "affected and subsequent windows plus consolidation",
                "model_change": "all window caches",
                "semantic_schema_change": "all window caches",
            },
        },
        "resume": {
            "plan_windows_deterministically": True,
            "compute_signatures": True,
            "load_and_validate_matching_cached_results": True,
            "execute_only_missing_or_invalid": True,
            "require_all_windows_valid_before_consolidation": True,
            "implementation": False,
        },
        "failure": {
            "states": ["WINDOW_PENDING", "WINDOW_SUCCESS", "WINDOW_FAILED"],
            "persist_successful_windows": True,
            "retry_policy": "not authorized now; 1 attempt per authorization",
        },
        "execution": {
            "order": EXECUTION_ORDER,
            "parallelism_v1": False,
            "why_sequential": [
                "cost control",
                "call guard",
                "debuggability",
                "rate limits",
                "deterministic operational behavior",
            ],
        },
        "artifacts_production": {
            "root": "analysis/hybrid/windows/WIN00N/",
            "files": ["input.json", "transport.json", "result.json"],
            "audit_root": "audit/",
            "source_map": "analysis/source_map.json",
        },
        "network": {"anthropic": 0, "openai": 0, "provider_calls": 0},
    }


def consolidation_design(simulation: Mapping[str, Any]) -> dict[str, Any]:
    expected_windows = simulation["selected_policy"]["expected_windows"]
    return {
        "schema_version": "1.0",
        "phase": "3B.7",
        "mode": "OFFLINE_DESIGN",
        "required": True,
        "why_required": (
            "Local Python cannot merge paraphrased topics/ideas or decide "
            "global theme/intent/audience/voice. Windows bound heavy "
            "semantic work; the consolidator restores global coherence."
        ),
        "input_contract": {
            "name": "ConsolidationInput",
            "contains_full_transcript": False,
            "contains": [
                "window_record_identity",
                "record_kind",
                "semantic_text_or_value",
                "canonical_controlled_attributes",
                "real_src_refs",
                "window_local_relations_remapped_to_WIN_R",
                "window_metadata",
                "global_field_candidates_and_evidence",
            ],
            "src_text_policy": {
                "include_full_src_text": False,
                "include_quoted_snippets": False,
                "reason": (
                    "Window records already distill meaning. Re-sending SRC "
                    "text would grow the consolidation request toward the "
                    "failed global pattern."
                ),
            },
        },
        "size_scenarios": {
            "mark": "SCENARIO ONLY",
            "window_outputs_do_not_exist": True,
            "assumptions": {
                "window_max_output_tokens": WINDOW_MAX_OUTPUT_TOKENS,
                "expected_windows": expected_windows,
                "records_are_compact_generation_c": True,
            },
            "scenarios": [
                {
                    "name": "sparse",
                    "assumed_records_per_window": 40,
                    "assumed_tokens_per_record": 80,
                    "estimated_consolidation_input_tokens": 40 * 80 * expected_windows,
                },
                {
                    "name": "moderate",
                    "assumed_records_per_window": 120,
                    "assumed_tokens_per_record": 100,
                    "estimated_consolidation_input_tokens": 120 * 100 * expected_windows,
                },
                {
                    "name": "dense",
                    "assumed_records_per_window": 250,
                    "assumed_tokens_per_record": 120,
                    "estimated_consolidation_input_tokens": 250 * 120 * expected_windows,
                },
            ],
            "safe_input_budget": CONSOLIDATION_SAFE_INPUT_TOKENS,
            "overflow": {
                "truncate": False,
                "error": "ConsolidationContextExceeded",
                "next": "STOP; future hierarchical consolidation only after review",
            },
        },
        "transport": {
            "generation_c_reused_directly": False,
            "reason": (
                "Consolidator must express merge groups, keep, global "
                "metadata, and cross-window relations — not a second "
                "window-level record dump and not a full SourceMap."
            ),
            "version": CONSOLIDATION_TRANSPORT_VERSION,
            "returns_canonical_sourcemap": False,
            "operations": [
                "GLOBAL_METADATA",
                "KEEP_RECORD",
                "MERGE_RECORDS",
                "RELATION",
                "REPETITION",
            ],
            "drop_records_v1": False,
            "drop_reason": (
                "Arbitrary DROP would threaten completeness. Repeated "
                "ideas become REPETITION, not silent deletion."
            ),
        },
        "semantic_responsibilities": [
            "global main_theme",
            "author_intent",
            "target_audience",
            "author_voice_profile",
            "topic equivalence across windows",
            "idea equivalence across windows",
            "cross-window idea relationships",
            "example-to-idea relationships across windows",
            "global repetitions",
            "reconciliation of semantic duplicates",
            "resolution of boundary-level fragmentation",
        ],
        "local_responsibilities": [
            "input validation",
            "record lookup",
            "SRC-set validation",
            "merge operation application",
            "canonical ordering",
            "canonical ID assignment",
            "stats",
            "coverage against CLEAN_SOURCE_SET",
            "schema construction",
            "serialization",
            "atomic publication",
        ],
        "python_must_not": [
            "semantically merge paraphrased topics or ideas",
            "guess missing SRC refs",
            "invent global theme from WIN001",
            "synonym-map vocabulary",
            "fuzzy-correct record ids",
        ],
        "merge_safety": {
            "must_reference_existing_intermediate_records": True,
            "no_arbitrary_invented_src": True,
            "synthesized_text_must_cite_input_records": True,
            "final_source_refs": "union of referenced validated records' SRC refs",
            "provider_should_not_type_raw_src_for_merged_item": True,
        },
        "kinds": {
            "topics": "candidates merged or kept; final TOP ids assigned locally",
            "ideas": "candidates merged or kept; final IDEA ids assigned locally",
            "examples": "keep; consolidator may retarget support across windows",
            "references": "keep individually; exact structural dup only where safe",
            "uncertainties": "keep individually; consolidator may mark boundary-resolved",
            "repetitions": "in-window kept; cross-window created by consolidator",
            "relations": "re-expressed via WIN:R identities; local remap to IDEA ids",
        },
        "global_metadata": {
            "main_theme": "consolidator only; never WIN001 theme",
            "window_themes": "evidence only",
            "author_intent": "consolidator only; window candidates are evidence",
            "target_audience": "consolidator only; window candidates are evidence",
            "author_voice_profile": "consolidator only; window VOICE records are evidence",
        },
        "unmerged_records": "KEEP_RECORD references a single WIN:R identity",
        "traceability": {
            "final_to_consolidation_decision": True,
            "consolidation_to_window_records": True,
            "window_records_to_src": True,
            "src_to_clean_transcript": True,
            "intermediate_ids_not_final_source_refs": True,
        },
        "validator": {
            "fail_closed": True,
            "no_synonym_mapping": True,
            "no_fuzzy_record_id_correction": True,
            "no_guessed_references": True,
            "checks": [
                "referenced window records exist",
                "merge groups valid",
                "no incompatible record types merged",
                "no duplicate ownership contradictions",
                "relations valid",
                "controlled vocabulary valid",
                "all global outputs grounded",
                "no editorial leakage",
            ],
        },
        "cache": {
            "signature_includes": [
                "all_validated_window_result_hashes_in_source_order",
                "consolidation_prompt_version",
                "consolidation_prompt_sha256",
                "consolidation_transport_version",
                "provider",
                "model",
                "temperature",
                "max_output_tokens",
                "output_language",
            ],
            "any_changed_window_invalidates_consolidation": True,
        },
        "provider": EXPECTED_PROVIDER,
        "model": EXPECTED_MODEL,
        "prompt_version": CONSOLIDATION_PROMPT_VERSION,
        "max_output_tokens": CONSOLIDATION_MAX_OUTPUT_TOKENS,
        "connect_timeout_seconds": CONSOLIDATION_CONNECT_TIMEOUT_SECONDS,
        "read_timeout_seconds": CONSOLIDATION_READ_TIMEOUT_SECONDS,
        "stage": STAGE_CONSOLIDATION,
        "prompt_1_3_modified": False,
        "network": {"anthropic": 0, "openai": 0, "provider_calls": 0},
    }


def architecture_design(
    simulation: Mapping[str, Any],
    window: Mapping[str, Any],
    consolidation: Mapping[str, Any],
) -> dict[str, Any]:
    selected = simulation["selected_policy"]
    expected_windows = selected["expected_windows"]
    return {
        "schema_version": "1.0",
        "phase": "3B.7",
        "mode": "OFFLINE_DESIGN",
        "strategy": "HYBRID_WINDOW_PLUS_GLOBAL_CONSOLIDATION",
        "why_hybrid": (
            "Global synchronous request is not operationally viable after "
            "two no-body timeouts. Context capacity is not the reason."
        ),
        "context_capacity_is_the_reason": False,
        "operational_reason": "GLOBAL_SYNCHRONOUS_REQUEST_NOT_OPERATIONALLY_VIABLE",
        "planner": {
            "version": PLANNER_VERSION,
            "target_input_tokens": TARGET_INPUT_TOKENS,
            "hard_max_input_tokens": HARD_MAX_INPUT_TOKENS,
            "overlap_policy": OVERLAP_POLICY,
            "tiny_tail_policy": window["planner"]["tiny_tail_policy"],
            "expected_windows": expected_windows,
        },
        "window_analysis": {
            "transport": WINDOW_TRANSPORT_VERSION,
            "prompt_version": WINDOW_PROMPT_VERSION,
            "provider": EXPECTED_PROVIDER,
            "model": EXPECTED_MODEL,
            "cache_granularity": "per_window",
        },
        "consolidation": {
            "input_contract": "ConsolidationInput",
            "transport_version": CONSOLIDATION_TRANSPORT_VERSION,
            "semantic_responsibilities": consolidation["semantic_responsibilities"],
            "local_responsibilities": consolidation["local_responsibilities"],
        },
        "traceability": {
            "final_to_intermediate": True,
            "intermediate_to_src": True,
            "sparse_src_preserved": True,
        },
        "resume": window["resume"],
        "publication": {
            "canonical_contract_unchanged": CANONICAL_SOURCEMAP_CONTRACT == "UNCHANGED",
            "canonical_validator_unchanged": CANONICAL_VALIDATOR == "UNCHANGED",
            "strategy_field": (
                "analysis.strategy remains a free string; future hybrid "
                "publication may store 'hybrid' without schema change. "
                "Phase 4 must not branch on strategy."
            ),
            "atomic": True,
            "path": "analysis/source_map.json",
        },
        "pipeline": [
            "TranscriptInput",
            "WindowPlannerV2",
            "WindowInput[]",
            "WindowAnalyzer",
            "WindowSemanticResult[]",
            "WindowValidator",
            "Window Cache / Resume",
            "ConsolidationInputBuilder",
            "GlobalConsolidator",
            "ConsolidationSemanticResult",
            "CanonicalReconstructor",
            "normalize_source_map()",
            "Canonical Validator",
            "Atomic SourceMap Publication",
        ],
        "ai_vs_local": {
            "ai": "semantic decisions",
            "local": "structural decisions",
            "no_silent_move_of_semantics_to_python": True,
        },
        "final_signature": {
            "must_include_hybrid_inputs": True,
            "must_not_collide_with_global": True,
            "includes": [
                "strategy=hybrid",
                "planner_version",
                "window_prompt_sha256",
                "consolidation_prompt_sha256",
                "all_window_result_hashes",
                "existing SignatureInputs fields",
            ],
        },
        "cost": {
            "window_stage": STAGE_WINDOW,
            "consolidation_stage": STAGE_CONSOLIDATION,
            "aggregate_stage": STAGE_AGGREGATE,
            "unknown_stays_unknown": True,
            "partial_success_cost_retained": True,
        },
        "project_state": {
            "coarse_key": "source_analysis",
            "coarse_values": ["pending", "failed", "completed"],
            "hybrid_detail": "analysis/hybrid/progress.json (future; not overloaded into project_state)",
            "success_only_after_source_map_publication": True,
            "do_not_mark_success_now": True,
        },
        "crash_recovery": {
            "during_window_call": "WINDOW_FAILED; others intact; no body expected",
            "after_response_before_transport": "treat as failed attempt; persist nothing as success",
            "after_transport_before_decode": "resume from transport; do not re-call if transport valid",
            "between_windows": "resume remaining windows",
            "during_consolidation": "windows remain valid; consolidation pending/failed",
            "after_consolidation_transport": "resume local reconstruction from transport",
            "before_source_map_publication": "do not publish partial source_map",
        },
        "call_consumption": {
            "planned": "does not consume",
            "attempted_http": "consumes the attempt even on timeout",
            "successful_generation": "recorded with usage if present",
            "valid_local_result": "cacheable only after validation",
        },
        "future_execution": {
            "provider_calls_this_phase": 0,
            "real_calls_authorized": False,
            "expected_future_calls_this_corpus": expected_windows + 1,
            "authorization_gates": [
                "one window canary",
                "review",
                "bounded remaining windows",
                "review",
                "consolidation canary / real consolidation",
                "canonical publication",
            ],
            "attempts_per_window_per_authorization": 1,
        },
        "implementation_sequence": [
            "3B.7.1 — WindowPlannerV2 + contracts (offline)",
            "3B.7.2 — Window analysis pipeline + FakeAI (offline)",
            "3B.7.3 — Window cache/resume + validation (offline)",
            "3B.7.4 — Consolidation transport + decoder (offline)",
            "3B.7.5 — End-to-end hybrid FakeAI (offline)",
            "3B.7.6 — One real window canary (one call)",
            "3B.7.7 — Remaining real windows controlled execution",
            "3B.7.8 — Consolidation canary / real consolidation",
            "3B FINAL HYBRID — canonical publication",
        ],
        "next_phase": NEXT_PHASE,
        "next_phase_label": NEXT_PHASE_LABEL,
        "historical_prompt_1_3": EXPECTED_PROMPT_VERSION,
        "prompt_1_3_unchanged": True,
        "generation_c_unchanged": True,
        "decoder_unchanged": True,
        "canonical_validator_unchanged": True,
        "clean_transcript_unchanged": True,
        "source_map_published": False,
        "phase_3b": "INCOMPLETE",
        "network": {
            "anthropic": 0,
            "openai": 0,
            "whisper": 0,
            "ollama": 0,
            "lm_studio": 0,
            "other": 0,
            "engine_generate": 0,
        },
    }
