"""Faits offline 3B.7.6 — transcript, plan, requêtes, cache, coûts."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from app.ai.capabilities import resolve_capabilities
from app.ai.pricing import build_default_catalog
from app.ai.settings import ENV_ANTHROPIC_API_KEY, get_api_key, resolve_stage_settings
from app.ai.timeouts import diagnose_stage_timeout
from app.cleanup_application.writer import audit_path, clean_json_path
from app.semantic_canary.integrity import sha256_of_file
from app.source_analysis.consolidation_models import (
    CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
    STAGE_CONSOLIDATION,
)
from app.source_analysis.consolidation_prompt import (
    CONSOLIDATION_ANALYSIS_PROMPT_VERSION,
    build_consolidation_system_prompt,
    consolidation_prompt_sha256,
)
from app.source_analysis.consolidation_schema import consolidation_schema_fingerprint
from app.source_analysis.consolidation_writer import production_consolidation_exist
from app.source_analysis.prompt import SOURCE_ANALYZER_PROMPT_VERSION
from app.source_analysis.provenance import validate_derived_provenance
from app.source_analysis.transcript_input import TranscriptInputMode
from app.source_analysis.window_analyzer import build_window_ai_request
from app.source_analysis.window_prompt import WINDOW_ANALYSIS_PROMPT_VERSION_V10
from app.source_analysis.window_cache import inspect_window_cache
from app.source_analysis.window_models import STAGE_WINDOW, WINDOW_MAX_OUTPUT_TOKENS
from app.source_analysis.window_prompt import window_prompt_sha256
from app.source_analysis.window_writer import (
    leftover_partial,
    metadata_path,
    production_windows_exist,
    result_path,
    transport_path,
    windows_root,
)
from app.source_analysis.writer import analysis_dir, source_map_path
from app.source_analysis_execution_strategy.review import inspect_project_state
from app.source_analysis_execution_strategy.windows import load_clean_transcript
from app.source_analysis_global_clean.writer import production_source_map_path
from app.source_analysis_hybrid.config import WindowPlannerConfig
from app.source_analysis_hybrid.constants import (
    HARD_MAX_INPUT_TOKENS,
    OVERLAP_POLICY,
    PLANNER_VERSION,
    TARGET_INPUT_TOKENS,
)
from app.source_analysis_hybrid.planner import plan_windows_v2
from app.source_analysis_hybrid.validation import validate_window_plan
from app.source_analysis_hybrid_readiness.constants import (
    OUTPUT_SCENARIOS,
    TARGET_MODEL,
    TARGET_PROVIDER,
)
from app.source_analysis_timeout_config.audit import generation_c_hashes
from app.source_analysis.writer import transcripts_dir


def anthropic_credential_available() -> bool:
    """True si une clé Anthropic est résolvable. Ne renvoie jamais la clé."""
    return bool(get_api_key(ENV_ANTHROPIC_API_KEY))


def verify_clean_transcript(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    clean_path = clean_json_path(project_name, sortie_dir=sortie_dir)
    provenance_path = audit_path(project_name, sortie_dir=sortie_dir)
    original_path = (
        transcripts_dir(project_name, sortie_dir=sortie_dir) / "transcript_data.json"
    )
    proven = validate_derived_provenance(
        derived_path=clean_path,
        provenance_path=provenance_path,
        original_transcript_path=original_path,
    )
    present_ids = transcript.src_ids()
    return {
        "project_name": project_name,
        "transcript_id": transcript.transcript_id,
        "mode": transcript.mode.value
        if isinstance(transcript.mode, TranscriptInputMode)
        else str(transcript.mode),
        "primary_language": transcript.primary_language,
        "segment_count": transcript.segment_count,
        "word_count": transcript.word_count,
        "duration_seconds": transcript.duration_seconds,
        "content_sha256": transcript.content_sha256,
        "file_sha256": sha256_of_file(clean_path),
        "sparse_ids_preserved": present_ids == tuple(sorted(present_ids, key=present_ids.index)),
        "first_src": present_ids[0] if present_ids else "",
        "last_src": present_ids[-1] if present_ids else "",
        "provenance": {
            "path": str(provenance_path),
            "original_segment_count": proven.original_segment_count,
            "derived_segment_count": proven.derived_segment_count,
            "removed_count": proven.removed_count,
            "removed_set_matches": proven.removed_set_matches,
            "survivors_unchanged": proven.survivors_unchanged,
            "policy": proven.policy,
            "original_sha256": proven.original_sha256,
            "derived_sha256": proven.derived_sha256,
        },
        "expected": {
            "transcript_id": "TR001",
            "mode": "DERIVED",
            "segment_count": 8298,
            "word_count": 38313,
            "duration_seconds": 19954.601,
            "removed_src": 117,
        },
        "matches_expected": (
            transcript.transcript_id == "TR001"
            and transcript.mode is TranscriptInputMode.DERIVED
            and transcript.segment_count == 8298
            and transcript.word_count == 38313
            and transcript.duration_seconds == 19954.601
            and proven.removed_count == 117
            and proven.removed_set_matches
            and proven.survivors_unchanged
        ),
    }


def _decimal_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _cost_scenarios(input_tokens: int) -> dict[str, Any]:
    catalog = build_default_catalog()
    pricing = catalog.get(TARGET_PROVIDER, TARGET_MODEL)
    scenarios: list[dict[str, Any]] = []
    for output_tokens in OUTPUT_SCENARIOS:
        breakdown = catalog.estimate_cost(
            TARGET_PROVIDER, TARGET_MODEL, input_tokens, output_tokens
        )
        scenarios.append(
            {
                "kind": "ESTIMATE",
                "not_actual": True,
                "output_tokens_scenario": output_tokens,
                "input_tokens": input_tokens,
                "currency": breakdown.currency,
                "input_cost": _decimal_str(breakdown.input_cost),
                "output_cost": _decimal_str(breakdown.output_cost),
                "total_cost": _decimal_str(breakdown.total_cost),
                "pricing_status": breakdown.status,
                "pricing_source": breakdown.pricing_source,
                "effective_date": breakdown.effective_date,
            }
        )
    return {
        "kind": "ESTIMATE",
        "not_actual": True,
        "unknown_represented_as_zero": False,
        "provider": TARGET_PROVIDER,
        "model": TARGET_MODEL,
        "input_cost_per_1m_tokens": (
            _decimal_str(pricing.input_cost_per_1m_tokens) if pricing else None
        ),
        "output_cost_per_1m_tokens": (
            _decimal_str(pricing.output_cost_per_1m_tokens) if pricing else None
        ),
        "long_context_modeled": False,
        "long_context_applicable": False,
        "scenarios": scenarios,
    }


def rebuild_window_requests(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    transcript=None,
    plan=None,
) -> dict[str, Any]:
    if transcript is None:
        transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    if plan is None:
        plan = plan_windows_v2(transcript)
    validate_window_plan(plan, transcript, WindowPlannerConfig())
    settings = resolve_stage_settings(STAGE_WINDOW)
    timeout = diagnose_stage_timeout(STAGE_WINDOW)
    capabilities = resolve_capabilities(TARGET_PROVIDER, TARGET_MODEL)
    usable = capabilities.usable_context(settings.context_safety_ratio)
    owned = []
    for src in transcript.src_ids():
        owned.append(src)
    owned_once = []
    seen: set[str] = set()
    duplicate = []
    for window in plan.windows:
        for src in window.owned_src_refs:
            if src in seen:
                duplicate.append(src)
            seen.add(src)
            owned_once.append(src)
    missing = [src for src in owned if src not in seen]
    extra = [src for src in seen if src not in set(owned)]
    rows: list[dict[str, Any]] = []
    for window in plan.windows:
        bundle = build_window_ai_request(
            window,
            transcript,
            settings=settings,
            prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10,
        )
        estimated = int(bundle.token_estimate["total_tokens"])
        full_request = estimated + int(WINDOW_MAX_OUTPUT_TOKENS)
        margin = usable - full_request
        rows.append(
            {
                "window_id": window.window_id,
                "owned_src_count": window.owned_src_count,
                "context_src_count": window.context_src_count,
                "first_src": window.first_owned_src_ref,
                "last_src": window.last_owned_src_ref,
                "word_count": window.word_count,
                "planner_estimated_input_tokens": window.estimated_input_tokens,
                "system_prompt_tokens": bundle.token_estimate["system_tokens"],
                "user_prompt_tokens": bundle.token_estimate["user_tokens"],
                "estimated_input_tokens": estimated,
                "estimator_method": bundle.token_estimate["method"],
                "max_output": int(bundle.request.max_output_tokens or 0),
                "estimated_full_request_tokens": full_request,
                "usable_context": usable,
                "context_safety_ratio": float(settings.context_safety_ratio),
                "margin": margin,
                "hard_max": HARD_MAX_INPUT_TOKENS,
                "within_hard_max": estimated <= HARD_MAX_INPUT_TOKENS,
                "fits_usable_context": full_request <= usable,
                "provider": TARGET_PROVIDER,
                "model": TARGET_MODEL,
                "temperature": bundle.request.temperature,
                "output_language": transcript.primary_language,
                "response_schema": "semantic-transport-v1",
                "response_schema_sha256": bundle.response_schema_sha256,
                "stage": bundle.request.stage,
                "connect_timeout_seconds": timeout["connect_seconds"],
                "read_timeout_seconds": timeout["read_seconds"],
                "timeout_connect_source": timeout["connect_source"],
                "timeout_read_source": timeout["read_source"],
                "effective_timeout": (
                    timeout["connect_seconds"],
                    timeout["read_seconds"],
                ),
                "analysis_signature": bundle.signature,
                "prompt_version": bundle.signature_inputs.prompt_version,
                "prompt_sha256": window_prompt_sha256(bundle.system_prompt),
                "cost_estimate": _cost_scenarios(estimated),
            }
        )
    return {
        "planner_version": plan.planner_version,
        "target_input_tokens": plan.target_input_tokens,
        "hard_max_input_tokens": plan.hard_max_input_tokens,
        "overlap_policy": plan.overlap_policy,
        "window_count": plan.window_count,
        "owned_src_count": plan.owned_src_count,
        "context_src_count": plan.context_src_count,
        "coverage": {
            "present": len(owned),
            "owned_once": len(seen),
            "missing": missing,
            "extra": extra,
            "duplicates": duplicate,
            "exact_once": (
                len(owned) == 8298
                and not missing
                and not extra
                and not duplicate
                and plan.owned_src_count == 8298
            ),
            "no_context_src": plan.context_src_count == 0,
            "no_hard_max_violation": all(row["within_hard_max"] for row in rows),
        },
        "model_capacity": {
            "provider": capabilities.provider,
            "model": capabilities.model,
            "context_window": capabilities.context_window,
            "max_output_tokens": capabilities.max_output_tokens,
            "known": capabilities.known,
            "source": capabilities.source,
            "usable_context": usable,
            "safety_ratio": float(settings.context_safety_ratio),
        },
        "windows": rows,
        "matches_expected_counts": (
            plan.window_count == 3
            and [row["owned_src_count"] for row in rows] == [2787, 2771, 2740]
        ),
        "contracts": {
            "planner_version": PLANNER_VERSION,
            "target": TARGET_INPUT_TOKENS,
            "hard_max": HARD_MAX_INPUT_TOKENS,
            "overlap": OVERLAP_POLICY,
            "prompt_1_3_unchanged": SOURCE_ANALYZER_PROMPT_VERSION == "1.3",
        },
    }


def inspect_production_cache(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
    transcript=None,
    plan=None,
) -> dict[str, Any]:
    if transcript is None:
        transcript = load_clean_transcript(project_name, sortie_dir=sortie_dir)
    if plan is None:
        plan = plan_windows_v2(transcript)
    root = windows_root(project_name, sortie_dir=sortie_dir)
    rows: list[dict[str, Any]] = []
    unexpected = False
    for window in plan.windows:
        bundle = build_window_ai_request(
            window, transcript, prompt_version=WINDOW_ANALYSIS_PROMPT_VERSION_V10
        )
        inspection = inspect_window_cache(
            window,
            transcript,
            windows_root=root,
            project_name=project_name,
            expected_signature=bundle.signature,
        )
        t_path = transport_path(project_name, window.window_id, root=root)
        r_path = result_path(project_name, window.window_id, root=root)
        m_path = metadata_path(project_name, window.window_id, root=root)
        present = any(path.is_file() for path in (t_path, r_path, m_path))
        if present or leftover_partial(t_path) or leftover_partial(r_path) or leftover_partial(m_path):
            unexpected = True
        rows.append(
            {
                "window_id": window.window_id,
                "cache_state": inspection.cache_state,
                "transport_exists": inspection.transport_present,
                "result_exists": inspection.result_present,
                "metadata_exists": inspection.metadata_present,
                "signature_expected": bundle.signature,
                "recoverable": inspection.recoverable,
                "error_classification": inspection.error_classification,
            }
        )
    return {
        "windows_root": str(root),
        "production_windows_exist": production_windows_exist(
            project_name, sortie_dir=sortie_dir
        ),
        "production_consolidation_exist": production_consolidation_exist(
            project_name, sortie_dir=sortie_dir
        ),
        "fake_ai_in_production_paths": unexpected,
        "unexpected_semantic_artifacts": unexpected
        or production_windows_exist(project_name, sortie_dir=sortie_dir)
        or production_consolidation_exist(project_name, sortie_dir=sortie_dir),
        "windows": rows,
        "all_miss": all(row["cache_state"] == "MISS" for row in rows),
    }


def inspect_publication_and_state(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    smap = source_map_path(project_name, sortie_dir=sortie_dir)
    v1 = production_source_map_path(project_name, sortie_dir=sortie_dir)
    state = inspect_project_state(project_name, sortie_dir=sortie_dir)
    error = state.get("error")
    if not isinstance(error, str) and error is not None:
        error = str(error)
    return {
        "source_map_path": str(smap),
        "source_map_present": smap.exists(),
        "v1_source_map_present": v1.exists(),
        "analysis_dir_exists": analysis_dir(project_name, sortie_dir=sortie_dir).exists(),
        "project_state_status": str(state.get("status") or ""),
        "project_state_error": error,
        "project_state_present": bool(state.get("present")),
        "matches_failed_timeout": (
            str(state.get("status") or "") == "failed"
            and "AITimeoutError" in str(error or "")
        ),
    }


def probe_disk_writable(
    project_name: str,
    *,
    sortie_dir: Path | None = None,
) -> dict[str, Any]:
    from app.language_cleanup.transcript_source import audit_dir

    directory = audit_dir(project_name, sortie_dir=sortie_dir)
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / ".readiness_write_probe_3b76"
    try:
        probe.write_text("ok\n", encoding="utf-8")
        writable = probe.is_file() and probe.read_text(encoding="utf-8") == "ok\n"
    finally:
        probe.unlink(missing_ok=True)
    leftover = probe.exists()
    return {
        "audit_dir": str(directory),
        "writable": writable and not leftover,
        "probe_removed": not leftover,
        "semantic_output_created": False,
    }


def schema_and_prompt_facts() -> dict[str, Any]:
    generation = generation_c_hashes()
    consolidation_system = build_consolidation_system_prompt()
    return {
        "window_prompt_version": "window-analysis-1.0",
        "generation_c": generation,
        "generation_c_unchanged": bool(generation["raw_matches_historical"])
        and bool(generation["anthropic_matches_historical"]),
        "generation_c_grammar_historical": "ACCEPTED_IN_PRIOR_CANARY",
        "consolidation_prompt_version": CONSOLIDATION_ANALYSIS_PROMPT_VERSION,
        "consolidation_prompt_sha256": consolidation_prompt_sha256(consolidation_system),
        "consolidation_transport_version": "consolidation-transport-v1",
        "consolidation_schema_sha256": consolidation_schema_fingerprint(),
        "consolidation_grammar_verified": False,
        "consolidation_grammar_status": "UNVERIFIED",
        "consolidation_safe_input_budget": CONSOLIDATION_SAFE_INPUT_BUDGET_TOKENS,
        "prompt_1_3": SOURCE_ANALYZER_PROMPT_VERSION,
        "consolidation_stage": STAGE_CONSOLIDATION,
        "credential_env_var": ENV_ANTHROPIC_API_KEY,
        "credential_available": anthropic_credential_available(),
        "secret_exposed": False,
    }
