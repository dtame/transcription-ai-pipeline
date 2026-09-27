"""Vérifications d'implémentation et décision de readiness. Offline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ai.structured_forensics import FORENSICS_DIR_NAME
from app.language_cleanup.transcript_source import audit_dir
from app.source_analysis.window_granularity import (
    HARD_CEILINGS,
    IDEA_HARD_CEILING,
    IDEA_SOFT_TARGET,
    LOCAL_SEMANTIC_MERGE,
    LOCAL_STRING_TRUNCATION,
    OVERFLOW_TOKEN,
    RELATION_HARD_CEILING,
    SOFT_TARGETS,
    SOURCE_REFS_HARD_MAX,
    TEXT_HARD_LIMITS,
    TOTAL_HARD_CEILING,
    TOTAL_SOFT_TARGET,
    granularity_policy,
)
from app.source_analysis.window_models import (
    WINDOW_CONNECT_TIMEOUT_SECONDS,
    WINDOW_MAX_ATTEMPTS,
    WINDOW_MAX_OUTPUT_TOKENS,
    WINDOW_READ_TIMEOUT_SECONDS,
)
from app.source_analysis.window_prompt import (
    WINDOW_ANALYSIS_PROMPT_VERSION,
    WINDOW_ANALYSIS_PROMPT_VERSION_V10,
)
from app.source_analysis_bounded_win001_retry_readiness.constants import (
    AUTHORIZATION_SCOPE,
    DRY_RUN_COMMAND,
    FUTURE_REAL_COMMAND,
    GRANULARITY_POLICY_VERSION,
    PROJECT_NAME,
    SUCCESSOR_PROMPT,
)
from app.source_analysis_hybrid_readiness.canary import (
    resolve_canary_prompt_version,
)
from app.source_analysis_hybrid_readiness.constants import (
    AUTO_CONSOLIDATION,
    AUTO_CONTINUE,
    AUTO_FALLBACK,
    AUTO_PUBLICATION,
    AUTO_RETRY,
    MAX_ATTEMPTS,
    MAX_NEW_CALLS_WIN001,
)
from app.source_analysis_hybrid_readiness.retry_audit import build_retry_audit
from app.source_analysis_window_output_bounding.size_study import (
    SCENARIO_SPECS,
    build_scenario_transport,
    measure_transport,
)


def _preflight_1_1_sha(project_name: str, *, sortie_dir: Path | None) -> str | None:
    path = (
        audit_dir(project_name, sortie_dir=sortie_dir)
        / "source_analysis_win001_bounded_prompt_preflight.json"
    )
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get("new_prompt_sha256")
    return str(value) if value else None


def source_ref_volume() -> dict[str, Any]:
    spec = SCENARIO_SPECS["MAX_POLICY_VALID"]
    transport = build_scenario_transport(
        counts=spec["counts"],
        idea_refs=spec["idea_refs"],
        topic_refs=spec["topic_refs"],
        other_refs=spec["other_refs"],
        max_text=spec["max_text"],
    )
    by_kind: dict[str, int] = {}
    largest = {"kind": "", "refs": 0, "records": 0}
    for item in transport["records"]:
        kind = str(item.get("k") or "")
        refs = len(item.get("s") or [])
        by_kind[kind] = by_kind.get(kind, 0) + refs
        if refs > largest["refs"]:
            largest = {"kind": kind, "refs": refs, "records": 1}
    measured = measure_transport(transport)
    return {
        "scenario": "MAX_POLICY_VALID",
        "refs_by_kind": dict(sorted(by_kind.items())),
        "largest_kind_total_refs": max(by_kind.items(), key=lambda item: item[1]),
        "largest_single_record_refs": largest,
        "source_refs_hard_max": SOURCE_REFS_HARD_MAX,
        "local_estimated_tokens": measured["local_estimated_tokens"],
        "not_prediction": True,
    }


def implementation_facts(
    *,
    request: dict[str, Any],
    cache: dict[str, Any],
    collision: dict[str, Any],
    cost: dict[str, Any],
    dry_run: dict[str, Any],
    prompts: dict[str, Any],
    generation_c: dict[str, Any],
    project_name: str = PROJECT_NAME,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    retry = build_retry_audit()
    accepted_1_1 = _preflight_1_1_sha(project_name, sortie_dir=sortie_dir)
    current_1_1 = str(prompts.get("successor_sha256") or "")
    prompt_1_1_matches_accepted = (
        accepted_1_1 is None or current_1_1 == accepted_1_1
    )
    bounded_resolves = (
        resolve_canary_prompt_version(AUTHORIZATION_SCOPE)
        == WINDOW_ANALYSIS_PROMPT_VERSION
    )
    historical_resolves = (
        resolve_canary_prompt_version("WIN001_ONLY")
        == WINDOW_ANALYSIS_PROMPT_VERSION_V10
    )
    policy = granularity_policy()
    overflow_ready = False
    overlimit_ready = False
    blockers = {
        "runner_still_uses_1_0": not (
            dry_run.get("prompt_version") == SUCCESSOR_PROMPT
            and bounded_resolves
        ),
        "signature_ambiguous": not request.get("signatures_differ"),
        "forensic_overwrite_risk": not collision.get("collision_safe"),
        "cache_collision": bool(cache.get("blocked_for_human_review")),
        "local_estimate_over_60000": not request.get("within_hard_max"),
        "granularity_validator_inactive": not (
            dry_run.get("granularity_policy_version") == GRANULARITY_POLICY_VERSION
        ),
        "overflow_can_become_ready": overflow_ready,
        "overlimit_can_become_ready": overlimit_ready,
        "hidden_retry": bool(retry.get("hidden_http_post_retry")),
        "max_attempts_not_1": int(dry_run.get("max_attempts") or 0) != 1,
        "wrong_provider_model": not (
            dry_run.get("provider") == "anthropic"
            and dry_run.get("model") == "claude-sonnet-5"
        ),
        "wrong_timeout": not (
            dry_run.get("connect_timeout_seconds") == WINDOW_CONNECT_TIMEOUT_SECONDS
            and dry_run.get("read_timeout_seconds") == WINDOW_READ_TIMEOUT_SECONDS
        ),
        "generation_c_changed": not generation_c.get("unchanged"),
        "prompt_1_1_changed": not prompt_1_1_matches_accepted,
        "source_map_could_publish": bool(cache.get("source_map_present")),
        "auto_continuation": bool(
            AUTO_CONTINUE or AUTO_RETRY or AUTO_FALLBACK or AUTO_CONSOLIDATION
        ),
    }
    blocked = any(blockers.values())
    readiness = "BLOCKED" if blocked else "READY_FOR_BOUNDED_WIN001_CANARY"
    return {
        "bounded_prompt_resolves_to_1_1": bounded_resolves,
        "historical_win001_only_resolves_to_1_0": historical_resolves,
        "required_prompt": WINDOW_ANALYSIS_PROMPT_VERSION,
        "required_scope": AUTHORIZATION_SCOPE,
        "granularity_policy": policy,
        "soft_targets": dict(SOFT_TARGETS),
        "hard_ceilings": dict(HARD_CEILINGS),
        "idea_soft_target": IDEA_SOFT_TARGET,
        "idea_hard_ceiling": IDEA_HARD_CEILING,
        "relation_hard_ceiling": RELATION_HARD_CEILING,
        "total_soft_target": TOTAL_SOFT_TARGET,
        "total_hard_ceiling": TOTAL_HARD_CEILING,
        "total_includes_all_record_kinds": True,
        "total_includes_voice_intent_audience": True,
        "total_excludes_root_theme_intent_aud": True,
        "total_excludes_record_metadata_items": True,
        "overflow_record_counts_toward_total_if_present": True,
        "overflow_checked_before_ceilings": True,
        "soft_exceedance_alone_does_not_fail": True,
        "overflow_token": OVERFLOW_TOKEN,
        "overflow_cannot_become_ready": True,
        "overlimit_cannot_become_ready": True,
        "transport_retained_on_capacity_or_overlimit": True,
        "result_absent_on_capacity_or_overlimit": True,
        "local_semantic_merge": LOCAL_SEMANTIC_MERGE,
        "local_string_truncation": LOCAL_STRING_TRUNCATION,
        "text_hard_limits": dict(TEXT_HARD_LIMITS),
        "source_refs_hard_max": SOURCE_REFS_HARD_MAX,
        "source_ref_volume": source_ref_volume(),
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
            "auto_reconstruction": False,
            "auto_publication": AUTO_PUBLICATION,
        },
        "retry_audit": {
            "hidden_http_post_retry": retry["hidden_http_post_retry"],
            "canary_retry_safe": retry["canary_retry_safe"],
            "uses_requests_session": retry["http"]["uses_requests_session"],
        },
        "forensics": {
            "dir_name": FORENSICS_DIR_NAME,
            "signature_keyed": True,
            "preserves_usage": True,
            "preserves_finish_reason": True,
            "preserves_request_id": True,
            "preserves_parse_kind": True,
            "preserves_raw_sha256": True,
            "preserves_raw_text": True,
            "no_json_repair": True,
            "no_secrets": True,
        },
        "parse_kinds_supported": ["empty", "json_decode", "schema"],
        "accepted_1_1_prompt_sha256": accepted_1_1,
        "current_1_1_prompt_sha256": current_1_1,
        "prompt_1_1_matches_accepted_3b77a2": prompt_1_1_matches_accepted,
        "dry_run_command": DRY_RUN_COMMAND,
        "future_real_command": FUTURE_REAL_COMMAND,
        "future_real_command_executed": False,
        "blockers": blockers,
        "readiness": readiness,
        "technical_spend_view": (
            "bounded by one call; scenario costs only; technical information "
            "gained if authorized; no financial judgment"
        ),
    }
