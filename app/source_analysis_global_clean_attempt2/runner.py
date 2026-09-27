"""Point d'entrée de l'essai #2 — délègue au runner global avec attempt_number=2."""

from __future__ import annotations

from pathlib import Path

from app.source_analysis_global_clean.runner import (
    GlobalCleanResult,
    run_global_clean_source_analysis,
)


def run_global_clean_attempt2(
    project_name: str,
    *,
    dry_run: bool,
    engine=None,
    sortie_dir: Path | None = None,
    require_protected: bool = True,
    require_credential: bool | None = None,
    write_artifacts: bool = True,
    lock_production_route: bool | None = None,
    inject_timeout_env: bool | None = None,
) -> GlobalCleanResult:
    return run_global_clean_source_analysis(
        project_name,
        dry_run=dry_run,
        engine=engine,
        sortie_dir=sortie_dir,
        require_protected=require_protected,
        require_credential=require_credential,
        write_artifacts=write_artifacts,
        lock_production_route=lock_production_route,
        attempt_number=2,
        inject_timeout_env=inject_timeout_env,
    )


def format_pre_call_snapshot(result: GlobalCleanResult) -> str:
    return (
        "GLOBAL_ATTEMPT_NUMBER = 2\n"
        f"provider = {result.provider}\n"
        f"model = {result.model}\n"
        f"segments = {result.segment_count}\n"
        f"words = {result.word_count}\n"
        f"strategy = {result.strategy}\n"
        f"estimated input = {result.estimated_tokens}\n"
        f"max output = {result.resolved_max_output}\n"
        f"connect timeout = {result.effective_connect_timeout_seconds}\n"
        f"read timeout = {result.effective_read_timeout_seconds}\n"
        f"connect source = {result.connect_source}\n"
        f"read source = {result.read_source}\n"
        f"max_real_calls = {result.max_real_calls}\n"
        f"max_attempts = {result.max_attempts}\n"
        f"retry = {result.retry}\n"
        f"fallback = {result.fallback}\n"
        "third_timeout_escalation = prohibited\n"
    )
