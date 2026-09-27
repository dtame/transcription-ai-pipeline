"""Décision de readiness 3B.7.7A.8. Offline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.source_analysis.window_granularity import (
    HARD_CEILINGS,
    LOCAL_SEMANTIC_MERGE,
    LOCAL_STRING_TRUNCATION,
    POLICY_VERSION,
    granularity_policy,
)
from app.source_analysis.window_models import (
    WINDOW_CONNECT_TIMEOUT_SECONDS,
    WINDOW_MAX_ATTEMPTS,
    WINDOW_MAX_OUTPUT_TOKENS,
    WINDOW_READ_TIMEOUT_SECONDS,
)
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION
from app.source_analysis_hybrid.constants import PLANNER_VERSION, WINDOW_TRANSPORT_VERSION
from app.source_analysis_hybrid_readiness.canary import resolve_canary_planner_version
from app.source_analysis_hybrid_readiness.constants import (
    AUTO_CONSOLIDATION,
    AUTO_CONTINUE,
    AUTO_FALLBACK,
    AUTO_PUBLICATION,
    AUTO_RETRY,
    MAX_ATTEMPTS,
    MAX_NEW_CALLS_WIN001,
)
from app.source_analysis_small_window_hierarchy.constants import CANDIDATE_PLANNER_VERSION
from app.source_analysis_small_window_hierarchy.facts import (
    inspect_clean,
    inspect_forensics_active,
    inspect_integrity,
    inspect_production_freeze,
    protected_hashes,
)
from app.source_analysis_small_window_readiness.constants import (
    AUTHORIZATION_SCOPE,
    DRY_RUN_COMMAND,
    FUTURE_REAL_COMMAND,
    HARD_MAX_LOCAL_ESTIMATE,
    PROJECT_NAME,
    PROMPT_VERSION_REQUIRED,
)


def implementation_facts(
    *,
    request: dict[str, Any],
    plan: dict[str, Any],
    cache: dict[str, Any],
    collision: dict[str, Any],
    dry_run: dict[str, Any],
    boundary: dict[str, Any],
    fakeai: dict[str, Any],
    taxonomy: dict[str, Any],
    retry: dict[str, Any],
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    freeze = inspect_production_freeze()
    clean = inspect_clean(project_name, sortie_dir=sortie_dir)
    integrity = inspect_integrity(project_name, sortie_dir=sortie_dir)
    forensics = inspect_forensics_active()
    planner_resolves = (
        resolve_canary_planner_version(AUTHORIZATION_SCOPE)
        == CANDIDATE_PLANNER_VERSION
    )
    historical_stays_v20 = (
        resolve_canary_planner_version("WIN001_ONLY") == PLANNER_VERSION
    )
    coverage = plan["coverage"]
    distinct = request["distinct_from_large"]
    dry_ok = (
        dry_run.get("planner_version") == CANDIDATE_PLANNER_VERSION
        and dry_run.get("window_id") == "WIN001"
        and dry_run.get("prompt_version") == PROMPT_VERSION_REQUIRED
        and dry_run.get("execution") is False
        and int(dry_run.get("actual_real_provider_calls") or 0) == 0
        and int(dry_run.get("max_attempts") or 0) == 1
        and dry_run.get("provider") == "anthropic"
        and dry_run.get("model") == "claude-sonnet-5"
        and dry_run.get("connect_timeout_seconds") == WINDOW_CONNECT_TIMEOUT_SECONDS
        and dry_run.get("read_timeout_seconds") == WINDOW_READ_TIMEOUT_SECONDS
        and dry_run.get("max_output_tokens") == WINDOW_MAX_OUTPUT_TOKENS
        and dry_run.get("cache_state") == "MISS"
    )
    fake_ok = (
        fakeai.get("success", {}).get("provider_calls") == 1
        and fakeai.get("success", {}).get("continued") is False
        and fakeai.get("success", {}).get("ready_windows") == 1
        and fakeai.get("provider_boundary", {}).get("forensics_json") is True
        and fakeai.get("structured", {}).get("forensics_present") is True
        and fakeai.get("capacity", {}).get("transport_present") is True
        and fakeai.get("capacity", {}).get("result_absent") is True
        and fakeai.get("hard_limit", {}).get("result_absent") is True
        and fakeai.get("success", {}).get("warm_used_cache") is True
    )
    blockers = {
        "production_default_changed": not freeze["defaults_still_v20"],
        "candidate_not_v21_small": plan["planner_version"] != CANDIDATE_PLANNER_VERSION,
        "window_count_not_7": not plan["window_count_matches"],
        "plan_materially_different": plan["a7_comparison"]["materially_different"],
        "coverage_incomplete": not coverage["every_present_src_owned_once"],
        "duplicates": bool(coverage["duplicate_owned_src"]),
        "missing": bool(coverage["missing_src"]),
        "context_not_empty": not coverage["context_src_empty"],
        "tiny_stub": bool(plan["tiny_stub"]),
        "over_hard_max": bool(plan["any_window_over_hard_max"]),
        "small_win001_over_35000": not request["within_hard_max"],
        "identity_not_distinct": not distinct["cryptographically_distinct"],
        "cache_hit_unexpected": bool(cache.get("blocked_for_human_review")),
        "historical_cache_collision": not cache.get(
            "large_win001_is_not_small_cache_candidate"
        ),
        "forensic_collision": not collision.get("collision_safe"),
        "forensics_inactive": not forensics.get("active"),
        "prompt_1_1_changed": not (
            integrity.get("prompt_11_sha") == integrity.get("prompt_11_expected")
        ),
        "generation_c_changed": not (
            integrity.get("generation_c_raw") == integrity.get("generation_c_raw_expected")
            and integrity.get("generation_c_anthropic")
            == integrity.get("generation_c_anthropic_expected")
        ),
        "clean_changed": not clean.get("matches_expected") or not clean.get(
            "clean_sha_matches"
        ),
        "wrong_timeout": not dry_ok,
        "max_attempts_not_1": int(dry_run.get("max_attempts") or 0) != 1,
        "hidden_retry": bool(retry.get("hidden_http_post_retry")),
        "auto_continuation": bool(
            AUTO_CONTINUE or AUTO_RETRY or AUTO_FALLBACK or AUTO_CONSOLIDATION
        ),
        "scope_can_select_v20": not planner_resolves or not historical_stays_v20,
        "source_map_present": bool(cache.get("source_map_present")),
        "none_context_indefensible": not boundary.get("none_context_defensible"),
        "fakeai_path_failed": not fake_ok,
        "state_marked_success": str(
            (cache.get("project_state") or {}).get("project_state_status") or ""
        ).lower()
        == "success",
    }
    blocked = any(blockers.values())
    readiness = "BLOCKED" if blocked else "READY_FOR_SMALL_WIN001_CANARY"
    return {
        "readiness": readiness,
        "blockers": blockers,
        "planner_scope_resolves_v21_small": planner_resolves,
        "historical_scope_stays_v20": historical_stays_v20,
        "production_freeze": freeze,
        "clean": clean,
        "integrity": integrity,
        "forensics_active": forensics,
        "granularity_policy": granularity_policy(),
        "hard_ceilings": dict(HARD_CEILINGS),
        "local_semantic_merge": LOCAL_SEMANTIC_MERGE,
        "local_string_truncation": LOCAL_STRING_TRUNCATION,
        "granularity_version": POLICY_VERSION,
        "transport_version": WINDOW_TRANSPORT_VERSION,
        "max_output_frozen": WINDOW_MAX_OUTPUT_TOKENS,
        "timeout": {
            "connect": WINDOW_CONNECT_TIMEOUT_SECONDS,
            "read": WINDOW_READ_TIMEOUT_SECONDS,
            "max_attempts_contract": WINDOW_MAX_ATTEMPTS,
        },
        "one_call": {
            "authorization_scope": AUTHORIZATION_SCOPE,
            "max_new_calls": MAX_NEW_CALLS_WIN001,
            "max_attempts": MAX_ATTEMPTS,
            "auto_retry": AUTO_RETRY,
            "auto_continue": AUTO_CONTINUE,
            "auto_fallback": AUTO_FALLBACK,
            "auto_consolidation": AUTO_CONSOLIDATION,
            "auto_publication": AUTO_PUBLICATION,
            "auto_reconstruction": False,
        },
        "taxonomy": taxonomy,
        "retry": retry,
        "dry_run_ok": dry_ok,
        "fakeai_ok": fake_ok,
        "required_prompt": WINDOW_ANALYSIS_PROMPT_VERSION,
        "required_scope": AUTHORIZATION_SCOPE,
        "dry_run_command": DRY_RUN_COMMAND,
        "future_real_command": FUTURE_REAL_COMMAND,
        "future_real_command_executed": False,
        "protected_hashes": protected_hashes(project_name, sortie_dir=sortie_dir),
    }


__all__ = ["implementation_facts"]
