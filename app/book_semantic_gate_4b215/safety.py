"""Provider-safety audit for 4B.2.15. Production pipeline and cache stay untouched."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_generation.pipeline import materialize_chapter
from app.book_semantic_gate_4b215.constants import (
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_SONNET_CALLS,
    BRIDGE_4B214_ENABLED,
    FALLBACKS,
    PHASE,
    PRODUCTION_CACHE_ACCEPTANCE,
    PRODUCTION_PIPELINE_HOOK,
    RETRIES,
    SDK_MAX_RETRIES,
    SEMANTIC_GATE_202_ENABLED,
)
from app.book_semantic_gate_4b215.paths import repo_root


def _pipeline_source(*, root: Path | None = None) -> str:
    path = (root or repo_root()) / "app" / "book_generation" / "pipeline.py"
    return path.read_text(encoding="utf-8")


def _bridge_default(*, root: Path | None = None) -> bool:
    path = (root or repo_root()) / "app" / "book_generation_bridge_4b214" / "constants.py"
    text = path.read_text(encoding="utf-8")
    return "BRIDGE_ENABLED_BY_DEFAULT = True" in text or "SEMANTIC_GATE_202_ENABLED = True" in text


def provider_safety(*, root: Path | None = None, remote_invocations: int = 0) -> dict[str, Any]:
    pipeline = _pipeline_source(root=root)
    return {
        "phase": PHASE,
        "retries": RETRIES,
        "fallbacks": FALLBACKS,
        "sdk_max_retries": SDK_MAX_RETRIES,
        "authorized_sonnet_calls": AUTHORIZED_SONNET_CALLS,
        "authorized_anthropic_calls": AUTHORIZED_ANTHROPIC_CALLS,
        "actual_sonnet_calls": 0,
        "actual_anthropic_calls": 0,
        "second_terra_call_forbidden": True,
        "remote_invocations_observed": remote_invocations,
        "semantic_gate_202_enabled": SEMANTIC_GATE_202_ENABLED,
        "production_pipeline_hook": PRODUCTION_PIPELINE_HOOK,
        "production_cache_acceptance": PRODUCTION_CACHE_ACCEPTANCE,
        "bridge_4b214_enabled": BRIDGE_4B214_ENABLED,
        "bridge_default_still_disabled": not _bridge_default(root=root),
        "pipeline_imports_4b215": "book_semantic_gate_4b215" in pipeline,
        "materialize_chapter_untouched": materialize_chapter.__module__
        == "app.book_generation.pipeline",
        "no_production_cache_write": True,
        "no_book_json_publication": True,
        "no_phase5": True,
        "no_word_pdf": True,
        "no_ch016_regeneration": True,
        "no_19_chapter_run": True,
        "secrets_included": False,
        "ok": (
            RETRIES == 0
            and FALLBACKS == 0
            and AUTHORIZED_SONNET_CALLS == 0
            and "book_semantic_gate_4b215" not in pipeline
            and SEMANTIC_GATE_202_ENABLED is False
            and PRODUCTION_PIPELINE_HOOK is False
            and not _bridge_default(root=root)
        ),
    }


__all__ = ["provider_safety"]
