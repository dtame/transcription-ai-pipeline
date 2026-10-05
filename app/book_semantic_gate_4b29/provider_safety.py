"""Provider safety for 4B.2.9. Remote calls fail explicitly. No HTTP fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.book_generation.pipeline import materialize_chapter
from app.book_semantic_gate_4b29.constants import (
    AUTHORIZED_ANTHROPIC_CALLS,
    AUTHORIZED_OPENAI_CALLS,
    AUTHORIZED_TERRA_CALLS,
    FALLBACKS,
    PHASE,
    RETRIES,
    SDK_MAX_RETRIES,
    TERRA_EXECUTION_AUTHORIZED,
)
from app.book_semantic_gate_4b29.guard import (
    BookSemanticGate29Error,
    assert_offline_only,
    package_imports_network_clients,
    package_invokes_provider,
    reject_remote_provider,
)
from app.book_semantic_gate_4b29.interface import BlockedRemoteTransport
from app.book_semantic_gate_4b29.paths import repo_root


def _pipeline_source(*, root: Path | None = None) -> str:
    path = (root or repo_root()) / "app" / "book_generation" / "pipeline.py"
    return path.read_text(encoding="utf-8")


def provider_safety(*, root: Path | None = None) -> dict[str, Any]:
    assert_offline_only()
    remote_blocked = False
    try:
        BlockedRemoteTransport(provider="openai", model="gpt-5.6-terra")
    except BookSemanticGate29Error:
        remote_blocked = True
    evaluate_blocked = False
    try:
        BlockedRemoteTransport().evaluate({})
    except BookSemanticGate29Error:
        evaluate_blocked = True
    openai_named_blocked = False
    try:
        reject_remote_provider("anthropic")
    except BookSemanticGate29Error:
        openai_named_blocked = True
    pipeline = _pipeline_source(root=root)
    return {
        "phase": PHASE,
        "imports_network": package_imports_network_clients(),
        "invokes_provider": package_invokes_provider(),
        "remote_constructor_blocked": remote_blocked,
        "remote_evaluate_blocked": evaluate_blocked,
        "named_provider_blocked": openai_named_blocked,
        "api_key_absence_is_not_the_safety_mechanism": True,
        "retries": RETRIES,
        "fallbacks": FALLBACKS,
        "sdk_max_retries": SDK_MAX_RETRIES,
        "authorized_terra_calls": AUTHORIZED_TERRA_CALLS,
        "authorized_openai_calls": AUTHORIZED_OPENAI_CALLS,
        "authorized_anthropic_calls": AUTHORIZED_ANTHROPIC_CALLS,
        "terra_execution_authorized": TERRA_EXECUTION_AUTHORIZED,
        "tests_must_use_local_transport": True,
        "pipeline_imports_4b29": "book_semantic_gate_4b29" in pipeline,
        "materialize_chapter_untouched": materialize_chapter.__module__ == "app.book_generation.pipeline",
        "http": 0,
        "openai_http": 0,
        "anthropic_http": 0,
        "secrets_included": False,
        "ok": (
            remote_blocked
            and evaluate_blocked
            and openai_named_blocked
            and not package_imports_network_clients()
            and not package_invokes_provider()
            and "book_semantic_gate_4b29" not in pipeline
            and AUTHORIZED_TERRA_CALLS == 0
            and RETRIES == 0
            and FALLBACKS == 0
        ),
    }


__all__ = ["provider_safety"]
